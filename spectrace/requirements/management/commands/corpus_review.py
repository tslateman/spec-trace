"""Management command that reviews a spec against the pinned corpus snapshot."""

import json
import sys

from django.core.management.base import BaseCommand, CommandError

from requirements.constants import (
    FINDING_CONFLICTING_OBLIGATIONS,
    FINDING_ORPHAN_CITATION,
    FINDING_STALE_CITATION,
    FINDING_UNADDRESSED_OBLIGATION,
    FINDING_UNMET_CHECK,
)
from requirements.services.corpus_checks import CitationFormatError
from requirements.services.corpus_review import (
    ReviewTargetError,
    UnknownCitationError,
    has_blocking_finding,
    review_as_dict,
    review_target,
)

FINDING_LABELS = {
    FINDING_UNADDRESSED_OBLIGATION: "Unaddressed obligation",
    FINDING_STALE_CITATION: "Stale citation",
    FINDING_ORPHAN_CITATION: "Orphan citation",
    FINDING_UNMET_CHECK: "Unmet structural check",
    FINDING_CONFLICTING_OBLIGATIONS: "Conflicting obligations",
}


class Command(BaseCommand):
    help = "Review a spec against the corpus and record coverage and findings"

    def add_arguments(self, parser):
        parser.add_argument(
            "target",
            type=str,
            help="Spec file path (e.g., specs/platform/tenant_isolation.md) or requirement id",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json", "md"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--reviewer",
            type=str,
            default="",
            help="Who ran the review, recorded on the review row",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help=(
                "Caller override: treat advisory findings as blocking for this run. "
                "Without it, only findings against an entry the owner marked "
                "'enforcement: blocking' exit nonzero"
            ),
        )

    def handle(self, *args, **options):
        output_format = options["format"]
        escalate_advisory = options["strict"]

        try:
            reviews = review_target(options["target"], reviewer=options["reviewer"])
        except (ReviewTargetError, UnknownCitationError, CitationFormatError) as exc:
            raise CommandError(str(exc)) from exc

        payloads = [review_as_dict(review) for review in reviews]

        if output_format == "json":
            self._output_json(payloads)
        elif output_format == "md":
            self._output_md(payloads)
        else:
            self._output_text(payloads)

        if has_blocking_finding(payloads, escalate_advisory):
            sys.exit(1)

    def _output_json(self, payloads):
        """Output the reviews as structured JSON."""
        self.stdout.write(
            json.dumps(
                {
                    "reviews": payloads,
                    "summary": {
                        "requirements_reviewed": len(payloads),
                        "entries_surfaced": sum(len(p["coverage"]) for p in payloads),
                        "findings": sum(len(p["findings"]) for p in payloads),
                    },
                },
                indent=2,
            )
        )

    def _output_text(self, payloads):
        """Output human-readable coverage and findings."""
        for payload in payloads:
            self.stdout.write(f"Review of {payload['requirement_id']} ({payload['spec_file']})")
            self.stdout.write(f"Snapshot: {payload['snapshot_hash'][:12]}")
            self.stdout.write(f"\nCoverage ({len(payload['coverage'])} entry versions surfaced):")
            for row in payload["coverage"]:
                citation = "cited" if row["cited"] else "not cited"
                self.stdout.write(
                    f"  {row['entry_id']}@{row['entry_version']} [{citation}] "
                    f"[{row['enforcement']}] {row['title']}"
                )
                self.stdout.write(f"    matched by {_rendered_reasons(row['matched_by'])}")

            if not payload["findings"]:
                self.stdout.write(self.style.SUCCESS("\n✓ No findings"))
            else:
                self.stdout.write(f"\nFindings ({len(payload['findings'])}):")
                for finding in payload["findings"]:
                    label = FINDING_LABELS[finding["finding_type"]]
                    check = f" check '{finding['check_id']}'" if finding["check_id"] else ""
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ✗ [{finding['enforcement']}] {label}: "
                            f"{finding['entry_id']}@{finding['entry_version']}{check}"
                        )
                    )
                    self.stdout.write(f"    {finding['detail']}")
            self.stdout.write("")

    def _output_md(self, payloads):
        """Output Markdown for PR comments and review write-ups."""
        lines = ["## 📋 SpecTrace Corpus Review"]
        for payload in payloads:
            lines.append("")
            lines.append(f"**{payload['requirement_id']}** — `{payload['spec_file']}`")
            lines.append(f"**Corpus snapshot:** `{payload['snapshot_hash'][:12]}`")
            lines.append(f"**Reviewed at:** {payload['reviewed_at']}")
            lines.append("")
            lines.append(f"### Coverage ({len(payload['coverage'])} entry versions)")
            lines.append("")
            lines.append("| Entry | Version | Kind | Enforcement | Cited | Matched by |")
            lines.append("|---|---|---|---|---|---|")
            for row in payload["coverage"]:
                cited = "yes" if row["cited"] else "no"
                lines.append(
                    f"| {row['entry_id']} | {row['entry_version']} | {row['kind']} | "
                    f"{row['enforcement']} | {cited} | {_rendered_reasons(row['matched_by'])} |"
                )
            lines.append("")
            if not payload["findings"]:
                lines.append("### Findings")
                lines.append("")
                lines.append("✅ **No findings.**")
                continue
            lines.append(f"### Findings ({len(payload['findings'])})")
            lines.append("")
            lines.append("| Type | Entry | Enforcement | Check | Detail |")
            lines.append("|---|---|---|---|---|")
            for finding in payload["findings"]:
                label = FINDING_LABELS[finding["finding_type"]]
                check = finding["check_id"] or "—"
                lines.append(
                    f"| {label} | {finding['entry_id']}@{finding['entry_version']} | "
                    f"{finding['enforcement']} | {check} | {finding['detail']} |"
                )
        self.stdout.write("\n".join(lines))


def _rendered_reasons(matched_by):
    """Render match reasons as `scope_key=matched_value` pairs, inherited marked."""
    rendered = []
    for reason in matched_by:
        pair = f"{reason['scope_key']}={reason['matched_value']}"
        if reason["inherited"]:
            pair = f"{pair} (via {reason['matched_requirement_id']})"
        rendered.append(pair)
    return ", ".join(rendered)

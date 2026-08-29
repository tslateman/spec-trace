"""Management command that proposes corpus scope-rule widenings for a human.

The command has no `--strict` flag and no nonzero exit. A suggestion is not a
finding, so it never gates anything; `corpus review --strict` remains the only
command that can fail a build.
"""

import json

from django.core.management.base import BaseCommand

from requirements.services.corpus_suggest import (
    DEFAULT_MIN_SCORE,
    SUGGESTION_NEAR_MISS,
    suggestions_as_dicts,
)

KIND_LABELS = {
    SUGGESTION_NEAR_MISS: "Near-miss scope rule",
    "text_similarity": "Text similarity",
}


class Command(BaseCommand):
    help = "Propose applies_to widenings that would close corpus scope gaps"

    def add_arguments(self, parser):
        parser.add_argument(
            "--requirement",
            type=str,
            default="",
            help="Limit the report to one requirement external id",
        )
        parser.add_argument(
            "--min-score",
            type=float,
            default=DEFAULT_MIN_SCORE,
            help=(
                f"Cosine floor for text-similarity suggestions "
                f"(default: {DEFAULT_MIN_SCORE}). Near misses ignore it"
            ),
        )
        parser.add_argument(
            "--format",
            choices=["text", "json", "md"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        rows = suggestions_as_dicts(options["requirement"], options["min_score"])
        output_format = options["format"]

        if output_format == "json":
            self._output_json(rows)
        elif output_format == "md":
            self._output_md(rows)
        else:
            self._output_text(rows)

    def _summary(self, rows):
        near_misses = sum(1 for row in rows if row["kind"] == SUGGESTION_NEAR_MISS)
        return {
            "suggestions": len(rows),
            "near_misses": near_misses,
            "text_similarity": len(rows) - near_misses,
        }

    def _output_json(self, rows):
        """Output the curation report as structured JSON."""
        self.stdout.write(
            json.dumps({"suggestions": rows, "summary": self._summary(rows)}, indent=2)
        )

    def _output_text(self, rows):
        """Output a human-readable curation report."""
        if not rows:
            self.stdout.write(self.style.SUCCESS("No scope-rule suggestions"))
            return

        for row in rows:
            self.stdout.write(
                f"{KIND_LABELS[row['kind']]}: {row['entry_id']}@{row['entry_version']} "
                f"{row['entry_title']}"
            )
            self.stdout.write(f"  motivated by {row['requirement_id']} ({row['spec_file']})")
            self.stdout.write(f"  add {row['proposed_edit']}  [score {row['score']:.2f}]")
            if row["existing_pattern"]:
                self.stdout.write(f"  widens '{row['existing_pattern']}'")
            self.stdout.write(f"  {row['rationale']}")
            self.stdout.write("")

        summary = self._summary(rows)
        self.stdout.write(
            f"Summary: {summary['suggestions']} suggestions — "
            f"{summary['near_misses']} near-miss scope rules, "
            f"{summary['text_similarity']} by text similarity"
        )
        self.stdout.write("Suggestions are proposals only. Nothing here is a review finding.")

    def _output_md(self, rows):
        """Output the curation report as a Markdown table."""
        lines = ["## 🔎 SpecTrace Corpus Scope Suggestions", ""]
        lines.append("Proposals for a human to accept. No suggestion is a review finding.")
        lines.append("")
        lines.append("| Kind | Entry | Motivating spec | Proposed edit | Widens | Score |")
        lines.append("|---|---|---|---|---|---|")
        for row in rows:
            lines.append(
                f"| {KIND_LABELS[row['kind']]} | {row['entry_id']}@{row['entry_version']} | "
                f"{row['requirement_id']} | `{row['proposed_edit']}` | "
                f"`{row['existing_pattern'] or '—'}` | {row['score']:.2f} |"
            )
        if not rows:
            lines.append("| — | — | — | — | — | — |")
        self.stdout.write("\n".join(lines))

"""Management command that reports the corpus coverage ledger per requirement."""

import json

from django.core.management.base import BaseCommand

from requirements.services.corpus_review import coverage_as_dicts


class Command(BaseCommand):
    help = "Report which corpus entries each requirement's latest review surfaced"

    def add_arguments(self, parser):
        parser.add_argument(
            "--requirement",
            type=str,
            default="",
            help="Limit the report to one requirement external id",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json", "md"],
            default="text",
            help="Output format (default: text)",
        )

    def handle(self, *args, **options):
        rows = coverage_as_dicts(options["requirement"])
        output_format = options["format"]

        if output_format == "json":
            self._output_json(rows)
        elif output_format == "md":
            self._output_md(rows)
        else:
            self._output_text(rows)

    def _output_json(self, rows):
        """Output the ledger as structured JSON."""
        self.stdout.write(
            json.dumps(
                {
                    "requirements": rows,
                    "summary": {
                        "requirements": len(rows),
                        "reviewed": sum(1 for row in rows if row["reviewed"]),
                        "unreviewed": sum(1 for row in rows if not row["reviewed"]),
                        "entries_surfaced": sum(row["entries_surfaced"] for row in rows),
                    },
                },
                indent=2,
            )
        )

    def _output_text(self, rows):
        """Output a human-readable ledger."""
        for row in rows:
            if not row["reviewed"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"{row['requirement_id']}: never reviewed against the corpus"
                    )
                )
                continue
            self.stdout.write(
                f"{row['requirement_id']}: {row['entries_surfaced']} entries surfaced at "
                f"{row['snapshot_hash'][:12]} on {row['reviewed_at']}"
            )
            for entry in row["coverage"]:
                citation = "cited" if entry["cited"] else "not cited"
                self.stdout.write(
                    f"  {entry['entry_id']}@{entry['entry_version']} [{citation}] {entry['title']}"
                )
            if row["unaddressed"]:
                self.stdout.write(
                    self.style.ERROR(f"  unaddressed: {', '.join(row['unaddressed'])}")
                )

        reviewed = sum(1 for row in rows if row["reviewed"])
        self.stdout.write(
            f"\nSummary: {reviewed} of {len(rows)} requirements reviewed, "
            f"{sum(row['entries_surfaced'] for row in rows)} entry versions surfaced"
        )

    def _output_md(self, rows):
        """Output the ledger as a Markdown table."""
        lines = ["## 📒 SpecTrace Corpus Coverage", ""]
        lines.append("| Requirement | Reviewed at | Snapshot | Entries surfaced | Unaddressed |")
        lines.append("|---|---|---|---|---|")
        for row in rows:
            if not row["reviewed"]:
                lines.append(f"| {row['requirement_id']} | never | — | 0 | — |")
                continue
            unaddressed = ", ".join(row["unaddressed"]) or "none"
            lines.append(
                f"| {row['requirement_id']} | {row['reviewed_at']} | "
                f"`{row['snapshot_hash'][:12]}` | {row['entries_surfaced']} | {unaddressed} |"
            )
        self.stdout.write("\n".join(lines))

"""Management command that names the reviews the corpus has moved out from under."""

import json
import sys

from django.core.management.base import BaseCommand

from requirements.services.corpus_drift import drift_as_dict


class Command(BaseCommand):
    help = "Name stale corpus reviews and the entries that now apply but were never reviewed"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["text", "json", "md"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit code 1 when stale reviews exist",
        )

    def handle(self, *args, **options):
        report = drift_as_dict()
        output_format = options["format"]

        if output_format == "json":
            self._output_json(report)
        elif output_format == "md":
            self._output_md(report)
        else:
            self._output_text(report)

        if options["strict"] and report["stale_reviews"]:
            sys.exit(1)

    def _output_json(self, report):
        """Output the drift report as structured JSON."""
        self.stdout.write(json.dumps(report, indent=2))

    def _output_text(self, report):
        """Output human-readable stale reviews and newly applicable entries."""
        self.stdout.write(f"Corpus snapshot: {report['current_snapshot'][:12]}")

        if not report["stale_reviews"]:
            self.stdout.write(self.style.SUCCESS("\n✓ No stale reviews"))
        else:
            self.stdout.write(f"\nStale reviews ({len(report['stale_reviews'])}):")
            for row in report["stale_reviews"]:
                self.stdout.write(
                    self.style.ERROR(
                        f"  ✗ {row['requirement_id']} ({row['spec_file']}) "
                        f"reviewed at {row['reviewed_at']} on {row['snapshot_hash'][:12]}"
                    )
                )
                for change in row["invalidated_by"]:
                    self.stdout.write(f"    {change['detail']}")

        if not report["newly_applicable"]:
            self.stdout.write("\nNo newly applicable entries")
        else:
            self.stdout.write(f"\nNewly applicable ({len(report['newly_applicable'])} specs):")
            for row in report["newly_applicable"]:
                self.stdout.write(self.style.WARNING(f"  {row['requirement_id']}:"))
                for entry in row["entries"]:
                    self.stdout.write(
                        f"    {entry['entry_id']}@{entry['entry_version']} "
                        f"({entry['kind']}) {entry['title']}"
                    )

        summary = report["summary"]
        self.stdout.write(
            f"\nSummary: {summary['stale_reviews']} of {summary['reviews_examined']} reviews "
            f"stale, {summary['newly_applicable_entries']} entry versions newly applicable "
            f"across {summary['specs_with_newly_applicable_entries']} specs"
        )

    def _output_md(self, report):
        """Output the drift report as Markdown tables."""
        lines = [
            "## 🌊 SpecTrace Corpus Drift",
            "",
            f"**Corpus snapshot:** `{report['current_snapshot'][:12]}`",
            "",
            f"### Stale reviews ({len(report['stale_reviews'])})",
            "",
        ]
        if not report["stale_reviews"]:
            lines.append("✅ **No stale reviews.**")
        else:
            lines.append("| Requirement | Spec | Reviewed at | Invalidated by | Detail |")
            lines.append("|---|---|---|---|---|")
            for row in report["stale_reviews"]:
                for change in row["invalidated_by"]:
                    lines.append(
                        f"| {row['requirement_id']} | `{row['spec_file']}` | "
                        f"{row['reviewed_at']} | "
                        f"{change['entry_id']}@{change['entry_version']} | "
                        f"{change['detail']} |"
                    )

        lines.append("")
        lines.append(f"### Newly applicable ({len(report['newly_applicable'])} specs)")
        lines.append("")
        if not report["newly_applicable"]:
            lines.append("✅ **No spec gained an unreviewed obligation.**")
        else:
            lines.append("| Requirement | Spec | Entry | Kind | Title |")
            lines.append("|---|---|---|---|---|")
            for row in report["newly_applicable"]:
                for entry in row["entries"]:
                    lines.append(
                        f"| {row['requirement_id']} | `{row['spec_file']}` | "
                        f"{entry['entry_id']}@{entry['entry_version']} | "
                        f"{entry['kind']} | {entry['title']} |"
                    )
        self.stdout.write("\n".join(lines))

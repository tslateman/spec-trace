"""Management command for code-level impact analysis across the ecosystem."""

import json
import sys

from django.core.management.base import BaseCommand, CommandError

from ...services.impact_analyzer import ImpactAnalyzer


class Command(BaseCommand):
    help = "Analyze code impact across the ecosystem between two git refs"

    def add_arguments(self, parser):
        parser.add_argument(
            "base_ref",
            type=str,
            help="Base git ref (commit, branch, tag)",
        )
        parser.add_argument(
            "head_ref",
            type=str,
            help="Head git ref to compare against base",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json", "md"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--project-roots",
            type=str,
            default=None,
            help="Comma-separated project=path pairs (e.g., lore=/path/to/lore,praxis=/path)",
        )

    def handle(self, *args, **options):
        base_ref = options["base_ref"]
        head_ref = options["head_ref"]
        output_format = options["format"]

        # Parse project roots
        project_roots = None
        if options["project_roots"]:
            from pathlib import Path

            project_roots = {}
            for pair in options["project_roots"].split(","):
                if "=" in pair:
                    name, path = pair.split("=", 1)
                    project_roots[name.strip()] = Path(path.strip())

        analyzer = ImpactAnalyzer()

        try:
            result = analyzer.code_analyze(base_ref, head_ref, project_roots=project_roots)
        except ValueError as e:
            raise CommandError(str(e))

        if output_format == "json":
            self._output_json(result)
        elif output_format == "md":
            self._output_md(result, base_ref, head_ref)
        else:
            self._output_text(result, base_ref, head_ref)

        # Exit code 1 for high/critical risk (CI gate)
        if result.risk_level in ("high", "critical"):
            sys.exit(1)

    def _output_json(self, result):
        """Output structured JSON."""
        output = {
            "changed_files": result.changed_files,
            "blast": result.blast,
            "affected_tests": result.affected_tests,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "edge_summary": result.edge_summary,
            "summary": {
                "files_changed": sum(len(v) for v in result.changed_files.values()),
                "tests_affected": len(result.affected_tests),
                "requirements_affected": len(result.blast.get("affected_requirements", [])),
                "projects_affected": len(result.blast.get("affected_projects", [])),
            },
        }
        self.stdout.write(json.dumps(output, indent=2))

    def _output_md(self, result, base_ref, head_ref):
        """Output Markdown for PR comments."""
        lines = []
        lines.append("## Code Impact Analysis")
        lines.append(f"**Comparing:** `{base_ref}` .. `{head_ref}`")
        lines.append("")

        total_files = sum(len(v) for v in result.changed_files.values())
        if not total_files:
            lines.append("No code files changed.")
            self.stdout.write("\n".join(lines) + "\n")
            return

        # Changed files
        lines.append(f"### Changed Files ({total_files})")
        for project, files in sorted(result.changed_files.items()):
            for f in files:
                lines.append(f"- `[{project}]` {f}")
        lines.append("")

        # Blast radius
        blast = result.blast
        reqs = blast.get("affected_requirements", [])
        mods = blast.get("affected_modules", [])
        projs = blast.get("affected_projects", [])

        if reqs:
            lines.append(f"### Affected Requirements ({len(reqs)})")
            for r in reqs:
                lines.append(f"- {r}")
            lines.append("")

        if mods:
            lines.append(f"### Affected Modules ({len(mods)})")
            for m in mods:
                lines.append(f"- {m}")
            lines.append("")

        if projs:
            lines.append(f"### Affected Projects ({len(projs)})")
            for p in projs:
                lines.append(f"- {p}")
            lines.append("")

        # Risk
        risk_emoji = {
            "low": "LOW",
            "medium": "MEDIUM",
            "high": "HIGH",
            "critical": "CRITICAL",
        }.get(result.risk_level, "UNKNOWN")

        lines.append("### Risk Assessment")
        lines.append(f"**Level:** {risk_emoji} (Score: {result.risk_score:.2f})")
        lines.append("")

        # Edge summary
        edges = result.edge_summary
        lines.append("### Edge Sources")
        lines.append(
            f"Annotated: {edges['annotated']} | "
            f"Inferred: {edges['inferred']} | "
            f"Contract: {edges['contract']}"
        )
        lines.append("")

        # Tests
        if result.affected_tests:
            lines.append(f"### Affected Tests ({len(result.affected_tests)})")
            lines.append("```bash")
            for test in sorted(result.affected_tests):
                lines.append(f"pytest {test}")
            lines.append("```")

        self.stdout.write("\n".join(lines) + "\n")

    def _output_text(self, result, base_ref, head_ref):
        """Output human-readable text."""
        self.stdout.write(f"Code Impact Analysis: {base_ref} .. {head_ref}\n")
        self.stdout.write("=" * 50 + "\n")

        total_files = sum(len(v) for v in result.changed_files.values())
        if not total_files:
            self.stdout.write(self.style.SUCCESS("\nNo code files changed.\n"))
            return

        # Changed files
        self.stdout.write(f"\nChanged Files ({total_files}):\n")
        for project, files in sorted(result.changed_files.items()):
            for f in files:
                self.stdout.write(f"  [{project}] {f}\n")

        # Blast radius
        blast = result.blast
        reqs = blast.get("affected_requirements", [])
        mods = blast.get("affected_modules", [])
        projs = blast.get("affected_projects", [])

        if reqs:
            self.stdout.write(f"\nAffected Requirements ({len(reqs)}):\n")
            for r in reqs:
                self.stdout.write(f"  {r}\n")

        if mods:
            self.stdout.write(f"\nAffected Modules ({len(mods)}):\n")
            for m in mods:
                self.stdout.write(f"  {m}\n")

        if projs:
            self.stdout.write(f"\nAffected Projects ({len(projs)}):\n")
            for p in projs:
                self.stdout.write(f"  {p}\n")

        # Risk
        risk_styles = {
            "low": self.style.SUCCESS,
            "medium": self.style.WARNING,
            "high": self.style.WARNING,
            "critical": self.style.ERROR,
        }
        style_fn = risk_styles.get(result.risk_level, self.style.WARNING)
        self.stdout.write(
            style_fn(f"\nRisk: {result.risk_level.upper()} ({result.risk_score:.2f})\n")
        )

        # Edge summary
        edges = result.edge_summary
        self.stdout.write(
            f"\nEdges: {edges['annotated']} annotated, "
            f"{edges['inferred']} inferred, "
            f"{edges['contract']} contract\n"
        )

        # Tests
        if result.affected_tests:
            self.stdout.write(
                self.style.WARNING(f"\nAffected Tests ({len(result.affected_tests)}):\n")
            )
            for test in sorted(result.affected_tests):
                self.stdout.write(f"  {test}\n")

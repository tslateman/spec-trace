"""Management command for code-level impact analysis across the ecosystem."""

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...services.impact_analyzer import ImpactAnalyzer
from ...services.impact_markdown import render_markdown

BLOCKING_LEVELS = ("high", "critical")


def parse_project_roots(raw: str) -> dict[str, Path]:
    """Parse comma-separated ``name=path`` pairs into project roots.

    Raises:
        CommandError: If a pair omits ``=`` or names a directory that is absent.
    """
    roots: dict[str, Path] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise CommandError(
                f"Invalid --project-roots entry {pair!r}. "
                "Expected name=path pairs, e.g. praxis=/path/to/praxis"
            )
        name, path = pair.split("=", 1)
        root = Path(path.strip()).expanduser()
        if not root.is_dir():
            raise CommandError(f"Project root for {name.strip()!r} is not a directory: {root}")
        roots[name.strip()] = root

    if not roots:
        raise CommandError("--project-roots was given but named no projects")
    return roots


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
            choices=["text", "json", "md", "markdown"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--project-roots",
            type=str,
            default=None,
            help="Comma-separated project=path pairs (e.g., lore=/path/to/lore,praxis=/path)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Write the report to this file instead of stdout",
        )

    def handle(self, *args, **options):
        base_ref = options["base_ref"]
        head_ref = options["head_ref"]
        output_format = options["format"]

        project_roots = None
        if options["project_roots"]:
            project_roots = parse_project_roots(options["project_roots"])

        analyzer = ImpactAnalyzer()

        try:
            result = analyzer.code_analyze(base_ref, head_ref, project_roots=project_roots)
        except ValueError as e:
            raise CommandError(str(e))

        if output_format == "json":
            report = self._render_json(result)
        elif output_format in ("md", "markdown"):
            report = render_markdown(result, base_ref, head_ref)
        else:
            report = self._render_text(result, base_ref, head_ref)

        destination = options.get("output")
        if destination:
            Path(destination).write_text(report)
        else:
            self.stdout.write(report)

        if result.risk_level in BLOCKING_LEVELS:
            sys.exit(1)

    def _render_json(self, result) -> str:
        """Render structured JSON."""
        output = {
            "changed_files": result.changed_files,
            "blast": result.blast,
            "affected_tests": result.affected_tests,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "edge_summary": result.edge_summary,
            "traversed_edges": result.traversed_edges,
            "summary": {
                "files_changed": sum(len(v) for v in result.changed_files.values()),
                "tests_affected": len(result.affected_tests),
                "requirements_affected": len(result.blast.get("affected_requirements", [])),
                "projects_affected": len(result.blast.get("affected_projects", [])),
            },
        }
        return json.dumps(output, indent=2)

    def _render_text(self, result, base_ref, head_ref) -> str:
        """Render human-readable text."""
        lines = [
            f"Code Impact Analysis: {base_ref} .. {head_ref}",
            "=" * 50,
            "",
        ]

        total_files = sum(len(v) for v in result.changed_files.values())
        if not total_files:
            lines.append(self.style.SUCCESS("No code files changed."))
            return "\n".join(lines) + "\n"

        lines.append(f"Changed Files ({total_files}):")
        for project, files in sorted(result.changed_files.items()):
            for f in files:
                lines.append(f"  [{project}] {f}")

        blast = result.blast
        reqs = blast.get("affected_requirements", [])
        mods = blast.get("affected_modules", [])
        projs = blast.get("affected_projects", [])

        for heading, items in (
            ("Affected Requirements", reqs),
            ("Affected Modules", mods),
            ("Affected Projects", projs),
        ):
            if items:
                lines.append("")
                lines.append(f"{heading} ({len(items)}):")
                lines.extend(f"  {item}" for item in items)

        risk_styles = {
            "low": self.style.SUCCESS,
            "medium": self.style.WARNING,
            "high": self.style.WARNING,
            "critical": self.style.ERROR,
        }
        style_fn = risk_styles.get(result.risk_level, self.style.WARNING)
        lines.append("")
        lines.append(style_fn(f"Risk: {result.risk_level.upper()} ({result.risk_score:.2f})"))

        edges = result.traversed_edges
        lines.append("")
        lines.append(
            f"Edges carrying this change: {edges['annotated']} annotated, "
            f"{edges['contract']} contract, "
            f"{edges['inferred']} inferred"
        )

        if result.affected_tests:
            lines.append("")
            lines.append(self.style.WARNING(f"Affected Tests ({len(result.affected_tests)}):"))
            lines.extend(f"  {test}" for test in sorted(result.affected_tests))

        return "\n".join(lines) + "\n"

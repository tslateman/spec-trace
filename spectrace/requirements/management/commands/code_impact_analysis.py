"""Management command for code-level impact analysis across the ecosystem."""

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...projects import display_node
from ...services.impact_analyzer import ImpactAnalyzer, RefPair, ref_labels
from ...services.impact_markdown import render_markdown

BLOCKING_LEVELS = ("high", "critical")
REF_RANGE_SEPARATOR = ".."


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


def parse_project_refs(raw: str) -> dict[str, RefPair]:
    """Parse comma-separated ``name=base..head`` entries into one ref pair per project.

    Raises:
        CommandError: If an entry omits ``=`` or ``..``, leaves a ref empty, or
            if the whole value names no project.
    """
    pairs: dict[str, RefPair] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise CommandError(
                f"Invalid --project-refs entry {entry!r}. "
                "Expected name=base..head entries, e.g. praxis=main..HEAD"
            )
        name, refs = entry.split("=", 1)
        if refs.count(REF_RANGE_SEPARATOR) != 1:
            raise CommandError(
                f"Invalid --project-refs entry {entry!r}. "
                f"Separate the two refs with one {REF_RANGE_SEPARATOR}, e.g. praxis=main..HEAD"
            )
        base, head = (part.strip() for part in refs.split(REF_RANGE_SEPARATOR))
        if not base or not head:
            raise CommandError(
                f"Invalid --project-refs entry {entry!r}. Name a base and a head ref."
            )
        pairs[name.strip()] = RefPair(base, head)

    if not pairs:
        raise CommandError("--project-refs was given but named no projects")
    return pairs


class Command(BaseCommand):
    help = "Analyze code impact across the ecosystem between two git refs"

    def add_arguments(self, parser):
        parser.add_argument(
            "base_ref",
            type=str,
            nargs="?",
            default=None,
            help="Base git ref (commit, branch, tag), shared by every project root",
        )
        parser.add_argument(
            "head_ref",
            type=str,
            nargs="?",
            default=None,
            help="Head git ref to compare against base, shared by every project root",
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
            "--project-refs",
            type=str,
            default=None,
            help=(
                "Comma-separated project=base..head entries, one per project root "
                "(e.g., spectrace=HEAD~1..HEAD,praxis=main..HEAD). Name every root, "
                "and leave the positional refs off."
            ),
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Write the report to this file instead of stdout",
        )

    def handle(self, *args, **options):
        output_format = options["format"]

        project_roots = None
        if options["project_roots"]:
            project_roots = parse_project_roots(options["project_roots"])

        project_refs = None
        if options["project_refs"]:
            project_refs = parse_project_refs(options["project_refs"])

        base_label, head_label = (
            ref_labels(project_refs) if project_refs else (options["base_ref"], options["head_ref"])
        )

        analyzer = ImpactAnalyzer()

        try:
            result = analyzer.code_analyze(
                options["base_ref"],
                options["head_ref"],
                project_roots=project_roots,
                project_refs=project_refs,
            )
        except ValueError as e:
            raise CommandError(str(e))

        if output_format == "json":
            report = self._render_json(result)
        elif output_format in ("md", "markdown"):
            report = render_markdown(result, base_label, head_label)
        else:
            report = self._render_text(result, base_label, head_label)

        destination = options.get("output")
        if destination:
            Path(destination).write_text(report)
        else:
            self.stdout.write(report)

        if result.risk_level in BLOCKING_LEVELS:
            sys.exit(1)

    def _test_lines(self, result) -> list[str]:
        """List affected tests under the project whose requirements they verify."""
        grouped = result.affected_tests_by_project
        if not grouped:
            return [f"  {test}" for test in sorted(result.affected_tests)]
        return [
            f"  [{project}] {test}" for project, tests in sorted(grouped.items()) for test in tests
        ]

    def _render_json(self, result) -> str:
        """Render structured JSON."""
        output = {
            "changed_files": result.changed_files,
            "blast": result.blast,
            "affected_tests": result.affected_tests,
            "affected_tests_by_project": result.affected_tests_by_project,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "edge_summary": result.edge_summary,
            "traversed_edges": result.traversed_edges,
            "unresolved_dependencies": result.unresolved_dependencies,
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
            ("Affected Requirements", [display_node(r) for r in reqs]),
            ("Affected Modules", [display_node(m) for m in mods]),
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
            f"{edges['inferred']} inferred, "
            f"{edges['dependency']} dependency"
        )

        if result.unresolved_dependencies:
            lines.append("")
            lines.append(
                self.style.WARNING(
                    f"Dependencies not analysed ({len(result.unresolved_dependencies)}): "
                    "a declared provider was absent from this run"
                )
            )
            for item in result.unresolved_dependencies:
                lines.append(
                    f"  {item['consumer']}:{item['module']} -> {item['provider']}:{item['surface']}"
                )

        if result.affected_tests:
            lines.append("")
            lines.append(self.style.WARNING(f"Affected Tests ({len(result.affected_tests)}):"))
            lines.extend(self._test_lines(result))

        return "\n".join(lines) + "\n"

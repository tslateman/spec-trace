"""Management command for code-level impact analysis across the ecosystem."""

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...projects import display_node
from ...services.impact_analyzer import ImpactAnalyzer, ProjectRevision
from ...services.impact_markdown import render_markdown

BLOCKING_LEVELS = ("high", "critical")


def _parse_pairs(raw: str, flag: str, shape: str, example: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise CommandError(
                f"Invalid {flag} entry {pair!r}. Expected {shape} pairs, e.g. {example}"
            )
        name, value = pair.split("=", 1)
        pairs[name.strip()] = value.strip()
    if not pairs:
        raise CommandError(f"{flag} was given but named no projects")
    return pairs


def parse_project_roots(raw: str) -> dict[str, Path]:
    """Parse comma-separated ``name=path`` pairs into project roots.

    Raises:
        CommandError: If a pair omits ``=`` or names a directory that is absent.
    """
    roots: dict[str, Path] = {}
    for name, path in _parse_pairs(
        raw, "--project-roots", "name=path", "praxis=/path/to/praxis"
    ).items():
        root = Path(path).expanduser()
        if not root.is_dir():
            raise CommandError(f"Project root for {name!r} is not a directory: {root}")
        roots[name] = root
    return roots


def parse_project_refs(raw: str) -> dict[str, tuple[str, str]]:
    """Parse comma-separated ``name=base..head`` pairs into a ref pair per project.

    Raises:
        CommandError: If a pair omits ``=`` or its value is not ``base..head``.
    """
    refs: dict[str, tuple[str, str]] = {}
    for name, span in _parse_pairs(
        raw, "--project-refs", "name=base..head", "praxis=main..HEAD"
    ).items():
        base_ref, sep, head_ref = span.partition("..")
        if not sep or not base_ref or not head_ref:
            raise CommandError(
                f"Invalid --project-refs entry for {name!r}: {span!r}. Expected base..head"
            )
        refs[name] = (base_ref, head_ref)
    return refs


def parse_projects(roots_raw: str, refs_raw: str) -> dict[str, ProjectRevision]:
    """Pair every project root with its own ref pair.

    Raises:
        CommandError: If either flag is missing, a root has no refs, a ref pair
            names no root, or a ref is malformed.
    """
    if not roots_raw or not refs_raw:
        raise CommandError(
            "--project-roots and --project-refs go together: "
            "every project root needs its own base..head"
        )
    roots = parse_project_roots(roots_raw)
    refs = parse_project_refs(refs_raw)
    unpaired_roots = sorted(set(roots) - set(refs))
    if unpaired_roots:
        raise CommandError(f"--project-refs names no refs for: {', '.join(unpaired_roots)}")
    unpaired_refs = sorted(set(refs) - set(roots))
    if unpaired_refs:
        raise CommandError(f"--project-roots names no root for: {', '.join(unpaired_refs)}")
    try:
        return {name: ProjectRevision(root, *refs[name]) for name, root in roots.items()}
    except ValueError as e:
        raise CommandError(str(e))


class Command(BaseCommand):
    help = "Analyze code impact across the ecosystem between two git refs"

    def add_arguments(self, parser):
        parser.add_argument(
            "base_ref",
            type=str,
            nargs="?",
            help="Base git ref (commit, branch, tag) for the local repository",
        )
        parser.add_argument(
            "head_ref",
            type=str,
            nargs="?",
            help="Head git ref to compare against base for the local repository",
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
            help=(
                "Comma-separated project=path pairs (e.g., lore=/path/to/lore,praxis=/path). "
                "Replaces the positional refs; pair it with --project-refs"
            ),
        )
        parser.add_argument(
            "--project-refs",
            type=str,
            default=None,
            help="Comma-separated project=base..head pairs, one per --project-roots entry",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Write the report to this file instead of stdout",
        )

    def handle(self, *args, **options):
        output_format = options["format"]
        analyzer = ImpactAnalyzer()
        projects = self._projects(analyzer, options)

        try:
            result = analyzer.code_analyze(projects)
        except ValueError as e:
            raise CommandError(str(e))

        if output_format == "json":
            report = self._render_json(result)
        elif output_format in ("md", "markdown"):
            report = render_markdown(result)
        else:
            report = self._render_text(result)

        destination = options.get("output")
        if destination:
            Path(destination).write_text(report)
        else:
            self.stdout.write(report)

        if result.risk_level in BLOCKING_LEVELS:
            sys.exit(1)

    def _projects(self, analyzer, options) -> dict[str, ProjectRevision]:
        """Resolve the projects to diff from positional refs or the per-project flags."""
        base_ref, head_ref = options["base_ref"], options["head_ref"]
        multi = options["project_roots"] or options["project_refs"]
        if multi and (base_ref or head_ref):
            raise CommandError(
                "Positional refs apply to the local repository only. "
                "With --project-roots, give each project its refs in --project-refs"
            )
        if multi:
            return parse_projects(options["project_roots"], options["project_refs"])
        if not (base_ref and head_ref):
            raise CommandError(
                "Give base_ref and head_ref for the local repository, "
                "or --project-roots with --project-refs"
            )
        try:
            return analyzer.local_revision(base_ref, head_ref)
        except ValueError as e:
            raise CommandError(str(e))

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
            "revisions": {
                project: {"base_ref": revision.base_ref, "head_ref": revision.head_ref}
                for project, revision in sorted(result.revisions.items())
            },
            "changed_files": result.changed_files,
            "blast": result.blast,
            "affected_tests": result.affected_tests,
            "affected_tests_by_project": result.affected_tests_by_project,
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

    def _render_text(self, result) -> str:
        """Render human-readable text."""
        if len(result.revisions) == 1:
            (revision,) = result.revisions.values()
            lines = [f"Code Impact Analysis: {revision.base_ref} .. {revision.head_ref}"]
        else:
            lines = ["Code Impact Analysis"]
            lines.extend(
                f"  [{project}] {revision.base_ref} .. {revision.head_ref}"
                for project, revision in sorted(result.revisions.items())
            )
        lines.extend(["=" * 50, ""])

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
            f"{edges['dependency']} dependency, "
            f"{edges['contract']} contract, "
            f"{edges['inferred']} inferred"
        )

        if result.affected_tests:
            lines.append("")
            lines.append(self.style.WARNING(f"Affected Tests ({len(result.affected_tests)}):"))
            lines.extend(self._test_lines(result))

        return "\n".join(lines) + "\n"

"""Render a CodeImpactResult as Markdown fit for a pull request comment."""

from ..projects import display_node
from .impact_analyzer import CodeImpactResult

MARKER_PREFIX = "<!-- spectrace-impact-gate"

DEFAULT_LIST_LIMIT = 25
DEFAULT_TEST_LIMIT = 15


def marker(risk_level: str) -> str:
    """Build the hidden marker line that identifies the gate's comment."""
    return f"{MARKER_PREFIX} risk={risk_level} -->"


def _truncated(items: list[str], limit: int) -> tuple[list[str], int]:
    if len(items) <= limit:
        return items, 0
    return items[:limit], len(items) - limit


def _section(lines: list[str], heading: str, items: list[str], limit: int, bullet: str) -> None:
    if not items:
        return
    shown, remaining = _truncated(items, limit)
    lines.append(f"### {heading} ({len(items)})")
    for item in shown:
        lines.append(f"{bullet}{item}")
    if remaining:
        lines.append(f"- …and {remaining} more")
    lines.append("")


def comparison_lines(result: CodeImpactResult) -> list[str]:
    """Name the ref pair each project was diffed across.

    A single project reads as one line; several projects list one line each,
    since each carries its own refs.
    """
    revisions = result.revisions
    if len(revisions) == 1:
        (revision,) = revisions.values()
        return [f"**Comparing:** `{revision.base_ref}` .. `{revision.head_ref}`"]
    return [
        "**Comparing:**",
        *(
            f"- `[{project}]` `{revision.base_ref}` .. `{revision.head_ref}`"
            for project, revision in sorted(revisions.items())
        ),
        "",
    ]


def render_markdown(
    result: CodeImpactResult,
    list_limit: int = DEFAULT_LIST_LIMIT,
    test_limit: int = DEFAULT_TEST_LIMIT,
) -> str:
    """Render the analysis as a Markdown comment body.

    The first line is the hidden marker used to find and update the gate's own
    comment on later pushes. Long lists are truncated with a remaining count so
    the comment stays readable.
    """
    lines = [
        marker(result.risk_level),
        "## Code Impact Analysis",
        "",
        *comparison_lines(result),
        f"**Risk:** {result.risk_level.upper()} ({result.risk_score:.2f})",
        "",
    ]

    changed = [
        f"`[{project}]` {path}"
        for project, files in sorted(result.changed_files.items())
        for path in files
    ]

    if not changed:
        lines.append("No code files changed.")
        return "\n".join(lines) + "\n"

    shown_changed, remaining_changed = _truncated(changed, list_limit)
    lines.append("<details>")
    lines.append(f"<summary>Changed Files ({len(changed)})</summary>")
    lines.append("")
    lines.extend(f"- {item}" for item in shown_changed)
    if remaining_changed:
        lines.append(f"- …and {remaining_changed} more")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    blast = result.blast
    _section(
        lines,
        "Affected Requirements",
        [display_node(node) for node in blast.get("affected_requirements", [])],
        list_limit,
        "- ",
    )
    _section(
        lines,
        "Affected Modules",
        [display_node(node) for node in blast.get("affected_modules", [])],
        list_limit,
        "- ",
    )
    _section(lines, "Affected Projects", list(blast.get("affected_projects", [])), list_limit, "- ")

    edges = result.traversed_edges
    lines.append("### Evidence")
    lines.append(
        "Edges carrying this change — "
        f"annotated: {edges['annotated']} | "
        f"dependency: {edges['dependency']} | "
        f"contract: {edges['contract']} | "
        f"inferred: {edges['inferred']}"
    )
    lines.append("")

    tests = sorted(result.affected_tests)
    if tests:
        shown, remaining = _truncated(tests, test_limit)
        lines.append(f"### Affected Tests ({len(tests)})")
        lines.append("```bash")
        for test in shown:
            lines.append(f"pytest {test}")
        lines.append("```")
        if remaining:
            lines.append(f"…and {remaining} more.")
        lines.append("")

    lines.append("---")
    lines.append("Informed-consent gate: this comment warns, it does not block the merge.")

    return "\n".join(lines) + "\n"

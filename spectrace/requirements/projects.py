"""Project namespacing for requirements and impact graph nodes.

Every requirement belongs to exactly one project. Graph node ids carry the same
name as a prefix, so two projects' identically-named modules stay distinct.

This module holds no model imports: `models.py` reads `default_project` from it.
"""

from django.conf import settings

NODE_SEPARATOR = ":"
FALLBACK_PROJECT = "default"


class AmbiguousProjectError(Exception):
    """Several projects are stored and the caller named none of them."""

    def __init__(self, projects: list[str]):
        self.projects = projects
        super().__init__(
            "The database holds requirements for several projects "
            f"({', '.join(projects)}). Name one to report on."
        )


def default_project() -> str:
    """Name the project this installation owns, from `settings.SPECTRACE_PROJECT`."""
    return getattr(settings, "SPECTRACE_PROJECT", FALLBACK_PROJECT)


def qualify(project: str, name: str) -> str:
    """Build the graph node id for a module path or requirement id in a project."""
    if not project:
        return name
    return f"{project}{NODE_SEPARATOR}{name}"


def unqualify(node_id: str) -> tuple[str, str]:
    """Split a graph node id back into its project and its name.

    Returns an empty project for a node id that carries none.
    """
    project, separator, name = node_id.partition(NODE_SEPARATOR)
    if not separator:
        return "", node_id
    return project, name


def node_name(node_id: str) -> str:
    """Return a node id's name without its project prefix."""
    return unqualify(node_id)[1]


def display_node(node_id: str) -> str:
    """Render a node id for a human reader, naming its project when it has one."""
    project, name = unqualify(node_id)
    if not project:
        return name
    return f"[{project}] {name}"


def resolve_project(requested: str | None, stored: list[str]) -> str:
    """Choose the one project a report covers.

    Args:
        requested: Project the caller named, or None
        stored: Distinct project names the database holds

    Returns:
        The requested project; else this installation's own project when it has
        requirements stored; else the single stored project; else the default.

    Raises:
        AmbiguousProjectError: Several projects are stored and none is this
            installation's own, so no answer covers one project at a time.
    """
    if requested:
        return requested
    installed = default_project()
    if installed in stored:
        return installed
    if len(stored) == 1:
        return stored[0]
    if not stored:
        return installed
    raise AmbiguousProjectError(sorted(stored))

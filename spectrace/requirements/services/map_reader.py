"""Reader for spectrace-map.yaml files."""

import logging
from pathlib import Path

import yaml

from ..projects import NODE_SEPARATOR, qualify, unqualify
from .impact_graph import EdgeSource, GraphEdge

logger = logging.getLogger(__name__)

MAP_FILENAME = "spectrace-map.yaml"
DEPENDS_ON_KEY = "depends_on"


def load_map(root: Path) -> dict | None:
    """Read one project root's map file, or None when it holds no readable map."""
    map_file = root / MAP_FILENAME
    if not map_file.exists():
        return None

    try:
        with open(map_file) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.warning("Invalid YAML in %s: %s", map_file, e)
        return None

    if not data or not isinstance(data, dict):
        return None
    return data


def project_for_path(start: Path) -> str | None:
    """Name the project owning a path, from the nearest map file above it."""
    start = Path(start).resolve()
    for candidate in [start, *start.parents]:
        data = load_map(candidate)
        if data and isinstance(data.get("project"), str) and data["project"]:
            return data["project"]
    return None


class MapReader:
    """Read spectrace-map.yaml files from project roots."""

    def __init__(self, project_roots: dict[str, Path]):
        self.project_roots = project_roots

    def project_name(self, project: str) -> str:
        """Name the project a root declares, falling back to the key it was given."""
        root = self.project_roots.get(project)
        if not root:
            return project
        data = load_map(root)
        if data and isinstance(data.get("project"), str) and data["project"]:
            return data["project"]
        return project

    def read_map(self, project: str) -> list[tuple[str, str]]:
        """Parse one spectrace-map.yaml, return (module, requirement) pairs."""
        root = self.project_roots.get(project)
        if not root:
            return []

        data = load_map(root)
        if data is None:
            return []

        modules = data.get("modules", {})
        if not isinstance(modules, dict):
            return []

        pairs = []
        for module_path, info in modules.items():
            if not isinstance(info, dict):
                continue
            reqs = info.get("requirements", [])
            if not isinstance(reqs, list):
                continue
            for req_id in reqs:
                if isinstance(req_id, str):
                    pairs.append((module_path, req_id))

        return pairs

    def read_dependencies(self, project: str) -> list[tuple[str, str]]:
        """Parse one spectrace-map.yaml, return (module, provider surface node) pairs.

        A module lists the surfaces it reads from other projects under
        ``depends_on`` as ``{provider}:{surface}`` strings, which are graph node
        ids as written.
        """
        root = self.project_roots.get(project)
        if not root:
            return []

        data = load_map(root)
        if data is None:
            return []

        modules = data.get("modules", {})
        if not isinstance(modules, dict):
            return []

        pairs = []
        for module_path, info in modules.items():
            if not isinstance(info, dict):
                continue
            dependencies = info.get(DEPENDS_ON_KEY, [])
            if not isinstance(dependencies, list):
                continue
            for surface_node in dependencies:
                if isinstance(surface_node, str):
                    pairs.append((module_path, surface_node))

        return pairs

    def read_all_dependencies(self) -> list[GraphEdge]:
        """Read all projects, return dependency GraphEdges into provider surfaces."""
        edges = []
        for project in self.project_roots:
            name = self.project_name(project)
            for module_path, surface_node in self.read_dependencies(project):
                edges.append(
                    GraphEdge(
                        source_id=qualify(name, module_path),
                        target_id=surface_node,
                        source=EdgeSource.DEPENDENCY,
                        weight=1.0,
                        project=name,
                    )
                )
        return edges

    def read_all(self) -> list[GraphEdge]:
        """Read all projects, return annotated GraphEdges keyed by project."""
        edges = []
        for project in self.project_roots:
            name = self.project_name(project)
            for module_path, req_id in self.read_map(project):
                edges.append(
                    GraphEdge(
                        source_id=qualify(name, module_path),
                        target_id=qualify(name, req_id),
                        source=EdgeSource.ANNOTATED,
                        weight=1.0,
                        project=name,
                    )
                )
        return edges

    def validate_map(self, data: dict) -> list[str]:
        """Validate map data structure, return error strings."""
        errors = []
        if not isinstance(data, dict):
            errors.append("Root must be a mapping")
            return errors

        if "project" not in data:
            errors.append("Missing required field: project")

        if "modules" not in data:
            errors.append("Missing required field: modules")
            return errors

        modules = data.get("modules", {})
        if not isinstance(modules, dict):
            errors.append("'modules' must be a mapping")
            return errors

        for path, info in modules.items():
            if not isinstance(info, dict):
                errors.append(f"Module '{path}': value must be a mapping")
                continue
            reqs = info.get("requirements")
            if reqs is None:
                errors.append(f"Module '{path}': missing 'requirements' field")
            elif not isinstance(reqs, list):
                errors.append(f"Module '{path}': 'requirements' must be a list")
            else:
                for req in reqs:
                    if not isinstance(req, str):
                        errors.append(
                            f"Module '{path}': requirement ID must be a string,"
                            f" got {type(req).__name__}"
                        )
            errors.extend(self._validate_dependencies(path, info))

        return errors

    def _validate_dependencies(self, path: str, info: dict) -> list[str]:
        """Check one module's ``depends_on`` list, return error strings."""
        if DEPENDS_ON_KEY not in info:
            return []
        dependencies = info[DEPENDS_ON_KEY]
        if not isinstance(dependencies, list):
            return [f"Module '{path}': '{DEPENDS_ON_KEY}' must be a list"]

        errors = []
        for surface_node in dependencies:
            if not isinstance(surface_node, str):
                errors.append(
                    f"Module '{path}': dependency must be a string,"
                    f" got {type(surface_node).__name__}"
                )
                continue
            provider, surface = unqualify(surface_node)
            if not provider or not surface:
                errors.append(
                    f"Module '{path}': dependency '{surface_node}' must name a provider"
                    f" and a surface as 'project{NODE_SEPARATOR}surface'"
                )
        return errors

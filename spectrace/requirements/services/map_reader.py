"""Reader for spectrace-map.yaml files."""

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..projects import NODE_SEPARATOR, qualify, unqualify
from .contract_snapshot import SNAPSHOT_FILENAME, ContractSnapshot
from .impact_graph import EdgeSource, GraphEdge

logger = logging.getLogger(__name__)

MAP_FILENAME = "spectrace-map.yaml"


class UnknownSurfaceError(ValueError):
    """A map declares a dependency on a surface its provider does not publish."""

    def __init__(self, consumer: str, module: str, declaration: str, known: list[str]):
        super().__init__(
            f"{consumer} module {module!r} declares a dependency on {declaration!r}, "
            f"which its provider does not publish. Known surfaces: {', '.join(sorted(known))}"
        )


class MalformedDependencyError(ValueError):
    """A dependency declaration does not name a project and a surface."""

    def __init__(self, consumer: str, module: str, declaration: str):
        super().__init__(
            f"{consumer} module {module!r} declares the dependency {declaration!r}, which "
            f"does not name a project and a surface as 'project{NODE_SEPARATOR}surface'."
        )


@dataclass
class UnresolvedDependency:
    """A declared dependency whose provider was absent from the analysed roots."""

    consumer: str
    module: str
    provider: str
    surface: str


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
        """Parse one map's dependency declarations, return (module, declaration) pairs."""
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
            declarations = info.get("depends_on", [])
            if not isinstance(declarations, list):
                continue
            for declaration in declarations:
                if isinstance(declaration, str):
                    pairs.append((module_path, declaration))

        return pairs

    def published_surfaces(self, project: str) -> set[str]:
        """Name every surface a project publishes: its contract surfaces and mapped modules."""
        root = self.project_roots.get(project)
        if not root:
            return set()

        surfaces = {module_path for module_path, _ in self.read_map(project)}
        snapshot_path = root / SNAPSHOT_FILENAME
        if snapshot_path.exists():
            surfaces |= set(ContractSnapshot.load(snapshot_path).surfaces)
        return surfaces

    def read_all_dependencies(self) -> tuple[list[GraphEdge], list[UnresolvedDependency]]:
        """Build directed provider-to-consumer edges from every map's declarations.

        Raises:
            MalformedDependencyError: A declaration does not name a project and a surface.
            UnknownSurfaceError: A declaration names a loaded project that does not
                publish the surface.
        """
        keys_by_name = {self.project_name(key): key for key in self.project_roots}
        surfaces_by_name: dict[str, set[str]] = {}

        edges: list[GraphEdge] = []
        unresolved: list[UnresolvedDependency] = []

        for key in self.project_roots:
            consumer = self.project_name(key)
            for module_path, declaration in self.read_dependencies(key):
                provider, surface = unqualify(declaration)
                if not provider or not surface:
                    raise MalformedDependencyError(consumer, module_path, declaration)

                if provider not in keys_by_name:
                    unresolved.append(
                        UnresolvedDependency(consumer, module_path, provider, surface)
                    )
                    continue

                if provider not in surfaces_by_name:
                    surfaces_by_name[provider] = self.published_surfaces(keys_by_name[provider])
                if surface not in surfaces_by_name[provider]:
                    raise UnknownSurfaceError(
                        consumer, module_path, declaration, surfaces_by_name[provider]
                    )

                edges.append(
                    GraphEdge(
                        source_id=qualify(provider, surface),
                        target_id=qualify(consumer, module_path),
                        source=EdgeSource.DEPENDENCY,
                        weight=1.0,
                        project=consumer,
                        directed=True,
                    )
                )

        return edges, unresolved

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

            declarations = info.get("depends_on")
            if declarations is None:
                continue
            if not isinstance(declarations, list):
                errors.append(f"Module '{path}': 'depends_on' must be a list")
                continue
            for declaration in declarations:
                if not isinstance(declaration, str):
                    errors.append(
                        f"Module '{path}': dependency must be a string,"
                        f" got {type(declaration).__name__}"
                    )
                elif NODE_SEPARATOR not in declaration:
                    errors.append(
                        f"Module '{path}': dependency '{declaration}' must name a project"
                        f" and a surface as 'project{NODE_SEPARATOR}surface'"
                    )

        return errors

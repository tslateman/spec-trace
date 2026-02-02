"""Dependency validation service for requirement dependencies."""
from collections import defaultdict
from dataclasses import dataclass

from requirements.models import Requirement


@dataclass
class CircularDependency:
    """A circular dependency detected between requirements."""
    cycle: list[str]  # List of external_ids forming the cycle

    def __str__(self) -> str:
        return " → ".join(self.cycle)


@dataclass
class DependencyChain:
    """Transitive dependencies for a requirement."""
    root_id: str
    direct: list[str]  # Direct dependencies
    transitive: list[str]  # All transitive dependencies (includes direct)


class DependencyValidator:
    """Validates requirement dependency relationships.

    Detects circular dependencies and computes transitive dependency chains.
    """

    def __init__(self):
        self._graph: dict[str, set[str]] = {}
        self._reverse_graph: dict[str, set[str]] = {}

    def _build_graph(self) -> None:
        """Build dependency graph from database."""
        self._graph = defaultdict(set)
        self._reverse_graph = defaultdict(set)

        for req in Requirement.objects.prefetch_related('depends_on').all():
            ext_id = req.external_id
            self._graph[ext_id]  # Ensure node exists even without dependencies
            for dep in req.depends_on.all():
                dep_id = dep.external_id
                self._graph[ext_id].add(dep_id)
                self._reverse_graph[dep_id].add(ext_id)

    def detect_circular_dependencies(self) -> list[CircularDependency]:
        """Detect all circular dependencies in the requirement graph.

        Uses DFS-based cycle detection.

        Returns:
            List of CircularDependency objects, one per cycle found.
        """
        self._build_graph()

        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[CircularDependency] = []
        path: list[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self._graph.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found cycle - extract it from path
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(CircularDependency(cycle=cycle))

            path.pop()
            rec_stack.remove(node)

        for node in self._graph:
            if node not in visited:
                dfs(node)

        return cycles

    def get_dependency_chain(self, external_id: str) -> DependencyChain:
        """Get all transitive dependencies for a requirement.

        Args:
            external_id: The requirement's external_id

        Returns:
            DependencyChain with direct and transitive dependencies
        """
        self._build_graph()

        direct = list(self._graph.get(external_id, set()))

        # BFS to find all transitive dependencies
        transitive: set[str] = set()
        queue = list(direct)

        while queue:
            current = queue.pop(0)
            if current in transitive:
                continue
            transitive.add(current)

            # Add dependencies of current node
            for dep in self._graph.get(current, set()):
                if dep not in transitive:
                    queue.append(dep)

        return DependencyChain(
            root_id=external_id,
            direct=direct,
            transitive=sorted(transitive),
        )

    def get_dependents(self, external_id: str) -> list[str]:
        """Get all requirements that depend on the given requirement.

        Args:
            external_id: The requirement's external_id

        Returns:
            List of external_ids that depend on this requirement (directly or transitively)
        """
        self._build_graph()

        # BFS on reverse graph
        dependents: set[str] = set()
        queue = list(self._reverse_graph.get(external_id, set()))

        while queue:
            current = queue.pop(0)
            if current in dependents:
                continue
            dependents.add(current)

            # Add requirements that depend on current
            for dep in self._reverse_graph.get(current, set()):
                if dep not in dependents:
                    queue.append(dep)

        return sorted(dependents)

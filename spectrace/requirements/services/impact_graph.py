"""Impact graph for cross-project blast radius analysis."""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ..projects import node_name, node_project

logger = logging.getLogger(__name__)


class EdgeSource(Enum):
    """Origin of a graph edge."""

    ANNOTATED = "annotated"
    GIT_INFERRED = "git-inferred"
    CONTRACT = "contract"
    DEPENDENCY = "dependency"


@dataclass
class GraphEdge:
    """A directed edge in the impact graph."""

    source_id: str
    target_id: str
    source: EdgeSource
    weight: float = 1.0
    project: str = ""
    directed: bool = False


@dataclass
class BlastResult:
    """Result of a blast radius computation."""

    directly_changed: list[str] = field(default_factory=list)
    affected_requirements: list[str] = field(default_factory=list)
    affected_modules: list[str] = field(default_factory=list)
    affected_projects: set[str] = field(default_factory=set)
    cross_project_edges: list[GraphEdge] = field(default_factory=list)
    traversed_edges: list[GraphEdge] = field(default_factory=list)
    risk_score: float = 0.0
    risk_level: str = "low"


class ImpactGraph:
    """In-memory impact graph assembled from multiple sources.

    No database storage. Built fresh at analysis time from:
    - spectrace-map.yaml (annotated edges)
    - Git co-change inference (inferred edges)
    - Contract snapshots (contract edges)
    """

    def __init__(self):
        self._edges: list[GraphEdge] = []
        self._adjacency: dict[str, list[GraphEdge]] = defaultdict(list)
        self._reverse: dict[str, list[GraphEdge]] = defaultdict(list)

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph."""
        self._edges.append(edge)
        self._adjacency[edge.source_id].append(edge)
        self._reverse[edge.target_id].append(edge)

    def blast_radius(self, changed_ids: list[str], max_depth: int = 3) -> BlastResult:
        """Compute blast radius via BFS from changed nodes.

        Follows BFS pattern from DependencyValidator.get_dependents():
        - deque for BFS queue
        - visited set to avoid cycles
        - max_depth limit
        - cross-project edge collection
        """
        result = BlastResult(directly_changed=list(changed_ids))
        visited: set[str] = set(changed_ids)
        queue: deque[tuple[str, int]] = deque((nid, 0) for nid in changed_ids)

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for edge in self._adjacency.get(current, []):
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append((edge.target_id, depth + 1))

            for edge in self._reverse.get(current, []):
                if edge.directed:
                    continue
                if edge.source_id not in visited:
                    visited.add(edge.source_id)
                    queue.append((edge.source_id, depth + 1))

        # Categorize affected nodes
        all_affected = visited - set(changed_ids)
        projects: set[str] = set()
        modules: list[str] = []
        requirements: list[str] = []

        for node_id in all_affected:
            name = node_name(node_id)
            if name.startswith("REQ-") or name.startswith("req-"):
                requirements.append(node_id)
            elif "/" in name:
                modules.append(node_id)
            project = node_project(node_id)
            if project:
                projects.add(project)

        # Detect cross-project edges among visited nodes
        traversed: list[GraphEdge] = []
        cross_project: list[GraphEdge] = []
        for edge in self._edges:
            if edge.source_id in visited and edge.target_id in visited:
                traversed.append(edge)
                source_project = node_project(edge.source_id)
                target_project = node_project(edge.target_id)
                if source_project and target_project and source_project != target_project:
                    cross_project.append(edge)

        result.affected_requirements = sorted(requirements)
        result.affected_modules = sorted(modules)
        result.affected_projects = projects
        result.cross_project_edges = cross_project
        result.traversed_edges = traversed
        result.risk_score, result.risk_level = self._compute_risk(result)

        return result

    def affected_requirements(self, changed_files: list[str]) -> list[str]:
        """Given changed file paths, find affected requirement IDs."""
        return self.blast_radius(changed_files).affected_requirements

    def _compute_risk(self, result: BlastResult) -> tuple[float, str]:
        """Compute risk score from blast result.

        Formula:
        - 0.3 * module_signal (saturates at 10)
        - 0.3 * requirement_signal (saturates at 10)
        - 0.2 * project_signal (saturates at 5)
        - 0.2 * cross_project_signal (saturates at 5)
        """
        module_signal = min(1.0, len(result.affected_modules) / 10)
        req_signal = min(1.0, len(result.affected_requirements) / 10)
        project_signal = min(1.0, len(result.affected_projects) / 5)
        cross_signal = min(1.0, len(result.cross_project_edges) / 5)

        score = round(
            0.3 * module_signal + 0.3 * req_signal + 0.2 * project_signal + 0.2 * cross_signal,
            2,
        )

        if score >= 0.75:
            level = "critical"
        elif score >= 0.5:
            level = "high"
        elif score >= 0.25:
            level = "medium"
        else:
            level = "low"

        return score, level

    @property
    def edges(self) -> list[GraphEdge]:
        return list(self._edges)

    @property
    def node_count(self) -> int:
        return len({e.source_id for e in self._edges} | {e.target_id for e in self._edges})


class ImpactGraphBuilder:
    """Assembles an ImpactGraph from all three edge sources."""

    def __init__(self, project_roots: dict[str, Path]):
        self.project_roots = project_roots

    def build(
        self,
        annotated_edges: Optional[list[GraphEdge]] = None,
        inferred_edges: Optional[list[GraphEdge]] = None,
        contract_edges: Optional[list[GraphEdge]] = None,
        dependency_edges: Optional[list[GraphEdge]] = None,
    ) -> ImpactGraph:
        """Build graph from provided edge lists."""
        graph = ImpactGraph()
        for edge in annotated_edges or []:
            graph.add_edge(edge)
        for edge in inferred_edges or []:
            graph.add_edge(edge)
        for edge in contract_edges or []:
            graph.add_edge(edge)
        for edge in dependency_edges or []:
            graph.add_edge(edge)
        return graph

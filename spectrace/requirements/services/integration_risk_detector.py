"""Integration risk detection for in-flight agent tasks.

Detects conflicts across active tasks that could cause integration problems:
- Overlapping requirements: Two tasks linked to the same requirement.
- Dependency chains: Task A modifies a requirement that Task B depends on.
- Scope overlap: Two tasks with intersecting scope_in paths.
"""

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from requirements.models import AgentTask, AgentTaskStatus


@dataclass
class IntegrationRisk:
    """A detected integration risk between two agent tasks."""

    task_a_id: str
    task_b_id: str
    task_a_title: str
    task_b_title: str
    risk_type: str  # "overlapping_requirement", "dependency_chain", "scope_overlap"
    risk_level: str  # "high", "medium", "low"
    details: dict
    recommendation: str


class IntegrationRiskDetector:
    """Detects integration risks across in-flight agent tasks."""

    def detect_all(self) -> list[IntegrationRisk]:
        """Run all detection rules on active tasks."""
        tasks = list(
            AgentTask.objects.filter(
                status__in=[AgentTaskStatus.IN_PROGRESS, AgentTaskStatus.READY_FOR_REVIEW]
            ).prefetch_related("requirements", "requirements__depends_on")
        )

        if not tasks:
            return []

        risks = []
        risks.extend(self.detect_overlapping_requirements(tasks))
        risks.extend(self.detect_dependency_chains(tasks))
        risks.extend(self.detect_scope_overlap(tasks))
        return risks

    def detect_overlapping_requirements(self, tasks: list[AgentTask]) -> list[IntegrationRisk]:
        """Two tasks linked to the same requirement.

        Risk: semantic merge conflict. Level: HIGH.
        """
        # Map requirement IDs to the tasks that reference them
        req_to_tasks: dict[int, list[AgentTask]] = defaultdict(list)
        for task in tasks:
            for req in task.requirements.all():
                req_to_tasks[req.id].append(task)

        risks = []
        seen_pairs: set[tuple[str, str]] = set()

        for req_id, linked_tasks in req_to_tasks.items():
            if len(linked_tasks) < 2:
                continue

            for task_a, task_b in combinations(linked_tasks, 2):
                pair_key = tuple(sorted([task_a.external_id, task_b.external_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Collect all shared requirement external_ids for this pair
                reqs_a = set(task_a.requirements.values_list("id", flat=True))
                reqs_b = set(task_b.requirements.values_list("id", flat=True))
                shared_ids = reqs_a & reqs_b

                from requirements.models import Requirement

                shared_external_ids = list(
                    Requirement.objects.filter(id__in=shared_ids).values_list(
                        "external_id", flat=True
                    )
                )

                risks.append(
                    IntegrationRisk(
                        task_a_id=task_a.external_id,
                        task_b_id=task_b.external_id,
                        task_a_title=task_a.title,
                        task_b_title=task_b.title,
                        risk_type="overlapping_requirement",
                        risk_level="high",
                        details={"shared_requirements": shared_external_ids},
                        recommendation="Review these tasks together before merging",
                    )
                )

        return risks

    def detect_dependency_chains(self, tasks: list[AgentTask]) -> list[IntegrationRisk]:
        """Task A modifies a requirement that Task B depends on.

        Risk: cascading invalidation. Level: MEDIUM.
        """
        # Build maps: task → its requirement IDs, and requirement ID → tasks
        task_req_ids: dict[str, set[int]] = {}
        for task in tasks:
            task_req_ids[task.external_id] = set(task.requirements.values_list("id", flat=True))

        risks = []
        seen_pairs: set[tuple[str, str]] = set()

        for task_a, task_b in combinations(tasks, 2):
            pair_key = tuple(sorted([task_a.external_id, task_b.external_id]))
            if pair_key in seen_pairs:
                continue

            reqs_a = task_req_ids[task_a.external_id]
            reqs_b = task_req_ids[task_b.external_id]

            # Check if any of task_b's requirements depend on task_a's requirements
            for req_b in task_b.requirements.all():
                deps = set(req_b.depends_on.values_list("id", flat=True))
                overlap = deps & reqs_a
                if overlap:
                    seen_pairs.add(pair_key)
                    risks.append(
                        IntegrationRisk(
                            task_a_id=task_a.external_id,
                            task_b_id=task_b.external_id,
                            task_a_title=task_a.title,
                            task_b_title=task_b.title,
                            risk_type="dependency_chain",
                            risk_level="medium",
                            details={
                                "upstream_task": task_a.external_id,
                                "downstream_task": task_b.external_id,
                            },
                            recommendation=(
                                f"Sequence these tasks — merge {task_a.external_id} first"
                            ),
                        )
                    )
                    break

            if pair_key in seen_pairs:
                continue

            # Check the reverse: task_a's requirements depend on task_b's
            for req_a in task_a.requirements.all():
                deps = set(req_a.depends_on.values_list("id", flat=True))
                overlap = deps & reqs_b
                if overlap:
                    seen_pairs.add(pair_key)
                    risks.append(
                        IntegrationRisk(
                            task_a_id=task_a.external_id,
                            task_b_id=task_b.external_id,
                            task_a_title=task_a.title,
                            task_b_title=task_b.title,
                            risk_type="dependency_chain",
                            risk_level="medium",
                            details={
                                "upstream_task": task_b.external_id,
                                "downstream_task": task_a.external_id,
                            },
                            recommendation=(
                                f"Sequence these tasks — merge {task_b.external_id} first"
                            ),
                        )
                    )
                    break

        return risks

    def detect_scope_overlap(self, tasks: list[AgentTask]) -> list[IntegrationRisk]:
        """Two tasks with intersecting scope_in paths.

        Risk: file-level merge conflict. Level: LOW.
        """
        risks = []

        for task_a, task_b in combinations(tasks, 2):
            paths_a = task_a.scope_in or []
            paths_b = task_b.scope_in or []

            if not paths_a or not paths_b:
                continue

            overlapping = self._find_overlapping_paths(paths_a, paths_b)
            if overlapping:
                risks.append(
                    IntegrationRisk(
                        task_a_id=task_a.external_id,
                        task_b_id=task_b.external_id,
                        task_a_title=task_a.title,
                        task_b_title=task_b.title,
                        risk_type="scope_overlap",
                        risk_level="low",
                        details={"overlapping_paths": overlapping},
                        recommendation="Check for file-level conflicts before merging",
                    )
                )

        return risks

    @staticmethod
    def _find_overlapping_paths(paths_a: list[str], paths_b: list[str]) -> list[str]:
        """Find paths that overlap via prefix matching.

        "src/auth/" overlaps with "src/auth/login.py" because one is a prefix of the other.
        """
        overlapping = []
        for pa in paths_a:
            for pb in paths_b:
                if pa.startswith(pb) or pb.startswith(pa):
                    overlapping.append(f"{pa} <-> {pb}")
        return overlapping

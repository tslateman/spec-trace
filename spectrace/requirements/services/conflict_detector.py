"""Conflict detection service for identifying requirement conflicts.

Detects patterns where requirements may be in conflict, such as:
- Mutual exclusion: Tests for both requirements never pass in the same run.
"""
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from django.db.models import Q

from requirements.models import (
    ConflictConfidence,
    ConflictLog,
    ConflictPattern,
    Requirement,
    TestRequirementLink,
    TestRun,
)


@dataclass
class ConflictResult:
    """A detected conflict between two requirements."""
    requirement_a_id: int
    requirement_b_id: int
    requirement_a_external_id: str
    requirement_b_external_id: str
    pattern: str
    confidence: str
    runs_analyzed: int
    details: dict


class ConflictDetector:
    """Detects conflicts between requirements based on test patterns.

    Currently implements:
    - Mutual exclusion detection: Requirements whose tests never both pass together.
    """

    def __init__(self, min_runs: int = 10, min_overlap: int = 5):
        """Initialize the conflict detector.

        Args:
            min_runs: Minimum test runs before analyzing for conflicts.
            min_overlap: Minimum runs where both requirements were tested.
        """
        self.min_runs = min_runs
        self.min_overlap = min_overlap

    def detect_mutual_exclusion(
        self,
        runs: list[TestRun] | None = None,
    ) -> list[ConflictResult]:
        """Detect mutual exclusion conflicts across test runs.

        Identifies requirement pairs where:
        - Tests for both requirements exist
        - They've been tested together min_overlap+ times
        - They've NEVER both passed in the same run
        - Shows inverse pattern (A passes when B fails, vice versa)

        Args:
            runs: List of TestRun objects to analyze. If None, uses recent runs.

        Returns:
            List of ConflictResult objects for detected conflicts.
        """
        if runs is None:
            runs = list(TestRun.objects.order_by('-imported_at')[:self.min_runs * 2])

        if len(runs) < self.min_runs:
            return []

        # Build per-run status matrix: {run_id: {req_id: 'passed'|'failed'|'mixed'}}
        run_statuses = {}
        for run in runs:
            run_statuses[run.id] = self._get_run_requirement_statuses(run)

        # Get all requirements that have linked tests
        req_ids_with_links = set(
            TestRequirementLink.objects.values_list('requirement_id', flat=True).distinct()
        )

        conflicts = []

        # Check all pairs of requirements
        for req_a_id, req_b_id in combinations(req_ids_with_links, 2):
            conflict = self._check_pair_for_mutual_exclusion(
                req_a_id, req_b_id, run_statuses
            )
            if conflict:
                conflicts.append(conflict)

        return conflicts

    def _get_run_requirement_statuses(self, run: TestRun) -> dict[int, str]:
        """Get aggregated status for each requirement in a test run.

        Returns dict mapping requirement_id to status:
        - 'passed': All tests passed
        - 'failed': At least one test failed/errored
        - 'skipped': All tests skipped
        """
        statuses = {}

        # Get all links that were tested in this run
        links = TestRequirementLink.objects.filter(
            last_run_at=run.imported_at
        ).select_related('requirement')

        # Group by requirement
        req_results = defaultdict(list)
        for link in links:
            req_results[link.requirement_id].append(link.last_status)

        # Aggregate status per requirement
        for req_id, link_statuses in req_results.items():
            if any(s in ('failed', 'error') for s in link_statuses):
                statuses[req_id] = 'failed'
            elif all(s == 'skipped' for s in link_statuses):
                statuses[req_id] = 'skipped'
            elif any(s == 'passed' for s in link_statuses):
                statuses[req_id] = 'passed'
            else:
                statuses[req_id] = 'unknown'

        return statuses

    def _check_pair_for_mutual_exclusion(
        self,
        req_a_id: int,
        req_b_id: int,
        run_statuses: dict[int, dict[int, str]],
    ) -> ConflictResult | None:
        """Check if two requirements show mutual exclusion pattern.

        Returns ConflictResult if detected, None otherwise.
        """
        # Count runs where both were tested
        both_tested = 0
        both_passed = 0
        a_passed_b_failed = 0
        a_failed_b_passed = 0
        both_failed = 0

        for run_id, statuses in run_statuses.items():
            if req_a_id not in statuses or req_b_id not in statuses:
                continue

            both_tested += 1
            status_a = statuses[req_a_id]
            status_b = statuses[req_b_id]

            if status_a == 'passed' and status_b == 'passed':
                both_passed += 1
            elif status_a == 'passed' and status_b == 'failed':
                a_passed_b_failed += 1
            elif status_a == 'failed' and status_b == 'passed':
                a_failed_b_passed += 1
            elif status_a == 'failed' and status_b == 'failed':
                both_failed += 1

        # Check for mutual exclusion pattern
        if both_tested < self.min_overlap:
            return None

        if both_passed > 0:
            return None  # They can both pass, no mutual exclusion

        # Calculate confidence
        inverse_runs = a_passed_b_failed + a_failed_b_passed
        if inverse_runs == 0:
            return None  # No inverse pattern

        inverse_ratio = inverse_runs / both_tested

        # Determine confidence
        if inverse_ratio >= 0.8 and both_tested >= 10:
            confidence = ConflictConfidence.HIGH
        elif inverse_ratio >= 0.5 and both_tested >= 5:
            confidence = ConflictConfidence.MEDIUM
        else:
            confidence = ConflictConfidence.LOW

        # Get requirement external IDs
        try:
            req_a = Requirement.objects.get(id=req_a_id)
            req_b = Requirement.objects.get(id=req_b_id)
        except Requirement.DoesNotExist:
            return None

        return ConflictResult(
            requirement_a_id=req_a_id,
            requirement_b_id=req_b_id,
            requirement_a_external_id=req_a.external_id,
            requirement_b_external_id=req_b.external_id,
            pattern=ConflictPattern.MUTUAL_EXCLUSION,
            confidence=confidence,
            runs_analyzed=both_tested,
            details={
                'both_passed': both_passed,
                'a_passed_b_failed': a_passed_b_failed,
                'a_failed_b_passed': a_failed_b_passed,
                'both_failed': both_failed,
                'inverse_ratio': inverse_ratio,
            }
        )

    def log_conflicts(
        self,
        conflicts: list[ConflictResult],
        skip_existing: bool = True,
    ) -> dict:
        """Log detected conflicts to the database.

        Args:
            conflicts: List of ConflictResult objects to log.
            skip_existing: Skip conflicts that already exist unresolved.

        Returns:
            Summary dict with created_count, skipped_count.
        """
        created_count = 0
        skipped_count = 0

        for conflict in conflicts:
            # Check for existing unresolved conflict (in either direction)
            existing = ConflictLog.objects.filter(
                Q(requirement_a_id=conflict.requirement_a_id, requirement_b_id=conflict.requirement_b_id) |
                Q(requirement_a_id=conflict.requirement_b_id, requirement_b_id=conflict.requirement_a_id),
                pattern=conflict.pattern,
                resolved=False,
            ).exists()

            if existing and skip_existing:
                skipped_count += 1
                continue

            ConflictLog.objects.create(
                requirement_a_id=conflict.requirement_a_id,
                requirement_b_id=conflict.requirement_b_id,
                pattern=conflict.pattern,
                confidence=conflict.confidence,
                details=conflict.details,
            )
            created_count += 1

        return {
            'created_count': created_count,
            'skipped_count': skipped_count,
        }

    def get_high_confidence_conflicts(self) -> list[ConflictLog]:
        """Get all unresolved high-confidence conflicts for alerting."""
        return list(
            ConflictLog.objects.filter(
                confidence=ConflictConfidence.HIGH,
                resolved=False,
            ).select_related('requirement_a', 'requirement_b')
        )

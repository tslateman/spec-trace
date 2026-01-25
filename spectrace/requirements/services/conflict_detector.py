"""Conflict detection service for identifying requirement conflicts.

Detects patterns where requirements may be in conflict, such as:
- Mutual exclusion: Tests for both requirements never pass in the same run.
- Condition overlap: Requirements with overlapping conditions on same component.
- Timing conflict: Same component, conflicting timing constraints.
- Response contradiction: Same trigger, different expected responses.
"""
import re
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

    def detect_condition_overlap(self) -> list[ConflictResult]:
        """Detect conflicts where requirements have overlapping conditions on same component.

        Identifies requirement pairs where:
        - Both have the same component
        - Both have conditions defined
        - Conditions appear to overlap (simple heuristic based on variable names)

        Returns:
            List of ConflictResult objects for detected conflicts.
        """
        # Get requirements with both component and condition defined
        requirements = list(
            Requirement.objects.exclude(component='').exclude(condition='')
        )

        if len(requirements) < 2:
            return []

        conflicts = []

        # Group by component
        by_component: dict[str, list[Requirement]] = defaultdict(list)
        for req in requirements:
            by_component[req.component.lower().strip()].append(req)

        # Check pairs within same component
        for component, reqs in by_component.items():
            if len(reqs) < 2:
                continue

            for req_a, req_b in combinations(reqs, 2):
                overlap_info = self._check_condition_overlap(req_a, req_b)
                if overlap_info:
                    confidence = self._calculate_condition_confidence(overlap_info)
                    conflicts.append(ConflictResult(
                        requirement_a_id=req_a.id,
                        requirement_b_id=req_b.id,
                        requirement_a_external_id=req_a.external_id,
                        requirement_b_external_id=req_b.external_id,
                        pattern=ConflictPattern.CONDITION_OVERLAP,
                        confidence=confidence,
                        runs_analyzed=0,
                        details={
                            'component': component,
                            'condition_a': req_a.condition,
                            'condition_b': req_b.condition,
                            **overlap_info,
                        }
                    ))

        return conflicts

    def _check_condition_overlap(
        self, req_a: Requirement, req_b: Requirement
    ) -> dict | None:
        """Check if two requirements have overlapping conditions.

        Uses simple heuristics:
        - Same variable names being compared
        - Overlapping numeric ranges

        Returns:
            Dict with overlap details, or None if no overlap detected.
        """
        cond_a = req_a.condition.lower()
        cond_b = req_b.condition.lower()

        # Extract variables being compared (e.g., "battery_level", "temperature")
        var_pattern = r'([a-z_][a-z0-9_]*)\s*[<>=!]+'
        vars_a = set(re.findall(var_pattern, cond_a))
        vars_b = set(re.findall(var_pattern, cond_b))

        common_vars = vars_a & vars_b
        if not common_vars:
            return None

        # Extract numeric thresholds for comparison
        threshold_pattern = r'[<>=!]+\s*(\d+(?:\.\d+)?)'
        thresholds_a = [float(t) for t in re.findall(threshold_pattern, cond_a)]
        thresholds_b = [float(t) for t in re.findall(threshold_pattern, cond_b)]

        # Check for potential range overlap
        overlap_type = 'variable_overlap'
        if thresholds_a and thresholds_b:
            # Simple overlap check: if ranges might intersect
            min_a, max_a = min(thresholds_a), max(thresholds_a)
            min_b, max_b = min(thresholds_b), max(thresholds_b)

            if max_a >= min_b and max_b >= min_a:
                overlap_type = 'range_overlap'

        return {
            'common_variables': list(common_vars),
            'overlap_type': overlap_type,
            'thresholds_a': thresholds_a,
            'thresholds_b': thresholds_b,
        }

    def _calculate_condition_confidence(self, overlap_info: dict) -> str:
        """Calculate confidence level for condition overlap."""
        if overlap_info.get('overlap_type') == 'range_overlap':
            return ConflictConfidence.HIGH
        elif len(overlap_info.get('common_variables', [])) > 1:
            return ConflictConfidence.MEDIUM
        return ConflictConfidence.LOW

    def detect_timing_conflicts(self) -> list[ConflictResult]:
        """Detect conflicts where same component has conflicting timing constraints.

        Identifies requirement pairs where:
        - Both have the same component
        - Both have timing constraints defined
        - Timing constraints appear contradictory

        Returns:
            List of ConflictResult objects for detected conflicts.
        """
        # Get requirements with both component and timing defined
        requirements = list(
            Requirement.objects.exclude(component='').exclude(timing='')
        )

        if len(requirements) < 2:
            return []

        conflicts = []

        # Group by component
        by_component: dict[str, list[Requirement]] = defaultdict(list)
        for req in requirements:
            by_component[req.component.lower().strip()].append(req)

        # Check pairs within same component
        for component, reqs in by_component.items():
            if len(reqs) < 2:
                continue

            for req_a, req_b in combinations(reqs, 2):
                timing_a = self._parse_timing(req_a.timing)
                timing_b = self._parse_timing(req_b.timing)

                if timing_a is None or timing_b is None:
                    continue

                # Different timing requirements for same component = potential conflict
                if timing_a != timing_b:
                    # Greater difference = higher confidence
                    ratio = max(timing_a, timing_b) / min(timing_a, timing_b) if min(timing_a, timing_b) > 0 else 10
                    if ratio >= 5:
                        confidence = ConflictConfidence.HIGH
                    elif ratio >= 2:
                        confidence = ConflictConfidence.MEDIUM
                    else:
                        confidence = ConflictConfidence.LOW

                    conflicts.append(ConflictResult(
                        requirement_a_id=req_a.id,
                        requirement_b_id=req_b.id,
                        requirement_a_external_id=req_a.external_id,
                        requirement_b_external_id=req_b.external_id,
                        pattern=ConflictPattern.TIMING_CONFLICT,
                        confidence=confidence,
                        runs_analyzed=0,
                        details={
                            'component': component,
                            'timing_a': req_a.timing,
                            'timing_b': req_b.timing,
                            'seconds_a': timing_a,
                            'seconds_b': timing_b,
                            'ratio': ratio,
                        }
                    ))

        return conflicts

    def _parse_timing(self, timing: str) -> float | None:
        """Parse timing constraint to seconds.

        Supports formats like:
        - "within 2 seconds"
        - "in 500ms"
        - "after 1 minute"
        - "2s"

        Returns:
            Timing in seconds, or None if unparseable.
        """
        timing = timing.lower().strip()

        # Match patterns like "2 seconds", "500ms", "1 minute"
        pattern = r'(\d+(?:\.\d+)?)\s*(seconds?|s|ms|milliseconds?|minutes?|m)'
        match = re.search(pattern, timing)

        if not match:
            return None

        value = float(match.group(1))
        unit = match.group(2)

        if unit in ('ms', 'millisecond', 'milliseconds'):
            return value / 1000
        elif unit in ('m', 'minute', 'minutes'):
            return value * 60
        else:  # seconds
            return value

    def detect_response_contradictions(self) -> list[ConflictResult]:
        """Detect conflicts where same trigger leads to different responses.

        Identifies requirement pairs where:
        - Both have similar conditions
        - Both have responses defined
        - Responses appear contradictory

        Returns:
            List of ConflictResult objects for detected conflicts.
        """
        # Get requirements with both condition and response defined
        requirements = list(
            Requirement.objects.exclude(condition='').exclude(response='')
        )

        if len(requirements) < 2:
            return []

        conflicts = []

        for req_a, req_b in combinations(requirements, 2):
            # Check if conditions are similar
            if not self._conditions_similar(req_a.condition, req_b.condition):
                continue

            # Check if responses are contradictory
            contradiction_info = self._check_response_contradiction(
                req_a.response, req_b.response
            )

            if contradiction_info:
                conflicts.append(ConflictResult(
                    requirement_a_id=req_a.id,
                    requirement_b_id=req_b.id,
                    requirement_a_external_id=req_a.external_id,
                    requirement_b_external_id=req_b.external_id,
                    pattern=ConflictPattern.RESPONSE_CONTRADICTION,
                    confidence=contradiction_info['confidence'],
                    runs_analyzed=0,
                    details={
                        'condition_a': req_a.condition,
                        'condition_b': req_b.condition,
                        'response_a': req_a.response,
                        'response_b': req_b.response,
                        **contradiction_info,
                    }
                ))

        return conflicts

    def _conditions_similar(self, cond_a: str, cond_b: str) -> bool:
        """Check if two conditions are similar enough to compare responses.

        Uses simple word overlap heuristic.
        """
        words_a = set(re.findall(r'[a-z_][a-z0-9_]*', cond_a.lower()))
        words_b = set(re.findall(r'[a-z_][a-z0-9_]*', cond_b.lower()))

        if not words_a or not words_b:
            return False

        overlap = words_a & words_b
        min_len = min(len(words_a), len(words_b))

        # At least 50% word overlap
        return len(overlap) >= min_len * 0.5

    def _check_response_contradiction(
        self, response_a: str, response_b: str
    ) -> dict | None:
        """Check if two responses are contradictory.

        Looks for patterns like:
        - "show" vs "hide"
        - "enable" vs "disable"
        - "start" vs "stop"
        - "allow" vs "deny"
        """
        antonym_pairs = [
            ('show', 'hide'),
            ('display', 'hide'),
            ('enable', 'disable'),
            ('start', 'stop'),
            ('allow', 'deny'),
            ('accept', 'reject'),
            ('open', 'close'),
            ('lock', 'unlock'),
            ('activate', 'deactivate'),
            ('on', 'off'),
        ]

        resp_a = response_a.lower()
        resp_b = response_b.lower()

        for word_a, word_b in antonym_pairs:
            # Check if a has word_a and b has word_b, or vice versa
            if (word_a in resp_a and word_b in resp_b) or (word_b in resp_a and word_a in resp_b):
                return {
                    'contradiction_type': 'antonym',
                    'antonym_pair': (word_a, word_b),
                    'confidence': ConflictConfidence.HIGH,
                }

        # Check for same action on same object (might be duplicate, not conflict)
        # This is lower confidence as it might be intentional
        words_a = set(re.findall(r'[a-z_][a-z0-9_]*', resp_a))
        words_b = set(re.findall(r'[a-z_][a-z0-9_]*', resp_b))

        if words_a != words_b and len(words_a & words_b) >= 2:
            return {
                'contradiction_type': 'partial_overlap',
                'common_words': list(words_a & words_b),
                'confidence': ConflictConfidence.LOW,
            }

        return None

    def detect_all_structured_conflicts(self) -> list[ConflictResult]:
        """Run all structured field-based conflict detection.

        Returns:
            Combined list of all detected structured conflicts.
        """
        conflicts = []
        conflicts.extend(self.detect_condition_overlap())
        conflicts.extend(self.detect_timing_conflicts())
        conflicts.extend(self.detect_response_contradictions())
        return conflicts

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

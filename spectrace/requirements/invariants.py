"""Invariant checking for SpecTrace data consistency.

Invariants are conditions that should always hold true in the database.
This module provides functions to detect and optionally fix violations.

Invariants:
- INV-A: Verification status matches computed status
- INV-B: Breached SLO forces failing status
- INV-D: At most one TestRequirementLink per (test, requirement) pair
- INV-E: Regression from passed to failed/error sets needs_review flag
- INV-F: Completed flow runs have completion timestamp
- INV-G: Claimed tasks have claimed_by set
- INV-H: CLAIMED status has lease_expires
- INV-I: Non-draft tasks have history entry
- INV-J: Approved tasks have approved review
- INV-K: Reviewers can't review own work
"""

from dataclasses import dataclass, field
from typing import Literal

from .models import (
    AgentTask,
    AgentTaskHistory,
    AgentTaskReview,
    AgentTaskStatus,
    Requirement,
    ReviewDecision,
    SLOStatus,
    TestRequirementLink,
    TestRun,
    VerificationFlowRun,
    VerificationFlowStatus,
)
from .status import compute_unified_verification_status


@dataclass
class InvariantViolation:
    """A single invariant violation."""

    code: str
    requirement_id: str
    message: str
    severity: Literal['error', 'warning']
    details: dict = field(default_factory=dict)
    fixable: bool = False


@dataclass
class InvariantCheckResult:
    """Result of running invariant checks."""

    violations: list[InvariantViolation] = field(default_factory=list)
    checks_performed: int = 0
    fixed_count: int = 0

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == 'error')

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == 'warning')

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            'violations': [
                {
                    'code': v.code,
                    'requirement_id': v.requirement_id,
                    'message': v.message,
                    'severity': v.severity,
                    'fixable': v.fixable,
                    **v.details,
                }
                for v in self.violations
            ],
            'summary': {
                'checks_performed': self.checks_performed,
                'total_violations': len(self.violations),
                'errors': self.error_count,
                'warnings': self.warning_count,
                'fixed': self.fixed_count,
            },
        }


def check_inv_a_status_consistency(
    latest_run: TestRun | None = None,
    fix: bool = False,
) -> InvariantCheckResult:
    """Check INV-A: Verification status equals computed status.

    ∀ req: req.verification_status == compute_unified_verification_status(req)

    Args:
        latest_run: TestRun to use for status computation.
        fix: If True, update mismatched statuses.

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    for req in Requirement.objects.all():
        result.checks_performed += 1
        computed = compute_unified_verification_status(req, latest_run)

        if req.verification_status != computed:
            violation = InvariantViolation(
                code='INV-A',
                requirement_id=req.external_id,
                message=(
                    f"Status mismatch: stored '{req.verification_status}', "
                    f"computed '{computed}'"
                ),
                severity='error',
                details={
                    'stored_status': req.verification_status,
                    'computed_status': computed,
                },
                fixable=True,
            )
            result.violations.append(violation)

            if fix:
                req.verification_status = computed
                req.save(update_fields=['verification_status'])
                result.fixed_count += 1

    return result


def check_inv_b_slo_override(fix: bool = False) -> InvariantCheckResult:
    """Check INV-B: Breached SLO forces failing status.

    ∀ req: req.slo_status == 'breached' ⟹ req.verification_status == 'failing'

    Args:
        fix: If True, update requirements to failing status.

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    breached_reqs = Requirement.objects.filter(slo_status=SLOStatus.BREACHED)

    for req in breached_reqs:
        result.checks_performed += 1

        if req.verification_status != 'failing':
            violation = InvariantViolation(
                code='INV-B',
                requirement_id=req.external_id,
                message=(
                    f"SLO breached but status is '{req.verification_status}', "
                    f"should be 'failing'"
                ),
                severity='error',
                details={
                    'slo_status': req.slo_status,
                    'verification_status': req.verification_status,
                },
                fixable=True,
            )
            result.violations.append(violation)

            if fix:
                req.verification_status = 'failing'
                req.save(update_fields=['verification_status'])
                result.fixed_count += 1

    return result


def check_inv_d_link_uniqueness() -> InvariantCheckResult:
    """Check INV-D: At most one link per (test, requirement) pair.

    ∀ (test_nodeid, requirement): |TestRequirementLink| ≤ 1

    This is enforced by unique_together in the model, but we check for
    any violations that might have occurred before the constraint was added.

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    # Find duplicate links using raw SQL aggregation
    from django.db.models import Count

    duplicates = (
        TestRequirementLink.objects.values('test_nodeid', 'requirement')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )

    for dup in duplicates:
        result.checks_performed += 1
        req = Requirement.objects.get(pk=dup['requirement'])

        violation = InvariantViolation(
            code='INV-D',
            requirement_id=req.external_id,
            message=(
                f"Duplicate links: {dup['count']} links for test "
                f"'{dup['test_nodeid']}'"
            ),
            severity='error',
            details={
                'test_nodeid': dup['test_nodeid'],
                'link_count': dup['count'],
            },
            fixable=False,  # Requires manual resolution
        )
        result.violations.append(violation)

    if not duplicates:
        result.checks_performed = TestRequirementLink.objects.count()

    return result


def check_inv_e_review_flag(fix: bool = False) -> InvariantCheckResult:
    """Check INV-E: Regression sets needs_review flag.

    ∀ link: last_status changed from 'passed' to ('failed'|'error')
            ⟹ needs_review == True

    We check links that are failed/error but not flagged for review,
    which indicates the flag wasn't set on regression.

    Args:
        fix: If True, set needs_review on unflagged regressions.

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    # Links with failed/error status but not flagged for review
    unflagged_failures = TestRequirementLink.objects.filter(
        last_status__in=['failed', 'error'],
        needs_review=False,
    )

    for link in unflagged_failures:
        result.checks_performed += 1

        violation = InvariantViolation(
            code='INV-E',
            requirement_id=link.requirement.external_id,
            message=(
                f"Test '{link.test_nodeid}' has status '{link.last_status}' "
                f"but needs_review is False"
            ),
            severity='warning',
            details={
                'test_nodeid': link.test_nodeid,
                'last_status': link.last_status,
            },
            fixable=True,
        )
        result.violations.append(violation)

        if fix:
            link.needs_review = True
            link.review_reason = 'INV-E fix: unflagged failure'
            link.save(update_fields=['needs_review', 'review_reason'])
            result.fixed_count += 1

    if not unflagged_failures:
        result.checks_performed = TestRequirementLink.objects.count()

    return result


def check_inv_f_flow_completion() -> InvariantCheckResult:
    """Check INV-F: Flow run completion consistency.

    ∀ flow_run: completed_at != NULL ⟺ status ∈ {'passed', 'failed'}

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    # Completed runs without terminal status
    incomplete_with_timestamp = VerificationFlowRun.objects.filter(
        completed_at__isnull=False,
        status=VerificationFlowStatus.RUNNING,
    )

    for run in incomplete_with_timestamp:
        result.checks_performed += 1
        violation = InvariantViolation(
            code='INV-F',
            requirement_id=f'flow-run-{run.id}',
            message=(
                f"Flow run {run.id} has completed_at but status is "
                f"'{run.status}' (expected 'passed' or 'failed')"
            ),
            severity='error',
            details={
                'flow_run_id': run.id,
                'flow_name': run.flow.name,
                'status': run.status,
            },
            fixable=False,
        )
        result.violations.append(violation)

    # Terminal status without completion timestamp
    complete_without_timestamp = VerificationFlowRun.objects.filter(
        completed_at__isnull=True,
        status__in=[VerificationFlowStatus.PASSED, VerificationFlowStatus.FAILED],
    )

    for run in complete_without_timestamp:
        result.checks_performed += 1
        violation = InvariantViolation(
            code='INV-F',
            requirement_id=f'flow-run-{run.id}',
            message=(
                f"Flow run {run.id} has status '{run.status}' but no "
                f"completed_at timestamp"
            ),
            severity='error',
            details={
                'flow_run_id': run.id,
                'flow_name': run.flow.name,
                'status': run.status,
            },
            fixable=False,
        )
        result.violations.append(violation)

    if not incomplete_with_timestamp and not complete_without_timestamp:
        result.checks_performed = VerificationFlowRun.objects.count()

    return result


def check_inv_g_claimed_has_agent() -> InvariantCheckResult:
    """Check INV-G: Claimed tasks have claimed_by set.

    ∀ task: task.status ∈ {CLAIMED, IN_PROGRESS} ⟹ task.claimed_by != NULL

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    orphan_tasks = AgentTask.objects.filter(
        status__in=[AgentTaskStatus.CLAIMED, AgentTaskStatus.IN_PROGRESS],
        claimed_by__isnull=True,
    )

    for task in orphan_tasks:
        result.checks_performed += 1
        violation = InvariantViolation(
            code='INV-G',
            requirement_id=task.external_id,
            message=(
                f"Task has status '{task.status}' but no claimed_by agent"
            ),
            severity='error',
            details={
                'task_status': task.status,
            },
            fixable=False,
        )
        result.violations.append(violation)

    if not orphan_tasks:
        result.checks_performed = AgentTask.objects.filter(
            status__in=[AgentTaskStatus.CLAIMED, AgentTaskStatus.IN_PROGRESS]
        ).count()

    return result


def check_inv_h_claimed_has_lease() -> InvariantCheckResult:
    """Check INV-H: CLAIMED status has lease_expires.

    ∀ task: task.status == CLAIMED ⟹ task.lease_expires != NULL

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    no_lease_tasks = AgentTask.objects.filter(
        status=AgentTaskStatus.CLAIMED,
        lease_expires__isnull=True,
    )

    for task in no_lease_tasks:
        result.checks_performed += 1
        violation = InvariantViolation(
            code='INV-H',
            requirement_id=task.external_id,
            message=(
                f"Task is CLAIMED but has no lease_expires timestamp"
            ),
            severity='error',
            details={
                'claimed_by': task.claimed_by.agent_id if task.claimed_by else None,
            },
            fixable=False,
        )
        result.violations.append(violation)

    if not no_lease_tasks:
        result.checks_performed = AgentTask.objects.filter(
            status=AgentTaskStatus.CLAIMED
        ).count()

    return result


def check_inv_i_nondraft_has_history() -> InvariantCheckResult:
    """Check INV-I: Non-draft tasks have history entry.

    ∀ task: task.status != DRAFT ⟹ |task.history| > 0

    Tasks should have at least one history entry once they leave DRAFT.

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    nondraft_tasks = AgentTask.objects.exclude(status=AgentTaskStatus.DRAFT)

    for task in nondraft_tasks:
        result.checks_performed += 1
        history_count = AgentTaskHistory.objects.filter(task=task).count()

        if history_count == 0:
            violation = InvariantViolation(
                code='INV-I',
                requirement_id=task.external_id,
                message=(
                    f"Task has status '{task.status}' but no history entries"
                ),
                severity='warning',
                details={
                    'task_status': task.status,
                },
                fixable=False,
            )
            result.violations.append(violation)

    return result


def check_inv_j_approved_has_review() -> InvariantCheckResult:
    """Check INV-J: Approved tasks have approved review.

    ∀ task: task.status ∈ {APPROVED, MERGED} ⟹
            ∃ review: review.task == task ∧ review.decision == APPROVED

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    approved_tasks = AgentTask.objects.filter(
        status__in=[AgentTaskStatus.APPROVED, AgentTaskStatus.MERGED]
    )

    for task in approved_tasks:
        result.checks_performed += 1
        has_approved_review = AgentTaskReview.objects.filter(
            task=task,
            decision=ReviewDecision.APPROVED,
        ).exists()

        if not has_approved_review:
            violation = InvariantViolation(
                code='INV-J',
                requirement_id=task.external_id,
                message=(
                    f"Task has status '{task.status}' but no approved review record"
                ),
                severity='error',
                details={
                    'task_status': task.status,
                },
                fixable=False,
            )
            result.violations.append(violation)

    return result


def check_inv_k_no_self_review() -> InvariantCheckResult:
    """Check INV-K: Reviewers can't review own work.

    ∀ review: review.task.claimed_by != review.reviewer

    Returns:
        InvariantCheckResult with any violations found.
    """
    result = InvariantCheckResult()

    reviews = AgentTaskReview.objects.select_related(
        'task__claimed_by', 'reviewer'
    ).all()

    for review in reviews:
        result.checks_performed += 1

        if (
            review.task.claimed_by
            and review.reviewer
            and review.task.claimed_by.agent_id == review.reviewer.agent_id
        ):
            violation = InvariantViolation(
                code='INV-K',
                requirement_id=review.task.external_id,
                message=(
                    f"Agent '{review.reviewer.agent_id}' reviewed their own work"
                ),
                severity='error',
                details={
                    'reviewer_id': review.reviewer.agent_id,
                    'review_id': review.id,
                    'decision': review.decision,
                },
                fixable=False,
            )
            result.violations.append(violation)

    return result


def check_all_invariants(
    latest_run: TestRun | None = None,
    fix: bool = False,
) -> InvariantCheckResult:
    """Run all invariant checks.

    Args:
        latest_run: TestRun to use for status computation.
        fix: If True, fix auto-fixable violations.

    Returns:
        Combined InvariantCheckResult from all checks.
    """
    combined = InvariantCheckResult()

    checks = [
        check_inv_a_status_consistency(latest_run, fix),
        check_inv_b_slo_override(fix),
        check_inv_d_link_uniqueness(),
        check_inv_e_review_flag(fix),
        check_inv_f_flow_completion(),
        check_inv_g_claimed_has_agent(),
        check_inv_h_claimed_has_lease(),
        check_inv_i_nondraft_has_history(),
        check_inv_j_approved_has_review(),
        check_inv_k_no_self_review(),
    ]

    for check_result in checks:
        combined.violations.extend(check_result.violations)
        combined.checks_performed += check_result.checks_performed
        combined.fixed_count += check_result.fixed_count

    return combined

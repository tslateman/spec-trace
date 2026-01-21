"""Verification status computation logic."""
from .models import Requirement


def compute_verification_status(requirement: Requirement, latest_run=None) -> str:
    """Compute verification status for a single requirement.

    Rules (from user decisions in CONTEXT.md):
    - All linked tests pass -> 'passing'
    - Any linked test fails/errors -> 'failing'
    - No linked tests -> 'untested'
    - All skipped counts as 'untested'

    Args:
        requirement: Requirement instance to compute status for.
        latest_run: Optional TestRun to filter results to. If provided,
            only tests from this run are considered.

    Returns:
        Status string: 'passing', 'failing', or 'untested'
    """
    linked_results = requirement.test_results.all()

    if latest_run:
        linked_results = linked_results.filter(test_run=latest_run)

    if not linked_results.exists():
        return 'untested'

    statuses = list(linked_results.values_list('status', flat=True))

    if 'failed' in statuses or 'error' in statuses:
        return 'failing'

    if all(s == 'passed' for s in statuses):
        return 'passing'

    # All skipped or mixed skipped/passed = untested
    return 'untested'


def update_all_verification_statuses(latest_run=None) -> dict:
    """Update verification_status for all requirements.

    Iterates through all requirements, computes their status based on
    linked test results, and updates the stored verification_status field.

    Args:
        latest_run: Optional TestRun to filter results to. If provided,
            only tests from this run are considered for status computation.

    Returns:
        Summary dict with counts by status:
        - passing: Number of requirements with passing status
        - failing: Number of requirements with failing status
        - untested: Number of requirements with untested status
    """
    counts = {'passing': 0, 'failing': 0, 'untested': 0}

    for req in Requirement.objects.all():
        new_status = compute_verification_status(req, latest_run)
        if req.verification_status != new_status:
            req.verification_status = new_status
            req.save(update_fields=['verification_status'])
        counts[new_status] += 1

    return counts

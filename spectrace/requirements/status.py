"""Verification status computation logic."""
from .models import (
    InAppValidationStatus,
    Requirement,
    SLOStatus,
    VerificationMethod,
)


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


def compute_inapp_validation_status(requirement: Requirement) -> str:
    """Compute in-app validation status for a requirement.

    Rules:
    - All linked validations succeed -> 'passing'
    - Any linked validation fails -> 'failing'
    - No linked validations or all not_run/unknown -> 'untested'

    Args:
        requirement: Requirement instance

    Returns:
        Status string: 'passing', 'failing', or 'untested'
    """
    validations = list(requirement.inapp_validations.all())

    if not validations:
        return 'untested'

    statuses = [v.status for v in validations]

    if InAppValidationStatus.FAILURE in statuses:
        return 'failing'

    if all(s == InAppValidationStatus.SUCCESS for s in statuses):
        return 'passing'

    # All not_run/unknown = untested
    return 'untested'


def compute_unified_verification_status(requirement: Requirement, latest_run=None) -> str:
    """Compute unified verification status based on verification_method.

    Logic:
    - 'test': use test results only
    - 'inapp': use in-app validation only
    - 'both': both must pass
    - 'unspecified': use whatever is available (test preferred, then inapp)

    SLOs are additive: if any linked SLO is breached, status becomes 'failing'.

    Args:
        requirement: Requirement instance
        latest_run: Optional TestRun to filter test results

    Returns:
        Status string: 'passing', 'failing', or 'untested'
    """
    method = requirement.verification_method

    # Compute individual statuses
    test_status = compute_verification_status(requirement, latest_run)
    inapp_status = compute_inapp_validation_status(requirement)

    # Determine base status based on verification method
    if method == VerificationMethod.TEST:
        base_status = test_status
    elif method == VerificationMethod.INAPP:
        base_status = inapp_status
    elif method == VerificationMethod.BOTH:
        # Both must pass
        if test_status == 'failing' or inapp_status == 'failing':
            base_status = 'failing'
        elif test_status == 'passing' and inapp_status == 'passing':
            base_status = 'passing'
        elif test_status == 'untested' and inapp_status == 'untested':
            base_status = 'untested'
        else:
            # One is passing, one is untested - partial verification
            base_status = 'untested'
    else:  # UNSPECIFIED
        # Use whatever is available - prefer tests, then inapp
        if test_status != 'untested':
            base_status = test_status
        elif inapp_status != 'untested':
            base_status = inapp_status
        else:
            base_status = 'untested'

    # Check SLO status - breached SLO overrides to failing
    if requirement.slo_status == SLOStatus.BREACHED:
        return 'failing'

    return base_status


def compute_slo_status(requirement: Requirement) -> str:
    """Compute SLO status for a requirement based on linked SLOs.

    Rules:
    - No linked SLOs -> 'not_linked'
    - Any SLO breached -> 'breached'
    - Any SLO at_risk -> 'at_risk'
    - All SLOs met -> 'met'

    Args:
        requirement: Requirement instance

    Returns:
        SLOStatus value
    """
    slos = requirement.slos.all()

    if not slos.exists():
        return SLOStatus.NOT_LINKED

    slo_statuses = list(slos.values_list('status', flat=True))

    if SLOStatus.BREACHED in slo_statuses:
        return SLOStatus.BREACHED

    if SLOStatus.AT_RISK in slo_statuses:
        return SLOStatus.AT_RISK

    if all(s == SLOStatus.MET for s in slo_statuses):
        return SLOStatus.MET

    # Mixed or unknown
    return SLOStatus.NOT_LINKED


def update_all_slo_statuses() -> dict:
    """Update slo_status for all requirements based on linked SLOs.

    Returns:
        Summary dict with counts by status
    """
    counts = {'met': 0, 'at_risk': 0, 'breached': 0, 'not_linked': 0}
    for req in Requirement.objects.all():
        new_status = compute_slo_status(req)
        if req.slo_status != new_status:
            req.slo_status = new_status
            req.save(update_fields=['slo_status'])
        counts[new_status] += 1
    return counts


def update_all_unified_statuses(latest_run=None) -> dict:
    """Update verification_status for all requirements using unified logic.

    This considers verification_method, test results, in-app validations,
    and SLO status to compute the final verification status.

    Args:
        latest_run: Optional TestRun to filter test results

    Returns:
        Summary dict with counts by status
    """
    counts = {'passing': 0, 'failing': 0, 'untested': 0}
    for req in Requirement.objects.all():
        new_status = compute_unified_verification_status(req, latest_run)
        if req.verification_status != new_status:
            req.verification_status = new_status
            req.save(update_fields=['verification_status'])
        counts[new_status] += 1
    return counts

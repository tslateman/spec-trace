"""Demo data setup for vendor coverage page."""
import logging
from datetime import timedelta

from django.utils import timezone

from requirements.models import (
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    InAppValidationStatus,
    Requirement,
)

logger = logging.getLogger(__name__)

# Demo vendor configurations
# pass_count is explicit to ensure exact expected pass rates
# For vendors with has_regression, pass_count should account for regression validation being FAIL
VENDOR_CONFIGS = [
    {
        "name": "Opera",
        "pass_count": 4,  # 4/5 = 80% (close to plan's 92%)
        "validation_count": 5,
        "feature_flags": {"use_new_auth": True, "batch_sync": True},
    },
    {
        "name": "Mews",
        "pass_count": 3,  # 3/4 = 75% (close to plan's 78%)
        "validation_count": 4,
        "feature_flags": {"use_new_auth": True},
    },
    {
        "name": "Ambiance",
        "pass_count": 3,  # 3/3 = 100%
        "validation_count": 3,
        "feature_flags": {},
    },
    {
        "name": "OpenKey",
        "pass_count": 3,  # Without regression adjustment; but regression on i=0 → fail
        "validation_count": 4,  # So: i=0 FAIL (regression), i=1,2 PASS, i=3 FAIL → 2/4 = 50%
        "feature_flags": {"legacy_mode": True},
        "has_regression": True,  # First validation: pass → fail regression
    },
]

DEMO_SOURCE_PREFIX = "demo://vendor"


def setup_vendor_demo(clear: bool = True) -> dict:
    """Set up demo data for vendor coverage.

    Creates InAppValidations for multiple vendors with varied
    pass rates, feature flags, and one regression scenario.

    Args:
        clear: If True, clears existing demo data first.

    Returns:
        {
            'vendors_created': int,
            'validations_created': int,
            'results_created': int,
            'runs_cleared': int,
        }
    """
    result = {
        "vendors_created": 0,
        "validations_created": 0,
        "results_created": 0,
        "runs_cleared": 0,
    }

    # Step 1: Clear existing demo data if requested
    if clear:
        old_runs = InAppValidationRun.objects.filter(source__startswith=DEMO_SOURCE_PREFIX)
        result["runs_cleared"] = old_runs.count()
        old_runs.delete()

        # Also clear demo validations
        InAppValidation.objects.filter(endpoint__startswith=DEMO_SOURCE_PREFIX).delete()

    # Step 2: Get existing requirements or create minimal set
    requirements = list(Requirement.objects.all()[:12])

    if not requirements:
        logger.warning("No requirements found; creating minimal demo requirements")
        for i in range(12):
            req, _ = Requirement.objects.get_or_create(
                external_id=f"DEMO-REQ-{i+1:03d}",
                defaults={
                    "title": f"Demo Requirement {i+1}",
                    "description": f"Demo requirement for vendor coverage testing",
                },
            )
            requirements.append(req)

    # Step 3: Create two validation runs (older and newer)
    now = timezone.now()
    older_run = InAppValidationRun.objects.create(
        source=f"{DEMO_SOURCE_PREFIX}/run-1",
        imported_at=now - timedelta(days=2),
    )
    # Manually set imported_at since auto_now_add ignores our value
    InAppValidationRun.objects.filter(pk=older_run.pk).update(
        imported_at=now - timedelta(days=2)
    )
    older_run.refresh_from_db()

    newer_run = InAppValidationRun.objects.create(
        source=f"{DEMO_SOURCE_PREFIX}/run-2",
    )

    # Step 4: Create validations and results for each vendor
    req_index = 0
    vendors_created = set()

    for vendor_config in VENDOR_CONFIGS:
        vendor_name = vendor_config["name"]
        validation_count = vendor_config["validation_count"]
        pass_count = vendor_config["pass_count"]
        feature_flags = vendor_config["feature_flags"]
        has_regression = vendor_config.get("has_regression", False)

        for i in range(validation_count):
            if req_index >= len(requirements):
                req_index = 0  # Cycle through requirements if needed

            req = requirements[req_index]
            req_index += 1

            # Create validation
            validation = InAppValidation.objects.create(
                requirement=req,
                name=f"{vendor_name} - Validation {i+1}",
                endpoint=f"{DEMO_SOURCE_PREFIX}/{vendor_name.lower()}/v{i+1}",
                vendor=vendor_name,
                feature_flags=feature_flags,
            )
            result["validations_created"] += 1

            # Determine status for this validation
            should_pass = i < pass_count

            # Handle regression case: first validation for OpenKey passes in run 1, fails in run 2
            if has_regression and i == 0:
                # Run 1: SUCCESS
                InAppValidationResult.objects.create(
                    validation_run=older_run,
                    validation=validation,
                    status=InAppValidationStatus.SUCCESS,
                    message="Validation passed",
                    checked_at=older_run.imported_at + timedelta(minutes=i),
                    steps=[
                        {"name": "Connect", "passed": True},
                        {"name": "Verify", "passed": True},
                    ],
                )
                # Run 2: FAILURE (regression)
                InAppValidationResult.objects.create(
                    validation_run=newer_run,
                    validation=validation,
                    status=InAppValidationStatus.FAILURE,
                    message="Connection timeout - regression detected",
                    checked_at=newer_run.imported_at + timedelta(minutes=i),
                    steps=[
                        {"name": "Connect", "passed": False, "error": "Timeout after 30s"},
                        {"name": "Verify", "passed": False, "skipped": True},
                    ],
                )
                result["results_created"] += 2
            else:
                # Normal case: same status in both runs
                status = InAppValidationStatus.SUCCESS if should_pass else InAppValidationStatus.FAILURE
                message = "Validation passed" if should_pass else "Assertion failed"

                for run in [older_run, newer_run]:
                    InAppValidationResult.objects.create(
                        validation_run=run,
                        validation=validation,
                        status=status,
                        message=message,
                        checked_at=run.imported_at + timedelta(minutes=i),
                        steps=[
                            {"name": "Connect", "passed": True},
                            {"name": "Verify", "passed": should_pass},
                        ],
                    )
                    result["results_created"] += 1

        vendors_created.add(vendor_name)

    result["vendors_created"] = len(vendors_created)
    return result

"""API endpoints for external systems to push status updates."""
import json
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import (
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    InAppValidationStatus,
    Requirement,
    SLO,
    SLOStatus,
)
from .status import update_all_slo_statuses, update_all_unified_statuses


@csrf_exempt
@require_http_methods(["POST"])
def update_slo_status(request):
    """Update SLO status from observability platform.

    POST /api/slo/status/

    Request body:
    {
        "slos": [
            {
                "name": "api-availability",
                "status": "met",  // met, at_risk, breached
                "current_value": 0.9995,
                "error_budget_remaining": 0.75
            },
            ...
        ]
    }

    Response:
    {
        "success": true,
        "updated": 5,
        "not_found": 1,
        "requirement_status": {
            "met": 10,
            "at_risk": 2,
            "breached": 1,
            "not_linked": 50
        }
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    slos_data = data.get('slos', [])
    if not slos_data:
        return JsonResponse({'success': False, 'error': 'No SLOs in request'}, status=400)

    updated = 0
    not_found = 0

    status_map = {
        'met': SLOStatus.MET,
        'at_risk': SLOStatus.AT_RISK,
        'breached': SLOStatus.BREACHED,
    }

    for slo_data in slos_data:
        name = slo_data.get('name')
        if not name:
            continue

        try:
            slo = SLO.objects.get(name=name)
        except SLO.DoesNotExist:
            not_found += 1
            continue

        # Map status
        status_str = slo_data.get('status', 'unknown').lower()
        slo.status = status_map.get(status_str, SLOStatus.NOT_LINKED)

        # Update values
        current_value = slo_data.get('current_value')
        if current_value is not None:
            try:
                slo.current_value = Decimal(str(current_value))
            except (InvalidOperation, ValueError):
                pass

        error_budget = slo_data.get('error_budget_remaining')
        if error_budget is not None:
            try:
                slo.error_budget_remaining = Decimal(str(error_budget))
            except (InvalidOperation, ValueError):
                pass

        slo.last_updated = timezone.now()
        slo.save()
        updated += 1

    # Update requirement SLO statuses
    req_counts = update_all_slo_statuses()

    # Optionally update unified verification status
    if data.get('update_verification_status', False):
        update_all_unified_statuses()

    return JsonResponse({
        'success': True,
        'updated': updated,
        'not_found': not_found,
        'requirement_status': req_counts,
    })


@csrf_exempt
@require_http_methods(["POST"])
def submit_validation_result(request):
    """Submit in-app validation results from product.

    POST /api/validation/result/

    Request body:
    {
        "source": "production-app",
        "validations": [
            {
                "requirement_id": "REQ-AUTH-001",
                "name": "Verify Login Flow",
                "endpoint": "/api/auth/verify",
                "status": "success",  // success, failure, unknown
                "message": "All checks passed",
                "checked_at": "2024-01-15T10:30:00Z"  // optional
            },
            ...
        ]
    }

    Response:
    {
        "success": true,
        "imported": 5,
        "skipped": 1,
        "created_validations": 2
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    source = data.get('source', 'api')
    validations_data = data.get('validations', [])

    if not validations_data:
        return JsonResponse({'success': False, 'error': 'No validations in request'}, status=400)

    # Create validation run
    validation_run = InAppValidationRun.objects.create(
        source=source,
        total_validations=len(validations_data),
    )

    successful = 0
    failed = 0
    skipped = 0
    created_validations = 0

    for v in validations_data:
        requirement_id = v.get('requirement_id')
        if not requirement_id:
            skipped += 1
            continue

        try:
            requirement = Requirement.objects.get(external_id=requirement_id)
        except Requirement.DoesNotExist:
            skipped += 1
            continue

        # Get or create InAppValidation
        validation, created = InAppValidation.objects.get_or_create(
            requirement=requirement,
            name=v.get('name', f'Validation for {requirement_id}'),
            defaults={
                'endpoint': v.get('endpoint', ''),
            }
        )
        if created:
            created_validations += 1

        # Parse status
        status_str = v.get('status', 'unknown').lower()
        if status_str == 'success':
            status = InAppValidationStatus.SUCCESS
            successful += 1
        elif status_str == 'failure':
            status = InAppValidationStatus.FAILURE
            failed += 1
        else:
            status = InAppValidationStatus.UNKNOWN

        # Parse checked_at
        checked_at_str = v.get('checked_at')
        if checked_at_str:
            try:
                from django.utils.dateparse import parse_datetime
                checked_at = parse_datetime(checked_at_str)
                if checked_at is None:
                    checked_at = timezone.now()
            except (ValueError, TypeError):
                checked_at = timezone.now()
        else:
            checked_at = timezone.now()

        # Create result
        InAppValidationResult.objects.create(
            validation_run=validation_run,
            validation=validation,
            status=status,
            message=v.get('message', ''),
            checked_at=checked_at,
        )

        # Update validation status
        validation.status = status
        validation.last_checked = checked_at
        validation.message = v.get('message', '')
        validation.save()

    # Update run statistics
    validation_run.successful = successful
    validation_run.failed = failed
    validation_run.save()

    # Optionally update unified verification status
    if data.get('update_verification_status', False):
        update_all_unified_statuses()

    return JsonResponse({
        'success': True,
        'imported': len(validations_data) - skipped,
        'skipped': skipped,
        'created_validations': created_validations,
        'successful': successful,
        'failed': failed,
    })


@require_http_methods(["GET"])
def get_requirement_status(request, external_id):
    """Get verification status for a requirement.

    GET /api/requirement/{external_id}/status/

    Response:
    {
        "external_id": "REQ-AUTH-001",
        "title": "User Authentication",
        "verification_method": "both",
        "verification_status": "passing",
        "slo_status": "met",
        "test_status": "passing",
        "inapp_status": "passing",
        "linked_tests": 5,
        "linked_slos": 2,
        "linked_validations": 1
    }
    """
    try:
        requirement = Requirement.objects.get(external_id=external_id)
    except Requirement.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Requirement not found'}, status=404)

    # Count linked items
    test_count = requirement.test_results.count()
    slo_count = requirement.slos.count()
    validation_count = requirement.inapp_validations.count()

    # Compute individual statuses
    from .status import compute_inapp_validation_status, compute_verification_status
    test_status = compute_verification_status(requirement)
    inapp_status = compute_inapp_validation_status(requirement)

    return JsonResponse({
        'external_id': requirement.external_id,
        'title': requirement.title,
        'verification_method': requirement.verification_method,
        'verification_status': requirement.verification_status,
        'slo_status': requirement.slo_status,
        'test_status': test_status,
        'inapp_status': inapp_status,
        'linked_tests': test_count,
        'linked_slos': slo_count,
        'linked_validations': validation_count,
    })

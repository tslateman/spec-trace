"""API endpoints for external systems to push status updates."""
import json
from dataclasses import asdict
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .health import TestConnectionResult, verify_linear_connection
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


def parse_decimal_safe(value) -> Decimal | None:
    """Safely parse a value to Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


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
        current_value = parse_decimal_safe(slo_data.get('current_value'))
        if current_value is not None:
            slo.current_value = current_value

        error_budget = parse_decimal_safe(slo_data.get('error_budget_remaining'))
        if error_budget is not None:
            slo.error_budget_remaining = error_budget

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

        # Create result (status/last_checked/message are computed from latest result)
        InAppValidationResult.objects.create(
            validation_run=validation_run,
            validation=validation,
            status=status,
            message=v.get('message', ''),
            checked_at=checked_at,
        )

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


# Cache key and timeout for Linear health check results
LINEAR_HEALTH_CACHE_KEY = 'linear_connection_health'
LINEAR_HEALTH_CACHE_TIMEOUT = 60  # 1 minute cache to respect rate limits


def _compute_overall_status(result: TestConnectionResult) -> str:
    """Compute overall status from test connection result.

    Returns:
        'healthy' if all checks passed
        'degraded' if some checks passed
        'unhealthy' if all checks failed or error occurred
    """
    if result.success:
        return 'healthy'

    if result.checks:
        passed_count = sum(1 for c in result.checks if c.passed)
        if passed_count > 0:
            return 'degraded'

    return 'unhealthy'


def _result_to_dict(result: TestConnectionResult) -> dict:
    """Convert TestConnectionResult to JSON-serializable dict."""
    checks_data = None
    if result.checks:
        checks_data = [asdict(check) for check in result.checks]

    return {
        'success': result.success,
        'message': result.message,
        'status': _compute_overall_status(result),
        'checks': checks_data,
        'error_details': result.error_details,
    }


@csrf_exempt
@require_http_methods(["POST"])
def test_linear_connection(request):
    """Test Linear API connection with fresh health check.

    POST /api/integrations/linear/test-connection/

    Request body: (optional)
    {
        "api_key": "lin_api_...",   // Override settings
        "workspace": "my-workspace",
        "team": "my-team"
    }

    If no body provided, uses Django settings:
    - LINEAR_API_KEY
    - LINEAR_WORKSPACE
    - LINEAR_TEAM

    Response:
    {
        "success": true,
        "message": "All checks passed",
        "status": "healthy",  // healthy, degraded, unhealthy
        "checks": [
            {
                "name": "Configuration",
                "passed": true,
                "details": "API key present, workspace: ...",
                "error_message": null,
                "response_status": null,
                "response_body": null,
                "timestamp": "2024-01-15T10:30:00.000Z"
            },
            ...
        ],
        "error_details": null,
        "cached": false
    }
    """
    # Parse optional override from request body
    api_key = getattr(settings, 'LINEAR_API_KEY', '')
    workspace = getattr(settings, 'LINEAR_WORKSPACE', '')
    team = getattr(settings, 'LINEAR_TEAM', '')

    # Only try to parse JSON if content type indicates JSON and body is not empty
    content_type = request.content_type or ''
    if 'application/json' in content_type and request.body:
        try:
            data = json.loads(request.body)
            api_key = data.get('api_key', api_key)
            workspace = data.get('workspace', workspace)
            team = data.get('team', team)
        except json.JSONDecodeError:
            return JsonResponse(
                {'success': False, 'error': 'Invalid JSON'},
                status=400
            )

    # Run fresh health check
    result = verify_linear_connection(api_key, workspace, team)

    # Convert to JSON response
    response_data = _result_to_dict(result)
    response_data['cached'] = False

    # Cache the result
    cache.set(LINEAR_HEALTH_CACHE_KEY, response_data, LINEAR_HEALTH_CACHE_TIMEOUT)

    return JsonResponse(response_data)


@require_http_methods(["GET"])
def get_linear_health(request):
    """Get cached Linear integration health status.

    GET /api/integrations/linear/health/

    Returns cached health check result without triggering a new test.
    Use POST /api/integrations/linear/test-connection/ to refresh.

    Response:
    {
        "success": true,
        "message": "All checks passed",
        "status": "healthy",  // healthy, degraded, unhealthy
        "checks": [...],
        "error_details": null,
        "cached": true,
        "cache_remaining_seconds": 45
    }

    If no cached result exists:
    {
        "success": false,
        "message": "No cached health check available",
        "status": "unknown",
        "checks": null,
        "error_details": null,
        "cached": false
    }
    """
    cached_result = cache.get(LINEAR_HEALTH_CACHE_KEY)

    if cached_result:
        response_data = cached_result.copy()
        response_data['cached'] = True

        # Try to get TTL if cache backend supports it
        try:
            ttl = cache.ttl(LINEAR_HEALTH_CACHE_KEY)
            if ttl is not None:
                response_data['cache_remaining_seconds'] = ttl
        except AttributeError:
            # Cache backend doesn't support TTL query
            pass

        return JsonResponse(response_data)

    return JsonResponse({
        'success': False,
        'message': 'No cached health check available',
        'status': 'unknown',
        'checks': None,
        'error_details': None,
        'cached': False,
    })

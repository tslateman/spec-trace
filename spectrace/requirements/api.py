"""API endpoints for external systems to push status updates."""

import hmac
import logging
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from .constants import (
    LINEAR_HEALTH_CACHE_TIMEOUT,
    RATE_LIMIT_EXTERNAL,
    RATE_LIMIT_HEAVY_WRITE,
    RATE_LIMIT_READ,
    RATE_LIMIT_WRITE,
)
from .health import TestConnectionResult, verify_linear_connection

logger = logging.getLogger(__name__)


def require_api_key(view_func):
    """Decorator to require API key authentication for endpoints.

    Checks for API key in:
    1. Authorization header: "Bearer <key>" or "Api-Key <key>"
    2. X-API-Key header

    The expected key is configured via SPECTRACE_API_KEY in settings.
    If SPECTRACE_API_KEY is not set, authentication is bypassed (dev mode warning).
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        expected_key = getattr(settings, "SPECTRACE_API_KEY", None)

        # If no API key configured, allow request but log warning
        if not expected_key:
            logger.warning(
                "SPECTRACE_API_KEY not configured - API endpoint accessed without auth: %s",
                request.path,
            )
            return view_func(request, *args, **kwargs)

        # Extract API key from headers
        provided_key = None

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:]
        elif auth_header.startswith("Api-Key "):
            provided_key = auth_header[8:]

        # Check X-API-Key header as fallback
        if not provided_key:
            provided_key = request.headers.get("X-API-Key", "")

        # Validate key using constant-time comparison
        if not provided_key or not hmac.compare_digest(provided_key, expected_key):
            logger.warning(
                "API authentication failed for endpoint: %s from IP: %s",
                request.path,
                request.META.get("REMOTE_ADDR", "unknown"),
            )
            return JsonResponse(
                {
                    "error": "Authentication required."
                    " Provide API key via Authorization or X-API-Key header."
                },
                status=401,
            )

        return view_func(request, *args, **kwargs)

    return wrapper


from .models import (
    SLO,
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    InAppValidationStatus,
    Requirement,
    SLOStatus,
    TestRun,
)
from .openapi.decorators import validate_request
from .openapi.schemas import (
    LatestTestRunResponse,
    LinearHealthResponse,
    LinearTestRequest,
    LinearTestResponse,
    RunningFlowRunsResponse,
    SLOStatusRequest,
    SLOStatusResponse,
    ValidationResultRequest,
    ValidationResultResponse,
    ValidationRunDetailResponse,
    ValidationRunsResponse,
    ValidationRunStepsResponse,
)
from .status import (
    update_all_slo_statuses,
    update_all_unified_statuses,
)


def parse_decimal_safe(value) -> Decimal | None:
    """Safely parse a value to Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


@csrf_exempt
@require_api_key
@require_http_methods(["POST"])
@ratelimit(key="ip", rate=RATE_LIMIT_WRITE, block=True)
@validate_request(
    request_schema=SLOStatusRequest,
    response_schema=SLOStatusResponse,
    tags=["SLO"],
    summary="Update SLO status",
    methods=["POST"],
    requires_auth=True,
)
def update_slo_status(request, data: SLOStatusRequest | None = None):
    """Update SLO status from observability platform."""
    if data is None:
        return JsonResponse({"success": False, "error": "No data provided"}, status=400)

    if not data.slos:
        return JsonResponse({"success": False, "error": "No SLOs in request"}, status=400)

    updated = 0
    not_found = 0

    for slo_item in data.slos:
        if not slo_item.name:
            continue

        try:
            slo = SLO.objects.get(name=slo_item.name)
        except SLO.DoesNotExist:
            not_found += 1
            continue

        # Map status
        slo.status = SLOStatus.from_string(slo_item.status)

        # Update values
        if slo_item.current_value is not None:
            current_value = parse_decimal_safe(slo_item.current_value)
            if current_value is not None:
                slo.current_value = current_value

        if slo_item.error_budget_remaining is not None:
            error_budget = parse_decimal_safe(slo_item.error_budget_remaining)
            if error_budget is not None:
                slo.error_budget_remaining = error_budget

        slo.last_updated = timezone.now()
        slo.save()
        updated += 1

    # Update requirement SLO statuses
    req_counts = update_all_slo_statuses()

    # Optionally update unified verification status
    if data.update_verification_status:
        update_all_unified_statuses()

    return JsonResponse(
        {
            "success": True,
            "updated": updated,
            "not_found": not_found,
            "requirement_status": req_counts,
        }
    )


@csrf_exempt
@require_api_key
@require_http_methods(["POST"])
@ratelimit(key="ip", rate=RATE_LIMIT_HEAVY_WRITE, block=True)
@validate_request(
    request_schema=ValidationResultRequest,
    response_schema=ValidationResultResponse,
    tags=["Verification"],
    summary="Submit verification results",
    methods=["POST"],
    requires_auth=True,
)
def submit_validation_result(request, data: ValidationResultRequest | None = None):
    """Submit in-app validation results from product."""
    if data is None:
        return JsonResponse({"success": False, "error": "No data provided"}, status=400)

    if not data.validations:
        return JsonResponse({"success": False, "error": "No validations in request"}, status=400)

    # Create verification run
    validation_run = InAppValidationRun.objects.create(
        source=data.source,
    )

    successful = 0
    failed = 0
    skipped = 0
    created_validations = 0

    for v in data.validations:
        if not v.requirement_id:
            skipped += 1
            continue

        try:
            requirement = Requirement.objects.get(external_id=v.requirement_id)
        except Requirement.DoesNotExist:
            skipped += 1
            continue

        # Extract context data - context is a flexible dict
        context_dict = v.context or {}
        vendor = context_dict.get("vendor", "")
        feature_flags = context_dict.get("feature_flags", {}) or {}

        # Get or create InAppValidation (lookup by requirement only to avoid duplicates)
        validation, created = InAppValidation.objects.get_or_create(
            requirement=requirement,
            defaults={
                "name": v.name or f"Validation for {v.requirement_id}",
                "endpoint": v.endpoint,
                "vendor": vendor,
                "feature_flags": feature_flags,
            },
        )
        if created:
            created_validations += 1
        else:
            # Update name, vendor, and feature_flags if provided
            if v.name:
                validation.name = v.name
            if vendor:
                validation.vendor = vendor
            if feature_flags:
                validation.feature_flags = feature_flags
            validation.save()

        # Parse status
        status_str = v.status.lower()
        if status_str == "success":
            status = InAppValidationStatus.SUCCESS
            successful += 1
        elif status_str == "failure":
            status = InAppValidationStatus.FAILURE
            failed += 1
        elif status_str == "degraded":
            # SDK sends 'degraded' for partial failures
            status = InAppValidationStatus.FAILURE
            failed += 1
        else:
            status = InAppValidationStatus.UNKNOWN

        # Parse checked_at
        checked_at = parse_datetime(v.checked_at) if v.checked_at else None
        if checked_at is None:
            checked_at = timezone.now()

        # Convert steps to dict format
        steps_data = [
            {
                "name": step.name,
                "passed": step.passed,
                "details": step.details,
                "error_message": step.error_message,
                "duration_ms": step.duration_ms,
            }
            for step in v.steps
        ]

        # Create result with steps and context
        InAppValidationResult.objects.create(
            validation_run=validation_run,
            validation=validation,
            status=status,
            message=v.message,
            checked_at=checked_at,
            steps=steps_data,
            context=context_dict,
        )

    # Optionally update unified verification status
    if data.update_verification_status:
        update_all_unified_statuses()

    return JsonResponse(
        {
            "success": True,
            "imported": len(data.validations) - skipped,
            "skipped": skipped,
            "created_validations": created_validations,
            "successful": successful,
            "failed": failed,
        }
    )


# Cache key for Linear health check results
LINEAR_HEALTH_CACHE_KEY = "linear_connection_health"


def _compute_overall_status(result: TestConnectionResult) -> str:
    """Compute overall status from test connection result.

    Returns:
        'healthy' if all checks passed
        'degraded' if some checks passed
        'unhealthy' if all checks failed or error occurred
    """
    if result.success:
        return "healthy"

    if result.checks:
        passed_count = sum(1 for c in result.checks if c.passed)
        if passed_count > 0:
            return "degraded"

    return "unhealthy"


def _result_to_dict(result: TestConnectionResult) -> dict:
    """Convert TestConnectionResult to JSON-serializable dict."""
    checks_data = None
    if result.checks:
        checks_data = [asdict(check) for check in result.checks]

    return {
        "success": result.success,
        "message": result.message,
        "status": _compute_overall_status(result),
        "checks": checks_data,
        "error_details": result.error_details,
    }


@csrf_exempt
@require_api_key
@require_http_methods(["POST"])
@ratelimit(key="ip", rate=RATE_LIMIT_EXTERNAL, block=True)
@validate_request(
    request_schema=LinearTestRequest,
    response_schema=LinearTestResponse,
    tags=["Integrations"],
    summary="Test Linear connection",
    methods=["POST"],
    requires_auth=True,
)
def test_linear_connection(request, data: LinearTestRequest | None = None):
    """Test Linear API connection with fresh health check.

    Note: Credential override from request body is disabled for security.
    Configure credentials via settings (LINEAR_API_KEY, LINEAR_WORKSPACE, LINEAR_TEAM).
    """
    # Use only configured credentials - no override from request to prevent
    # credential enumeration attacks
    api_key = getattr(settings, "LINEAR_API_KEY", "")
    workspace = getattr(settings, "LINEAR_WORKSPACE", "")
    team = getattr(settings, "LINEAR_TEAM", "")

    # Run fresh health check
    result = verify_linear_connection(api_key, workspace, team)

    # Convert to JSON response
    response_data = _result_to_dict(result)
    response_data["cached"] = False

    # Cache the result
    cache.set(LINEAR_HEALTH_CACHE_KEY, response_data, LINEAR_HEALTH_CACHE_TIMEOUT)

    return JsonResponse(response_data)


@require_api_key
@require_http_methods(["GET"])
@ratelimit(key="ip", rate=RATE_LIMIT_READ, block=True)
@validate_request(
    requires_auth=True,
    response_schema=ValidationRunsResponse,
    tags=["Verification Runs"],
    summary="List verification runs",
    methods=["GET"],
    query_parameters=[
        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
        {
            "name": "per_page",
            "in": "query",
            "schema": {"type": "integer", "default": 20, "maximum": 100},
        },
        {"name": "requirement_id", "in": "query", "schema": {"type": "string"}},
        {"name": "vendor", "in": "query", "schema": {"type": "string"}},
        {
            "name": "status",
            "in": "query",
            "schema": {"type": "string", "enum": ["pass", "fail", "error", "skip"]},
        },
        {
            "name": "start_date",
            "in": "query",
            "schema": {"type": "string", "format": "date"},
        },
        {
            "name": "end_date",
            "in": "query",
            "schema": {"type": "string", "format": "date"},
        },
    ],
)
def list_validation_runs(request, data=None):
    """List verification runs with filtering and pagination."""
    # Parse pagination
    page = int(request.GET.get("page", 1))
    per_page = min(int(request.GET.get("per_page", 20)), 100)

    # Build queryset with filters
    queryset = InAppValidationRun.objects.prefetch_related("results__validation__requirement")

    # Filter by requirement_id
    requirement_id = request.GET.get("requirement_id")
    if requirement_id:
        queryset = queryset.filter(
            results__validation__requirement__external_id=requirement_id
        ).distinct()

    # Filter by vendor
    vendor = request.GET.get("vendor")
    if vendor:
        queryset = queryset.filter(results__validation__vendor=vendor).distinct()

    # Filter by status
    status = request.GET.get("status")
    if status:
        queryset = queryset.filter(results__status=status).distinct()

    # Filter by date range
    start_date = request.GET.get("start_date")
    if start_date:
        parsed_start = parse_datetime(start_date)
        if parsed_start:
            queryset = queryset.filter(imported_at__gte=parsed_start)

    end_date = request.GET.get("end_date")
    if end_date:
        parsed_end = parse_datetime(end_date)
        if parsed_end:
            queryset = queryset.filter(imported_at__lte=parsed_end)

    # Order by newest first
    queryset = queryset.order_by("-imported_at")

    # Paginate
    total = queryset.count()
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    offset = (page - 1) * per_page
    runs = queryset[offset : offset + per_page]

    # Serialize
    runs_data = []
    for run in runs:
        runs_data.append(
            {
                "id": run.id,
                "source": run.source,
                "imported_at": run.imported_at.isoformat(),
                "total_validations": run.total_validations,
                "successful": run.successful,
                "failed": run.failed,
            }
        )

    return JsonResponse(
        {
            "runs": runs_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }
    )


@require_api_key
@require_http_methods(["GET"])
@ratelimit(key="ip", rate=RATE_LIMIT_READ, block=True)
@validate_request(
    requires_auth=True,
    response_schema=ValidationRunDetailResponse,
    tags=["Verification Runs"],
    summary="Get verification run detail",
    methods=["GET"],
)
def get_validation_run(request, run_id, data=None):
    """Get verification run detail with all results."""
    try:
        run = InAppValidationRun.objects.prefetch_related("results__validation__requirement").get(
            id=run_id
        )
    except InAppValidationRun.DoesNotExist:
        return JsonResponse({"error": "Verification run not found"}, status=404)

    results_data = []
    for result in run.results.all():
        steps = result.steps or []
        results_data.append(
            {
                "id": result.id,
                "validation_id": result.validation.id,
                "validation_name": result.validation.name,
                "requirement_id": result.validation.requirement.external_id,
                "vendor": result.validation.vendor,
                "status": result.status,
                "message": result.message,
                "checked_at": result.checked_at.isoformat(),
                "step_count": len(steps),
                "steps_passed": sum(1 for s in steps if s.get("passed")),
            }
        )

    return JsonResponse(
        {
            "id": run.id,
            "source": run.source,
            "imported_at": run.imported_at.isoformat(),
            "total_validations": run.total_validations,
            "successful": run.successful,
            "failed": run.failed,
            "results": results_data,
        }
    )


@require_api_key
@require_http_methods(["GET"])
@ratelimit(key="ip", rate=RATE_LIMIT_READ, block=True)
@validate_request(
    requires_auth=True,
    response_schema=ValidationRunStepsResponse,
    tags=["Verification Runs"],
    summary="Get verification run steps",
    methods=["GET"],
    query_parameters=[
        {
            "name": "result_id",
            "in": "query",
            "schema": {"type": "integer"},
            "description": "Filter steps by validation result",
        },
    ],
)
def get_validation_run_steps(request, run_id, data=None):
    """Get step-level detail for a verification run."""
    try:
        run = InAppValidationRun.objects.prefetch_related("results__validation__requirement").get(
            id=run_id
        )
    except InAppValidationRun.DoesNotExist:
        return JsonResponse({"error": "Verification run not found"}, status=404)

    # Optional filter to specific result
    result_id = request.GET.get("result_id")
    results = run.results.all()
    if result_id:
        results = results.filter(id=result_id)

    results_data = []
    for result in results:
        results_data.append(
            {
                "result_id": result.id,
                "validation_name": result.validation.name,
                "requirement_id": result.validation.requirement.external_id,
                "status": result.status,
                "steps": result.steps or [],
                "context": result.context or {},
            }
        )

    return JsonResponse(
        {
            "run_id": run.id,
            "results": results_data,
        }
    )


@require_api_key
@require_http_methods(["GET"])
@ratelimit(key="ip", rate=RATE_LIMIT_READ, block=True)
@validate_request(
    requires_auth=True,
    response_schema=RunningFlowRunsResponse,
    tags=["Flows"],
    summary="Get running flow runs",
    methods=["GET"],
)
def get_running_flow_runs(request, data=None):
    """Get currently running flow runs for live monitoring."""
    from .models import VerificationFlowRun, VerificationFlowStatus

    runs = (
        VerificationFlowRun.objects.filter(status=VerificationFlowStatus.RUNNING)
        .select_related("flow")
        .prefetch_related("steps")
        .order_by("-started_at")
    )

    runs_data = []
    for run in runs:
        steps = list(run.steps.order_by("step_order"))
        completed_steps = [s for s in steps if s.completed_at]
        current_step = next((s for s in steps if not s.completed_at), None)

        runs_data.append(
            {
                "id": run.id,
                "flow_name": run.flow.name,
                "flow_display_name": run.flow.display_name,
                "started_at": run.started_at.isoformat(),
                "total_steps": len(steps),
                "completed_steps": len(completed_steps),
                "current_step": current_step.name if current_step else None,
                "current_step_order": current_step.step_order if current_step else None,
            }
        )

    return JsonResponse({"runs": runs_data})


@require_api_key
@require_http_methods(["GET"])
@ratelimit(key="ip", rate=RATE_LIMIT_READ, block=True)
@validate_request(
    requires_auth=True,
    response_schema=LinearHealthResponse,
    tags=["Integrations"],
    summary="Get Linear health status",
    methods=["GET"],
)
def get_linear_health(request, data=None):
    """Get cached Linear integration health status."""
    cached_result = cache.get(LINEAR_HEALTH_CACHE_KEY)

    if cached_result:
        response_data = cached_result.copy()
        response_data["cached"] = True

        # Try to get TTL if cache backend supports it
        try:
            ttl = cache.ttl(LINEAR_HEALTH_CACHE_KEY)
            if ttl is not None:
                response_data["cache_remaining_seconds"] = ttl
        except AttributeError:
            # Cache backend doesn't support TTL query
            pass

        return JsonResponse(response_data)

    return JsonResponse(
        {
            "success": False,
            "message": "No cached health check available",
            "status": "unknown",
            "checks": None,
            "error_details": None,
            "cached": False,
        }
    )


@require_api_key
@require_http_methods(["GET"])
@ratelimit(key="ip", rate=RATE_LIMIT_READ, block=True)
@validate_request(
    requires_auth=True,
    response_schema=LatestTestRunResponse,
    tags=["Test Runs"],
    summary="Get latest test run",
    methods=["GET"],
    query_parameters=[
        {
            "name": "since",
            "in": "query",
            "schema": {"type": "string", "format": "date-time"},
            "description": "Only return run newer than this timestamp",
        },
        {
            "name": "repo",
            "in": "query",
            "schema": {"type": "string"},
            "description": "Filter by repository (e.g., owner/repo)",
        },
    ],
)
def get_latest_test_run(request, data=None):
    """Get the latest test run for dashboard polling.

    Returns summary of the most recent test run, used by dashboard
    to check for new CI/CD imports without full page refresh.

    Query Parameters:
        since: ISO datetime - only return run if newer than this timestamp
        repo: Filter by repository (e.g., 'owner/repo')

    Returns:
        200 with test run data if new run exists
        204 if no new run since 'since' timestamp
        200 with null data if no runs exist
    """
    since = request.GET.get("since")
    repo = request.GET.get("repo")

    queryset = TestRun.objects.all()

    if repo:
        queryset = queryset.filter(repository=repo)

    if since:
        try:
            since_dt = timezone.datetime.fromisoformat(since.replace("Z", "+00:00"))
            queryset = queryset.filter(imported_at__gt=since_dt)
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid since parameter"}, status=400)

    latest = queryset.order_by("-imported_at").first()

    if not latest:
        if since:
            # No new runs since the timestamp - return 204
            return JsonResponse({}, status=204)
        return JsonResponse({"test_run": None})

    return JsonResponse(
        {
            "test_run": {
                "id": latest.id,
                "imported_at": latest.imported_at.isoformat(),
                "source_file": latest.source_file,
                "git_sha": latest.git_sha,
                "git_branch": latest.git_branch,
                "workflow_name": latest.workflow_name,
                "workflow_run_id": latest.workflow_run_id,
                "repository": latest.repository,
                "total_tests": latest.total_tests,
                "passed": latest.passed,
                "failed": latest.failed,
                "errors": latest.errors,
                "skipped": latest.skipped,
            }
        }
    )

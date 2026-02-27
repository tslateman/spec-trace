import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

from requirements.models import AgentTask, AgentTaskStatus, TestRequirementLink
from requirements.services.agent_tasks import claim_task, submit_for_review, TransitionError

logger = logging.getLogger(__name__)


def _error_response(message, code="bad_request", status=400, details=None):
    error_payload = {
        "code": code,
        "message": message,
    }
    if details:
        error_payload["details"] = details
    return JsonResponse({"error": error_payload}, status=status)


def _success_response(data, meta=None, status=200):
    response_data = {"data": data}
    if meta:
        response_data["meta"] = meta
    return JsonResponse(response_data, status=status)


@require_http_methods(["GET"])
def list_tasks(request):
    try:
        limit = int(request.GET.get("limit", 50))
        limit = min(limit, 100)
    except ValueError:
        return _error_response("Invalid limit parameter", "invalid_query_param")

    try:
        offset = int(request.GET.get("offset", 0))
    except ValueError:
        return _error_response("Invalid offset parameter", "invalid_query_param")

    status_filter = request.GET.get("status")
    sort = request.GET.get("sort", "-created_at")

    queryset = AgentTask.objects.select_related("claimed_by", "sprint")

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    sort_fields = sort.split(",")
    # validate sort fields to prevent errors
    valid_sort_fields = []
    for f in sort_fields:
        clean_f = f.lstrip("-")
        if hasattr(AgentTask, clean_f):
            valid_sort_fields.append(f)

    if valid_sort_fields:
        queryset = queryset.order_by(*valid_sort_fields)

    total = queryset.count()
    tasks = queryset[offset : offset + limit]

    data = []
    for task in tasks:
        data.append(
            {
                "id": task.external_id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "claimed_by": task.claimed_by.agent_id if task.claimed_by else None,
                "sprint": task.sprint.name if task.sprint else None,
                "lease_expires": task.lease_expires.isoformat() if task.lease_expires else None,
                "attempt_count": task.attempt_count,
                "created_at": task.created_at.isoformat(),
            }
        )

    meta = {"limit": limit, "offset": offset, "total": total}
    return _success_response(data, meta=meta)


@csrf_exempt
@require_http_methods(["POST"])
def claim_task_view(request, task_id):
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return _error_response("Invalid JSON body", "invalid_json")

    agent_id = body.get("agent_id")
    if not agent_id:
        return _error_response("agent_id is required", "missing_field")

    lease_minutes = body.get("lease_minutes", 30)

    try:
        result = claim_task(task_id, agent_id, lease_minutes)
        return _success_response(result.to_dict())
    except TransitionError as e:
        return _error_response(str(e), code=e.code)
    except Exception as e:
        logger.exception("Error claiming task")
        return _error_response("Internal server error", "internal_error", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def complete_task_view(request, task_id):
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return _error_response("Invalid JSON body", "invalid_json")

    agent_id = body.get("agent_id")
    commit_sha = body.get("commit_sha")

    if not agent_id or not commit_sha:
        return _error_response("agent_id and commit_sha are required", "missing_field")

    try:
        result = submit_for_review(task_id, agent_id, commit_sha)
        return _success_response(result.to_dict())
    except TransitionError as e:
        return _error_response(str(e), code=e.code)
    except Exception as e:
        logger.exception("Error completing task")
        return _error_response("Internal server error", "internal_error", status=500)


@require_http_methods(["GET"])
def spec_context_view(request, external_id):
    from requirements.models import Requirement, TestRequirementLink

    # Retrieve the Requirement for context
    try:
        req = Requirement.objects.get(external_id=external_id)
    except Requirement.DoesNotExist:
        return _error_response(f"Spec not found for {external_id}", "not_found", status=404)

    test_links = TestRequirementLink.objects.filter(requirement=req).order_by("test_nodeid")
    depends_on = list(req.depends_on.values_list("external_id", flat=True).order_by("external_id"))
    depended_by = list(
        req.depended_by.values_list("external_id", flat=True).order_by("external_id")
    )

    fret = {}
    for field in ("scope", "condition", "component", "timing", "response"):
        value = getattr(req, field, "")
        if value:
            fret[field] = value

    context = {
        "external_id": req.external_id,
        "title": req.title,
        "description": req.description,
        "tags": req.tags,
        "status": req.status,
        "verification_status": req.verification_status,
        "priority": req.priority,
        "test_results": [
            {"test_nodeid": link.test_nodeid, "last_status": link.last_status}
            for link in test_links
        ],
        "depends_on": depends_on,
        "depended_by": depended_by,
    }

    if fret:
        context["fret"] = fret

    return _success_response(context)

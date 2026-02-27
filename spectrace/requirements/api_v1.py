import json
import logging
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.db.models import Count, Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError

from requirements.models import AgentTask, AgentTaskStatus, Requirement, TestRequirementLink
from requirements.services.agent_tasks import claim_task, submit_for_review, TransitionError
from requirements.validator import detect_all_drift, detect_spec_drift, detect_stale_links

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


@require_http_methods(["GET"])
def specs_coverage_view(request):
    """Returns coverage metrics and lists of stale requirements."""
    metrics = Requirement.objects.aggregate(
        total=Count("id"),
        non_draft=Count("id", filter=~Q(status="draft")),
        passing=Count("id", filter=Q(verification_status="passing")),
        failing=Count("id", filter=Q(verification_status="failing")),
        untested=Count("id", filter=Q(verification_status="untested")),
    )

    stale_req_ids = set()

    # 1. Stale links (tests missing from latest run)
    stale_result = detect_stale_links()
    for error in stale_result.errors:
        if error.type == "stale_link":
            stale_req_ids.add(error.details.get("requirement_id"))

    # 2. Spec drift (spec modified after latest run)
    specs_dir = Path(settings.BASE_DIR).parent / "specs"
    if specs_dir.exists():
        drift_result = detect_spec_drift(specs_dir)
        for warning in drift_result.warnings:
            if warning.type == "spec_drift":
                affected = warning.details.get("affected_requirements", [])
                stale_req_ids.update(affected)

    data = {
        "metrics": {
            "total": metrics["total"],
            "non_draft": metrics["non_draft"],
            "passing": metrics["passing"],
            "failing": metrics["failing"],
            "untested": metrics["untested"],
            "stale": len(stale_req_ids),
        },
        "stale_requirements": sorted(list(stale_req_ids)),
    }

    return _success_response(data)


@require_http_methods(["GET"])
def specs_drift_view(request):
    """Returns actionable drift detections."""
    specs_path_param = request.GET.get("specs_dir")
    tests_path_param = request.GET.get("tests_dir")

    project_root = Path(settings.BASE_DIR).parent

    if specs_path_param:
        specs_dir = Path(specs_path_param)
    else:
        specs_dir = project_root / "specs"

    if tests_path_param:
        tests_dir = Path(tests_path_param)
    else:
        # Default to checking root for tests, detect_unmarked_tests recursively searches
        tests_dir = project_root

    result = detect_all_drift(
        test_directory=tests_dir if tests_dir.exists() else None,
        specs_directory=specs_dir if specs_dir.exists() else None,
    )

    return _success_response(result.to_dict())

@require_http_methods(["GET"])
def specs_impact_view(request):
    """Return a dependency graph of affected specs."""
    spec_id = request.GET.get("spec_id")
    file_path = request.GET.get("file_path")
    
    from requirements.services.impact_analyzer import ImpactAnalyzer, ImpactResult
    
    analyzer = ImpactAnalyzer()
    req_ids = []
    
    if spec_id:
        req_ids = [spec_id]
    elif file_path:
        req_ids = analyzer.extract_requirement_ids([file_path], "HEAD")
    else:
        return _error_response("Must provide spec_id or file_path", "invalid_query_param")
    
    if not req_ids:
        return _error_response("No requirements found", "not_found", status=404)
        
    tests, hierarchy, dependencies = analyzer.get_affected_tests(
        req_ids, include_hierarchy=True, include_dependents=True
    )
    
    result = ImpactResult(
        changed_requirements=req_ids,
        affected_tests=tests,
        hierarchy_expansion=hierarchy,
        dependency_expansion=dependencies,
    )
    result.risk_score, result.risk_level = analyzer.compute_risk(result)
    
    return _success_response({
        "changed_requirements": result.changed_requirements,
        "affected_tests": result.affected_tests,
        "hierarchy_expansion": result.hierarchy_expansion,
        "dependency_expansion": result.dependency_expansion,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
    })


@require_http_methods(["GET"])
def list_conflicts_view(request):
    """List conflicts with filtering and pagination."""
    from requirements.models import ConflictLog, ConflictConfidence

    try:
        limit = int(request.GET.get("limit", 25))
        limit = min(limit, 100)
    except ValueError:
        return _error_response("Invalid limit parameter", "invalid_query_param")

    try:
        offset = int(request.GET.get("offset", 0))
    except ValueError:
        return _error_response("Invalid offset parameter", "invalid_query_param")

    queryset = ConflictLog.objects.select_related("requirement_a", "requirement_b")

    confidence = request.GET.get("confidence")
    if confidence and confidence in ConflictConfidence.values:
        queryset = queryset.filter(confidence=confidence)

    pattern = request.GET.get("pattern")
    if pattern:
        queryset = queryset.filter(pattern=pattern)

    resolved = request.GET.get("resolved")
    if resolved is not None and resolved != "":
        queryset = queryset.filter(resolved=resolved.lower() == "true")

    requirement_id = request.GET.get("requirement_id")
    if requirement_id:
        from django.db.models import Q
        queryset = queryset.filter(
            Q(requirement_a__external_id=requirement_id)
            | Q(requirement_b__external_id=requirement_id)
        )

    queryset = queryset.order_by("-created_at")

    total = queryset.count()
    conflicts = queryset[offset : offset + limit]

    data = []
    for c in conflicts:
        data.append(
            {
                "id": c.id,
                "requirement_a": c.requirement_a.external_id,
                "requirement_b": c.requirement_b.external_id,
                "pattern": c.pattern,
                "confidence": c.confidence,
                "resolved": c.resolved,
                "created_at": c.created_at.isoformat(),
            }
        )

    meta = {"limit": limit, "offset": offset, "total": total}
    return _success_response(data, meta=meta)


@csrf_exempt
@require_http_methods(["POST"])
def detect_conflicts_view(request):
    """Run conflict detection and log results."""
    from requirements.services.conflict_detector import ConflictDetector

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return _error_response("Invalid JSON body", "invalid_json")

    min_runs = body.get("min_runs", 10)
    min_overlap = body.get("min_overlap", 5)
    include_structured = body.get("include_structured", True)

    detector = ConflictDetector(min_runs=min_runs, min_overlap=min_overlap)

    conflicts = detector.detect_mutual_exclusion()

    if include_structured:
        conflicts.extend(detector.detect_all_structured_conflicts())

    result = detector.log_conflicts(conflicts)

    return _success_response({
        "conflicts_found": len(conflicts),
        "logged": result["created_count"],
        "skipped_existing": result["skipped_count"],
    })


@require_http_methods(["GET"])
def get_conflict_view(request, conflict_id):
    """Get full detail for a single conflict."""
    from requirements.models import ConflictLog

    try:
        conflict = ConflictLog.objects.select_related("requirement_a", "requirement_b").get(
            id=conflict_id
        )
    except ConflictLog.DoesNotExist:
        return _error_response("Conflict not found", "not_found", status=404)

    return _success_response(
        {
            "id": conflict.id,
            "requirement_a": conflict.requirement_a.external_id,
            "requirement_b": conflict.requirement_b.external_id,
            "requirement_a_title": conflict.requirement_a.title,
            "requirement_b_title": conflict.requirement_b.title,
            "pattern": conflict.pattern,
            "confidence": conflict.confidence,
            "details": conflict.details,
            "resolved": conflict.resolved,
            "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None,
            "resolution_notes": conflict.resolution_notes,
            "created_at": conflict.created_at.isoformat(),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def resolve_conflict_view(request, conflict_id):
    """Mark a conflict as resolved."""
    from django.utils import timezone
    from requirements.models import ConflictLog

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return _error_response("Invalid JSON body", "invalid_json")

    try:
        conflict = ConflictLog.objects.get(id=conflict_id)
    except ConflictLog.DoesNotExist:
        return _error_response("Conflict not found", "not_found", status=404)

    if conflict.resolved:
        return _error_response("Conflict already resolved", "invalid_state")

    now = timezone.now()
    conflict.resolved = True
    conflict.resolved_at = now
    conflict.resolution_notes = body.get("resolution_notes", "")
    conflict.save()

    return _success_response({
        "conflict_id": conflict.id,
        "resolved_at": now.isoformat(),
    })

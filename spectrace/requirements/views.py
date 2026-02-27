"""Views for requirements app."""

import csv
import json
from pathlib import Path

import yaml
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from requirements.flows.parser import FlowParseError

from .filter_utils import (
    FLOW_RUN_FILTERS,
    MATRIX_FILTERS,
    VALIDATION_RUN_FILTERS,
    parse_pagination,
)
from .flow_editor import (
    FlowEditorError,
    get_flow_files,
    load_flow_for_editing,
    save_flow,
    validate_flow_path,
)
from .flow_status import (
    get_flow_runs_data,
    get_flows_overview,
    get_run_detail,
    setup_demo_data,
)
from .matrix import get_cell_color, get_matrix_data, setup_matrix_demo
from .models import (
    SLO,
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    InAppValidationStatus,
    Requirement,
    RiskLevel,
    TestRequirementLink,
    VerificationFlow,
)
from .services.impact_analyzer import ImpactAnalyzer, validate_git_ref
from .validation_runs import (
    build_run_comparison,
    get_adjacent_runs,
    get_run_results_grouped,
    get_run_steps_data,
    get_unique_sources,
    get_unique_vendors,
    get_validation_runs_data,
)


def landing_view(request):
    """Landing page with paths to dashboard and tour.

    Shows live stats if data exists to make the page feel alive.
    """
    from .models import InAppValidation, Requirement, TestRequirementLink

    # Gather stats
    total_requirements = Requirement.objects.count()
    total_tests = TestRequirementLink.objects.count()
    total_vendors = InAppValidation.objects.exclude(vendor="").values("vendor").distinct().count()

    # Calculate passing percentage
    passing_count = Requirement.objects.filter(verification_status="passing").count()
    passing_pct = round((passing_count / total_requirements * 100)) if total_requirements > 0 else 0

    stats = {
        "total_requirements": total_requirements,
        "total_tests": total_tests,
        "total_vendors": total_vendors,
        "passing": passing_pct,
    }

    return render(request, "admin/requirements/landing.html", {"stats": stats})


@staff_member_required
def matrix_view(request):
    """Render the traceability matrix grid.

    Query parameters:
        page: Page number (default: 1)
        per_page: Items per page (default: 25)
        status: Filter by requirement status (passing, failing, untested)
        tags: Comma-separated list of tags to filter by
        parent_id: Show only children of this requirement
    """
    page, per_page = parse_pagination(request)
    filters = MATRIX_FILTERS.build(request)

    # Get matrix data
    data = get_matrix_data(page=page, per_page=per_page, filters=filters)

    # Add color information to cells for template
    cells_with_colors = {}
    for key, cell in data["cells"].items():
        cells_with_colors[key] = {
            **cell,
            "color": get_cell_color(cell["status"]),
        }

    # Get parent requirements for filter dropdown (requirements that have children)
    parent_requirements = Requirement.objects.filter(
        depth=1  # Root level requirements (could be parents)
    ).order_by("external_id")

    context = {
        "title": "Traceability Matrix",
        "requirements": data["requirements"],
        "tests": data["tests"],
        "cells": cells_with_colors,
        "pagination": data["pagination"],
        "parent_requirements": parent_requirements,
        "current_filters": MATRIX_FILTERS.get_current_filters(request, per_page),
    }

    return render(request, "admin/requirements/matrix.html", context)


@staff_member_required
def matrix_export(request):
    """Export the traceability matrix as CSV.

    Query parameters same as matrix_view, plus:
        format: 'csv' (default)
    """
    filters = MATRIX_FILTERS.build(request)

    # Get all matrix data (no pagination for export)
    data = get_matrix_data(page=1, per_page=10000, filters=filters)

    # Create CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="traceability_matrix.csv"'

    writer = csv.writer(response)

    # Header row: Requirement ID, Requirement Title, then test names
    header = ["Requirement ID", "Requirement Title", "Status"]
    for test in data["tests"]:
        header.append(test["nodeid"])
    writer.writerow(header)

    # Data rows
    for req in data["requirements"]:
        row = [req.external_id, req.title, req.verification_status]
        for test in data["tests"]:
            cell = data["cells"].get((req.external_id, test["nodeid"]), {})
            row.append(cell.get("status", "unlinked"))
        writer.writerow(row)

    return response


@staff_member_required
@require_http_methods(["POST"])
def vendor_load_demo_view(request):
    """Load demo data for vendor coverage.

    Creates sample vendors with validations and results to demonstrate
    the vendor coverage dashboard features.
    """
    from django.contrib import messages

    from .services.vendor_demo import setup_vendor_demo

    result = setup_vendor_demo()

    messages.success(
        request,
        f"Demo loaded: {result['vendors_created']} vendors, "
        f"{result['validations_created']} validations, "
        f"{result['results_created']} results.",
    )

    return redirect("admin-vendor-coverage")


@staff_member_required
def vendor_coverage_view(request):
    """Dashboard showing validation coverage by vendor.

    Shows:
    - Vendor list with validation counts
    - Per-vendor pass/fail rates
    - Recent regressions per vendor
    """
    # Group validations by vendor with Prefetch to avoid N+1 queries
    # Order results by checked_at descending so we can access latest without re-querying
    vendors = {}
    all_flags = set()

    prefetch = Prefetch("results", queryset=InAppValidationResult.objects.order_by("-checked_at"))

    for validation in InAppValidation.objects.exclude(vendor="").prefetch_related(prefetch):
        vendor = validation.vendor
        if vendor not in vendors:
            vendors[vendor] = {
                "name": vendor,
                "total": 0,
                "passing": 0,
                "failing": 0,
                "degraded": 0,
                "not_run": 0,
                "regressions": [],
                "common_flags": {},
            }

        vendors[vendor]["total"] += 1

        # Access prefetched results (already ordered by -checked_at) without triggering new query
        results = list(validation.results.all())
        latest = results[0] if results else None
        status = latest.status if latest else InAppValidationStatus.NOT_RUN

        if status == InAppValidationStatus.SUCCESS:
            vendors[vendor]["passing"] += 1
        elif status == InAppValidationStatus.FAILURE:
            vendors[vendor]["failing"] += 1
        elif status == InAppValidationStatus.NOT_RUN:
            vendors[vendor]["not_run"] += 1

        # Check for regression using prefetched results (no additional query)
        if len(results) >= 2:
            current, previous = results[0], results[1]
            is_regression = (
                previous.status == InAppValidationStatus.SUCCESS
                and current.status == InAppValidationStatus.FAILURE
            )
            if is_regression:
                vendors[vendor]["regressions"].append(
                    {
                        "name": validation.name,
                        "regressed_at": current.checked_at,
                        "run_id": current.validation_run_id,
                    }
                )

        # Collect feature flags
        if validation.feature_flags:
            all_flags.update(validation.feature_flags.keys())
            for flag, value in validation.feature_flags.items():
                if flag not in vendors[vendor]["common_flags"]:
                    vendors[vendor]["common_flags"][flag] = 0
                vendors[vendor]["common_flags"][flag] += 1

    # Calculate pass rates
    for vendor_data in vendors.values():
        total = vendor_data["total"]
        vendor_data["pass_rate"] = round((vendor_data["passing"] / total) * 100, 1)

    context = {
        "title": "Vendor Coverage",
        "vendors": sorted(vendors.values(), key=lambda v: v["name"]),
        "all_flags": sorted(all_flags),
        "total_vendors": len(vendors),
        "total_validations": sum(v["total"] for v in vendors.values()),
    }

    return render(request, "admin/requirements/vendor_coverage.html", context)


@staff_member_required
@require_http_methods(["GET", "POST"])
def impact_analysis_view(request):
    """View for impact analysis with git ref comparison."""
    context = {
        "title": "Impact Analysis",
        "site_header": "SpecTrace Dashboard",
    }

    if request.method == "POST":
        base_ref = request.POST.get("base_ref", "").strip()
        head_ref = request.POST.get("head_ref", "").strip()
        include_hierarchy = request.POST.get("include_hierarchy", "true") == "true"

        if not base_ref or not head_ref:
            return JsonResponse({"error": "Both base_ref and head_ref are required"}, status=400)

        # Validate git refs before processing
        try:
            validate_git_ref(base_ref)
            validate_git_ref(head_ref)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        analyzer = ImpactAnalyzer()

        try:
            result = analyzer.analyze(base_ref, head_ref, include_hierarchy=include_hierarchy)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse(
            {
                "changed_requirements": result.changed_requirements,
                "affected_tests": result.affected_tests,
                "hierarchy_expansion": result.hierarchy_expansion,
                "summary": {
                    "requirements_changed": len(result.changed_requirements),
                    "tests_affected": len(result.affected_tests),
                    "has_impact": len(result.affected_tests) > 0,
                },
            }
        )

    return render(request, "admin/requirements/impact_analysis.html", context)


@staff_member_required
@require_http_methods(["POST"])
def impact_load_demo_view(request):
    """Load demo data for impact analysis.

    Creates specs in git, test links, and a demo branch with changes.
    """
    from django.contrib import messages

    from .services.impact_analyzer import setup_impact_demo

    result = setup_impact_demo()

    parts = []
    if result["specs_committed"]:
        parts.append("specs committed to git")
    if result["test_links_created"]:
        parts.append(f"{result['test_links_created']} test links created")
    parts.append(f"demo branch '{result['demo_branch']}' ready")

    messages.success(request, f"Demo loaded: {', '.join(parts)}.")

    # Redirect with pre-filled refs
    return redirect(
        f"/admin/impact-analysis/?base_ref={result['base_ref']}&head_ref={result['head_ref']}"
    )


@staff_member_required
def validation_run_list_view(request):
    """List view for validation runs with filtering and pagination.

    Query parameters:
        page: Page number (default: 1)
        per_page: Items per page (default: 25)
        source: Filter by source string
        vendor: Filter by vendor
        date_from: Filter by start date (YYYY-MM-DD)
        date_to: Filter by end date (YYYY-MM-DD)
    """
    page, per_page = parse_pagination(request)
    filters = VALIDATION_RUN_FILTERS.build(request)
    data = get_validation_runs_data(page=page, per_page=per_page, filters=filters)

    # Get requirements with validations for filter dropdown
    requirements_with_validations = (
        Requirement.objects.filter(inapp_validations__isnull=False)
        .distinct()
        .order_by("external_id")
        .values_list("external_id", flat=True)
    )

    context = {
        "title": "Verification Runs",
        "runs": data["runs"],
        "pagination": data["pagination"],
        "summary": data["summary"],
        "vendors": get_unique_vendors(),
        "sources": get_unique_sources(),
        "requirements": list(requirements_with_validations),
        "current_filters": VALIDATION_RUN_FILTERS.get_current_filters(request, per_page),
    }

    return render(request, "admin/requirements/validation_runs.html", context)


@staff_member_required
def validation_run_detail_view(request, run_id: int):
    """Detail view for a single validation run.

    Shows results grouped by vendor with expandable step timelines.
    """
    run = get_object_or_404(InAppValidationRun, id=run_id)
    results_by_vendor = get_run_results_grouped(run)
    adjacent = get_adjacent_runs(run)

    context = {
        "title": f"Validation Run #{run.id}",
        "run": run,
        "results_by_vendor": results_by_vendor,
        "previous_run": adjacent["previous"],
        "next_run": adjacent["next"],
    }

    return render(request, "admin/requirements/validation_run_detail.html", context)


@staff_member_required
def validation_run_steps_view(request, run_id: int):
    """View all steps from a validation run.

    Shows a flat list of all steps across all results, with filtering.
    """
    run = get_object_or_404(InAppValidationRun, id=run_id)
    steps_data = get_run_steps_data(run)
    adjacent = get_adjacent_runs(run)

    # Calculate totals
    total_steps = sum(len(r["steps"]) for r in steps_data)
    total_passed = sum(r["steps_passed"] for r in steps_data)
    total_failed = sum(r["steps_failed"] for r in steps_data)

    context = {
        "title": f"Validation Run #{run.id} - Steps",
        "run": run,
        "steps_data": steps_data,
        "previous_run": adjacent["previous"],
        "next_run": adjacent["next"],
        "total_steps": total_steps,
        "total_passed": total_passed,
        "total_failed": total_failed,
    }

    return render(request, "admin/requirements/validation_run_steps.html", context)


@staff_member_required
def validation_run_compare_view(request):
    """Compare two validation runs side-by-side.

    Query parameters:
        run_a: ID of first run (older)
        run_b: ID of second run (newer)

    Without parameters, shows a run selector UI.
    """
    run_a_id = request.GET.get("run_a")
    run_b_id = request.GET.get("run_b")

    # If both IDs provided, show comparison
    if run_a_id and run_b_id:
        run_a = get_object_or_404(InAppValidationRun, id=run_a_id)
        run_b = get_object_or_404(InAppValidationRun, id=run_b_id)
        comparison = build_run_comparison(run_a, run_b)

        context = {
            "title": "Run Comparison",
            "comparison": comparison,
            "run_a": run_a,
            "run_b": run_b,
        }

        return render(request, "admin/requirements/validation_run_compare.html", context)

    # Otherwise, show run selector
    recent_runs = InAppValidationRun.objects.order_by("-imported_at")[:20]

    context = {
        "title": "Compare Verification Runs",
        "recent_runs": recent_runs,
    }

    return render(request, "admin/requirements/validation_run_compare_select.html", context)


@staff_member_required
def about_view(request):
    """About SpecTrace page - explains what SpecTrace is and why it exists."""
    context = {
        "title": "About SpecTrace",
    }
    return render(request, "admin/requirements/about.html", context)


@staff_member_required
def spec_syntax_help_view(request):
    """Help page explaining FRET-inspired spec syntax."""
    context = {
        "title": "Spec Syntax Guide",
    }
    return render(request, "admin/requirements/spec_syntax_help.html", context)


@staff_member_required
def flow_live_status_view(request):
    """Live monitoring view for currently running flows."""
    context = {
        "title": "Live Flow Status",
    }
    return render(request, "admin/requirements/flow_live.html", context)


@staff_member_required
def flow_status_list_view(request):
    """List all verification flows with their latest run status.

    Shows flow cards with step pipeline preview, latest run badge,
    and run statistics.
    """
    data = get_flows_overview()

    first_flow_with_runs = next(
        (f["name"] for f in data["flows"] if f.get("total_runs", 0) > 0), ""
    )

    context = {
        "title": "Flow Status",
        "flows": data["flows"],
        "summary": data["summary"],
        "has_any_runs": bool(first_flow_with_runs),
        "first_flow_with_runs": first_flow_with_runs,
    }

    return render(request, "admin/requirements/flow_status.html", context)


@staff_member_required
def flow_runs_view(request, flow_name: str):
    """List runs for a specific verification flow.

    Query parameters:
        page: Page number (default: 1)
        per_page: Items per page (default: 25)
        status: Filter by run status (passed, failed, running)
        date_from: Filter runs started on or after this date (YYYY-MM-DD)
        date_to: Filter runs started on or before this date (YYYY-MM-DD)
    """
    page, per_page = parse_pagination(request)
    filters = FLOW_RUN_FILTERS.build(request)
    data = get_flow_runs_data(flow_name, page=page, per_page=per_page, filters=filters)

    if not data["flow_def"]:
        from django.http import Http404

        raise Http404(f"Flow '{flow_name}' not found")

    context = {
        "title": f"{data['flow_def'].display_name} Runs",
        "flow_def": data["flow_def"],
        "flow": data["flow"],
        "runs": data["runs"],
        "pagination": data["pagination"],
        "summary": data["summary"],
        "current_filters": FLOW_RUN_FILTERS.get_current_filters(request, per_page),
    }

    return render(request, "admin/requirements/flow_runs.html", context)


@staff_member_required
def flow_run_detail_view(request, run_id: int):
    """Detail view for a single flow run.

    Shows step pipeline with color-coded status, expandable step details,
    and navigation to adjacent runs.
    """
    data = get_run_detail(run_id)

    if not data["run"]:
        from django.http import Http404

        raise Http404(f"Flow run #{run_id} not found")

    context = {
        "title": f"Run #{run_id} - {data['run'].flow.display_name}",
        "run": data["run"],
        "flow_def": data["flow_def"],
        "steps": data["steps"],
        "previous_run": data["previous_run"],
        "next_run": data["next_run"],
        "summary": data["summary"],
    }

    return render(request, "admin/requirements/flow_run_detail.html", context)


@staff_member_required
@require_http_methods(["POST"])
def flow_load_demo_view(request):
    """Load demo data for flow status dashboard.

    Creates sample runs to demonstrate the dashboard features.
    """
    from django.contrib import messages
    from django.shortcuts import redirect

    result = setup_demo_data(clear=True)

    messages.success(
        request,
        f"Demo loaded: {len(result['runs_created'])} runs created. "
        "Click on a flow below to explore.",
    )

    return redirect("admin-flow-status")


@staff_member_required
def demo_hub(request):
    """Demo catalog showing all available SpecTrace demos.

    Reads from demos.yaml to display demos as cards. Web-based demos
    link directly; CLI demos show the command to run.
    """
    demos_file = Path(__file__).resolve().parent.parent.parent / "demos.yaml"

    demos = []
    if demos_file.exists():
        with open(demos_file) as f:
            data = yaml.safe_load(f)
            demos = data.get("demos", [])

    # Filter out the demo-hub entry (no need to show the hub in itself)
    demos = [d for d in demos if d.get("id") != "demo-hub"]

    # Add URL paths for web-based demos
    web_demo_urls = {
        "spectrace-overview": "spectrace_overview",
        "qa-ecosystem": "qa_ecosystem",
        "agent-pipeline": "demo_agent_pipeline",
        "flow-status-dashboard": "admin-flow-status",
        "traceability-matrix": "admin-matrix",
        "vendor-coverage": "admin-vendor-coverage",
    }

    # Demos with instant in-browser demo data loading (no CLI required)
    instant_demo_ids = {
        "flow-status-dashboard",
        "traceability-matrix",
        "vendor-coverage",
    }

    for demo in demos:
        demo["web_url"] = web_demo_urls.get(demo["id"])
        demo["is_web"] = demo["web_url"] is not None
        demo["has_instant_demo"] = demo["id"] in instant_demo_ids

    return render(request, "admin/requirements/demo_hub.html", {"demos": demos})


@staff_member_required
def demo_agent_pipeline(request):
    """Interactive slideshow presenter for the agent pipeline demo.

    A web-based walkthrough of the SpecTrace agent workflow, replacing
    the CLI demo script with a visual presentation.
    """
    return render(request, "admin/requirements/demo_presenter.html")


@staff_member_required
def spectrace_overview(request):
    """Interactive deep dive into SpecTrace features.

    A web-based slideshow explaining the core concepts, features, and
    benefits of SpecTrace with links to try each feature.
    """
    return render(request, "admin/requirements/spectrace_overview.html")


@staff_member_required
def qa_ecosystem_view(request):
    """How SpecTrace fits in the QA ecosystem.

    Explains how SpecTrace connects to other QA initiatives like PR smoke
    tests, mutation testing, and ephemeral environments.
    """
    return render(request, "admin/requirements/qa_ecosystem.html")


@staff_member_required
@require_http_methods(["POST"])
def matrix_load_demo_view(request):
    """Load demo data for traceability matrix.

    Creates sample test results linked to requirements to demonstrate
    the matrix grid visualization.
    """
    from django.contrib import messages
    from django.shortcuts import redirect

    result = setup_matrix_demo(clear=True)

    if result["requirements_count"] == 0:
        messages.warning(
            request, "No requirements found. Run 'manage.py parse_specs specs/' first."
        )
    else:
        messages.success(
            request,
            f"Demo loaded: {result['test_results_created']} test results "
            f"linked to {result['requirements_count']} requirements.",
        )

    return redirect("admin-matrix")


@staff_member_required
def flow_editor_list_view(request):
    """List all flow YAML files for editing.

    Displays files from the flows/ directory with validation status
    and links to the edit form.
    """
    flows = get_flow_files()

    # Calculate summary
    total = len(flows)
    valid = sum(1 for f in flows if f["valid"])
    invalid = total - valid

    context = {
        "title": "Flow Editor",
        "flows": flows,
        "summary": {
            "total": total,
            "valid": valid,
            "invalid": invalid,
        },
    }

    return render(request, "admin/requirements/flow_editor_list.html", context)


@staff_member_required
@require_http_methods(["GET", "POST"])
def flow_editor_view(request, file_path: str):
    """Edit a flow YAML file.

    GET: Load and display the flow for editing
    POST: Save changes to the flow file
    """
    from django.contrib import messages

    error = None

    if request.method == "POST":
        try:
            flow_data_json = request.POST.get("flow_data", "{}")
            flow_data = json.loads(flow_data_json)
            save_flow(file_path, flow_data)
            messages.success(request, f"Flow '{file_path}' saved successfully.")
            return redirect("admin-flow-editor-edit", file_path=file_path)
        except json.JSONDecodeError as e:
            error = f"Invalid JSON: {e}"
        except FlowParseError as e:
            error = f"Validation error: {e.message}"
        except FlowEditorError as e:
            error = str(e)
        except PermissionError:
            return HttpResponseForbidden("Access denied: invalid file path")

    # Load flow for editing (GET or POST with error)
    try:
        flow_data = load_flow_for_editing(file_path)
    except FileNotFoundError:
        from django.http import Http404

        raise Http404(f"Flow file not found: {file_path}")
    except PermissionError:
        return HttpResponseForbidden("Access denied: invalid file path")
    except ValueError as e:
        from django.http import Http404

        raise Http404(str(e))

    # Get flow title for display
    flow_title = flow_data.get("title", flow_data.get("id", file_path))

    context = {
        "title": f"Edit: {flow_title}",
        "file_path": file_path,
        "flow_data": json.dumps(flow_data),
        "error": error,
    }

    return render(request, "admin/requirements/flow_editor_form.html", context)


@staff_member_required
@require_http_methods(["POST"])
def flow_sync_to_db_view(request, file_path: str):
    """Sync a single flow YAML file to the database."""
    from django.contrib import messages

    from .flows.parser import YAMLFlowParser
    from .flows.sync import sync_yaml_flows_to_db

    try:
        resolved_path = validate_flow_path(file_path)
    except (PermissionError, ValueError) as e:
        messages.error(request, str(e))
        return redirect("admin-flow-editor")

    parser = YAMLFlowParser()
    try:
        flow = parser.parse_file(resolved_path)
        if flow:
            sync_yaml_flows_to_db([flow])
            messages.success(request, f"Flow '{flow.display_name}' synced to database.")
        else:
            messages.warning(request, f"File is not a valid flow: {file_path}")
    except Exception as e:
        messages.error(request, f"Sync failed: {e}")

    return redirect("admin-flow-editor-edit", file_path=file_path)


@staff_member_required
def requirement_detail_view(request, external_id: str):
    """Detailed view for a single requirement.

    Shows all linked items:
    - Test links with last run status
    - In-app validations with latest results
    - Linked SLOs with compliance status
    - Verification flows
    - Child requirements (if any)
    """
    from django.db.models import Max

    requirement = get_object_or_404(Requirement, external_id=external_id)

    # Get test links with last status
    test_links = (
        TestRequirementLink.objects.filter(requirement=requirement)
        .select_related("requirement")
        .order_by("-last_run_at")
    )

    # Get in-app validations with latest results
    validations = (
        InAppValidation.objects.filter(requirement=requirement)
        .prefetch_related("results")
        .order_by("name")
    )

    validations_with_status = []
    for validation in validations:
        results = list(validation.results.order_by("-checked_at")[:1])
        latest = results[0] if results else None
        validations_with_status.append(
            {
                "validation": validation,
                "latest_result": latest,
                "status": latest.status if latest else InAppValidationStatus.NOT_RUN,
            }
        )

    # Get linked SLOs
    slos = SLO.objects.filter(requirement=requirement).order_by("name")

    # Get verification flows
    flows = (
        VerificationFlow.objects.filter(requirements=requirement)
        .prefetch_related("runs")
        .order_by("display_name")
    )

    flows_with_status = []
    for flow in flows:
        latest_run = flow.runs.order_by("-started_at").first()
        flows_with_status.append(
            {
                "flow": flow,
                "latest_run": latest_run,
            }
        )

    # Get child requirements
    children = requirement.get_children().order_by("external_id")

    # Get parent requirement
    parent = requirement.get_parent()

    # Get dependencies
    depends_on = requirement.depends_on.all().order_by("external_id")
    depended_by = requirement.depended_by.all().order_by("external_id")

    # Calculate health indicators
    has_tests = test_links.exists()
    has_passing_tests = test_links.filter(last_status="passed").exists()
    last_test_run = test_links.aggregate(last_run=Max("last_run_at"))["last_run"]

    context = {
        "title": f"{requirement.external_id}: {requirement.title}",
        "requirement": requirement,
        "test_links": test_links,
        "validations": validations_with_status,
        "slos": slos,
        "flows": flows_with_status,
        "children": children,
        "parent": parent,
        "depends_on": depends_on,
        "depended_by": depended_by,
        "health": {
            "has_tests": has_tests,
            "has_passing_tests": has_passing_tests,
            "last_test_run": last_test_run,
            "has_slos": slos.exists(),
            "has_validations": validations.exists(),
        },
    }

    return render(request, "admin/requirements/requirement_detail.html", context)


@staff_member_required
def high_risk_dashboard_view(request):
    """Dashboard showing high-risk requirements with health indicators.

    Shows critical and high-risk requirements with:
    - Test coverage status
    - Last test run date
    - SLO compliance
    - Verification status
    """
    from django.db.models import Count, Max, Q

    # Get high-risk requirements (critical or high)
    high_risk_reqs = (
        Requirement.objects.filter(risk_level__in=[RiskLevel.CRITICAL, RiskLevel.HIGH])
        .annotate(
            test_count=Count("test_links"),
            passing_test_count=Count("test_links", filter=Q(test_links__last_status="passed")),
            failing_test_count=Count(
                "test_links", filter=Q(test_links__last_status__in=["failed", "error"])
            ),
            last_test_run=Max("test_links__last_run_at"),
            slo_count=Count("slos"),
            validation_count=Count("inapp_validations"),
        )
        .order_by("risk_level", "external_id")
    )

    # Calculate summary stats
    total = high_risk_reqs.count()
    with_tests = high_risk_reqs.filter(test_count__gt=0).count()
    with_passing = high_risk_reqs.filter(passing_test_count__gt=0, failing_test_count=0).count()
    with_failing = high_risk_reqs.filter(failing_test_count__gt=0).count()
    with_slos = high_risk_reqs.filter(slo_count__gt=0).count()
    untested = high_risk_reqs.filter(test_count=0).count()

    # Group by risk level
    critical = [r for r in high_risk_reqs if r.risk_level == RiskLevel.CRITICAL]
    high = [r for r in high_risk_reqs if r.risk_level == RiskLevel.HIGH]

    context = {
        "title": "High-Risk Requirements",
        "requirements": high_risk_reqs,
        "critical_requirements": critical,
        "high_requirements": high,
        "summary": {
            "total": total,
            "with_tests": with_tests,
            "with_passing": with_passing,
            "with_failing": with_failing,
            "with_slos": with_slos,
            "untested": untested,
            "coverage_percent": round((with_tests / total * 100) if total > 0 else 0, 1),
            "passing_percent": round((with_passing / total * 100) if total > 0 else 0, 1),
        },
    }

    return render(request, "admin/requirements/high_risk_dashboard.html", context)

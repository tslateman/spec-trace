"""Views for requirements app."""
import csv

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .matrix import get_matrix_data, get_cell_color
from .models import Requirement, InAppValidation, InAppValidationStatus
from .services.impact_analyzer import ImpactAnalyzer


def _build_matrix_filters(request) -> dict:
    """Build filter dict from request query parameters."""
    filters = {}
    if request.GET.get('status'):
        filters['status'] = request.GET['status']
    if request.GET.get('tags'):
        filters['tags'] = [t.strip() for t in request.GET['tags'].split(',')]
    if request.GET.get('parent_id'):
        filters['parent_id'] = request.GET['parent_id']
    return filters


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
    # Parse query parameters
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 25))

    # Build filters from query params
    filters = _build_matrix_filters(request)

    # Get matrix data
    data = get_matrix_data(page=page, per_page=per_page, filters=filters)

    # Add color information to cells for template
    cells_with_colors = {}
    for key, cell in data['cells'].items():
        cells_with_colors[key] = {
            **cell,
            'color': get_cell_color(cell['status']),
        }

    # Get parent requirements for filter dropdown (requirements that have children)
    parent_requirements = Requirement.objects.filter(
        depth=1  # Root level requirements (could be parents)
    ).order_by('external_id')

    context = {
        'title': 'Traceability Matrix',
        'requirements': data['requirements'],
        'tests': data['tests'],
        'cells': cells_with_colors,
        'pagination': data['pagination'],
        'parent_requirements': parent_requirements,
        'current_filters': {
            'status': request.GET.get('status', ''),
            'tags': request.GET.get('tags', ''),
            'parent_id': request.GET.get('parent_id', ''),
            'per_page': per_page,
        },
    }

    return render(request, 'admin/requirements/matrix.html', context)


@staff_member_required
def matrix_export(request):
    """Export the traceability matrix as CSV.

    Query parameters same as matrix_view, plus:
        format: 'csv' (default)
    """
    # Parse query parameters (same as matrix_view)
    filters = _build_matrix_filters(request)

    # Get all matrix data (no pagination for export)
    data = get_matrix_data(page=1, per_page=10000, filters=filters)

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="traceability_matrix.csv"'

    writer = csv.writer(response)

    # Header row: Requirement ID, Requirement Title, then test names
    header = ['Requirement ID', 'Requirement Title', 'Status']
    for test in data['tests']:
        header.append(test['nodeid'])
    writer.writerow(header)

    # Data rows
    for req in data['requirements']:
        row = [req.external_id, req.title, req.verification_status]
        for test in data['tests']:
            cell = data['cells'].get((req.external_id, test['nodeid']), {})
            row.append(cell.get('status', 'unlinked'))
        writer.writerow(row)

    return response


@staff_member_required
def vendor_coverage_view(request):
    """Dashboard showing validation coverage by vendor.
    
    Shows:
    - Vendor list with validation counts
    - Per-vendor pass/fail rates
    - Recent regressions per vendor
    """
    # Group validations by vendor (prefetch results to avoid N+1 queries)
    vendors = {}
    all_flags = set()
    
    for validation in InAppValidation.objects.exclude(vendor='').prefetch_related('results'):
        vendor = validation.vendor
        if vendor not in vendors:
            vendors[vendor] = {
                'name': vendor,
                'total': 0,
                'passing': 0,
                'failing': 0,
                'degraded': 0,
                'not_run': 0,
                'regressions': [],
                'common_flags': {},
            }
        
        vendors[vendor]['total'] += 1
        status = validation.status
        if status == InAppValidationStatus.SUCCESS:
            vendors[vendor]['passing'] += 1
        elif status == InAppValidationStatus.FAILURE:
            vendors[vendor]['failing'] += 1
        elif status == InAppValidationStatus.NOT_RUN:
            vendors[vendor]['not_run'] += 1
        
        # Check for regression
        regression = validation.detect_regression()
        if regression['is_regression']:
            vendors[vendor]['regressions'].append({
                'name': validation.name,
                'regressed_at': regression['regressed_at'],
            })
        
        # Collect feature flags
        if validation.feature_flags:
            all_flags.update(validation.feature_flags.keys())
            for flag, value in validation.feature_flags.items():
                if flag not in vendors[vendor]['common_flags']:
                    vendors[vendor]['common_flags'][flag] = 0
                vendors[vendor]['common_flags'][flag] += 1
    
    # Calculate pass rates
    for vendor_data in vendors.values():
        total = vendor_data['total']
        vendor_data['pass_rate'] = round((vendor_data['passing'] / total) * 100, 1)
    
    context = {
        'title': 'Vendor Coverage',
        'vendors': sorted(vendors.values(), key=lambda v: v['name']),
        'all_flags': sorted(all_flags),
        'total_vendors': len(vendors),
        'total_validations': sum(v['total'] for v in vendors.values()),
    }
    
    return render(request, 'admin/requirements/vendor_coverage.html', context)


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
            return JsonResponse(
                {"error": "Both base_ref and head_ref are required"}, status=400
            )

        analyzer = ImpactAnalyzer()

        try:
            result = analyzer.analyze(base_ref, head_ref, include_hierarchy=include_hierarchy)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse({
            "changed_requirements": result.changed_requirements,
            "affected_tests": result.affected_tests,
            "hierarchy_expansion": result.hierarchy_expansion,
            "summary": {
                "requirements_changed": len(result.changed_requirements),
                "tests_affected": len(result.affected_tests),
                "has_impact": len(result.affected_tests) > 0,
            },
        })

    return render(request, "admin/requirements/impact_analysis.html", context)

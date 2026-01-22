"""Views for requirements app."""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .matrix import get_matrix_data, get_cell_color
from .models import Requirement


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
    filters = {}
    if request.GET.get('status'):
        filters['status'] = request.GET['status']
    if request.GET.get('tags'):
        filters['tags'] = [t.strip() for t in request.GET['tags'].split(',')]
    if request.GET.get('parent_id'):
        filters['parent_id'] = request.GET['parent_id']

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

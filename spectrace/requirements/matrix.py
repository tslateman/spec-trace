"""Matrix data layer for traceability matrix view.

Provides efficient queries for rendering the requirement-test matrix grid.
"""
from collections import defaultdict
from django.db.models import Prefetch

from .models import Requirement, TestResult


def get_matrix_data(page=1, per_page=25, filters=None):
    """
    Get matrix data for rendering the traceability grid.

    Args:
        page: Page number (1-indexed)
        per_page: Requirements per page (default 25)
        filters: Optional dict with filters:
            - status: 'passing', 'failing', 'untested' (requirement status)
            - tags: list of tags to filter by
            - parent_id: requirement ID to show children of

    Returns:
        dict with:
            - requirements: list of Requirement objects for current page
            - tests: list of test info dicts (nodeid, name, file)
            - cells: dict mapping (req_external_id, test_nodeid) -> cell data
            - pagination: pagination metadata
    """
    filters = filters or {}

    # Build base queryset with filters
    queryset = _build_requirement_queryset(filters)

    # Get total count for pagination
    total_count = queryset.count()
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    # Clamp page to valid range
    page = max(1, min(page, total_pages))

    # Calculate offset
    offset = (page - 1) * per_page

    # Get paginated requirements with prefetched test results
    requirements = list(
        queryset
        .prefetch_related(
            Prefetch(
                'test_results',
                queryset=TestResult.objects.select_related('test_run')
                .order_by('-test_run__imported_at')
            )
        )
        .order_by('external_id')[offset:offset + per_page]
    )

    # Get unique tests for these requirements
    tests = _get_tests_for_requirements(requirements)

    # Build cell matrix
    cells = _build_cell_matrix(requirements, tests)

    return {
        'requirements': requirements,
        'tests': tests,
        'cells': cells,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_requirements': total_count,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        }
    }


def _build_requirement_queryset(filters):
    """Build requirement queryset with filters applied."""
    queryset = Requirement.objects.all()

    # Status filter
    if filters.get('status'):
        queryset = queryset.filter(verification_status=filters['status'])

    # Tags filter (any tag matches)
    # Note: Using icontains on JSON field as SQLite doesn't support __contains
    if filters.get('tags'):
        from django.db.models import Q
        tag_q = Q()
        for tag in filters['tags']:
            # Cast tags to string and check if tag is in the JSON array
            # This works because JSONField stores as text in SQLite
            tag_q |= Q(tags__icontains=tag)
        queryset = queryset.filter(tag_q)

    # Parent filter (show descendants of a requirement)
    if filters.get('parent_id'):
        try:
            parent = Requirement.objects.get(external_id=filters['parent_id'])
            # Get all descendants using treebeard
            queryset = parent.get_descendants()
        except Requirement.DoesNotExist:
            # Invalid parent, return empty queryset
            queryset = Requirement.objects.none()

    return queryset


def _get_tests_for_requirements(requirements):
    """Get unique tests linked to any of the given requirements.

    Returns list of dicts with test info, ordered by file then name.
    """
    if not requirements:
        return []

    # Get all test results linked to these requirements
    req_ids = [r.id for r in requirements]
    test_results = (
        TestResult.objects
        .filter(requirements__id__in=req_ids)
        .select_related('test_run')
        .order_by('-test_run__imported_at')
    )

    # Build unique test list (using dict to preserve order and dedupe)
    seen_nodeids = {}
    for result in test_results:
        if result.test_nodeid not in seen_nodeids:
            # Parse file from nodeid (format: path/to/test.py::test_name)
            parts = result.test_nodeid.split('::')
            file_path = parts[0] if parts else ''

            seen_nodeids[result.test_nodeid] = {
                'nodeid': result.test_nodeid,
                'name': result.name,
                'file': file_path,
                'classname': result.classname,
            }

    # Sort by file path, then by name
    tests = sorted(
        seen_nodeids.values(),
        key=lambda t: (t['file'], t['name'])
    )

    return tests


def _build_cell_matrix(requirements, tests):
    """Build the cell matrix mapping (req_external_id, test_nodeid) -> cell data.

    Cell data contains:
        - status: 'passed', 'failed', 'error', 'skipped', 'untested', or 'unlinked'
        - test_result_id: ID of the test result (if linked)
        - linked: boolean indicating if there's a link
    """
    if not requirements or not tests:
        return {}

    # Build a map of (requirement_id, test_nodeid) -> most recent test result
    # for efficient lookup
    result_map = defaultdict(dict)

    for req in requirements:
        # test_results is prefetched, so this doesn't hit DB
        for result in req.test_results.all():
            key = (req.external_id, result.test_nodeid)
            # Only keep the most recent result (they're ordered by -imported_at)
            if key not in result_map:
                result_map[key] = {
                    'status': result.status,
                    'test_result_id': result.id,
                    'linked': True,
                }

    # Build full matrix including unlinked cells
    cells = {}
    test_nodeids = {t['nodeid'] for t in tests}

    for req in requirements:
        for nodeid in test_nodeids:
            key = (req.external_id, nodeid)
            if key in result_map:
                cells[key] = result_map[key]
            else:
                cells[key] = {
                    'status': 'unlinked',
                    'test_result_id': None,
                    'linked': False,
                }

    return cells


def get_cell_css_class(status):
    """Get CSS class for a cell based on its status.

    Args:
        status: Cell status string

    Returns:
        CSS class name for styling
    """
    css_classes = {
        'passed': 'matrix-cell-passed',
        'failed': 'matrix-cell-failed',
        'error': 'matrix-cell-failed',
        'skipped': 'matrix-cell-skipped',
        'untested': 'matrix-cell-untested',
        'unlinked': 'matrix-cell-unlinked',
    }
    return css_classes.get(status, 'matrix-cell-unlinked')


def get_cell_color(status):
    """Get background color for a cell based on its status.

    Args:
        status: Cell status string

    Returns:
        Tailwind CSS color class
    """
    colors = {
        'passed': 'bg-green-500',
        'failed': 'bg-red-500',
        'error': 'bg-red-500',
        'skipped': 'bg-gray-400',
        'untested': 'bg-yellow-500',
        'unlinked': 'bg-gray-200',
    }
    return colors.get(status, 'bg-gray-200')

# Phase 1: Matrix Data Layer

## Goal
Create an efficient query layer and data structure for rendering the traceability matrix grid.

## Context

The matrix needs to display:
- Rows: Requirements (paginated, 25 per page)
- Columns: Tests (unique test node IDs)
- Cells: Status of each requirement-test link (passed/failed/untested/unlinked)

**Existing models:**
- `Requirement` — has `external_id`, `verification_status`, hierarchy (MP_Node)
- `TestResult` — has `test_nodeid`, `status`, linked via ManyToMany to requirements
- Relationship: `TestResult.requirements` ↔ `Requirement.test_results`

## Tasks

### Task 1: Create matrix.py module
**File:** `spectrace/requirements/matrix.py`

Create the matrix data layer module with:

```python
def get_matrix_data(page=1, per_page=25, filters=None):
    """
    Returns matrix data for rendering the grid.

    Args:
        page: Page number (1-indexed)
        per_page: Requirements per page
        filters: Dict with optional filters:
            - status: 'passing', 'failing', 'untested'
            - tags: list of tags
            - parent_id: show children of this requirement

    Returns:
        {
            'requirements': [...],  # Requirement objects for this page
            'tests': [...],  # Unique Test info dicts
            'cells': {...},  # (req_id, test_nodeid) -> cell data
            'pagination': {
                'page': 1,
                'per_page': 25,
                'total_pages': 4,
                'total_requirements': 100,
                'has_next': True,
                'has_prev': False,
            }
        }
    """
```

### Task 2: Implement requirement pagination
Query requirements with filters and pagination:
- Order by `external_id` for consistent ordering
- Apply status filter if provided
- Apply tag filter if provided
- Apply parent filter to show subtree

### Task 3: Implement test column discovery
For the current page of requirements:
- Get all unique test node IDs that link to any requirement on the page
- Return test info (nodeid, name, file) for column headers
- Order tests by file path, then name

### Task 4: Build cell matrix
For each requirement-test combination:
- Determine if linked
- If linked, determine status from most recent test run
- Return cell data: `{status: 'passed'|'failed'|'untested'|'unlinked', test_result_id: int|null}`

### Task 5: Add tests
**File:** `spectrace/requirements/tests/test_matrix.py`

Test cases:
1. `test_get_matrix_data_empty` — No requirements returns empty matrix
2. `test_get_matrix_data_basic` — Basic matrix with requirements and tests
3. `test_pagination` — Pagination works correctly
4. `test_filter_by_status` — Status filter
5. `test_filter_by_tags` — Tag filter
6. `test_cell_status_passing` — Linked test passing = green cell
7. `test_cell_status_failing` — Linked test failing = red cell
8. `test_cell_status_untested` — Linked but no result = yellow cell
9. `test_cell_status_unlinked` — No link = gray cell

## Implementation Notes

### Query Optimization
Use `prefetch_related` to minimize database queries:
```python
requirements = Requirement.objects.filter(...).prefetch_related(
    Prefetch(
        'test_results',
        queryset=TestResult.objects.select_related('test_run').order_by('-test_run__imported_at')
    )
)
```

### Test Discovery Approach
Get tests for visible requirements in one query:
```python
test_nodeids = TestResult.objects.filter(
    requirements__in=requirements
).values_list('test_nodeid', flat=True).distinct()
```

### Cell Status Logic
```python
def get_cell_status(requirement, test_nodeid, test_results_by_nodeid):
    if test_nodeid not in test_results_by_nodeid:
        return {'status': 'unlinked', 'test_result_id': None}

    result = test_results_by_nodeid[test_nodeid]
    if result.requirements.filter(id=requirement.id).exists():
        return {
            'status': result.status,  # passed, failed, error, skipped
            'test_result_id': result.id
        }
    return {'status': 'unlinked', 'test_result_id': None}
```

## Success Criteria

1. ✓ `get_matrix_data()` returns correct structure
2. ✓ Pagination works (page, per_page, total)
3. ✓ Filters apply correctly
4. ✓ Cell status matches test result status
5. ✓ Query count is O(1) not O(n) per requirement
6. ✓ Tests pass

## Files Changed

- `spectrace/requirements/matrix.py` (new)
- `spectrace/requirements/tests/test_matrix.py` (new)

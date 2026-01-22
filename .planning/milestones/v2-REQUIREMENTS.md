# v2 Requirements: Traceability Matrix

## Milestone Goal

Provide a visual grid view showing which tests verify which requirements, enabling at-a-glance understanding of test coverage distribution and gaps.

## Requirements

### MATRIX-01: Grid View
**Priority:** Must Have
**Description:** Display a paginated grid with requirements as rows and tests as columns, showing verification relationships.

**Acceptance Criteria:**
- Grid shows requirements on Y-axis (rows)
- Grid shows tests on X-axis (columns)
- Each cell indicates the relationship: linked+passing, linked+failing, linked+untested, not linked
- Pagination supports 25-50 requirements per page
- Test columns are scrollable horizontally

### MATRIX-02: Status Colors
**Priority:** Must Have
**Description:** Color-code matrix cells to indicate verification status at a glance.

**Acceptance Criteria:**
- Green cell: requirement linked to test, test passing
- Red cell: requirement linked to test, test failing
- Yellow cell: requirement linked to test, test not yet run
- Gray/empty cell: no link between requirement and test
- Legend explains color meanings

### MATRIX-03: Filtering
**Priority:** Must Have
**Description:** Filter the matrix to focus on specific requirements or statuses.

**Acceptance Criteria:**
- Filter by requirement status (passing, failing, untested)
- Filter by requirement tags/categories
- Filter by test file/module
- Filter by parent requirement (show children)
- Filters persist in URL for bookmarking

### MATRIX-04: Dashboard Integration
**Priority:** Must Have
**Description:** Matrix view accessible as a tab within the django-unfold admin dashboard.

**Acceptance Criteria:**
- New "Matrix" tab in dashboard navigation
- Consistent styling with existing dashboard
- Accessible from main dashboard page
- Mobile-responsive (scrollable)

### MATRIX-05: Cell Drill-Down
**Priority:** Should Have
**Description:** Click a cell to see details about the requirement-test relationship.

**Acceptance Criteria:**
- Click cell → popover or modal with details
- Shows requirement ID, title, status
- Shows test name, file, last result
- Link to navigate to requirement detail page
- Link to navigate to test detail page

### MATRIX-06: Export
**Priority:** Should Have
**Description:** Export the current matrix view to CSV for offline analysis or reporting.

**Acceptance Criteria:**
- Export button on matrix page
- CSV includes all visible rows/columns
- Respects current filters
- Includes status in each cell
- Filename includes timestamp

### MATRIX-07: Sparse Mode (Future)
**Priority:** Nice to Have
**Description:** Option to show only cells where links exist, hiding empty columns.

**Acceptance Criteria:**
- Toggle between "full" and "sparse" view
- Sparse view hides tests with no requirement links
- Useful for large test suites with many unlinked tests

## Out of Scope (v2)

- Real-time updates (cells update as tests run) — future milestone
- Interactive editing (create/delete links from matrix) — use admin for now
- Traceability to code (requirements → source files) — different feature
- Comparison views (diff between two test runs) — analytics milestone

## Dependencies

- v1 complete (requirement model, test links, status computation)
- django-unfold dashboard already in place

## Success Metrics

- PMs can answer "which tests cover requirement X?" in < 5 seconds
- Engineers can identify coverage gaps visually
- Matrix loads in < 2 seconds for 100 requirements × 500 tests

---
status: testing
phase: 04-dashboard-features
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 02-01-SUMMARY.md, 03-01-SUMMARY.md, 03-02-SUMMARY.md, extended features]
started: 2026-01-21T07:30:00Z
updated: 2026-01-21T21:30:00Z
---

## Current Test

number: 2
name: View Requirements in Admin
expected: |
  Visit http://localhost:8000/admin/requirements/requirement/ and see hierarchical tree view with requirements showing status indicators (green/red/gray dots).
awaiting: user response

## Tests

### 1. Parse Spec Files
expected: Running `python spectrace/manage.py parse_specs specs/` parses markdown files and populates database with requirements including their hierarchy, tags, and status.
result: issue
reported: "seems we need better demo / dummy data - produce some and add this to the idempotent demo script"
severity: major
fix: "Created scripts/setup_demo.py idempotent script, expanded specs/ with 9 requirements across auth/data/dashboard categories, fixed nodeid normalization in importer.py"

### 2. View Requirements in Admin
expected: Visit http://localhost:8000/admin/requirements/requirement/ and see hierarchical tree view with requirements showing status indicators (green/red/gray dots).
result: [pending]

### 3. Dashboard Metrics
expected: Admin dashboard shows metrics banner with total requirements, passing count, failing count, and untested count with percentages.
result: [pending]

### 4. Annotate Test with Requirement
expected: Adding `@pytest.mark.requirement("REQ-XXX")` decorator to a test and running extract_links includes it in the JSON output.
result: [pending]

### 5. Extract Test-Requirement Links
expected: Running `python spectrace/manage.py extract_links spectrace/tests/` outputs JSON with all test-requirement mappings.
result: [pending]

### 6. Import JUnit Test Results
expected: Running `python spectrace/manage.py import_results test_results.xml links.json` imports test results and links them to requirements.
result: [pending]

### 7. Verification Status Updates
expected: After importing results, requirements with linked passing tests show "passing" status, failed tests show "failing", no tests show "untested".
result: [pending]

### 8. Untested Requirements Highlighted
expected: Requirements without linked tests appear with yellow background in the tree view (coverage gap visibility).
result: [pending]

### 9. Validate Links Command
expected: Running `python spectrace/manage.py validate_links links.json` reports errors for unknown requirements and warnings for uncovered active requirements.
result: [pending]

### 10. Bidirectional Navigation
expected: Clicking a requirement in admin shows linked tests; test results show which requirements they verify.
result: [pending]

## Summary

total: 10
passed: 0
issues: 1
pending: 9
skipped: 0

## Gaps

- truth: "parse_specs command works with demo data"
  status: fixed
  reason: "User reported: seems we need better demo / dummy data - produce some and add this to the idempotent demo script"
  severity: major
  test: 1
  root_cause: "Missing comprehensive demo data, no idempotent setup script, nodeid format mismatch between JUnit XML and extract_links"
  artifacts:
    - path: "scripts/setup_demo.py"
      issue: "Created idempotent demo setup script"
    - path: "specs/auth/*.md, specs/data/*.md, specs/dashboard/*.md"
      issue: "Created 9 demo requirements"
    - path: "spectrace/requirements/importer.py"
      issue: "Added _normalize_nodeid to handle format differences"
  missing: []
  debug_session: ""

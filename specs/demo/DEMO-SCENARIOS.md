---
id: DEMO-SCENARIOS
title: Demo Data Scenarios
tags: [demo, internal, documentation]
priority: low
status: active
verification_method: test
---

This document describes the demo data scenarios used to showcase SpecTrace capabilities.

## Vendor Coverage Demo

The vendor demo (`python manage.py setup_vendor_demo`) creates realistic scenarios:

| Vendor | Pass Rate | Validations | Special Scenario |
|--------|-----------|-------------|------------------|
| Opera | 80% | 5 | Majority passing |
| Mews | 75% | 4 | Single failure |
| Ambiance | 100% | 3 | All passing |
| OpenKey | 50% | 4 | Regression (pass -> fail) |

### Regression Scenario

OpenKey's first validation demonstrates regression detection:
- Run 1 (2 days ago): SUCCESS
- Run 2 (current): FAILURE with "Connection timeout"

This shows how SpecTrace tracks verification status changes over time.

## Sample Requirements Demo

Sample requirements (`specs/sample/`) demonstrate hierarchy and verification:

| Requirement | Status | Reason |
|-------------|--------|--------|
| SAMPLE-AUTH-001-001 | Passing | 2 linked tests pass |
| SAMPLE-AUTH-001-002 | Failing | 1 linked test fails |
| SAMPLE-API-001-001 | Passing | 1 linked test passes |
| SAMPLE-API-001-002 | Untested | No linked tests |

Parent requirements (SAMPLE-001, SAMPLE-AUTH-001, SAMPLE-API-001) use `verification_method: both`, so their status aggregates from children.

## Running Demo Data

```bash
# Set up vendor demo
python spectrace/manage.py setup_vendor_demo

# Parse sample specs
python spectrace/manage.py parse_specs specs/sample/

# Run sample tests and import results
pytest tests/sample/ --junitxml=/tmp/sample-results.xml
python spectrace/manage.py extract_links --path tests/sample --output /tmp/sample-links.json
python spectrace/manage.py import_results /tmp/sample-results.xml --links /tmp/sample-links.json
```

## Expected Dashboard State

After running all demo data setup:
- **Mixed verification status**: Green (passing), red (failing), and gray (untested) requirements visible
- **Vendor coverage**: 4 vendors with varied pass rates showing realistic integration scenarios
- **Regression detection**: OpenKey shows status change from success to failure
- **Hierarchy visualization**: 3-level requirement hierarchy (epic > feature > story) with status rollup

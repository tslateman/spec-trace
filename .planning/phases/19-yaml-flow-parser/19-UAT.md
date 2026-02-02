---
status: diagnosed
phase: 19-yaml-flow-parser
source: [19-01-SUMMARY.md, 19-02-SUMMARY.md]
started: 2026-02-02T15:00:00Z
updated: 2026-02-02T15:08:00Z
---

## Current Test

[testing complete]

## Tests

### 1. YAML Flow Files Exist
expected: Run `ls flows/` and see linear-connection.yaml and example-api-check.yaml files.
result: pass

### 2. Parse Single YAML Flow
expected: Run `python spectrace/manage.py parse_flows flows/linear-connection.yaml --dry-run` and see parsed flow details without database changes.
result: issue
reported: "CommandError: Path is not a directory: flows/linear-connection.yaml"
severity: major

### 3. Parse Flow Directory
expected: Run `python spectrace/manage.py parse_flows flows/ --dry-run` and see both example flows parsed.
result: pass

### 4. Sync Flows to Database
expected: Run `python spectrace/manage.py parse_flows flows/` (without --dry-run) and see flows synced to database. Verify with shell query returns True.
result: pass

### 5. Flow Metadata Preserved
expected: After syncing, the flow steps JSON includes _metadata with source_file and requirements fields.
result: pass

### 6. Clear and Resync Works
expected: Run `python spectrace/manage.py parse_flows flows/ --clear` and see flows deleted then re-created. Running twice produces same result (idempotent).
result: pass

## Summary

total: 6
passed: 5
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "parse_flows command accepts single YAML file path"
  status: failed
  reason: "User reported: CommandError: Path is not a directory: flows/linear-connection.yaml"
  severity: major
  test: 2
  root_cause: "BaseImportCommand has path_must_be_dir=True default, parse_flows inherits this without override. Command only calls parse_directory(), not parse_file()."
  artifacts:
    - path: "spectrace/requirements/management/commands/parse_flows.py"
      issue: "Missing path_must_be_dir=False override and file vs directory detection"
    - path: "spectrace/requirements/management/commands/base.py"
      issue: "path_must_be_dir=True is default (not a bug, just context)"
  missing:
    - "Set path_must_be_dir = False in parse_flows.py"
    - "Add file vs directory detection in do_import"
    - "Call parse_file() for single files, parse_directory() for directories"
  debug_session: ""

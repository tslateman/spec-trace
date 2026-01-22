---
phase: 05-health-check-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - spectrace/requirements/health.py
  - spectrace/requirements/tests/test_health.py
autonomous: true

must_haves:
  truths:
    - "VerificationCheck dataclass has name, passed, details, timestamp fields"
    - "VerificationCheck includes error_message and response_body for failures"
    - "TestConnectionResult aggregates multiple VerificationCheck instances"
    - "Timestamps are auto-generated in ISO 8601 format"
  artifacts:
    - path: "spectrace/requirements/health.py"
      provides: "VerificationCheck and TestConnectionResult dataclasses"
      exports: ["VerificationCheck", "TestConnectionResult", "_get_timestamp"]
    - path: "spectrace/requirements/tests/test_health.py"
      provides: "Unit tests for dataclasses"
      contains: "test_verification_check"
  key_links: []
---

<objective>
Create VerificationCheck and TestConnectionResult dataclasses for health check domain objects.

Purpose: These dataclasses are the foundation for all health check operations - every check function returns VerificationCheck, and the aggregator returns TestConnectionResult. This satisfies HEALTH-03 (name, passed, details, timestamp fields).

Output: `spectrace/requirements/health.py` with dataclasses, `spectrace/requirements/tests/test_health.py` with unit tests
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/05-health-check-foundation/05-RESEARCH.md

# Existing patterns to follow
@spectrace/requirements/status.py (computation pattern)
@spectrace/requirements/models.py (enum patterns)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create health.py with dataclasses</name>
  <files>spectrace/requirements/health.py</files>
  <action>
Create new file `spectrace/requirements/health.py` with:

1. `_get_timestamp()` function that returns ISO 8601 UTC timestamp string
   - Use `datetime.utcnow().isoformat() + 'Z'` format
   - This is a private helper for field(default_factory=...)

2. `VerificationCheck` dataclass with fields:
   - `name: str` - Check name (e.g., "Configuration", "Authentication")
   - `passed: bool` - True if check succeeded
   - `details: str | None = None` - Success details
   - `error_message: str | None = None` - Error description (HEALTH-04)
   - `response_status: int | None = None` - HTTP status code if API request
   - `response_body: str | None = None` - Sanitized response for debugging (HEALTH-04)
   - `timestamp: str = field(default_factory=_get_timestamp)` - Auto-generated

3. `TestConnectionResult` dataclass with fields:
   - `success: bool` - True if all checks passed
   - `message: str` - Human-readable summary
   - `checks: list[VerificationCheck] | None = None` - Individual check results
   - `error_details: str | None = None` - Catastrophic error details

Include docstrings explaining each field's purpose. Follow existing docstring style from status.py.
  </action>
  <verify>
    `python -c "from requirements.health import VerificationCheck, TestConnectionResult; print('Import OK')"`
  </verify>
  <done>
    VerificationCheck and TestConnectionResult dataclasses exist with all required fields and can be imported.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add unit tests for dataclasses</name>
  <files>spectrace/requirements/tests/test_health.py</files>
  <action>
Create test file `spectrace/requirements/tests/test_health.py` with:

1. `test_verification_check_creation()` - Test basic creation with required fields
   - Assert name and passed fields work
   - Assert optional fields default to None

2. `test_verification_check_timestamp_auto_generated()` - Test timestamp auto-generation
   - Create two instances with small delay
   - Assert both have timestamps
   - Assert timestamps are different (proving per-instance generation)
   - Assert timestamp format is ISO 8601 (ends with 'Z')

3. `test_verification_check_failure_fields()` - Test error fields
   - Create check with error_message and response_body
   - Assert fields are set correctly

4. `test_connection_result_success()` - Test successful result
   - Create TestConnectionResult with success=True and checks list
   - Assert aggregation works

5. `test_connection_result_failure()` - Test failed result
   - Create TestConnectionResult with success=False and error_details
   - Assert fields are set correctly

Use pytest patterns from existing test files. Follow existing test structure.
  </action>
  <verify>
    `cd /Users/tslater/dev/spec-trace/spectrace && python -m pytest requirements/tests/test_health.py -v`
  </verify>
  <done>
    All dataclass tests pass, confirming VerificationCheck has auto-generated timestamps and TestConnectionResult aggregates checks correctly.
  </done>
</task>

</tasks>

<verification>
- `python -c "from requirements.health import VerificationCheck, TestConnectionResult"` succeeds
- `pytest requirements/tests/test_health.py -v` all tests pass
- VerificationCheck has: name, passed, details, error_message, response_status, response_body, timestamp
- TestConnectionResult has: success, message, checks, error_details
</verification>

<success_criteria>
1. VerificationCheck dataclass exists with all HEALTH-03 fields (name, passed, details, timestamp)
2. VerificationCheck includes HEALTH-04 fields (error_message, response_body)
3. TestConnectionResult aggregates VerificationCheck instances
4. Timestamps are auto-generated per-instance in ISO 8601 format
5. All unit tests pass
</success_criteria>

<output>
After completion, create `.planning/phases/05-health-check-foundation/05-01-SUMMARY.md`
</output>

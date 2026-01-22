---
phase: 05-health-check-foundation
plan: 03
type: execute
wave: 2
depends_on: ["05-01"]
files_modified:
  - spectrace/requirements/health.py
  - spectrace/requirements/tests/test_health.py
autonomous: true

must_haves:
  truths:
    - "Configuration check validates LINEAR_API_KEY presence"
    - "Configuration check validates API key format (lin_api_* prefix)"
    - "Configuration check validates LINEAR_WORKSPACE presence"
    - "Configuration check validates LINEAR_TEAM presence"
    - "Failed config check includes specific error_message"
  artifacts:
    - path: "spectrace/requirements/health.py"
      provides: "check_configuration function"
      exports: ["check_configuration"]
    - path: "spectrace/requirements/tests/test_health.py"
      provides: "Unit tests for configuration check"
      contains: "test_check_configuration"
  key_links:
    - from: "spectrace/requirements/health.py:check_configuration"
      to: "VerificationCheck"
      via: "returns VerificationCheck instance"
      pattern: "return VerificationCheck"
---

<objective>
Create configuration check function that validates Linear API settings.

Purpose: Part of HEALTH-02 (granular diagnostic checks). Configuration check runs first - no point making API calls if settings are missing or malformed. This catches common setup errors before they become confusing API failures.

Output: `check_configuration()` function that returns VerificationCheck with pass/fail and specific error messages
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/05-health-check-foundation/05-RESEARCH.md

# Existing Linear patterns
@spectrace/requirements/linear.py (API key format: starts with 'lin_api_')
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create check_configuration function</name>
  <files>spectrace/requirements/health.py</files>
  <action>
Add to `spectrace/requirements/health.py` after dataclass definitions:

```python
def check_configuration(api_key: str, workspace: str, team: str) -> VerificationCheck:
    """Validate Linear configuration presence and format.

    Checks:
    1. API key is present (not empty)
    2. API key matches expected format (lin_api_* prefix)
    3. Workspace identifier is present
    4. Team identifier is present

    Args:
        api_key: Linear API key (should start with 'lin_api_')
        workspace: Workspace identifier
        team: Team identifier

    Returns:
        VerificationCheck with passed=True if all config valid,
        or passed=False with specific error_message
    """
    if not api_key:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_API_KEY not configured"
        )

    if not api_key.startswith('lin_api_'):
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_API_KEY does not match expected format (should start with 'lin_api_')"
        )

    if not workspace:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_WORKSPACE not configured"
        )

    if not team:
        return VerificationCheck(
            name="Configuration",
            passed=False,
            error_message="LINEAR_TEAM not configured"
        )

    return VerificationCheck(
        name="Configuration",
        passed=True,
        details=f"API key present, workspace: {workspace}, team: {team}"
    )
```

Note: This function validates presence and format only - no API calls. API validation happens in check_authentication (Plan 04).
  </action>
  <verify>
    `python -c "from requirements.health import check_configuration; c = check_configuration('lin_api_test', 'ws', 'team'); print(f'passed={c.passed}, details={c.details}')"`
  </verify>
  <done>
    check_configuration function exists and returns VerificationCheck with passed=True for valid config.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add configuration check tests</name>
  <files>spectrace/requirements/tests/test_health.py</files>
  <action>
Add to `spectrace/requirements/tests/test_health.py`:

```python
from requirements.health import check_configuration

class TestCheckConfiguration:
    """Tests for check_configuration function."""

    def test_valid_configuration(self):
        """All valid config returns passed=True."""
        result = check_configuration(
            api_key='lin_api_test123',
            workspace='my-workspace',
            team='engineering'
        )
        assert result.passed is True
        assert result.name == "Configuration"
        assert 'my-workspace' in result.details
        assert 'engineering' in result.details
        assert result.error_message is None

    def test_missing_api_key(self):
        """Empty API key returns passed=False with message."""
        result = check_configuration(
            api_key='',
            workspace='my-workspace',
            team='engineering'
        )
        assert result.passed is False
        assert 'LINEAR_API_KEY' in result.error_message
        assert 'not configured' in result.error_message

    def test_invalid_api_key_format(self):
        """API key without lin_api_ prefix returns passed=False."""
        result = check_configuration(
            api_key='invalid_key_format',
            workspace='my-workspace',
            team='engineering'
        )
        assert result.passed is False
        assert 'lin_api_' in result.error_message
        assert 'format' in result.error_message.lower()

    def test_missing_workspace(self):
        """Empty workspace returns passed=False with message."""
        result = check_configuration(
            api_key='lin_api_test123',
            workspace='',
            team='engineering'
        )
        assert result.passed is False
        assert 'LINEAR_WORKSPACE' in result.error_message

    def test_missing_team(self):
        """Empty team returns passed=False with message."""
        result = check_configuration(
            api_key='lin_api_test123',
            workspace='my-workspace',
            team=''
        )
        assert result.passed is False
        assert 'LINEAR_TEAM' in result.error_message

    def test_none_values_treated_as_missing(self):
        """None values are treated as empty/missing."""
        result = check_configuration(
            api_key=None,
            workspace='my-workspace',
            team='engineering'
        )
        assert result.passed is False
        assert 'not configured' in result.error_message

    def test_check_has_timestamp(self):
        """Configuration check includes timestamp."""
        result = check_configuration(
            api_key='lin_api_test',
            workspace='ws',
            team='team'
        )
        assert result.timestamp is not None
        assert result.timestamp.endswith('Z')  # ISO 8601 UTC
```

Note: Test for None handling - this catches cases where settings return None instead of empty string.
  </action>
  <verify>
    `cd /Users/tslater/dev/spec-trace/spectrace && python -m pytest requirements/tests/test_health.py::TestCheckConfiguration -v`
  </verify>
  <done>
    All configuration check tests pass, confirming each validation scenario returns appropriate VerificationCheck.
  </done>
</task>

</tasks>

<verification>
- `check_configuration('lin_api_x', 'ws', 'team')` returns passed=True
- `check_configuration('', 'ws', 'team')` returns passed=False with 'LINEAR_API_KEY' error
- `check_configuration('invalid', 'ws', 'team')` returns passed=False with format error
- `check_configuration('lin_api_x', '', 'team')` returns passed=False with 'LINEAR_WORKSPACE' error
- `check_configuration('lin_api_x', 'ws', '')` returns passed=False with 'LINEAR_TEAM' error
- All TestCheckConfiguration tests pass
</verification>

<success_criteria>
1. check_configuration function exists in health.py
2. Returns VerificationCheck with name="Configuration"
3. Validates API key presence and lin_api_* format
4. Validates workspace presence
5. Validates team presence
6. Failed checks have specific error_message (not generic)
7. Passed checks include details with workspace and team
8. All tests pass
</success_criteria>

<output>
After completion, create `.planning/phases/05-health-check-foundation/05-03-SUMMARY.md`
</output>

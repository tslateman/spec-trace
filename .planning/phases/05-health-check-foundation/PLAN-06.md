---
phase: 05-health-check-foundation
plan: 06
type: execute
wave: 3
depends_on: ["05-01", "05-02", "05-03", "05-04", "05-05"]
files_modified:
  - spectrace/requirements/health.py
  - spectrace/requirements/tests/test_health.py
autonomous: true

must_haves:
  truths:
    - "test_linear_connection runs checks in order: config -> auth -> permissions"
    - "Failed config check short-circuits (no API calls made)"
    - "Failed auth check short-circuits (no permissions check)"
    - "All checks are included in TestConnectionResult.checks"
    - "Overall success is True only if all checks pass"
  artifacts:
    - path: "spectrace/requirements/health.py"
      provides: "test_linear_connection aggregator function"
      exports: ["test_linear_connection"]
    - path: "spectrace/requirements/tests/test_health.py"
      provides: "Integration tests for connection test"
      contains: "test_linear_connection"
  key_links:
    - from: "spectrace/requirements/health.py:test_linear_connection"
      to: "check_configuration"
      via: "sequential check execution"
      pattern: "check_configuration"
    - from: "spectrace/requirements/health.py:test_linear_connection"
      to: "check_authentication"
      via: "sequential check execution after config passes"
      pattern: "check_authentication"
    - from: "spectrace/requirements/health.py:test_linear_connection"
      to: "check_permissions"
      via: "sequential check execution after auth passes"
      pattern: "check_permissions"
    - from: "spectrace/requirements/health.py:test_linear_connection"
      to: "TestConnectionResult"
      via: "aggregation return type"
      pattern: "return TestConnectionResult"
---

<objective>
Create test_linear_connection aggregator that runs all checks and returns unified result.

Purpose: Completes HEALTH-02 by aggregating config, auth, and permissions checks into a single function that returns TestConnectionResult. This is the entry point for the health check API endpoint (Phase 6).

Output: `test_linear_connection()` function that orchestrates checks and returns TestConnectionResult
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/05-health-check-foundation/05-RESEARCH.md

# Components to aggregate
@spectrace/requirements/health.py (VerificationCheck, TestConnectionResult, check_* functions)
@spectrace/requirements/linear.py (LinearClient)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create test_linear_connection aggregator</name>
  <files>spectrace/requirements/health.py</files>
  <action>
Add to `spectrace/requirements/health.py` after check_permissions:

```python
def test_linear_connection(api_key: str, workspace: str, team: str) -> TestConnectionResult:
    """Test Linear API connection with granular diagnostics.

    Runs three checks in sequence:
    1. Configuration: Validate settings presence and format
    2. Authentication: Verify API key with viewer query
    3. Permissions: Verify read access to issues

    Checks short-circuit on failure - if configuration fails, no API
    calls are made. If authentication fails, permissions check is skipped.

    Args:
        api_key: Linear API key (lin_api_...)
        workspace: Workspace identifier
        team: Team identifier

    Returns:
        TestConnectionResult with:
        - success: True if all checks passed
        - message: Human-readable summary
        - checks: List of individual VerificationCheck results
        - error_details: Set if catastrophic error occurs
    """
    checks = []

    # Check 1: Configuration
    config_check = check_configuration(api_key, workspace, team)
    checks.append(config_check)
    if not config_check.passed:
        return TestConnectionResult(
            success=False,
            message="Configuration invalid",
            checks=checks
        )

    # Check 2: Authentication (requires valid config)
    from requirements.linear import LinearClient
    try:
        client = LinearClient(api_key)
    except Exception as e:
        return TestConnectionResult(
            success=False,
            message="Failed to create Linear client",
            checks=checks,
            error_details=f"{type(e).__name__}: {str(e)}"
        )

    auth_check = check_authentication(client)
    checks.append(auth_check)
    if not auth_check.passed:
        return TestConnectionResult(
            success=False,
            message="Authentication failed",
            checks=checks
        )

    # Check 3: Permissions (requires valid auth)
    perm_check = check_permissions(client)
    checks.append(perm_check)

    # Determine overall result
    all_passed = all(c.passed for c in checks)

    if all_passed:
        return TestConnectionResult(
            success=True,
            message="All checks passed",
            checks=checks
        )
    else:
        return TestConnectionResult(
            success=False,
            message="Permission check failed",
            checks=checks
        )
```

Note: Import LinearClient inside function to avoid circular import. Short-circuit behavior prevents unnecessary API calls on early failure.
  </action>
  <verify>
    `python -c "from requirements.health import test_linear_connection; print('Import OK')"`
  </verify>
  <done>
    test_linear_connection function exists and can be imported.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add aggregator tests</name>
  <files>spectrace/requirements/tests/test_health.py</files>
  <action>
Add to `spectrace/requirements/tests/test_health.py`:

```python
from requirements.health import test_linear_connection

class TestLinearConnection:
    """Tests for test_linear_connection aggregator."""

    def test_all_checks_pass(self):
        """All valid config and mocked API returns success=True."""
        with patch('requirements.health.LinearClient') as MockClient:
            mock_client = Mock()
            # Auth succeeds
            mock_client._execute_query.side_effect = [
                {'viewer': {'id': '1', 'name': 'Test', 'email': 'test@test.com'}},
                {'issues': {'nodes': []}}
            ]
            MockClient.return_value = mock_client

            result = test_linear_connection(
                api_key='lin_api_test123',
                workspace='my-workspace',
                team='engineering'
            )

            assert result.success is True
            assert result.message == "All checks passed"
            assert len(result.checks) == 3
            assert all(c.passed for c in result.checks)

    def test_config_failure_short_circuits(self):
        """Invalid config returns immediately without API calls."""
        with patch('requirements.health.LinearClient') as MockClient:
            result = test_linear_connection(
                api_key='',  # Invalid - missing
                workspace='my-workspace',
                team='engineering'
            )

            assert result.success is False
            assert 'Configuration' in result.message
            assert len(result.checks) == 1
            assert result.checks[0].name == "Configuration"
            # No API calls should be made
            MockClient.assert_not_called()

    def test_auth_failure_short_circuits(self):
        """Failed auth skips permissions check."""
        with patch('requirements.health.LinearClient') as MockClient:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = '{"error": "Unauthorized"}'
            http_error = requests.HTTPError()
            http_error.response = mock_response
            mock_client._execute_query.side_effect = http_error
            MockClient.return_value = mock_client

            result = test_linear_connection(
                api_key='lin_api_test123',
                workspace='my-workspace',
                team='engineering'
            )

            assert result.success is False
            assert 'Authentication' in result.message
            assert len(result.checks) == 2  # Config passed, Auth failed, Perm skipped
            assert result.checks[0].passed is True  # Config
            assert result.checks[1].passed is False  # Auth

    def test_permission_failure(self):
        """All checks run but permissions fails."""
        with patch('requirements.health.LinearClient') as MockClient:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 403
            mock_response.text = '{"error": "Forbidden"}'
            http_error = requests.HTTPError()
            http_error.response = mock_response

            # Auth succeeds, permissions fails
            def side_effect(query):
                if 'viewer' in query:
                    return {'viewer': {'id': '1', 'name': 'Test', 'email': 'test@test.com'}}
                else:
                    raise http_error

            mock_client._execute_query.side_effect = side_effect
            MockClient.return_value = mock_client

            result = test_linear_connection(
                api_key='lin_api_test123',
                workspace='my-workspace',
                team='engineering'
            )

            assert result.success is False
            assert 'Permission' in result.message
            assert len(result.checks) == 3
            assert result.checks[0].passed is True  # Config
            assert result.checks[1].passed is True  # Auth
            assert result.checks[2].passed is False  # Permissions

    def test_checks_in_correct_order(self):
        """Checks are ordered: Configuration, Authentication, Permissions."""
        with patch('requirements.health.LinearClient') as MockClient:
            mock_client = Mock()
            mock_client._execute_query.side_effect = [
                {'viewer': {'id': '1', 'name': 'Test', 'email': 'test@test.com'}},
                {'issues': {'nodes': []}}
            ]
            MockClient.return_value = mock_client

            result = test_linear_connection(
                api_key='lin_api_test123',
                workspace='my-workspace',
                team='engineering'
            )

            check_names = [c.name for c in result.checks]
            assert check_names == ["Configuration", "Authentication", "Permissions"]

    def test_all_checks_have_timestamps(self):
        """Every check in result has a timestamp."""
        with patch('requirements.health.LinearClient') as MockClient:
            mock_client = Mock()
            mock_client._execute_query.side_effect = [
                {'viewer': {'id': '1', 'name': 'Test', 'email': 'test@test.com'}},
                {'issues': {'nodes': []}}
            ]
            MockClient.return_value = mock_client

            result = test_linear_connection(
                api_key='lin_api_test123',
                workspace='my-workspace',
                team='engineering'
            )

            for check in result.checks:
                assert check.timestamp is not None
                assert check.timestamp.endswith('Z')
```

Add necessary import at top of test file if not present:
```python
from unittest.mock import Mock, patch
import requests
```
  </action>
  <verify>
    `cd /Users/tslater/dev/spec-trace/spectrace && python -m pytest requirements/tests/test_health.py::TestLinearConnection -v`
  </verify>
  <done>
    All aggregator tests pass, confirming correct check ordering, short-circuit behavior, and result aggregation.
  </done>
</task>

<task type="auto">
  <name>Task 3: Run full test suite for health module</name>
  <files>spectrace/requirements/tests/test_health.py</files>
  <action>
Run the complete test suite for the health module to ensure all components work together:

```bash
cd /Users/tslater/dev/spec-trace/spectrace && python -m pytest requirements/tests/test_health.py -v --tb=short
```

Verify:
- All dataclass tests pass
- All sanitization tests pass
- All check_configuration tests pass
- All check_authentication tests pass
- All check_permissions tests pass
- All test_linear_connection tests pass

If any test fails, fix the issue before marking task complete.
  </action>
  <verify>
    `cd /Users/tslater/dev/spec-trace/spectrace && python -m pytest requirements/tests/test_health.py -v`
  </verify>
  <done>
    Complete health module test suite passes with all tests green.
  </done>
</task>

</tasks>

<verification>
- `test_linear_connection('lin_api_x', 'ws', 'team')` returns TestConnectionResult
- Config failure returns 1 check (no API calls)
- Auth failure returns 2 checks (config passed, auth failed)
- Perm failure returns 3 checks (all run, perm failed)
- Success returns 3 checks (all passed)
- All TestLinearConnection tests pass
- Full health module test suite passes
</verification>

<success_criteria>
1. test_linear_connection function exists in health.py
2. Runs checks in order: Configuration -> Authentication -> Permissions
3. Short-circuits on failure (no unnecessary API calls)
4. Returns TestConnectionResult with all check results
5. success=True only when all checks pass
6. Message reflects which check failed
7. All aggregator tests pass
8. Full health module test suite passes (30+ tests)
</success_criteria>

<output>
After completion, create `.planning/phases/05-health-check-foundation/05-06-SUMMARY.md`
</output>

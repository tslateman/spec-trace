---
phase: 05-health-check-foundation
plan: 05
type: execute
wave: 2
depends_on: ["05-01", "05-02"]
files_modified:
  - spectrace/requirements/health.py
  - spectrace/requirements/tests/test_health.py
autonomous: true

must_haves:
  truths:
    - "Permissions check verifies read access to issues endpoint"
    - "Permissions check uses GraphQL issues query"
    - "Successful check confirms read access"
    - "Failed check includes HTTP status and sanitized response"
  artifacts:
    - path: "spectrace/requirements/health.py"
      provides: "check_permissions function"
      exports: ["check_permissions"]
    - path: "spectrace/requirements/tests/test_health.py"
      provides: "Unit tests for permissions check"
      contains: "test_check_permissions"
  key_links:
    - from: "spectrace/requirements/health.py:check_permissions"
      to: "LinearClient._execute_query"
      via: "issues query execution"
      pattern: "_execute_query.*issues"
    - from: "spectrace/requirements/health.py:check_permissions"
      to: "_sanitize_response"
      via: "error response sanitization"
      pattern: "_sanitize_response"
---

<objective>
Create permissions check function that verifies read access to Linear issues.

Purpose: Part of HEALTH-02 (granular diagnostic checks). This check verifies the API token has permissions to read issues, which is required for the Linear sync feature. Even with valid authentication, the token might lack specific permissions.

Output: `check_permissions()` function that returns VerificationCheck with permissions validation result
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/05-health-check-foundation/05-RESEARCH.md

# LinearClient pattern
@spectrace/requirements/linear.py (LinearClient with _execute_query and issues query)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create check_permissions function</name>
  <files>spectrace/requirements/health.py</files>
  <action>
Add to `spectrace/requirements/health.py` after check_authentication:

```python
def check_permissions(client) -> VerificationCheck:
    """Verify read access to Linear issues endpoint.

    Makes a minimal GraphQL query to fetch one issue, validating
    that the API token has read permissions for issues. This is
    separate from authentication - a valid token might still lack
    specific permissions.

    Args:
        client: LinearClient instance (from requirements.linear)

    Returns:
        VerificationCheck with passed=True if read access confirmed,
        or passed=False with error details
    """
    import requests

    try:
        result = client._execute_query("""
            query TestIssueAccess {
                issues(first: 1) {
                    nodes {
                        id
                    }
                }
            }
        """)

        # Query succeeded - we have read access
        # Note: Empty result is fine (no issues exist), we just need query to work
        return VerificationCheck(
            name="Permissions",
            passed=True,
            details="Read access to issues endpoint confirmed",
            response_status=200
        )

    except requests.HTTPError as e:
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message=f"HTTP {e.response.status_code}: Insufficient permissions for issues",
            response_status=e.response.status_code,
            response_body=_sanitize_response(e.response.text)
        )
    except ValueError as e:
        # GraphQL errors raised by _execute_query
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message=f"GraphQL error: {str(e)}"
        )
    except Exception as e:
        # Network errors, timeouts, etc.
        return VerificationCheck(
            name="Permissions",
            passed=False,
            error_message=f"Request failed: {type(e).__name__}: {str(e)}"
        )
```

Note: Fetches `first: 1` to minimize data transfer. Empty results (no issues) is still success - we're validating permissions, not data existence.
  </action>
  <verify>
    `python -c "from requirements.health import check_permissions; print('Import OK')"`
  </verify>
  <done>
    check_permissions function exists and can be imported.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add permissions check tests</name>
  <files>spectrace/requirements/tests/test_health.py</files>
  <action>
Add to `spectrace/requirements/tests/test_health.py`:

```python
from requirements.health import check_permissions

class TestCheckPermissions:
    """Tests for check_permissions function."""

    def test_successful_permissions_with_issues(self):
        """Read access with issues returns passed=True."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {
            'issues': {
                'nodes': [{'id': 'issue-123'}]
            }
        }

        result = check_permissions(mock_client)

        assert result.passed is True
        assert result.name == "Permissions"
        assert 'read access' in result.details.lower()
        assert result.response_status == 200

    def test_successful_permissions_no_issues(self):
        """Read access with no issues still returns passed=True."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {
            'issues': {
                'nodes': []
            }
        }

        result = check_permissions(mock_client)

        assert result.passed is True
        assert result.name == "Permissions"
        # Empty workspace is fine - we just need query permission
        assert 'read access' in result.details.lower()

    def test_http_403_forbidden(self):
        """403 error returns passed=False with permission message."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = '{"error": "Access denied to issues"}'

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_client._execute_query.side_effect = http_error

        result = check_permissions(mock_client)

        assert result.passed is False
        assert result.name == "Permissions"
        assert '403' in result.error_message
        assert 'permission' in result.error_message.lower()
        assert result.response_status == 403

    def test_graphql_permission_error(self):
        """GraphQL permission error returns passed=False."""
        mock_client = Mock()
        mock_client._execute_query.side_effect = ValueError(
            "GraphQL errors: [{'message': 'Not authorized to access issues'}]"
        )

        result = check_permissions(mock_client)

        assert result.passed is False
        assert 'GraphQL error' in result.error_message

    def test_sanitized_response_on_error(self):
        """Error response has credentials sanitized."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = '{"request": {"authorization": "lin_api_secret"}}'

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_client._execute_query.side_effect = http_error

        result = check_permissions(mock_client)

        assert result.passed is False
        assert 'lin_api_secret' not in (result.response_body or '')

    def test_check_has_timestamp(self):
        """Permissions check includes timestamp."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {'issues': {'nodes': []}}

        result = check_permissions(mock_client)

        assert result.timestamp is not None
        assert result.timestamp.endswith('Z')
```
  </action>
  <verify>
    `cd /Users/tslater/dev/spec-trace/spectrace && python -m pytest requirements/tests/test_health.py::TestCheckPermissions -v`
  </verify>
  <done>
    All permissions check tests pass, confirming success and failure scenarios are handled correctly.
  </done>
</task>

</tasks>

<verification>
- `check_permissions(valid_client)` returns passed=True
- `check_permissions(forbidden_client)` returns passed=False with 403
- Empty issue list still returns passed=True (permissions exist, just no data)
- Error responses have sanitized response_body
- All TestCheckPermissions tests pass
</verification>

<success_criteria>
1. check_permissions function exists in health.py
2. Returns VerificationCheck with name="Permissions"
3. Uses GraphQL issues query with first:1 for efficiency
4. Success confirms read access (even with empty results)
5. HTTP errors include status and sanitized response
6. GraphQL errors are caught and reported
7. All tests pass
</success_criteria>

<output>
After completion, create `.planning/phases/05-health-check-foundation/05-05-SUMMARY.md`
</output>

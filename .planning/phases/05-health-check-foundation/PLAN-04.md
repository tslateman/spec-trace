---
phase: 05-health-check-foundation
plan: 04
type: execute
wave: 2
depends_on: ["05-01", "05-02"]
files_modified:
  - spectrace/requirements/health.py
  - spectrace/requirements/tests/test_health.py
autonomous: true

must_haves:
  truths:
    - "Authentication check makes actual API request to Linear"
    - "Authentication check uses GraphQL viewer query"
    - "Successful auth shows authenticated user name/email"
    - "Failed auth includes HTTP status code in error"
    - "Failed auth includes sanitized response body"
  artifacts:
    - path: "spectrace/requirements/health.py"
      provides: "check_authentication function"
      exports: ["check_authentication"]
    - path: "spectrace/requirements/tests/test_health.py"
      provides: "Unit tests for authentication check"
      contains: "test_check_authentication"
  key_links:
    - from: "spectrace/requirements/health.py:check_authentication"
      to: "LinearClient._execute_query"
      via: "viewer query execution"
      pattern: "_execute_query.*viewer"
    - from: "spectrace/requirements/health.py:check_authentication"
      to: "_sanitize_response"
      via: "error response sanitization"
      pattern: "_sanitize_response"
---

<objective>
Create authentication check function that verifies Linear API token validity.

Purpose: Part of HEALTH-02 (granular diagnostic checks). This check makes an actual API request using the viewer query to verify the token is valid and retrieve authenticated user info. Failed attempts include HTTP status and sanitized response for debugging (HEALTH-04).

Output: `check_authentication()` function that returns VerificationCheck with API validation result
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
@spectrace/requirements/linear.py (LinearClient with _execute_query method)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create check_authentication function</name>
  <files>spectrace/requirements/health.py</files>
  <action>
Add to `spectrace/requirements/health.py` after check_configuration:

```python
def check_authentication(client) -> VerificationCheck:
    """Verify Linear API token validity with viewer query.

    Makes actual API request to Linear using the GraphQL viewer query,
    which returns the authenticated user's info. This validates that
    the API key is not just formatted correctly but actually works.

    Args:
        client: LinearClient instance (from requirements.linear)

    Returns:
        VerificationCheck with passed=True if authenticated,
        or passed=False with error details including status code
        and sanitized response body
    """
    import requests

    try:
        result = client._execute_query("""
            query Me {
                viewer {
                    id
                    name
                    email
                }
            }
        """)

        viewer = result.get('viewer', {})
        name = viewer.get('name', 'Unknown')
        email = viewer.get('email', 'unknown@example.com')

        return VerificationCheck(
            name="Authentication",
            passed=True,
            details=f"Authenticated as {name} ({email})",
            response_status=200
        )

    except requests.HTTPError as e:
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"HTTP {e.response.status_code}: Authentication failed",
            response_status=e.response.status_code,
            response_body=_sanitize_response(e.response.text)
        )
    except ValueError as e:
        # GraphQL errors raised by _execute_query
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"GraphQL error: {str(e)}"
        )
    except Exception as e:
        # Network errors, timeouts, etc.
        return VerificationCheck(
            name="Authentication",
            passed=False,
            error_message=f"Request failed: {type(e).__name__}: {str(e)}"
        )
```

Note: Import requests inside function to isolate dependency. Uses _sanitize_response from Plan 02.
  </action>
  <verify>
    `python -c "from requirements.health import check_authentication; print('Import OK')"`
  </verify>
  <done>
    check_authentication function exists and can be imported.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add authentication check tests with mocking</name>
  <files>spectrace/requirements/tests/test_health.py</files>
  <action>
Add to `spectrace/requirements/tests/test_health.py`:

```python
from unittest.mock import Mock, patch
import requests

from requirements.health import check_authentication

class TestCheckAuthentication:
    """Tests for check_authentication function."""

    def test_successful_authentication(self):
        """Valid token returns passed=True with user info."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {
            'viewer': {
                'id': 'user-123',
                'name': 'Test User',
                'email': 'test@example.com'
            }
        }

        result = check_authentication(mock_client)

        assert result.passed is True
        assert result.name == "Authentication"
        assert 'Test User' in result.details
        assert 'test@example.com' in result.details
        assert result.response_status == 200
        assert result.error_message is None

    def test_http_401_unauthorized(self):
        """401 error returns passed=False with status and sanitized body."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = '{"error": "Invalid API key: lin_api_secret123"}'

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_client._execute_query.side_effect = http_error

        result = check_authentication(mock_client)

        assert result.passed is False
        assert result.name == "Authentication"
        assert '401' in result.error_message
        assert result.response_status == 401
        # API key should be sanitized
        assert 'lin_api_secret123' not in (result.response_body or '')
        assert '[REDACTED]' in (result.response_body or '')

    def test_http_403_forbidden(self):
        """403 error returns passed=False."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = '{"error": "Forbidden"}'

        http_error = requests.HTTPError()
        http_error.response = mock_response
        mock_client._execute_query.side_effect = http_error

        result = check_authentication(mock_client)

        assert result.passed is False
        assert '403' in result.error_message
        assert result.response_status == 403

    def test_graphql_error(self):
        """GraphQL error from _execute_query returns passed=False."""
        mock_client = Mock()
        mock_client._execute_query.side_effect = ValueError("GraphQL errors: [{'message': 'Invalid query'}]")

        result = check_authentication(mock_client)

        assert result.passed is False
        assert 'GraphQL error' in result.error_message

    def test_network_error(self):
        """Network error returns passed=False with exception info."""
        mock_client = Mock()
        mock_client._execute_query.side_effect = requests.ConnectionError("Connection refused")

        result = check_authentication(mock_client)

        assert result.passed is False
        assert 'ConnectionError' in result.error_message

    def test_timeout_error(self):
        """Timeout error returns passed=False."""
        mock_client = Mock()
        mock_client._execute_query.side_effect = requests.Timeout("Request timed out")

        result = check_authentication(mock_client)

        assert result.passed is False
        assert 'Timeout' in result.error_message

    def test_check_has_timestamp(self):
        """Authentication check includes timestamp."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {
            'viewer': {'id': '1', 'name': 'Test', 'email': 'test@test.com'}
        }

        result = check_authentication(mock_client)

        assert result.timestamp is not None
        assert result.timestamp.endswith('Z')
```

Note: Uses Mock to simulate LinearClient - no real API calls in tests.
  </action>
  <verify>
    `cd /Users/tslater/dev/spec-trace/spectrace && python -m pytest requirements/tests/test_health.py::TestCheckAuthentication -v`
  </verify>
  <done>
    All authentication check tests pass, confirming success and various failure scenarios are handled correctly.
  </done>
</task>

</tasks>

<verification>
- `check_authentication(valid_client)` returns passed=True with user details
- `check_authentication(invalid_client)` returns passed=False with HTTP status
- Error responses have sanitized response_body (no lin_api_ tokens)
- GraphQL errors are caught and reported
- Network errors are caught and reported
- All TestCheckAuthentication tests pass
</verification>

<success_criteria>
1. check_authentication function exists in health.py
2. Returns VerificationCheck with name="Authentication"
3. Makes actual GraphQL viewer query via LinearClient
4. Success shows authenticated user name and email
5. HTTP errors include status code and sanitized response body
6. GraphQL errors are caught and reported
7. Network errors (ConnectionError, Timeout) are caught
8. All tests pass
</success_criteria>

<output>
After completion, create `.planning/phases/05-health-check-foundation/05-04-SUMMARY.md`
</output>

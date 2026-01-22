---
phase: 05-health-check-foundation
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - spectrace/requirements/health.py
  - spectrace/requirements/tests/test_health.py
autonomous: true

must_haves:
  truths:
    - "_sanitize_response removes lin_api_ tokens from responses"
    - "_sanitize_response removes Bearer tokens from responses"
    - "_sanitize_response truncates long responses"
    - "Sensitive data never appears in response_body field"
  artifacts:
    - path: "spectrace/requirements/health.py"
      provides: "_sanitize_response function"
      exports: ["_sanitize_response"]
    - path: "spectrace/requirements/tests/test_health.py"
      provides: "Unit tests for sanitization"
      contains: "test_sanitize_response"
  key_links:
    - from: "spectrace/requirements/health.py"
      to: "VerificationCheck.response_body"
      via: "_sanitize_response function"
      pattern: "_sanitize_response"
---

<objective>
Create response sanitization function to remove credentials from error responses.

Purpose: HEALTH-04 requires error responses for debugging, but credentials must be redacted. This function ensures API keys and tokens are never exposed in logs, databases, or API responses.

Output: `_sanitize_response()` function in health.py with comprehensive tests
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/05-health-check-foundation/05-RESEARCH.md

# Pattern reference
@spectrace/requirements/linear.py (API key format: lin_api_*)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create _sanitize_response function</name>
  <files>spectrace/requirements/health.py</files>
  <action>
Add to `spectrace/requirements/health.py` (after imports, before dataclasses):

```python
def _sanitize_response(response_text: str, max_length: int = 500) -> str:
    """Sanitize API response by removing credentials and truncating.

    Removes:
    - Linear API keys (lin_api_...)
    - Bearer tokens
    - Authorization header values

    Args:
        response_text: Raw response body
        max_length: Maximum length of sanitized response

    Returns:
        Sanitized response string safe for logging/storage
    """
    import re

    # Truncate first to limit processing
    sanitized = response_text[:max_length]

    # Remove API key patterns (lin_api_...)
    sanitized = re.sub(r'lin_api_[A-Za-z0-9_-]+', '[REDACTED]', sanitized)

    # Remove bearer tokens
    sanitized = re.sub(r'Bearer\s+[A-Za-z0-9_.-]+', 'Bearer [REDACTED]', sanitized, flags=re.IGNORECASE)

    # Remove authorization headers in JSON
    sanitized = re.sub(r'"authorization":\s*"[^"]*"', '"authorization": "[REDACTED]"', sanitized, flags=re.IGNORECASE)

    if len(response_text) > max_length:
        sanitized += '... [truncated]'

    return sanitized
```

Note: Import `re` inside function to avoid module-level import (keeps health.py imports minimal). This matches research guidance.
  </action>
  <verify>
    `python -c "from requirements.health import _sanitize_response; print(_sanitize_response('key: lin_api_test123'))"`
  </verify>
  <done>
    _sanitize_response function exists and redacts lin_api_ patterns.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add comprehensive sanitization tests</name>
  <files>spectrace/requirements/tests/test_health.py</files>
  <action>
Add to `spectrace/requirements/tests/test_health.py`:

```python
from requirements.health import _sanitize_response

class TestSanitizeResponse:
    """Tests for _sanitize_response function."""

    def test_sanitize_linear_api_key(self):
        """API keys matching lin_api_* pattern are redacted."""
        response = '{"error": "Invalid key: lin_api_ABC123xyz_test"}'
        result = _sanitize_response(response)
        assert 'lin_api_' not in result
        assert '[REDACTED]' in result

    def test_sanitize_bearer_token(self):
        """Bearer tokens are redacted."""
        response = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test'
        result = _sanitize_response(response)
        assert 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' not in result
        assert 'Bearer [REDACTED]' in result

    def test_sanitize_authorization_header_json(self):
        """Authorization header values in JSON are redacted."""
        response = '{"headers": {"authorization": "lin_api_secret123"}}'
        result = _sanitize_response(response)
        assert 'lin_api_secret123' not in result
        assert '"authorization": "[REDACTED]"' in result

    def test_truncate_long_response(self):
        """Responses longer than max_length are truncated."""
        long_response = 'x' * 1000
        result = _sanitize_response(long_response, max_length=100)
        assert len(result) < 150  # 100 + truncation message
        assert '[truncated]' in result

    def test_no_truncation_short_response(self):
        """Short responses are not truncated."""
        short_response = 'Error: Not found'
        result = _sanitize_response(short_response)
        assert result == short_response
        assert '[truncated]' not in result

    def test_multiple_credentials(self):
        """Multiple credentials in same response are all redacted."""
        response = 'key1: lin_api_first, key2: lin_api_second, Bearer token123'
        result = _sanitize_response(response)
        assert 'lin_api_first' not in result
        assert 'lin_api_second' not in result
        assert 'token123' not in result
        assert result.count('[REDACTED]') >= 2

    def test_empty_response(self):
        """Empty response returns empty string."""
        assert _sanitize_response('') == ''

    def test_safe_content_unchanged(self):
        """Content without credentials is unchanged."""
        response = '{"error": "Rate limit exceeded", "status": 429}'
        result = _sanitize_response(response)
        assert result == response
```

Run tests to verify all sanitization scenarios work correctly.
  </action>
  <verify>
    `cd /Users/tslater/dev/spec-trace/spectrace && python -m pytest requirements/tests/test_health.py::TestSanitizeResponse -v`
  </verify>
  <done>
    All sanitization tests pass, confirming lin_api_, Bearer tokens, and authorization headers are redacted.
  </done>
</task>

</tasks>

<verification>
- `_sanitize_response('lin_api_test')` returns string with '[REDACTED]'
- `_sanitize_response('Bearer abc123')` returns 'Bearer [REDACTED]'
- Long responses (>500 chars) are truncated with '... [truncated]'
- All TestSanitizeResponse tests pass
</verification>

<success_criteria>
1. _sanitize_response function exists in health.py
2. Linear API keys (lin_api_*) are redacted
3. Bearer tokens are redacted
4. Authorization header values in JSON are redacted
5. Long responses are truncated
6. All sanitization tests pass
</success_criteria>

<output>
After completion, create `.planning/phases/05-health-check-foundation/05-02-SUMMARY.md`
</output>

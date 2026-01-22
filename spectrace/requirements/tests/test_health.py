"""Tests for health check utilities."""
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

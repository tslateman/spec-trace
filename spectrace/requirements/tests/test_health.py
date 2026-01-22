"""Tests for health check utilities and domain objects."""
import time
from unittest.mock import Mock

import requests

from requirements.health import (
    TestConnectionResult,
    VerificationCheck,
    _sanitize_response,
    check_configuration,
    check_permissions,
)


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


class TestVerificationCheck:
    """Tests for VerificationCheck dataclass."""

    def test_verification_check_creation(self):
        """Basic creation with required fields works."""
        check = VerificationCheck(name="Configuration", passed=True)

        assert check.name == "Configuration"
        assert check.passed is True
        # Optional fields default to None
        assert check.details is None
        assert check.error_message is None
        assert check.response_status is None
        assert check.response_body is None
        # timestamp is auto-generated
        assert check.timestamp is not None

    def test_verification_check_timestamp_auto_generated(self):
        """Each instance gets a unique auto-generated timestamp."""
        check1 = VerificationCheck(name="Check1", passed=True)
        time.sleep(0.01)  # Small delay to ensure different timestamps
        check2 = VerificationCheck(name="Check2", passed=False)

        # Both have timestamps
        assert check1.timestamp is not None
        assert check2.timestamp is not None

        # Timestamps are different (proving per-instance generation)
        assert check1.timestamp != check2.timestamp

        # Timestamp format is ISO 8601 (ends with 'Z')
        assert check1.timestamp.endswith('Z')
        assert check2.timestamp.endswith('Z')

        # Timestamp has expected format (contains T separator)
        assert 'T' in check1.timestamp

    def test_verification_check_failure_fields(self):
        """Error fields are set correctly for failures."""
        check = VerificationCheck(
            name="Authentication",
            passed=False,
            error_message="Invalid API key",
            response_status=401,
            response_body='{"error": "unauthorized"}',
        )

        assert check.name == "Authentication"
        assert check.passed is False
        assert check.error_message == "Invalid API key"
        assert check.response_status == 401
        assert check.response_body == '{"error": "unauthorized"}'

    def test_verification_check_success_details(self):
        """Details field captures success information."""
        check = VerificationCheck(
            name="API Access",
            passed=True,
            details="Successfully retrieved team information",
            response_status=200,
        )

        assert check.passed is True
        assert check.details == "Successfully retrieved team information"
        assert check.response_status == 200


class TestTestConnectionResult:
    """Tests for TestConnectionResult dataclass."""

    def test_connection_result_success(self):
        """Successful result with checks list."""
        checks = [
            VerificationCheck(name="Config", passed=True, details="API key configured"),
            VerificationCheck(name="Auth", passed=True, details="Authenticated"),
        ]
        result = TestConnectionResult(
            success=True,
            message="Connection successful",
            checks=checks,
        )

        assert result.success is True
        assert result.message == "Connection successful"
        assert result.checks is not None
        assert len(result.checks) == 2
        assert result.checks[0].name == "Config"
        assert result.checks[1].name == "Auth"
        assert result.error_details is None

    def test_connection_result_failure(self):
        """Failed result with error details."""
        checks = [
            VerificationCheck(name="Config", passed=True),
            VerificationCheck(
                name="Auth",
                passed=False,
                error_message="API key invalid",
            ),
        ]
        result = TestConnectionResult(
            success=False,
            message="Connection failed: Authentication error",
            checks=checks,
            error_details="The API key was rejected by the server",
        )

        assert result.success is False
        assert "failed" in result.message.lower()
        assert result.checks is not None
        assert len(result.checks) == 2
        assert result.error_details == "The API key was rejected by the server"

    def test_connection_result_catastrophic_error(self):
        """Catastrophic error with no checks completed."""
        result = TestConnectionResult(
            success=False,
            message="Connection failed: Network unreachable",
            checks=None,
            error_details="Could not resolve hostname: api.linear.app",
        )

        assert result.success is False
        assert result.checks is None
        assert result.error_details is not None
        assert "hostname" in result.error_details.lower()

    def test_connection_result_empty_checks(self):
        """Result with empty checks list (different from None)."""
        result = TestConnectionResult(
            success=True,
            message="No checks required",
            checks=[],
        )

        assert result.success is True
        assert result.checks is not None
        assert len(result.checks) == 0


class TestCheckConfiguration:
    """Tests for check_configuration function."""

    def test_valid_configuration(self):
        """Valid configuration returns passed=True with details."""
        result = check_configuration(
            api_key="lin_api_abc123",
            workspace="my-workspace",
            team="my-team"
        )

        assert result.passed is True
        assert result.name == "Configuration"
        assert result.error_message is None
        assert "API key present" in result.details
        assert "my-workspace" in result.details
        assert "my-team" in result.details

    def test_missing_api_key(self):
        """Empty API key returns specific error message."""
        result = check_configuration(
            api_key="",
            workspace="my-workspace",
            team="my-team"
        )

        assert result.passed is False
        assert result.name == "Configuration"
        assert result.error_message == "LINEAR_API_KEY not configured"

    def test_invalid_api_key_format(self):
        """API key without lin_api_ prefix returns format error."""
        result = check_configuration(
            api_key="invalid_key_format",
            workspace="my-workspace",
            team="my-team"
        )

        assert result.passed is False
        assert result.name == "Configuration"
        assert "does not match expected format" in result.error_message
        assert "lin_api_" in result.error_message

    def test_missing_workspace(self):
        """Empty workspace returns specific error message."""
        result = check_configuration(
            api_key="lin_api_abc123",
            workspace="",
            team="my-team"
        )

        assert result.passed is False
        assert result.name == "Configuration"
        assert result.error_message == "LINEAR_WORKSPACE not configured"

    def test_missing_team(self):
        """Empty team returns specific error message."""
        result = check_configuration(
            api_key="lin_api_abc123",
            workspace="my-workspace",
            team=""
        )

        assert result.passed is False
        assert result.name == "Configuration"
        assert result.error_message == "LINEAR_TEAM not configured"

    def test_none_values_treated_as_missing(self):
        """None values are treated as missing (falsy check)."""
        # None api_key
        result = check_configuration(
            api_key=None,
            workspace="my-workspace",
            team="my-team"
        )
        assert result.passed is False
        assert "LINEAR_API_KEY not configured" in result.error_message

        # None workspace (with valid api_key)
        result = check_configuration(
            api_key="lin_api_abc123",
            workspace=None,
            team="my-team"
        )
        assert result.passed is False
        assert "LINEAR_WORKSPACE not configured" in result.error_message

        # None team (with valid api_key and workspace)
        result = check_configuration(
            api_key="lin_api_abc123",
            workspace="my-workspace",
            team=None
        )
        assert result.passed is False
        assert "LINEAR_TEAM not configured" in result.error_message

    def test_check_has_timestamp(self):
        """Configuration check result includes auto-generated timestamp."""
        result = check_configuration(
            api_key="lin_api_abc123",
            workspace="my-workspace",
            team="my-team"
        )

        assert result.timestamp is not None
        assert result.timestamp.endswith('Z')
        assert 'T' in result.timestamp


class TestCheckPermissions:
    """Tests for check_permissions function."""

    def test_successful_permissions_with_issues(self):
        """Successful query with issues returns passed=True."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {
            'issues': {
                'nodes': [{'id': 'issue-123'}]
            }
        }

        result = check_permissions(mock_client)

        assert result.passed is True
        assert result.name == "Permissions"
        assert result.response_status == 200
        assert "Read access" in result.details
        assert result.error_message is None

    def test_successful_permissions_no_issues(self):
        """Empty issues result (no issues exist) is still success."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {
            'issues': {
                'nodes': []
            }
        }

        result = check_permissions(mock_client)

        assert result.passed is True
        assert result.name == "Permissions"
        assert result.response_status == 200
        assert "Read access" in result.details

    def test_http_403_forbidden(self):
        """HTTP 403 returns failed check with status code."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = '{"error": "Forbidden"}'
        http_error = requests.HTTPError(response=mock_response)
        mock_client._execute_query.side_effect = http_error

        result = check_permissions(mock_client)

        assert result.passed is False
        assert result.name == "Permissions"
        assert result.response_status == 403
        assert "HTTP 403" in result.error_message
        assert "Insufficient permissions" in result.error_message

    def test_graphql_permission_error(self):
        """GraphQL permission error (ValueError) returns failed check."""
        mock_client = Mock()
        mock_client._execute_query.side_effect = ValueError(
            "GraphQL errors: [{'message': 'Not authorized'}]"
        )

        result = check_permissions(mock_client)

        assert result.passed is False
        assert result.name == "Permissions"
        assert "GraphQL error" in result.error_message
        assert "Not authorized" in result.error_message

    def test_sanitized_response_on_error(self):
        """Error responses have credentials sanitized."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = '{"error": "Invalid key: lin_api_secret123"}'
        http_error = requests.HTTPError(response=mock_response)
        mock_client._execute_query.side_effect = http_error

        result = check_permissions(mock_client)

        assert result.passed is False
        assert result.response_body is not None
        assert 'lin_api_secret123' not in result.response_body
        assert '[REDACTED]' in result.response_body

    def test_check_has_timestamp(self):
        """Permissions check result includes auto-generated timestamp."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {
            'issues': {'nodes': []}
        }

        result = check_permissions(mock_client)

        assert result.timestamp is not None
        assert result.timestamp.endswith('Z')
        assert 'T' in result.timestamp
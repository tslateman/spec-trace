"""Tests for step executors.

Tests cover:
- api_call executor (HTTP requests, status verification)
- assertion executor (field validation with operators)
- wait executor (delay execution)
- execute_step dispatcher
- Engine integration with executors
"""

from unittest.mock import Mock, patch

import pytest
import responses

from requirements.flows.executors import STEP_EXECUTORS, execute_step
from requirements.flows.executors.api_call import execute_api_call_step
from requirements.flows.executors.assertion import execute_assertion_step
from requirements.flows.executors.wait import execute_wait_step
from requirements.flows.engine import SequentialFlowEngine
from requirements.models import VerificationFlow, VerificationFlowStatus


# ============================================================================
# API Call Executor Tests
# ============================================================================


class TestExecuteApiCallStep:
    """Tests for execute_api_call_step."""

    @responses.activate
    def test_execute_api_call_step__success_with_expected_status(self):
        """Successful GET returns passed check."""
        responses.add(
            responses.GET,
            "https://api.example.com/health",
            json={"status": "ok"},
            status=200,
        )

        step_def = {
            "name": "health_check",
            "type": "api_call",
            "config": {
                "url": "https://api.example.com/health",
                "method": "GET",
                "expected_status": 200,
            },
        }

        check, ctx = execute_api_call_step(step_def, {})

        assert check.passed is True
        assert check.name == "health_check"
        assert check.response_status == 200
        assert ctx["last_response"] == {"status": "ok"}

    @responses.activate
    def test_execute_api_call_step__failure_with_wrong_status(self):
        """Wrong status code returns failed check."""
        responses.add(
            responses.GET,
            "https://api.example.com/health",
            json={"error": "Internal Server Error"},
            status=500,
        )

        step_def = {
            "name": "health_check",
            "type": "api_call",
            "config": {
                "url": "https://api.example.com/health",
                "expected_status": 200,
            },
        }

        check, ctx = execute_api_call_step(step_def, {})

        assert check.passed is False
        assert "Expected status 200, got 500" in check.error_message
        assert check.response_status == 500

    @responses.activate
    def test_execute_api_call_step__stores_json_response_in_context(self):
        """JSON response is stored in last_response."""
        responses.add(
            responses.GET,
            "https://api.example.com/users/1",
            json={"id": 1, "name": "Alice", "email": "alice@example.com"},
            status=200,
        )

        step_def = {
            "name": "get_user",
            "type": "api_call",
            "config": {"url": "https://api.example.com/users/1"},
        }

        check, ctx = execute_api_call_step(step_def, {})

        assert ctx["last_response"]["id"] == 1
        assert ctx["last_response"]["name"] == "Alice"

    @responses.activate
    def test_execute_api_call_step__truncates_large_response_body(self):
        """Response body > 1000 chars is truncated."""
        large_body = "x" * 2000
        responses.add(
            responses.GET,
            "https://api.example.com/large",
            body=large_body,
            status=200,
        )

        step_def = {
            "name": "large_response",
            "type": "api_call",
            "config": {"url": "https://api.example.com/large"},
        }

        check, ctx = execute_api_call_step(step_def, {})

        assert len(check.response_body) <= 1020  # 1000 + "... [truncated]"
        assert "truncated" in check.response_body

    @responses.activate
    def test_execute_api_call_step__handles_timeout(self):
        """Request timeout returns failed check."""
        import requests

        responses.add(
            responses.GET,
            "https://api.example.com/slow",
            body=requests.Timeout("Connection timed out"),
        )

        step_def = {
            "name": "slow_endpoint",
            "type": "api_call",
            "config": {"url": "https://api.example.com/slow", "timeout": 5},
        }

        check, ctx = execute_api_call_step(step_def, {})

        assert check.passed is False
        assert "timed out" in check.error_message

    @responses.activate
    def test_execute_api_call_step__handles_connection_error(self):
        """Connection error returns failed check."""
        import requests

        responses.add(
            responses.GET,
            "https://api.example.com/unreachable",
            body=requests.ConnectionError("Network unreachable"),
        )

        step_def = {
            "name": "unreachable",
            "type": "api_call",
            "config": {"url": "https://api.example.com/unreachable"},
        }

        check, ctx = execute_api_call_step(step_def, {})

        assert check.passed is False
        assert "Connection error" in check.error_message

    @responses.activate
    def test_execute_api_call_step__merges_context_headers(self):
        """Headers from context and config are merged."""
        responses.add(
            responses.GET,
            "https://api.example.com/auth",
            json={"authenticated": True},
            status=200,
        )

        step_def = {
            "name": "auth_request",
            "type": "api_call",
            "config": {
                "url": "https://api.example.com/auth",
                "headers": {"X-Custom": "custom-value"},
            },
        }
        context = {"headers": {"Authorization": "Bearer token123"}}

        check, ctx = execute_api_call_step(step_def, context)

        assert check.passed is True
        # Both headers should have been sent
        request = responses.calls[0].request
        assert request.headers["Authorization"] == "Bearer token123"
        assert request.headers["X-Custom"] == "custom-value"

    @responses.activate
    def test_execute_api_call_step__supports_base_url_prefix(self):
        """URL starting with / uses base_url from context."""
        responses.add(
            responses.GET,
            "https://myapi.example.com/api/v1/users",
            json={"users": []},
            status=200,
        )

        step_def = {
            "name": "list_users",
            "type": "api_call",
            "config": {"url": "/api/v1/users"},
        }
        context = {"base_url": "https://myapi.example.com"}

        check, ctx = execute_api_call_step(step_def, context)

        assert check.passed is True


# ============================================================================
# Assertion Executor Tests
# ============================================================================


class TestExecuteAssertionStep:
    """Tests for execute_assertion_step."""

    def test_execute_assertion_step__equals_passes(self):
        """Field equals expected value passes."""
        step_def = {
            "name": "check_status",
            "type": "assertion",
            "config": {"field": "status", "operator": "equals", "value": "ok"},
        }
        context = {"last_response": {"status": "ok"}}

        check, ctx = execute_assertion_step(step_def, context)

        assert check.passed is True
        assert "equals" in check.details

    def test_execute_assertion_step__equals_fails(self):
        """Field not equal to expected value fails."""
        step_def = {
            "name": "check_status",
            "type": "assertion",
            "config": {"field": "status", "operator": "equals", "value": "ok"},
        }
        context = {"last_response": {"status": "error"}}

        check, ctx = execute_assertion_step(step_def, context)

        assert check.passed is False
        assert "expected 'ok'" in check.error_message
        assert "got 'error'" in check.error_message

    def test_execute_assertion_step__contains_passes(self):
        """Value contains substring passes."""
        step_def = {
            "name": "check_message",
            "type": "assertion",
            "config": {
                "field": "message",
                "operator": "contains",
                "value": "success",
            },
        }
        context = {"last_response": {"message": "Operation completed successfully"}}

        check, ctx = execute_assertion_step(step_def, context)

        assert check.passed is True

    def test_execute_assertion_step__exists_passes(self):
        """Field exists (not None) passes."""
        step_def = {
            "name": "check_id",
            "type": "assertion",
            "config": {"field": "id", "operator": "exists"},
        }
        context = {"last_response": {"id": 123}}

        check, ctx = execute_assertion_step(step_def, context)

        assert check.passed is True

    def test_execute_assertion_step__not_empty_passes(self):
        """Field is truthy passes."""
        step_def = {
            "name": "check_items",
            "type": "assertion",
            "config": {"field": "items", "operator": "not_empty"},
        }
        context = {"last_response": {"items": [1, 2, 3]}}

        check, ctx = execute_assertion_step(step_def, context)

        assert check.passed is True

    def test_execute_assertion_step__nested_field_access(self):
        """Dot notation accesses nested fields."""
        step_def = {
            "name": "check_user_name",
            "type": "assertion",
            "config": {
                "field": "data.user.name",
                "operator": "equals",
                "value": "Alice",
            },
        }
        context = {"last_response": {"data": {"user": {"name": "Alice"}}}}

        check, ctx = execute_assertion_step(step_def, context)

        assert check.passed is True

    def test_execute_assertion_step__missing_source_fails(self):
        """Source not in context fails."""
        step_def = {
            "name": "check_value",
            "type": "assertion",
            "config": {"field": "status", "operator": "equals", "value": "ok"},
        }
        context = {}  # No last_response

        check, ctx = execute_assertion_step(step_def, context)

        assert check.passed is False
        assert "not found in context" in check.error_message

    def test_execute_assertion_step__unknown_operator_fails(self):
        """Invalid operator returns error."""
        step_def = {
            "name": "check_value",
            "type": "assertion",
            "config": {"field": "status", "operator": "invalid_op", "value": "ok"},
        }
        context = {"last_response": {"status": "ok"}}

        check, ctx = execute_assertion_step(step_def, context)

        assert check.passed is False
        assert "Unknown operator" in check.error_message


# ============================================================================
# Wait Executor Tests
# ============================================================================


class TestExecuteWaitStep:
    """Tests for execute_wait_step."""

    @patch("requirements.flows.executors.wait.time.sleep", autospec=True)
    def test_execute_wait_step__waits_correct_duration(self, mock_sleep):
        """Wait calls time.sleep with configured seconds."""
        step_def = {
            "name": "pause",
            "type": "wait",
            "config": {"seconds": 5},
        }

        check, ctx = execute_wait_step(step_def, {})

        mock_sleep.assert_called_once_with(5)
        assert check.passed is True

    @patch("requirements.flows.executors.wait.time.sleep", autospec=True)
    def test_execute_wait_step__always_passes(self, mock_sleep):
        """Wait steps always return passed=True."""
        step_def = {"name": "wait", "type": "wait", "config": {}}

        check, ctx = execute_wait_step(step_def, {})

        assert check.passed is True
        assert "Waited" in check.details


# ============================================================================
# Execute Step Dispatcher Tests
# ============================================================================


class TestExecuteStep:
    """Tests for execute_step dispatcher."""

    @responses.activate
    def test_execute_step__dispatches_to_api_call(self):
        """type='api_call' routes to api_call executor."""
        responses.add(
            responses.GET,
            "https://api.example.com/test",
            json={"ok": True},
            status=200,
        )

        step_def = {
            "name": "test_api",
            "type": "api_call",
            "config": {"url": "https://api.example.com/test"},
        }

        check, ctx = execute_step(step_def, {})

        assert check.passed is True
        assert "last_response" in ctx

    def test_execute_step__dispatches_to_assertion(self):
        """type='assertion' routes to assertion executor."""
        step_def = {
            "name": "check",
            "type": "assertion",
            "config": {"field": "status", "operator": "equals", "value": "ok"},
        }
        context = {"last_response": {"status": "ok"}}

        check, ctx = execute_step(step_def, context)

        assert check.passed is True

    def test_execute_step__dispatches_to_handler(self):
        """type='handler' routes to handler executor."""
        step_def = {
            "name": "config_check",
            "type": "handler",
            "handler": "requirements.flows.handlers.linear.check_configuration",
        }
        context = {
            "api_key": "lin_api_test123",
            "workspace": "ws",
            "team": "tm",
        }

        check, ctx = execute_step(step_def, context)

        assert check.passed is True
        assert check.name == "Configuration"

    def test_execute_step__unknown_type_returns_error(self):
        """Unknown step type returns failed check."""
        step_def = {
            "name": "mystery",
            "type": "unknown_type",
            "config": {},
        }

        check, ctx = execute_step(step_def, {})

        assert check.passed is False
        assert "Unknown step type" in check.error_message


# ============================================================================
# Engine Integration Tests
# ============================================================================


@pytest.fixture
def api_call_flow(db):
    """Create a flow with an api_call step."""
    return VerificationFlow.objects.create(
        name="api-test-flow",
        display_name="API Test Flow",
        steps=[
            {
                "name": "check_api",
                "type": "api_call",
                "config": {
                    "url": "https://api.example.com/health",
                    "expected_status": 200,
                },
            }
        ],
        version=1,
    )


@pytest.fixture
def flow_with_metadata(db):
    """Create a flow with _metadata entry in steps."""
    return VerificationFlow.objects.create(
        name="metadata-flow",
        display_name="Flow with Metadata",
        steps=[
            {
                "_metadata": {
                    "source_file": "flows/test.yaml",
                    "requirements": ["REQ-001"],
                }
            },
            {
                "name": "config",
                "type": "handler",
                "handler": "requirements.flows.handlers.linear.check_configuration",
            },
        ],
        version=1,
    )


class TestEngineExecutorIntegration:
    """Tests for engine integration with executors."""

    @responses.activate
    def test_engine__executes_api_call_step(self, api_call_flow):
        """Engine executes api_call steps correctly."""
        responses.add(
            responses.GET,
            "https://api.example.com/health",
            json={"status": "healthy"},
            status=200,
        )

        engine = SequentialFlowEngine()
        run = engine.execute(api_call_flow, {})

        assert run.status == VerificationFlowStatus.PASSED
        assert run.steps.count() == 1
        step = run.steps.first()
        assert step.passed is True
        assert step.response_status == 200

    def test_engine__filters_metadata_from_steps(self, flow_with_metadata):
        """_metadata entries are skipped during execution."""
        engine = SequentialFlowEngine()
        # Provide valid config for the handler step
        context = {
            "api_key": "lin_api_test123",
            "workspace": "my-workspace",
            "team": "my-team",
        }

        run = engine.execute(flow_with_metadata, context)

        # Should only execute the config step, not _metadata
        assert run.steps.count() == 1
        assert run.steps.first().name == "Configuration"

    @patch("requirements.flows.engine.SequentialFlowEngine._step_timeout_context")
    def test_engine__step_timeout_recorded_as_failure(self, mock_context, db):
        """Step timeout results in failed step."""
        from requirements.flows.engine import StepTimeoutError

        # Make the context manager raise StepTimeoutError
        mock_context.return_value.__enter__ = Mock(
            side_effect=StepTimeoutError("Step timed out after 1 seconds")
        )
        mock_context.return_value.__exit__ = Mock(return_value=False)

        flow = VerificationFlow.objects.create(
            name="timeout-flow",
            display_name="Timeout Flow",
            steps=[
                {
                    "name": "slow_step",
                    "type": "handler",
                    "handler": "requirements.flows.handlers.linear.check_configuration",
                }
            ],
            version=1,
        )

        engine = SequentialFlowEngine()
        run = engine.execute(flow, {}, step_timeout=1)

        assert run.status == VerificationFlowStatus.FAILED
        step = run.steps.first()
        assert step.passed is False
        assert "timed out" in step.error_message


# ============================================================================
# STEP_EXECUTORS Registry Tests
# ============================================================================


class TestStepExecutorsRegistry:
    """Tests for STEP_EXECUTORS registry."""

    def test_registry_contains_all_types(self):
        """Registry has all expected step types."""
        expected_types = {"handler", "api_call", "assertion", "wait"}
        assert set(STEP_EXECUTORS.keys()) == expected_types

    def test_all_executors_are_callable(self):
        """All registered executors are callable."""
        for name, executor in STEP_EXECUTORS.items():
            assert callable(executor), f"Executor '{name}' is not callable"

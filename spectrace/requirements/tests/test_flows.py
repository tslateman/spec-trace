"""Tests for verification flows system.

Tests cover:
- Flow definitions (dataclasses, registry)
- Flow engine (sequential execution, early-exit)
- Flow sync (code to database)
- Linear handlers
- TestConnectionResult.from_flow_run()
"""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import requests

from requirements.flows.definitions import (
    REGISTERED_FLOWS,
    FlowDef,
    FlowStepDef,
    get_flow_by_name,
)
from requirements.flows.engine import SequentialFlowEngine, load_handler
from requirements.flows.handlers.linear import (
    check_authentication,
    check_configuration,
    check_permissions,
)
from requirements.flows.sync import sync_flows_safe, sync_flows_to_db
from requirements.health import TestConnectionResult
from requirements.models import (
    VerificationFlow,
    VerificationFlowRun,
    VerificationFlowSource,
    VerificationFlowStatus,
    VerificationFlowStep,
)

# ============================================================================
# Flow Definitions Tests
# ============================================================================


class TestFlowStepDef:
    """Tests for FlowStepDef dataclass."""

    def test_creation_with_required_fields(self):
        """Can create with only required fields."""
        step = FlowStepDef(
            name="test",
            handler="module.function",
            display_name="Test Step",
        )

        assert step.name == "test"
        assert step.handler == "module.function"
        assert step.display_name == "Test Step"
        assert step.description == ""  # Default

    def test_creation_with_all_fields(self):
        """Can create with all fields."""
        step = FlowStepDef(
            name="config",
            handler="requirements.flows.handlers.linear.check_configuration",
            display_name="Configuration Check",
            description="Validate API key format",
        )

        assert step.name == "config"
        assert step.description == "Validate API key format"

    def test_to_dict(self):
        """Can convert to dict for JSON storage."""
        step = FlowStepDef(
            name="test",
            handler="module.function",
            display_name="Test",
            description="Description",
        )

        step_dict = asdict(step)

        assert step_dict == {
            "name": "test",
            "handler": "module.function",
            "display_name": "Test",
            "description": "Description",
            "type": "handler",
            "config": {},
        }


class TestFlowDef:
    """Tests for FlowDef dataclass."""

    def test_creation_with_required_fields(self):
        """Can create with only required fields."""
        flow = FlowDef(
            name="test-flow",
            display_name="Test Flow",
            description="A test flow",
        )

        assert flow.name == "test-flow"
        assert flow.display_name == "Test Flow"
        assert flow.description == "A test flow"
        assert flow.steps == []  # Default
        assert flow.version == 1  # Default

    def test_creation_with_steps(self):
        """Can create with steps."""
        steps = [
            FlowStepDef(name="step1", handler="a.b", display_name="Step 1"),
            FlowStepDef(name="step2", handler="c.d", display_name="Step 2"),
        ]
        flow = FlowDef(
            name="test-flow",
            display_name="Test Flow",
            description="A test flow",
            steps=steps,
            version=2,
        )

        assert len(flow.steps) == 2
        assert flow.steps[0].name == "step1"
        assert flow.steps[1].name == "step2"
        assert flow.version == 2


class TestRegisteredFlows:
    """Tests for the REGISTERED_FLOWS registry."""

    def test_linear_connection_flow_registered(self):
        """Linear connection flow is in the registry."""
        flow_names = [f.name for f in REGISTERED_FLOWS]
        assert "linear-connection" in flow_names

    def test_get_flow_by_name_found(self):
        """Can get flow by name."""
        flow = get_flow_by_name("linear-connection")

        assert flow is not None
        assert flow.name == "linear-connection"
        assert len(flow.steps) == 3

    def test_get_flow_by_name_not_found(self):
        """Returns None for unknown flow."""
        flow = get_flow_by_name("nonexistent-flow")
        assert flow is None

    def test_linear_connection_flow_steps(self):
        """Linear connection flow has correct steps."""
        flow = get_flow_by_name("linear-connection")

        step_names = [s.name for s in flow.steps]
        assert step_names == ["config", "auth", "permissions"]

        # Check handlers
        assert "check_configuration" in flow.steps[0].handler
        assert "check_authentication" in flow.steps[1].handler
        assert "check_permissions" in flow.steps[2].handler


# ============================================================================
# Flow Handlers Tests (Linear)
# ============================================================================


class TestLinearCheckConfiguration:
    """Tests for Linear configuration handler."""

    def test_valid_configuration(self):
        """Valid configuration returns success."""
        check, ctx = check_configuration(
            {
                "api_key": "lin_api_abc123",
                "workspace": "my-workspace",
                "team": "my-team",
            }
        )

        assert check.passed is True
        assert check.name == "Configuration"
        assert "API key present" in check.details
        assert ctx == {}  # No context updates

    def test_missing_api_key(self):
        """Missing API key returns failure."""
        check, ctx = check_configuration(
            {
                "workspace": "my-workspace",
                "team": "my-team",
            }
        )

        assert check.passed is False
        assert "LINEAR_API_KEY not configured" in check.error_message

    def test_invalid_api_key_format(self):
        """Invalid API key format returns failure."""
        check, ctx = check_configuration(
            {
                "api_key": "invalid_key",
                "workspace": "my-workspace",
                "team": "my-team",
            }
        )

        assert check.passed is False
        assert "does not match expected format" in check.error_message

    def test_missing_workspace(self):
        """Missing workspace returns failure."""
        check, ctx = check_configuration(
            {
                "api_key": "lin_api_abc123",
                "team": "my-team",
            }
        )

        assert check.passed is False
        assert "LINEAR_WORKSPACE not configured" in check.error_message

    def test_missing_team(self):
        """Missing team returns failure."""
        check, ctx = check_configuration(
            {
                "api_key": "lin_api_abc123",
                "workspace": "my-workspace",
            }
        )

        assert check.passed is False
        assert "LINEAR_TEAM not configured" in check.error_message


class TestLinearCheckAuthentication:
    """Tests for Linear authentication handler."""

    def test_successful_authentication(self):
        """Successful auth returns success and client in context."""
        with patch("requirements.flows.handlers.linear.LinearClient") as MockClient:
            mock_client = Mock()
            mock_client._execute_query.return_value = {
                "viewer": {"id": "1", "name": "Test User", "email": "test@example.com"}
            }
            MockClient.return_value = mock_client

            check, ctx = check_authentication({"api_key": "lin_api_abc123"})

            assert check.passed is True
            assert check.name == "Authentication"
            assert "Authenticated as Test User" in check.details
            assert "client" in ctx
            assert ctx["client"] is mock_client

    def test_http_401_error(self):
        """HTTP 401 returns failure."""
        with patch("requirements.flows.handlers.linear.LinearClient") as MockClient:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = '{"error": "Unauthorized"}'
            http_error = requests.HTTPError(response=mock_response)
            mock_client._execute_query.side_effect = http_error
            MockClient.return_value = mock_client

            check, ctx = check_authentication({"api_key": "lin_api_abc123"})

            assert check.passed is False
            assert check.response_status == 401
            assert "HTTP 401" in check.error_message
            assert ctx == {}

    def test_graphql_error(self):
        """GraphQL error returns failure."""
        with patch("requirements.flows.handlers.linear.LinearClient") as MockClient:
            mock_client = Mock()
            mock_client._execute_query.side_effect = ValueError("GraphQL error")
            MockClient.return_value = mock_client

            check, ctx = check_authentication({"api_key": "lin_api_abc123"})

            assert check.passed is False
            assert "GraphQL error" in check.error_message


class TestLinearCheckPermissions:
    """Tests for Linear permissions handler."""

    def test_successful_permissions(self):
        """Successful permissions check returns success."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {"issues": {"nodes": [{"id": "issue-1"}]}}

        check, ctx = check_permissions({"client": mock_client})

        assert check.passed is True
        assert check.name == "Permissions"
        assert "Read access" in check.details
        assert ctx == {}

    def test_no_client_in_context(self):
        """Missing client returns failure."""
        check, ctx = check_permissions({})

        assert check.passed is False
        assert "No Linear client in context" in check.error_message

    def test_http_403_error(self):
        """HTTP 403 returns failure."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = '{"error": "Forbidden"}'
        http_error = requests.HTTPError(response=mock_response)
        mock_client._execute_query.side_effect = http_error

        check, ctx = check_permissions({"client": mock_client})

        assert check.passed is False
        assert check.response_status == 403
        assert "Insufficient permissions" in check.error_message


# ============================================================================
# Flow Engine Tests
# ============================================================================


@pytest.fixture
def verification_flow(db):
    """Create a test verification flow."""
    return VerificationFlow.objects.create(
        name="test-flow",
        display_name="Test Flow",
        description="Test flow description",
        steps=[
            {
                "name": "step1",
                "handler": "requirements.flows.handlers.linear.check_configuration",
                "display_name": "Step 1",
                "description": "First step",
            },
            {
                "name": "step2",
                "handler": "requirements.flows.handlers.linear.check_authentication",
                "display_name": "Step 2",
                "description": "Second step",
            },
        ],
        version=1,
    )


class TestLoadHandler:
    """Tests for load_handler function."""

    def test_load_existing_handler(self):
        """Can load an existing handler function."""
        handler = load_handler("requirements.flows.handlers.linear.check_configuration")

        # Should be the actual function
        assert callable(handler)
        assert handler.__name__ == "check_configuration"

    def test_load_nonexistent_module(self):
        """Raises ImportError for nonexistent module."""
        with pytest.raises(ImportError):
            load_handler("nonexistent.module.function")

    def test_load_nonexistent_function(self):
        """Raises AttributeError for nonexistent function."""
        with pytest.raises(AttributeError):
            load_handler("requirements.flows.handlers.linear.nonexistent")


class TestSequentialFlowEngine:
    """Tests for SequentialFlowEngine."""

    def test_execute_all_steps_pass(self, db, verification_flow):
        """All passing steps results in PASSED run."""
        with patch("requirements.flows.handlers.linear.LinearClient") as MockClient:
            mock_client = Mock()
            mock_client._execute_query.return_value = {
                "viewer": {"id": "1", "name": "Test", "email": "test@test.com"}
            }
            MockClient.return_value = mock_client

            engine = SequentialFlowEngine()
            run = engine.execute(
                verification_flow,
                {
                    "api_key": "lin_api_test123",
                    "workspace": "ws",
                    "team": "tm",
                },
            )

            assert run.status == VerificationFlowStatus.PASSED
            assert run.completed_at is not None
            assert run.steps.count() == 2
            assert all(s.passed for s in run.steps.all())

    def test_execute_early_exit_on_failure(self, db, verification_flow):
        """First failing step causes early exit."""
        engine = SequentialFlowEngine()
        run = engine.execute(
            verification_flow,
            {
                "api_key": "",  # Will fail config check
                "workspace": "ws",
                "team": "tm",
            },
        )

        assert run.status == VerificationFlowStatus.FAILED
        assert run.completed_at is not None
        # Only first step should have run
        assert run.steps.count() == 1
        step = run.steps.first()
        assert step.passed is False
        assert step.step_order == 0

    def test_execute_records_step_details(self, db, verification_flow):
        """Step details are recorded correctly."""
        engine = SequentialFlowEngine()
        run = engine.execute(
            verification_flow,
            {
                "api_key": "lin_api_test123",
                "workspace": "my-workspace",
                "team": "my-team",
            },
        )

        # Check first step details
        step = run.steps.filter(step_order=0).first()
        assert step.name == "Configuration"
        assert step.passed is True
        assert "API key present" in step.details
        assert step.started_at is not None
        assert step.completed_at is not None

    def test_execute_source_recorded(self, db, verification_flow):
        """Source is recorded on the run."""
        engine = SequentialFlowEngine()

        run = engine.execute(
            verification_flow,
            {"api_key": "", "workspace": "", "team": ""},
            source=VerificationFlowSource.MANUAL,
        )

        assert run.source == VerificationFlowSource.MANUAL

    def test_execute_context_sanitized(self, db, verification_flow):
        """Sensitive context values are sanitized before storage."""
        engine = SequentialFlowEngine()

        run = engine.execute(
            verification_flow,
            {
                "api_key": "lin_api_secret",
                "workspace": "ws",
                "team": "tm",
                "token": "secret-token",
            },
        )

        # API key should be redacted in stored context
        assert run.context.get("api_key") == "[REDACTED]"
        assert run.context.get("token") == "[REDACTED]"
        # Non-sensitive values preserved
        assert run.context.get("workspace") == "ws"

    def test_execute_handler_error_handled(self, db):
        """Handler errors are caught and reported."""
        flow = VerificationFlow.objects.create(
            name="bad-flow",
            display_name="Bad Flow",
            steps=[
                {
                    "name": "bad",
                    "handler": "nonexistent.module.function",
                    "display_name": "Bad Step",
                }
            ],
            version=1,
        )

        engine = SequentialFlowEngine()
        run = engine.execute(flow, {})

        assert run.status == VerificationFlowStatus.FAILED
        step = run.steps.first()
        assert step.passed is False
        assert "Handler error" in step.error_message


# ============================================================================
# Flow Sync Tests
# ============================================================================


class TestSyncFlowsToDb:
    """Tests for sync_flows_to_db function."""

    def test_creates_new_flow(self, db):
        """Creates flow when it doesn't exist."""
        # Delete any existing flows
        VerificationFlow.objects.all().delete()

        result = sync_flows_to_db()

        assert result.get("linear-connection") == "created"
        flow = VerificationFlow.objects.get(name="linear-connection")
        assert flow.display_name == "Linear Connection Verification"
        assert len(flow.steps) == 3
        assert flow.synced_at is not None

    def test_updates_existing_flow(self, db):
        """Updates flow when it already exists."""
        # Create existing flow
        VerificationFlow.objects.create(
            name="linear-connection",
            display_name="Old Name",
            steps=[],
            version=0,
        )

        result = sync_flows_to_db()

        assert result.get("linear-connection") == "updated"
        flow = VerificationFlow.objects.get(name="linear-connection")
        assert flow.display_name == "Linear Connection Verification"
        assert len(flow.steps) == 3

    def test_sync_flows_safe_handles_errors(self, db):
        """sync_flows_safe returns None on error."""
        with patch("requirements.flows.sync.REGISTERED_FLOWS", None):
            result = sync_flows_safe()
            assert result is None


# ============================================================================
# TestConnectionResult.from_flow_run Tests
# ============================================================================


@pytest.fixture
def flow_run_passed(db):
    """Create a passed flow run with steps."""
    flow = VerificationFlow.objects.create(
        name="test-flow",
        display_name="Test Flow",
        steps=[],
        version=1,
    )
    run = VerificationFlowRun.objects.create(
        flow=flow,
        status=VerificationFlowStatus.PASSED,
        completed_at=datetime.now(UTC),
    )
    now = datetime.now(UTC)
    VerificationFlowStep.objects.create(
        flow_run=run,
        step_order=0,
        name="Configuration",
        passed=True,
        details="Config OK",
        started_at=now,
        completed_at=now + timedelta(milliseconds=100),
    )
    VerificationFlowStep.objects.create(
        flow_run=run,
        step_order=1,
        name="Authentication",
        passed=True,
        details="Auth OK",
        started_at=now + timedelta(milliseconds=100),
        completed_at=now + timedelta(milliseconds=200),
    )
    return run


@pytest.fixture
def flow_run_failed(db):
    """Create a failed flow run with steps."""
    flow = VerificationFlow.objects.create(
        name="test-flow-failed",
        display_name="Test Flow",
        steps=[],
        version=1,
    )
    run = VerificationFlowRun.objects.create(
        flow=flow,
        status=VerificationFlowStatus.FAILED,
        completed_at=datetime.now(UTC),
    )
    now = datetime.now(UTC)
    VerificationFlowStep.objects.create(
        flow_run=run,
        step_order=0,
        name="Configuration",
        passed=True,
        details="Config OK",
        started_at=now,
        completed_at=now + timedelta(milliseconds=100),
    )
    VerificationFlowStep.objects.create(
        flow_run=run,
        step_order=1,
        name="Authentication",
        passed=False,
        error_message="Auth failed",
        response_status=401,
        started_at=now + timedelta(milliseconds=100),
        completed_at=now + timedelta(milliseconds=200),
    )
    return run


class TestTestConnectionResultFromFlowRun:
    """Tests for TestConnectionResult.from_flow_run()."""

    def test_from_passed_run(self, flow_run_passed):
        """Creates success result from passed run."""
        result = TestConnectionResult.from_flow_run(flow_run_passed)

        assert result.success is True
        assert result.message == "All checks passed"
        assert len(result.checks) == 2
        assert result.checks[0].name == "Configuration"
        assert result.checks[0].passed is True
        assert result.checks[1].name == "Authentication"
        assert result.checks[1].passed is True

    def test_from_failed_run(self, flow_run_failed):
        """Creates failure result from failed run."""
        result = TestConnectionResult.from_flow_run(flow_run_failed)

        assert result.success is False
        assert "Authentication" in result.message
        assert len(result.checks) == 2
        assert result.checks[0].passed is True
        assert result.checks[1].passed is False
        assert result.checks[1].error_message == "Auth failed"
        assert result.checks[1].response_status == 401

    def test_checks_have_timestamps(self, flow_run_passed):
        """All checks have timestamps."""
        result = TestConnectionResult.from_flow_run(flow_run_passed)

        for check in result.checks:
            assert check.timestamp is not None
            assert "T" in check.timestamp


# ============================================================================
# Integration Tests
# ============================================================================


class TestVerifyLinearConnectionWithFlows:
    """Integration tests for verify_linear_connection using flows."""

    def test_uses_flow_engine_when_synced(self, db):
        """Uses flow engine when flow is synced to DB."""
        # Sync flows first
        sync_flows_to_db()

        with patch("requirements.flows.handlers.linear.LinearClient") as MockClient:
            mock_client = Mock()
            mock_client._execute_query.side_effect = [
                {"viewer": {"id": "1", "name": "Test", "email": "test@test.com"}},
                {"issues": {"nodes": []}},
            ]
            MockClient.return_value = mock_client

            from requirements.health import verify_linear_connection

            result = verify_linear_connection(
                api_key="lin_api_test123",
                workspace="my-workspace",
                team="my-team",
            )

            assert result.success is True
            assert result.message == "All checks passed"
            assert len(result.checks) == 3

            # Verify flow run was created
            run = VerificationFlowRun.objects.filter(flow__name="linear-connection").latest(
                "started_at"
            )
            assert run.status == VerificationFlowStatus.PASSED
            assert run.steps.count() == 3

    def test_fallback_when_flow_not_synced(self, db):
        """Falls back to direct execution when flow not synced."""
        # Delete all flows
        VerificationFlow.objects.all().delete()

        with patch("requirements.health.LinearClient") as MockClient:
            mock_client = Mock()
            mock_client._execute_query.side_effect = [
                {"viewer": {"id": "1", "name": "Test", "email": "test@test.com"}},
                {"issues": {"nodes": []}},
            ]
            MockClient.return_value = mock_client

            from requirements.health import verify_linear_connection

            result = verify_linear_connection(
                api_key="lin_api_test123",
                workspace="my-workspace",
                team="my-team",
            )

            assert result.success is True
            # No flow run created since we used fallback
            assert VerificationFlowRun.objects.count() == 0

    def test_early_exit_on_config_failure(self, db):
        """Config failure short-circuits via flow engine."""
        sync_flows_to_db()

        from requirements.health import verify_linear_connection

        result = verify_linear_connection(
            api_key="",  # Invalid
            workspace="my-workspace",
            team="my-team",
        )

        assert result.success is False
        assert len(result.checks) == 1  # Only config ran
        assert result.checks[0].name == "Configuration"
        assert result.checks[0].passed is False

        # Verify flow run was created and failed
        run = VerificationFlowRun.objects.filter(flow__name="linear-connection").latest(
            "started_at"
        )
        assert run.status == VerificationFlowStatus.FAILED
        assert run.steps.count() == 1

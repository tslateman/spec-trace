"""Tests for SpecTrace validation SDK."""

import json
import os
from unittest.mock import Mock, patch

import pytest
import requests
import responses
from django.test import TestCase, override_settings

from spectrace_client import (
    ValidationClient,
    ValidationRun,
    ValidationStatus,
    verify_requirement,
)


class ValidationClientTests(TestCase):
    """Tests for ValidationClient configuration and submission."""

    def test_from_settings_uses_env_vars(self):
        """Client should read config from environment variables."""
        with patch.dict(
            os.environ,
            {
                "SPECTRACE_URL": "https://spectrace.example.com",
                "SPECTRACE_API_KEY": "test-key-123",
                "SPECTRACE_ENABLED": "true",
            },
        ):
            client = ValidationClient.from_settings()

            assert client.api_url == "https://spectrace.example.com"
            assert client.api_key == "test-key-123"
            assert client.enabled is True

    @override_settings(
        SPECTRACE={
            "API_URL": "https://settings.example.com",
            "API_KEY": "settings-key",
            "ENABLED": False,
        }
    )
    def test_from_settings_uses_django_settings(self):
        """Client should fall back to Django settings if env vars not set."""
        client = ValidationClient.from_settings()

        assert client.api_url == "https://settings.example.com"
        assert client.api_key == "settings-key"
        assert client.enabled is False

    @patch("spectrace_client.client.requests.Session")
    def test_submit_validation_disabled(self, mock_session):
        """Client should skip submission when disabled."""
        client = ValidationClient(
            api_url="https://example.com",
            enabled=False,
        )

        from spectrace_client.models import ValidationResult

        result = ValidationResult(
            requirement_id="REQ-TEST-001",
            name="Test",
            status=ValidationStatus.SUCCESS,
        )

        success = client.submit_validation(result)

        assert success is True
        mock_session.return_value.post.assert_not_called()


class ValidationRunTests(TestCase):
    """Tests for ValidationRun context manager."""

    @patch("spectrace_client.context.ValidationClient")
    def test_validation_run_all_pass(self, mock_client_class):
        """ValidationRun should compute SUCCESS when all steps pass."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client

        with ValidationRun("REQ-TEST-001", "Test Validation") as run:
            run.step("step1", passed=True, details="Step 1 ok")
            run.step("step2", passed=True, details="Step 2 ok")

        assert run.result is not None
        assert run.result.status == ValidationStatus.SUCCESS
        assert len(run.result.steps) == 2
        assert run.result.message == "All 2 checks passed"
        mock_client.submit_validation.assert_called_once()

    @patch("spectrace_client.context.ValidationClient")
    def test_validation_run_mixed_results(self, mock_client_class):
        """ValidationRun should compute DEGRADED when some steps fail."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client

        with ValidationRun("REQ-TEST-001", "Test Validation") as run:
            run.step("step1", passed=True, details="Step 1 ok")
            run.step("step2", passed=False, error_message="Step 2 failed")
            run.step("step3", passed=True, details="Step 3 ok")

        assert run.result is not None
        assert run.result.status == ValidationStatus.DEGRADED
        assert run.result.message == "2 passed, 1 failed"

    @patch("spectrace_client.context.ValidationClient")
    def test_validation_run_all_fail(self, mock_client_class):
        """ValidationRun should compute FAILURE when all steps fail."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client

        with ValidationRun("REQ-TEST-001", "Test Validation") as run:
            run.step("step1", passed=False, error_message="Failed 1")
            run.step("step2", passed=False, error_message="Failed 2")

        assert run.result is not None
        assert run.result.status == ValidationStatus.FAILURE
        assert run.result.message == "All 2 checks failed"

    @patch("spectrace_client.context.ValidationClient")
    def test_validation_run_exception_handling(self, mock_client_class):
        """ValidationRun should mark status as ERROR on exception."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client

        run = None
        with pytest.raises(ValueError):
            with ValidationRun("REQ-TEST-001", "Test Validation") as run:
                run.step("step1", passed=True)
                raise ValueError("Something went wrong")

        assert run is not None
        assert run.result is not None
        assert run.result.status == ValidationStatus.ERROR
        assert "Something went wrong" in run.result.message


class VerifyRequirementDecoratorTests(TestCase):
    """Tests for @verify_requirement decorator."""

    @patch("spectrace_client.decorators.ValidationClient")
    def test_decorator_injects_validation_run(self, mock_client_class):
        """Decorator should inject validation_run kwarg to function."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client

        @verify_requirement("REQ-TEST-001", name="Test")
        def validate_something(validation_run: ValidationRun):
            validation_run.step("check", passed=True)
            return validation_run.result

        result = validate_something()  # type: ignore[call-arg]

        assert result is not None
        assert result.requirement_id == "REQ-TEST-001"
        assert result.status == ValidationStatus.SUCCESS
        mock_client.submit_validation.assert_called_once()

    @patch("spectrace_client.decorators.ValidationClient")
    def test_decorator_with_function_args(self, mock_client_class):
        """Decorator should pass through function args."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client

        @verify_requirement("REQ-TEST-001", name="Test")
        def validate_with_args(obj, validation_run: ValidationRun):
            validation_run.step("check", passed=True, details=f"Checked {obj.name}")
            return validation_run.result

        mock_obj = Mock()
        mock_obj.name = "TestObject"

        result = validate_with_args(mock_obj)  # type: ignore[call-arg]

        assert result is not None
        assert result.steps[0].details == "Checked TestObject"

    @patch("spectrace_client.decorators.ValidationClient")
    def test_decorator_with_context_fn(self, mock_client_class):
        """Decorator should extract context using context_fn."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client

        @verify_requirement(
            "REQ-TEST-001",
            name="Test",
            context_fn=lambda obj: {"obj_id": obj.id, "obj_name": obj.name},
        )
        def validate_with_context(obj, validation_run: ValidationRun):
            validation_run.step("check", passed=True)
            return validation_run.result

        mock_obj = Mock()
        mock_obj.id = 123
        mock_obj.name = "TestObject"

        result = validate_with_context(mock_obj)  # type: ignore[call-arg]

        assert result.context == {"obj_id": 123, "obj_name": "TestObject"}

    @patch("spectrace_client.decorators.ValidationClient")
    def test_decorator_without_validation_run_kwarg(self, mock_client_class):
        """Decorator should work even if function doesn't accept validation_run."""
        mock_client = Mock()
        mock_client_class.from_settings.return_value = mock_client

        @verify_requirement("REQ-TEST-001", name="Test")
        def validate_without_kwarg():
            # Function doesn't accept validation_run
            return "done"

        result = validate_without_kwarg()

        # Since function didn't use validation_run, should return ValidationResult
        # with empty steps (from wrapper's default behavior)
        assert result is not None


API_URL = "https://spectrace.example.com"


def _client() -> ValidationClient:
    return ValidationClient(api_url=API_URL, api_key="test-key-123")


def test_init__sends_api_key_in_x_api_key_header():
    assert _client().session.headers["X-API-Key"] == "test-key-123"


@responses.activate
def test_push_specs__puts_project_tree_and_returns_counts():
    counts = {
        "project": "spec-trace",
        "requirements": {"created": 2, "updated": 0, "deleted": 1},
        "links": {"created": 1, "updated": 0, "deleted": 0},
        "flows": {"created": 0, "updated": 1, "deleted": 0},
        "unresolved": [],
    }
    responses.add(responses.PUT, f"{API_URL}/api/v1/specs/", json={"data": counts})
    requirements = [
        {"external_id": "REQ-001", "title": "Root", "source_file": "specs/root.md"},
        {
            "external_id": "REQ-002",
            "title": "Child",
            "source_file": "specs/root.md",
            "parent_id": "REQ-001",
        },
    ]
    links = [{"test_nodeid": "tests/test_a.py::test_root", "requirement_id": "REQ-001"}]
    flows = [
        {
            "name": "checkout",
            "display_name": "Checkout",
            "requirements": ["REQ-002"],
            "steps": [{"name": "load", "display_name": "Load"}],
        }
    ]

    result = _client().push_specs("spec-trace", requirements, links, flows)

    assert result == counts
    sent = json.loads(responses.calls[0].request.body)
    assert sent == {
        "project": "spec-trace",
        "replace": False,
        "requirements": requirements,
        "links": links,
        "flows": flows,
    }


@responses.activate
def test_push_specs__sends_replace_flag():
    responses.add(responses.PUT, f"{API_URL}/api/v1/specs/", json={"data": {}})

    _client().push_specs("spec-trace", [], [], [], replace=True)

    assert json.loads(responses.calls[0].request.body)["replace"] is True


@responses.activate
def test_push_results__posts_validations_and_returns_summary():
    summary = {
        "success": True,
        "imported": 1,
        "skipped": 0,
        "created_validations": 1,
        "successful": 1,
        "failed": 0,
    }
    responses.add(responses.POST, f"{API_URL}/api/v1/results/enforcement/", json=summary)
    validations = [{"requirement_id": "REQ-001", "name": "Login", "status": "success"}]

    result = _client().push_results("junit.xml", validations)

    assert result == summary
    assert json.loads(responses.calls[0].request.body) == {
        "source": "junit.xml",
        "validations": validations,
        "update_verification_status": False,
    }


@responses.activate
def test_push_results__asks_for_a_status_recompute_when_told_to():
    responses.add(responses.POST, f"{API_URL}/api/v1/results/enforcement/", json={})

    _client().push_results("junit.xml", [], update_verification_status=True)

    assert json.loads(responses.calls[0].request.body)["update_verification_status"] is True


@responses.activate
def test_push_specs__raises_http_error_when_unauthorized():
    responses.add(
        responses.PUT,
        f"{API_URL}/api/v1/specs/",
        status=401,
        json={"error": {"code": "unauthorized", "message": "Missing API key"}},
    )

    with pytest.raises(requests.HTTPError):
        _client().push_specs("spec-trace", [], [], [])


@responses.activate
def test_push_impact__posts_report_and_returns_receipt():
    receipt = {
        "project": "spec-trace",
        "generated_at": "2026-08-31T12:00:00Z",
        "stored_at": "2026-08-31T12:00:01Z",
    }
    responses.add(
        responses.POST, f"{API_URL}/api/v1/results/impact/", status=201, json={"data": receipt}
    )
    report = {
        "project": "spec-trace",
        "base": "main",
        "head": "HEAD",
        "generated_at": "2026-08-31T12:00:00Z",
        "changed_requirements": ["REQ-001"],
        "affected_tests": ["tests/test_a.py::test_root"],
        "hierarchy_expansion": {"REQ-001": ["REQ-002"]},
        "dependency_expansion": {},
        "risk_score": 0.12,
        "risk_level": "low",
    }

    result = _client().push_impact(report)

    assert result == receipt
    assert json.loads(responses.calls[0].request.body) == report


@responses.activate
def test_push_drift__posts_report_and_returns_receipt():
    receipt = {
        "project": "spec-trace",
        "generated_at": "2026-08-31T12:00:00Z",
        "stored_at": "2026-08-31T12:00:01Z",
    }
    responses.add(
        responses.POST, f"{API_URL}/api/v1/results/drift/", status=201, json={"data": receipt}
    )
    report = {
        "project": "spec-trace",
        "generated_at": "2026-08-31T12:00:00Z",
        "errors": [
            {
                "type": "stale_link",
                "id": "tests/test_a.py::test_root",
                "message": "Test not seen in 30 days",
                "test_nodeid": "tests/test_a.py::test_root",
                "requirement_id": "REQ-001",
                "last_status": "passed",
                "last_run_at": None,
            }
        ],
        "warnings": [],
        "summary": {"items_checked": 1, "errors": 1, "warnings": 0},
    }

    result = _client().push_drift(report)

    assert result == receipt
    assert json.loads(responses.calls[0].request.body) == report


@responses.activate
def test_task_outcomes__reads_page_after_cursor():
    page = {
        "data": [
            {
                "cursor": "42",
                "task_id": "TASK-007",
                "title": "Port the matrix screen",
                "status": "merged",
                "done_when_results": [{"criterion": "Screen renders", "passed": True}],
                "commit_sha": "abc1234",
                "attempt_count": 1,
                "max_attempts": 2,
                "occurred_at": "2026-08-31T12:00:00Z",
                "task_created_at": "2026-08-30T09:00:00Z",
                "drained": False,
            }
        ],
        "meta": {"limit": 10, "next_cursor": None},
    }
    responses.add(responses.GET, f"{API_URL}/api/v1/tasks/outcomes", json=page)

    result = _client().task_outcomes(since="41", limit=10)

    assert result == page
    assert responses.calls[0].request.params == {"since": "41", "limit": "10"}


@responses.activate
def test_task_outcomes__omits_since_when_not_given():
    responses.add(
        responses.GET,
        f"{API_URL}/api/v1/tasks/outcomes",
        json={"data": [], "meta": {"limit": 50, "next_cursor": None}},
    )

    _client().task_outcomes()

    assert responses.calls[0].request.params == {"limit": "50"}


@responses.activate
def test_ack_task_outcomes__posts_cursor_and_returns_drained_count():
    responses.add(
        responses.POST,
        f"{API_URL}/api/v1/tasks/outcomes/ack",
        json={"data": {"cursor": "42", "drained": 3}},
    )

    result = _client().ack_task_outcomes("42")

    assert result == {"cursor": "42", "drained": 3}
    assert json.loads(responses.calls[0].request.body) == {"cursor": "42"}


TRANSITION = {
    "success": True,
    "task_id": "task-auth-001",
    "from_status": "unclaimed",
    "to_status": "claimed",
    "message": "Task claimed by coder-1",
}


def _sent_body() -> dict:
    return json.loads(responses.calls[0].request.body)


@responses.activate
def test_list_tasks__sends_filters_and_returns_page():
    page = {
        "data": [{"id": "task-auth-001", "status": "unclaimed"}],
        "meta": {
            "page": 2,
            "per_page": 10,
            "total": 11,
            "total_pages": 2,
            "has_next": False,
            "has_prev": True,
        },
    }
    responses.add(responses.GET, f"{API_URL}/api/v1/tasks/", json=page)

    result = _client().list_tasks(status="unclaimed", page=2, per_page=10, sort="-priority")

    assert result == page
    assert responses.calls[0].request.params == {
        "status": "unclaimed",
        "page": "2",
        "per_page": "10",
        "sort": "-priority",
    }


@responses.activate
def test_list_tasks__sends_only_the_page_by_default():
    responses.add(responses.GET, f"{API_URL}/api/v1/tasks/", json={"data": [], "meta": {}})

    _client().list_tasks()

    assert responses.calls[0].request.params == {"page": "1"}


@responses.activate
def test_register_agent__posts_role_and_config_and_returns_agent():
    agent = {"agent_id": "coder-1", "role": "coder", "is_active": True}
    responses.add(responses.POST, f"{API_URL}/api/v1/tasks/agents/register/", json={"data": agent})

    result = _client().register_agent("coder-1", "coder", config={"model": "opus"})

    assert result == agent
    assert _sent_body() == {"agent_id": "coder-1", "role": "coder", "config": {"model": "opus"}}


@responses.activate
def test_register_agent__sends_an_empty_config_by_default():
    responses.add(responses.POST, f"{API_URL}/api/v1/tasks/agents/register/", json={"data": {}})

    _client().register_agent("coder-1", "coder")

    assert _sent_body()["config"] == {}


@responses.activate
def test_create_task__posts_the_draft_and_returns_the_stored_task():
    draft = {
        "agent_id": "planner-1",
        "task_id": "task-auth-001",
        "title": "Lock accounts",
        "requirements": ["REQ-AUTH-004"],
        "done_when": ["pytest -k lockout exits 0"],
        "scope_in": ["spectrace/auth/"],
    }
    stored = {**draft, "id": "task-auth-001", "status": "draft"}
    responses.add(responses.POST, f"{API_URL}/api/v1/tasks/", status=201, json={"data": stored})

    result = _client().create_task(draft)

    assert result == stored
    assert _sent_body() == draft


@responses.activate
def test_approve_spec__posts_reviewer_and_feedback():
    approved = {
        **TRANSITION,
        "from_status": "draft",
        "to_status": "unclaimed",
        "reviewer_id": "r-1",
    }
    responses.add(
        responses.POST,
        f"{API_URL}/api/v1/tasks/task-auth-001/approve-spec",
        json={"data": approved},
    )

    result = _client().approve_spec("task-auth-001", "r-1", feedback="Scope is tight")

    assert result == approved
    assert _sent_body() == {"reviewer_id": "r-1", "feedback": "Scope is tight"}


@responses.activate
def test_record_intent_validation__posts_scores_and_omits_passed_unless_given():
    verdict = {
        "task_id": "task-auth-001",
        "commit_sha": "a1b2c3d",
        "strategic_score": 88,
        "opportunity_score": 91,
        "drift_score": 79,
        "passed": True,
        "failure_reasons": [],
        "created_at": "2026-09-14T12:00:00Z",
    }
    responses.add(
        responses.POST,
        f"{API_URL}/api/v1/tasks/task-auth-001/intent-validations",
        status=201,
        json={"data": verdict},
    )

    result = _client().record_intent_validation("task-auth-001", "scorer-1", "a1b2c3d", 88, 91, 79)

    assert result == verdict
    assert _sent_body() == {
        "validator_id": "scorer-1",
        "commit_sha": "a1b2c3d",
        "strategic_score": 88,
        "opportunity_score": 91,
        "drift_score": 79,
        "failure_reasons": [],
    }


@responses.activate
def test_record_intent_validation__sends_the_override_and_reasons():
    responses.add(
        responses.POST,
        f"{API_URL}/api/v1/tasks/task-auth-001/intent-validations",
        status=201,
        json={"data": {}},
    )

    _client().record_intent_validation(
        "task-auth-001",
        "scorer-1",
        "a1b2c3d",
        90,
        90,
        90,
        passed=False,
        failure_reasons=["Misread spec"],
    )

    assert _sent_body()["passed"] is False
    assert _sent_body()["failure_reasons"] == ["Misread spec"]


@responses.activate
def test_claim_task__posts_agent_and_lease():
    claimed = {**TRANSITION, "lease_expires": "2026-09-14T12:30:00Z", "agent_id": "coder-1"}
    responses.add(
        responses.POST, f"{API_URL}/api/v1/tasks/task-auth-001/claim", json={"data": claimed}
    )

    result = _client().claim_task("task-auth-001", "coder-1", lease_minutes=60)

    assert result == claimed
    assert _sent_body() == {"agent_id": "coder-1", "lease_minutes": 60}


@responses.activate
def test_start_task__posts_the_agent():
    responses.add(
        responses.POST, f"{API_URL}/api/v1/tasks/task-auth-001/start", json={"data": TRANSITION}
    )

    result = _client().start_task("task-auth-001", "coder-1")

    assert result == TRANSITION
    assert _sent_body() == {"agent_id": "coder-1"}


@responses.activate
def test_complete_task__posts_agent_and_commit():
    responses.add(
        responses.POST, f"{API_URL}/api/v1/tasks/task-auth-001/complete", json={"data": TRANSITION}
    )

    result = _client().complete_task("task-auth-001", "coder-1", "a1b2c3d")

    assert result == TRANSITION
    assert _sent_body() == {"agent_id": "coder-1", "commit_sha": "a1b2c3d"}


@responses.activate
def test_complete_task__raises_on_the_intent_gate():
    responses.add(
        responses.POST,
        f"{API_URL}/api/v1/tasks/task-auth-001/complete",
        status=409,
        json={
            "error": {
                "code": "transition_error",
                "message": "Commit a1b2c3d on task 'task-auth-001' has no intent validation",
                "details": {"reason": "INTENT_NOT_VALIDATED"},
            }
        },
    )

    with pytest.raises(requests.HTTPError) as refused:
        _client().complete_task("task-auth-001", "coder-1", "a1b2c3d")

    assert refused.value.response.json()["error"]["details"]["reason"] == "INTENT_NOT_VALIDATED"


@responses.activate
def test_review_task__posts_decision_feedback_and_lists():
    responses.add(
        responses.POST, f"{API_URL}/api/v1/tasks/task-auth-001/review", json={"data": TRANSITION}
    )

    result = _client().review_task(
        "task-auth-001",
        "reviewer-1",
        "changes_requested",
        feedback="Tests missing",
        blocking_issues=["Add unit tests"],
        suggestions=["Rename helper"],
    )

    assert result == TRANSITION
    assert _sent_body() == {
        "reviewer_id": "reviewer-1",
        "decision": "changes_requested",
        "feedback": "Tests missing",
        "blocking_issues": ["Add unit tests"],
        "suggestions": ["Rename helper"],
    }


@responses.activate
def test_merge_task__posts_without_a_body():
    responses.add(
        responses.POST, f"{API_URL}/api/v1/tasks/task-auth-001/merge", json={"data": TRANSITION}
    )

    result = _client().merge_task("task-auth-001")

    assert result == TRANSITION
    assert responses.calls[0].request.body is None


@responses.activate
def test_release_task__posts_the_reason():
    responses.add(
        responses.POST, f"{API_URL}/api/v1/tasks/task-auth-001/release", json={"data": TRANSITION}
    )

    result = _client().release_task("task-auth-001", reason="handoff")

    assert result == TRANSITION
    assert _sent_body() == {"reason": "handoff"}


@responses.activate
def test_task_context__unwraps_the_bundle_from_the_envelope():
    bundle = {"task_id": "task-auth-001", "requirements": [], "drift": {}}
    responses.add(
        responses.GET,
        f"{API_URL}/api/v1/tasks/task-auth-001/context",
        json={"data": bundle},
    )

    result = _client().task_context("task-auth-001")

    assert result == bundle
    assert responses.calls[0].request.method == "GET"


@responses.activate
def test_task_context__raises_on_a_task_the_ledger_has_never_seen():
    responses.add(
        responses.GET,
        f"{API_URL}/api/v1/tasks/nope/context",
        status=404,
        json={"error": {"code": "not_found", "message": "Task not found: nope"}},
    )

    with pytest.raises(requests.HTTPError):
        _client().task_context("nope")

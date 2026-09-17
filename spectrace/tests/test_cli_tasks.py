"""Tests for the spectrace tasks commands, which drive the Worker's task ledger."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import responses
from click.testing import CliRunner

from cli import cli

URL = "http://worker.test"
AUTH = ["--url", URL, "--api-key", "secret"]
TRANSITION = {
    "success": True,
    "task_id": "task-auth-001",
    "from_status": "unclaimed",
    "to_status": "claimed",
    "message": "Task claimed by coder-1",
}
INTENT_NOT_VALIDATED = {
    "error": {
        "code": "transition_error",
        "message": "Commit a1b2c3d on task 'task-auth-001' has no intent validation",
        "details": {"reason": "INTENT_NOT_VALIDATED"},
    }
}


@pytest.fixture
def runner():
    return CliRunner()


def _sent() -> dict:
    return json.loads(responses.calls[0].request.body)


@responses.activate
def test_tasks_register__posts_to_the_worker_and_reports_the_agent(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/agents/register/",
        json={"data": {"agent_id": "coder-1", "role": "coder", "is_active": True}},
    )

    result = runner.invoke(
        cli, ["tasks", "register", "coder-1", "--role", "coder", "--config", '{"m": 1}', *AUTH]
    )

    assert result.exit_code == 0, result.output
    assert result.output == "Registered coder-1 as coder (active)\n"
    assert responses.calls[0].request.headers["X-API-Key"] == "secret"
    assert _sent() == {"agent_id": "coder-1", "role": "coder", "config": {"m": 1}}


@responses.activate
def test_tasks_register__reads_url_and_key_from_environment(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/agents/register/",
        json={"data": {"agent_id": "coder-1", "role": "coder", "is_active": True}},
    )

    result = runner.invoke(
        cli,
        ["tasks", "register", "coder-1", "--role", "coder"],
        env={"SPECTRACE_URL": URL, "SPECTRACE_API_KEY": "from-env"},
    )

    assert result.exit_code == 0, result.output
    assert responses.calls[0].request.headers["X-API-Key"] == "from-env"


@responses.activate
def test_tasks_create__posts_the_draft_from_repeatable_options(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/",
        status=201,
        json={"data": {"id": "task-auth-001", "status": "draft"}},
    )

    result = runner.invoke(
        cli,
        [
            "tasks",
            "create",
            "task-auth-001",
            "--agent",
            "planner-1",
            "--title",
            "Lock accounts",
            "--description",
            "Count failures per account",
            "--requirement",
            "REQ-AUTH-004",
            "--done-when",
            "pytest -k lockout exits 0",
            "--done-when",
            "A sixth attempt returns 423",
            "--scope-in",
            "spectrace/auth/",
            "--scope-out",
            "spectrace/notifications/",
            "--spec-ref",
            "specs/auth.md#REQ-AUTH-004",
            "--max-attempts",
            "3",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "Created task-auth-001 in draft\n"
    assert _sent() == {
        "agent_id": "planner-1",
        "task_id": "task-auth-001",
        "title": "Lock accounts",
        "description": "Count failures per account",
        "requirements": ["REQ-AUTH-004"],
        "done_when": ["pytest -k lockout exits 0", "A sixth attempt returns 423"],
        "scope_in": ["spectrace/auth/"],
        "scope_out": ["spectrace/notifications/"],
        "spec_ref": "specs/auth.md#REQ-AUTH-004",
        "max_attempts": 3,
    }


@responses.activate
def test_tasks_approve_spec__posts_reviewer_and_prints_the_transition(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/approve-spec",
        json={
            "data": {
                **TRANSITION,
                "from_status": "draft",
                "to_status": "unclaimed",
                "message": "Spec approved by reviewer-1",
                "reviewer_id": "reviewer-1",
            }
        },
    )

    result = runner.invoke(
        cli,
        [
            "tasks",
            "approve-spec",
            "task-auth-001",
            "--reviewer",
            "reviewer-1",
            "--feedback",
            "Scope is tight",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "task-auth-001: draft -> unclaimed\nSpec approved by reviewer-1\n"
    assert _sent() == {"reviewer_id": "reviewer-1", "feedback": "Scope is tight"}


@responses.activate
def test_tasks_approve_spec__reports_an_incomplete_spec(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/approve-spec",
        status=409,
        json={
            "error": {
                "code": "transition_error",
                "message": "Task 'task-auth-001' names no done_when criteria",
                "details": {"reason": "SPEC_INCOMPLETE"},
            }
        },
    )

    result = runner.invoke(
        cli, ["tasks", "approve-spec", "task-auth-001", "--reviewer", "reviewer-1", *AUTH]
    )

    assert result.exit_code == 1
    assert "409 from" in result.output
    assert "names no done_when criteria [SPEC_INCOMPLETE]" in result.output


@responses.activate
def test_tasks_list__prints_one_line_per_task_and_the_page(runner):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/",
        json={
            "data": [
                {
                    "id": "task-auth-001",
                    "status": "claimed",
                    "claimed_by": "coder-1",
                    "title": "Lock",
                },
                {
                    "id": "task-auth-002",
                    "status": "unclaimed",
                    "claimed_by": None,
                    "title": "Reset",
                },
            ],
            "meta": {"page": 1, "total_pages": 1, "total": 2},
        },
    )

    result = runner.invoke(cli, ["tasks", "list", "--status", "unclaimed", *AUTH])

    assert result.exit_code == 0, result.output
    assert result.output == (
        "task-auth-001  claimed  coder-1  Lock\n"
        "task-auth-002  unclaimed  -  Reset\n"
        "Page 1 of 1 (2 tasks)\n"
    )
    assert responses.calls[0].request.params == {"status": "unclaimed", "page": "1"}


@responses.activate
def test_tasks_list__json_prints_the_page_envelope(runner):
    page = {"data": [], "meta": {"page": 1, "total_pages": 0, "total": 0}}
    responses.add(responses.GET, f"{URL}/api/v1/tasks/", json=page)

    result = runner.invoke(cli, ["tasks", "list", "--format", "json", *AUTH])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == page


@responses.activate
def test_tasks_claim__posts_lease_and_prints_its_expiry(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/claim",
        json={
            "data": {**TRANSITION, "lease_expires": "2026-09-14T12:30:00Z", "agent_id": "coder-1"}
        },
    )

    result = runner.invoke(
        cli,
        ["tasks", "claim", "task-auth-001", "--agent", "coder-1", "--lease-minutes", "60", *AUTH],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        "task-auth-001: unclaimed -> claimed\n"
        "Task claimed by coder-1\n"
        "Lease expires 2026-09-14T12:30:00Z\n"
    )
    assert _sent() == {"agent_id": "coder-1", "lease_minutes": 60}


@responses.activate
def test_tasks_claim__reports_a_draft_task(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/claim",
        status=409,
        json={
            "error": {
                "code": "transition_error",
                "message": "Cannot transition from draft to claimed",
                "details": {"reason": "INVALID_TRANSITION"},
            }
        },
    )

    result = runner.invoke(cli, ["tasks", "claim", "task-auth-001", "--agent", "coder-1", *AUTH])

    assert result.exit_code == 1
    assert "Cannot transition from draft to claimed [INVALID_TRANSITION]" in result.output


@responses.activate
def test_tasks_start__posts_the_agent(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/start",
        json={"data": {**TRANSITION, "from_status": "claimed", "to_status": "in_progress"}},
    )

    result = runner.invoke(cli, ["tasks", "start", "task-auth-001", "--agent", "coder-1", *AUTH])

    assert result.exit_code == 0, result.output
    assert "task-auth-001: claimed -> in_progress" in result.output
    assert _sent() == {"agent_id": "coder-1"}


@responses.activate
def test_tasks_validate_intent__posts_scores_and_prints_the_verdict(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/intent-validations",
        status=201,
        json={
            "data": {
                "task_id": "task-auth-001",
                "commit_sha": "a1b2c3d",
                "passed": True,
                "failure_reasons": [],
            }
        },
    )

    result = runner.invoke(
        cli,
        [
            "tasks",
            "validate-intent",
            "task-auth-001",
            "--validator",
            "scorer-1",
            "--commit-sha",
            "a1b2c3d",
            "--strategic-score",
            "88",
            "--opportunity-score",
            "91",
            "--drift-score",
            "79",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "Intent validation for a1b2c3d on task-auth-001: passed\n"
    assert _sent() == {
        "validator_id": "scorer-1",
        "commit_sha": "a1b2c3d",
        "strategic_score": 88,
        "opportunity_score": 91,
        "drift_score": 79,
        "failure_reasons": [],
    }


@responses.activate
def test_tasks_validate_intent__sends_the_failed_override_and_lists_reasons(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/intent-validations",
        status=201,
        json={
            "data": {
                "task_id": "task-auth-001",
                "commit_sha": "a1b2c3d",
                "passed": False,
                "failure_reasons": ["Tests encode the misread spec"],
            }
        },
    )

    result = runner.invoke(
        cli,
        [
            "tasks",
            "validate-intent",
            "task-auth-001",
            "--validator",
            "scorer-1",
            "--commit-sha",
            "a1b2c3d",
            "--strategic-score",
            "90",
            "--opportunity-score",
            "90",
            "--drift-score",
            "90",
            "--failed",
            "--failure-reason",
            "Tests encode the misread spec",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        "Intent validation for a1b2c3d on task-auth-001: failed\n  Tests encode the misread spec\n"
    )
    assert _sent()["passed"] is False
    assert _sent()["failure_reasons"] == ["Tests encode the misread spec"]


def test_tasks_validate_intent__rejects_a_score_above_100(runner):
    result = runner.invoke(
        cli,
        [
            "tasks",
            "validate-intent",
            "task-auth-001",
            "--validator",
            "scorer-1",
            "--commit-sha",
            "a1b2c3d",
            "--strategic-score",
            "101",
            "--opportunity-score",
            "90",
            "--drift-score",
            "90",
            *AUTH,
        ],
    )

    assert result.exit_code == 2
    assert "101" in result.output


@responses.activate
def test_tasks_complete__posts_agent_and_commit(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/complete",
        json={
            "data": {
                **TRANSITION,
                "from_status": "in_progress",
                "to_status": "ready_for_review",
                "message": "Task submitted for review",
                "commit_sha": "a1b2c3d",
            }
        },
    )

    result = runner.invoke(
        cli,
        [
            "tasks",
            "complete",
            "task-auth-001",
            "--agent",
            "coder-1",
            "--commit-sha",
            "a1b2c3d",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    assert (
        result.output
        == "task-auth-001: in_progress -> ready_for_review\nTask submitted for review\n"
    )
    assert _sent() == {"agent_id": "coder-1", "commit_sha": "a1b2c3d", "branch": ""}


@responses.activate
def test_tasks_complete__reports_the_intent_gate_in_text(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/complete",
        status=409,
        json=INTENT_NOT_VALIDATED,
    )

    result = runner.invoke(
        cli,
        [
            "tasks",
            "complete",
            "task-auth-001",
            "--agent",
            "coder-1",
            "--commit-sha",
            "a1b2c3d",
            *AUTH,
        ],
    )

    assert result.exit_code == 1
    assert result.output == (
        f"Error: 409 from {URL}/api/v1/tasks/task-auth-001/complete: "
        "Commit a1b2c3d on task 'task-auth-001' has no intent validation [INTENT_NOT_VALIDATED]\n"
    )


@responses.activate
def test_tasks_complete__reports_the_intent_gate_as_json(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/complete",
        status=409,
        json=INTENT_NOT_VALIDATED,
    )

    result = runner.invoke(
        cli,
        [
            "tasks",
            "complete",
            "task-auth-001",
            "--agent",
            "coder-1",
            "--commit-sha",
            "a1b2c3d",
            "--format",
            "json",
            *AUTH,
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.output) == INTENT_NOT_VALIDATED


@responses.activate
def test_tasks_complete__reports_an_unknown_task(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-gone/complete",
        status=404,
        json={
            "error": {
                "code": "not_found",
                "message": "Task 'task-gone' not found",
                "details": {"reason": "TASK_NOT_FOUND"},
            }
        },
    )

    result = runner.invoke(
        cli, ["tasks", "complete", "task-gone", "--agent", "coder-1", "--commit-sha", "a1", *AUTH]
    )

    assert result.exit_code == 1
    assert "404 from" in result.output
    assert "Task 'task-gone' not found [TASK_NOT_FOUND]" in result.output


@responses.activate
def test_tasks_complete__falls_back_to_the_code_when_the_envelope_has_no_reason(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/complete",
        status=400,
        json={"error": {"code": "validation_error", "message": "commit_sha is required"}},
    )

    result = runner.invoke(
        cli,
        ["tasks", "complete", "task-auth-001", "--agent", "coder-1", "--commit-sha", "x", *AUTH],
    )

    assert result.exit_code == 1
    assert "commit_sha is required [validation_error]" in result.output


@responses.activate
def test_tasks_complete__prints_a_non_json_error_body_verbatim(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/complete",
        status=502,
        body="Bad gateway",
        content_type="text/plain",
    )

    result = runner.invoke(
        cli,
        ["tasks", "complete", "task-auth-001", "--agent", "coder-1", "--commit-sha", "x", *AUTH],
    )

    assert result.exit_code == 1
    assert "502 from" in result.output
    assert "Bad gateway" in result.output


@responses.activate
def test_tasks_review__posts_decision_and_lists(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/review",
        json={"data": {**TRANSITION, "from_status": "ready_for_review", "to_status": "approved"}},
    )

    result = runner.invoke(
        cli,
        [
            "tasks",
            "review",
            "task-auth-001",
            "--reviewer",
            "reviewer-1",
            "--decision",
            "approved",
            "--feedback",
            "Looks good",
            "--blocking-issues",
            "issue-1",
            "--suggestions",
            "nit-1",
            "--suggestions",
            "nit-2",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    assert "task-auth-001: ready_for_review -> approved" in result.output
    assert _sent() == {
        "reviewer_id": "reviewer-1",
        "decision": "approved",
        "feedback": "Looks good",
        "blocking_issues": ["issue-1"],
        "suggestions": ["nit-1", "nit-2"],
    }


@responses.activate
def test_tasks_merge__prints_the_refusal_as_json_and_exits_nonzero(runner, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/task-auth-001",
        json={
            "data": {
                "id": "task-auth-001",
                "status": "approved",
                "branch": "",
                "commit_sha": "a1b2c3d",
            }
        },
    )

    result = runner.invoke(
        cli,
        ["tasks", "merge", "task-auth-001", "--repo", str(repo), "--format", "json", *AUTH],
    )

    assert result.exit_code == 1, result.output
    assert json.loads(result.output) == {
        "task_id": "task-auth-001",
        "code": "BRANCH_UNKNOWN",
        "reason": "the ledger records no branch; name one with --branch",
    }


@responses.activate
def test_tasks_release__posts_the_reason(runner):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-auth-001/release",
        json={"data": {**TRANSITION, "from_status": "claimed", "to_status": "unclaimed"}},
    )

    result = runner.invoke(cli, ["tasks", "release", "task-auth-001", "--reason", "handoff", *AUTH])

    assert result.exit_code == 0, result.output
    assert "task-auth-001: claimed -> unclaimed" in result.output
    assert _sent() == {"reason": "handoff"}


def test_tasks_claim__needs_a_remote(runner):
    result = runner.invoke(cli, ["tasks", "claim", "task-auth-001", "--agent", "coder-1"])

    assert result.exit_code == 2
    assert "--url" in result.output


CONTEXT_BUNDLE = {
    "task_id": "task-auth-001",
    "title": "Lock an account after five failed logins",
    "description": "Count failures per account, not per IP.",
    "status": "unclaimed",
    "done_when": ["pytest -k lockout exits 0"],
    "scope_in": ["spectrace/auth/lockout.py"],
    "scope_out": ["spectrace/notifications/"],
    "spec_ref": "specs/auth/login.md#REQ-AUTH-004",
    "requirements": [
        {
            "external_id": "REQ-AUTH-004",
            "title": "Account lockout",
            "description": "Lock after five failures.",
            "verification_status": "failing",
            "priority": "high",
            "tags": ["auth", "security"],
            "source_file": "specs/auth/login.md",
            "test_results": [
                {"test_nodeid": "tests/test_auth.py::test_lockout", "last_status": "failed"}
            ],
            "tree": {
                "parent": {"external_id": "REQ-AUTH", "title": "Authentication"},
                "children": [{"external_id": "REQ-AUTH-004-A", "title": "Retry-After header"}],
            },
            "fret": {"component": "Lock", "timing": "within 1 second"},
        }
    ],
    "drift": {
        "stale_links": {
            "errors": [
                {
                    "type": "stale_link",
                    "id": "tests/test_gone.py::test_gone:REQ-AUTH-004",
                    "message": "Link references test not in latest run",
                }
            ],
            "warnings": [],
            "summary": {"items_checked": 2, "errors": 1, "warnings": 0},
        },
        "orphan_requirements": {
            "errors": [],
            "warnings": [],
            "summary": {"items_checked": 3, "errors": 0, "warnings": 0},
        },
    },
}


@responses.activate
def test_tasks_context__renders_the_worker_bundle_as_markdown(runner):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/task-auth-001/context",
        json={"data": CONTEXT_BUNDLE},
    )

    result = runner.invoke(cli, ["tasks", "context", "task-auth-001", "--no-lore", *AUTH])

    assert result.exit_code == 0, result.output
    assert "# Agent Context Bundle" in result.output
    assert "## Task: Lock an account after five failed logins" in result.output
    assert "  - [ ] pytest -k lockout exits 0" in result.output
    assert "- Scope In: spectrace/auth/lockout.py" in result.output
    assert "- Spec: specs/auth/login.md#REQ-AUTH-004" in result.output
    assert "### Spec: Account lockout" in result.output
    assert "- FRET: component=Lock, timing=within 1 second" in result.output
    assert "- Parent: REQ-AUTH: Authentication" in result.output
    assert "  - REQ-AUTH-004-A: Retry-After header" in result.output
    assert "- tests/test_auth.py::test_lockout: failed" in result.output
    assert (
        "- [stale_link] tests/test_gone.py::test_gone:REQ-AUTH-004: Link references test"
        in result.output
    )


@responses.activate
def test_tasks_context__emits_the_bundle_verbatim_as_json(runner):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/task-auth-001/context",
        json={"data": CONTEXT_BUNDLE},
    )

    result = runner.invoke(
        cli, ["tasks", "context", "task-auth-001", "--format", "json", "--no-lore", *AUTH]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == CONTEXT_BUNDLE


@responses.activate
def test_tasks_context__writes_the_bundle_to_output(runner, tmp_path):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/task-auth-001/context",
        json={"data": CONTEXT_BUNDLE},
    )
    destination = tmp_path / "context.md"

    result = runner.invoke(
        cli,
        ["tasks", "context", "task-auth-001", "--output", str(destination), "--no-lore", *AUTH],
    )

    assert result.exit_code == 0, result.output
    assert destination.read_text() + "\n" == result.output


@responses.activate
def test_tasks_context__reports_a_task_the_ledger_has_never_seen(runner):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/nope/context",
        status=404,
        json={"error": {"code": "not_found", "message": "Task not found: nope"}},
    )

    result = runner.invoke(cli, ["tasks", "context", "nope", "--no-lore", *AUTH])

    assert result.exit_code == 1
    assert "Task not found: nope" in result.output


@responses.activate
def test_tasks_context__overlays_lore_when_the_cli_is_present(runner, monkeypatch):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/task-auth-001/context",
        json={"data": CONTEXT_BUNDLE},
    )
    from requirements.services import task_context as service

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps([{"title": "Lock accounts per account, not per IP"}])
        )

    monkeypatch.setattr(service, "find_lore_cli", lambda: "/usr/local/bin/lore")
    monkeypatch.setattr(service.subprocess, "run", fake_run)

    result = runner.invoke(cli, ["tasks", "context", "task-auth-001", *AUTH])

    assert result.exit_code == 0, result.output
    assert "## Lore Context" in result.output
    assert "- Lock accounts per account, not per IP" in result.output
    assert "auth OR security OR account OR lockout" in captured["command"]


@responses.activate
def test_tasks_context__omits_the_lore_section_when_the_cli_is_absent(runner, monkeypatch):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/task-auth-001/context",
        json={"data": CONTEXT_BUNDLE},
    )
    from requirements.services import task_context as service

    monkeypatch.setattr(service, "find_lore_cli", lambda: None)

    result = runner.invoke(cli, ["tasks", "context", "task-auth-001", *AUTH])

    assert result.exit_code == 0, result.output
    assert "## Lore Context" not in result.output


def _seeded_repo(path):
    import subprocess

    path.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "runner@test"],
        ["config", "user.name", "Runner"],
    ):
        subprocess.run(["git", *args], cwd=path, check=True)
    (path / "README.md").write_text("seed\n")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=path, check=True)
    return path


def _mock_task_1_pipeline():
    responses.add(
        responses.GET, f"{URL}/api/v1/tasks/", json={"data": [{"id": "task-1"}], "meta": {}}
    )
    responses.add(responses.POST, f"{URL}/api/v1/tasks/task-1/claim", json={"data": TRANSITION})
    responses.add(responses.POST, f"{URL}/api/v1/tasks/task-1/start", json={"data": TRANSITION})
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/task-1/context",
        json={"data": {"task_id": "task-1", "title": "Add login", "requirements": []}},
    )


@responses.activate
def test_tasks_run__submits_each_task_and_reports_where_it_worked(runner, tmp_path):
    repo = _seeded_repo(tmp_path / "repo")
    _mock_task_1_pipeline()
    responses.add(responses.POST, f"{URL}/api/v1/tasks/task-1/complete", json={"data": TRANSITION})

    result = runner.invoke(
        cli,
        [
            "tasks",
            "run",
            "--agent",
            "coder-1",
            "--repo",
            str(repo),
            "--worktrees",
            str(tmp_path / "tasks"),
            "--coder",
            "echo x > x.txt",
            "--tests",
            "true",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0] == f"task-1: working in {tmp_path / 'tasks' / 'task-1'} on task/task-1"
    assert lines[1].startswith("task-1: submitted ")
    assert (tmp_path / "tasks" / "task-1" / "x.txt").exists()


@responses.activate
def test_tasks_run__exits_nonzero_with_the_task_and_reason_at_the_first_refusal(runner, tmp_path):
    repo = _seeded_repo(tmp_path / "repo")
    _mock_task_1_pipeline()
    responses.add(
        responses.POST, f"{URL}/api/v1/tasks/task-1/complete", status=409, json=INTENT_NOT_VALIDATED
    )

    result = runner.invoke(
        cli,
        [
            "tasks",
            "run",
            "--agent",
            "coder-1",
            "--repo",
            str(repo),
            "--worktrees",
            str(tmp_path / "tasks"),
            "--coder",
            "echo x > x.txt",
            "--tests",
            "true",
            "--format",
            "json",
            *AUTH,
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.output) == {
        "task_id": "task-1",
        "stage": "complete",
        "reason": "INTENT_NOT_VALIDATED",
    }


@responses.activate
def test_tasks_run__reports_an_empty_queue(runner, tmp_path):
    repo = _seeded_repo(tmp_path / "repo")
    responses.add(responses.GET, f"{URL}/api/v1/tasks/", json={"data": [], "meta": {}})

    result = runner.invoke(
        cli,
        [
            "tasks",
            "run",
            "--agent",
            "coder-1",
            "--repo",
            str(repo),
            "--coder",
            "true",
            "--tests",
            "true",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "No unclaimed tasks\n"


def test_tasks_run__refuses_a_scorer_with_no_agent_to_post_under(runner, tmp_path):
    repo = _seeded_repo(tmp_path / "repo")

    result = runner.invoke(
        cli,
        [
            "tasks",
            "run",
            "--agent",
            "coder-1",
            "--repo",
            str(repo),
            "--coder",
            "true",
            "--tests",
            "true",
            "--scorer",
            "./score.sh",
            *AUTH,
        ],
    )

    assert result.exit_code == 2
    assert "--scorer needs --scorer-agent" in result.output


def test_tasks_run__refuses_a_scorer_agent_that_is_the_coder(runner, tmp_path):
    repo = _seeded_repo(tmp_path / "repo")

    result = runner.invoke(
        cli,
        [
            "tasks",
            "run",
            "--agent",
            "coder-1",
            "--repo",
            str(repo),
            "--coder",
            "true",
            "--tests",
            "true",
            "--scorer",
            "./score.sh",
            "--scorer-agent",
            "coder-1",
            *AUTH,
        ],
    )

    assert result.exit_code == 2
    assert "--scorer-agent must name an agent other than --agent" in result.output


def test_tasks_run__imports_its_service_in_a_fresh_interpreter(tmp_path):
    repo = _seeded_repo(tmp_path / "repo")
    root = Path(__file__).resolve().parents[2]
    probe = textwrap.dedent(
        """
        import sys

        sys.path.insert(0, %r)
        import spectrace.cli as module
        import requests
        from click.testing import CliRunner

        def refuse(*args, **kwargs):
            raise RuntimeError("network reached")

        requests.Session.request = refuse
        result = CliRunner().invoke(
            module.cli,
            ["tasks", "run", "--agent", "probe", "--repo", %r,
             "--coder", "true", "--tests", "true",
             "--url", "http://worker.test", "--api-key", "secret"],
        )
        print(type(result.exception).__name__)
        """
    ) % (str(root), str(repo))

    finished = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, cwd=tmp_path
    )

    assert finished.stdout.strip() == "RuntimeError", finished.stdout + finished.stderr

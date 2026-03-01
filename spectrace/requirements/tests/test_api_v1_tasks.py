"""Tests for API v1 task endpoints."""

import json
from unittest.mock import patch

import pytest

from requirements.models import AgentTask, AgentTaskStatus
from requirements.services.agent_tasks import TransitionError, TransitionResult

# ============================================================================
# Local Fixtures
# ============================================================================


@pytest.fixture
def claimed_task(db, coder_agent):
    """Create a task claimed by the coder agent."""
    return AgentTask.objects.create(
        external_id="task-002",
        title="Fix logout bug",
        status=AgentTaskStatus.CLAIMED,
        claimed_by=coder_agent,
    )


@pytest.fixture
def multiple_tasks(db, coder_agent):
    """Create several tasks with varying statuses for pagination/filter tests."""
    t1 = AgentTask.objects.create(
        external_id="task-010",
        title="Alpha task",
        status=AgentTaskStatus.UNCLAIMED,
    )
    t2 = AgentTask.objects.create(
        external_id="task-011",
        title="Beta task",
        status=AgentTaskStatus.CLAIMED,
        claimed_by=coder_agent,
    )
    t3 = AgentTask.objects.create(
        external_id="task-012",
        title="Gamma task",
        status=AgentTaskStatus.UNCLAIMED,
    )
    t4 = AgentTask.objects.create(
        external_id="task-013",
        title="Delta task",
        status=AgentTaskStatus.IN_PROGRESS,
        claimed_by=coder_agent,
    )
    return [t1, t2, t3, t4]


# ============================================================================
# GET /api/v1/tasks/
# ============================================================================


@pytest.mark.django_db
def test_list_tasks__returns_empty_list(client):
    resp = client.get("/api/v1/tasks/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["meta"] == {"limit": 50, "offset": 0, "total": 0}


@pytest.mark.django_db
def test_list_tasks__returns_tasks_with_pagination_meta(client, unclaimed_task):
    resp = client.get("/api/v1/tasks/")
    body = resp.json()
    assert resp.status_code == 200
    assert body["meta"]["total"] == 1
    task = body["data"][0]
    assert task["id"] == "task-001"
    assert task["title"] == "Implement login"
    assert task["status"] == AgentTaskStatus.UNCLAIMED
    assert task["claimed_by"] is None
    assert "created_at" in task


@pytest.mark.django_db
def test_list_tasks__filters_by_status(client, multiple_tasks):
    resp = client.get("/api/v1/tasks/", {"status": AgentTaskStatus.UNCLAIMED})
    body = resp.json()
    assert resp.status_code == 200
    assert body["meta"]["total"] == 2
    ids = {t["id"] for t in body["data"]}
    assert ids == {"task-010", "task-012"}


@pytest.mark.django_db
def test_list_tasks__respects_limit_and_offset(client, multiple_tasks):
    resp = client.get("/api/v1/tasks/", {"limit": "2", "offset": "0", "sort": "external_id"})
    body = resp.json()
    assert resp.status_code == 200
    assert len(body["data"]) == 2
    assert body["meta"]["limit"] == 2
    assert body["meta"]["offset"] == 0
    assert body["meta"]["total"] == 4

    resp2 = client.get("/api/v1/tasks/", {"limit": "2", "offset": "2", "sort": "external_id"})
    body2 = resp2.json()
    assert len(body2["data"]) == 2
    # Second page should have different tasks
    page1_ids = {t["id"] for t in body["data"]}
    page2_ids = {t["id"] for t in body2["data"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.django_db
def test_list_tasks__clamps_limit_to_100(client, unclaimed_task):
    resp = client.get("/api/v1/tasks/", {"limit": "999"})
    body = resp.json()
    assert resp.status_code == 200
    assert body["meta"]["limit"] == 100


@pytest.mark.django_db
def test_list_tasks__rejects_invalid_limit(client):
    resp = client.get("/api/v1/tasks/", {"limit": "abc"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_query_param"


@pytest.mark.django_db
def test_list_tasks__rejects_invalid_offset(client):
    resp = client.get("/api/v1/tasks/", {"offset": "xyz"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_query_param"


@pytest.mark.django_db
def test_list_tasks__sorts_by_field(client, multiple_tasks):
    resp = client.get("/api/v1/tasks/", {"sort": "title"})
    body = resp.json()
    assert resp.status_code == 200
    titles = [t["title"] for t in body["data"]]
    assert titles == sorted(titles)


# ============================================================================
# POST /api/v1/tasks/{task_id}/claim
# ============================================================================


@pytest.mark.django_db
@patch("requirements.api_v1.claim_task", autospec=True)
def test_claim_task__succeeds(mock_claim, client, unclaimed_task):
    mock_claim.return_value = TransitionResult(
        success=True,
        task_id="task-001",
        from_status=AgentTaskStatus.UNCLAIMED,
        to_status=AgentTaskStatus.CLAIMED,
        message="Task claimed",
    )

    resp = client.post(
        "/api/v1/tasks/task-001/claim",
        json.dumps({"agent_id": "coder-1", "lease_minutes": 30}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["success"] is True
    assert body["data"]["task_id"] == "task-001"
    assert body["data"]["to_status"] == AgentTaskStatus.CLAIMED
    mock_claim.assert_called_once_with("task-001", "coder-1", 30)


@pytest.mark.django_db
@patch("requirements.api_v1.claim_task", autospec=True)
def test_claim_task__returns_transition_error(mock_claim, client, unclaimed_task):
    mock_claim.side_effect = TransitionError("Already claimed", code="ALREADY_CLAIMED")

    resp = client.post(
        "/api/v1/tasks/task-001/claim",
        json.dumps({"agent_id": "coder-1"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "ALREADY_CLAIMED"
    assert body["error"]["message"] == "Already claimed"


@pytest.mark.django_db
def test_claim_task__rejects_missing_agent_id(client, unclaimed_task):
    resp = client.post(
        "/api/v1/tasks/task-001/claim",
        json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "missing_field"


@pytest.mark.django_db
def test_claim_task__rejects_invalid_json(client, unclaimed_task):
    resp = client.post(
        "/api/v1/tasks/task-001/claim",
        "not json",
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_json"


# ============================================================================
# POST /api/v1/tasks/{task_id}/complete
# ============================================================================


@pytest.mark.django_db
@patch("requirements.api_v1.submit_for_review", autospec=True)
def test_complete_task__succeeds(mock_submit, client, claimed_task):
    mock_submit.return_value = TransitionResult(
        success=True,
        task_id="task-002",
        from_status=AgentTaskStatus.CLAIMED,
        to_status=AgentTaskStatus.READY_FOR_REVIEW,
        message="Submitted for review",
    )

    resp = client.post(
        "/api/v1/tasks/task-002/complete",
        json.dumps({"agent_id": "coder-1", "commit_sha": "abc123"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["success"] is True
    assert body["data"]["to_status"] == AgentTaskStatus.READY_FOR_REVIEW
    mock_submit.assert_called_once_with("task-002", "coder-1", "abc123")


@pytest.mark.django_db
def test_complete_task__rejects_missing_fields(client, claimed_task):
    # Missing commit_sha
    resp = client.post(
        "/api/v1/tasks/task-002/complete",
        json.dumps({"agent_id": "coder-1"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "missing_field"

    # Missing agent_id
    resp2 = client.post(
        "/api/v1/tasks/task-002/complete",
        json.dumps({"commit_sha": "abc123"}),
        content_type="application/json",
    )
    assert resp2.status_code == 400
    assert resp2.json()["error"]["code"] == "missing_field"

"""Tests for detect_integration_risks management command."""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from requirements.models import Agent, AgentRole, AgentTask, AgentTaskStatus, Requirement


@pytest.fixture
def agent(db):
    """Create an agent for task claiming."""
    return Agent.objects.create(agent_id="coder-1", role=AgentRole.CODER)


@pytest.fixture
def req_a(db):
    """Create requirement A."""
    return Requirement.add_root(external_id="REQ-A", title="Req A", source_file="specs/a.md")


@pytest.fixture
def req_b(db):
    """Create requirement B."""
    return Requirement.add_root(external_id="REQ-B", title="Req B", source_file="specs/b.md")


@pytest.fixture
def req_c(db):
    """Create requirement C (independent)."""
    return Requirement.add_root(external_id="REQ-C", title="Req C", source_file="specs/c.md")


class TestDetectIntegrationRisksCommand:
    """Tests for the detect_integration_risks management command."""

    @pytest.mark.django_db
    def test_detect_integration_risks__overlapping_requirements(self, agent, req_a):
        """Two tasks sharing a requirement produce a high risk."""
        task_1 = AgentTask.objects.create(
            external_id="task-1",
            title="Task 1",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
        )
        task_1.requirements.add(req_a)

        task_2 = AgentTask.objects.create(
            external_id="task-2",
            title="Task 2",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
        )
        task_2.requirements.add(req_a)

        out = StringIO()
        call_command("detect_integration_risks", stdout=out)
        output = out.getvalue()

        assert "HIGH" in output
        assert "Overlapping Requirements" in output
        assert "task-1" in output
        assert "task-2" in output
        assert "REQ-A" in output

    @pytest.mark.django_db
    def test_detect_integration_risks__dependency_chain(self, agent, req_a, req_b):
        """Task A's req depended on by Task B's req produces medium risk."""
        req_b.depends_on.add(req_a)

        task_1 = AgentTask.objects.create(
            external_id="task-1",
            title="Task 1",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
        )
        task_1.requirements.add(req_a)

        task_2 = AgentTask.objects.create(
            external_id="task-2",
            title="Task 2",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
        )
        task_2.requirements.add(req_b)

        out = StringIO()
        call_command("detect_integration_risks", stdout=out)
        output = out.getvalue()

        assert "MEDIUM" in output
        assert "Dependency Chain" in output
        assert "task-1" in output
        assert "task-2" in output

    @pytest.mark.django_db
    def test_detect_integration_risks__scope_overlap(self, agent, req_a, req_b):
        """Two tasks with overlapping scope_in paths produce low risk."""
        task_1 = AgentTask.objects.create(
            external_id="task-1",
            title="Task 1",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
            scope_in=["src/auth/"],
        )
        task_1.requirements.add(req_a)

        task_2 = AgentTask.objects.create(
            external_id="task-2",
            title="Task 2",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
            scope_in=["src/auth/login.py"],
        )
        task_2.requirements.add(req_b)

        out = StringIO()
        call_command("detect_integration_risks", stdout=out)
        output = out.getvalue()

        assert "LOW" in output
        assert "Scope Overlap" in output
        assert "task-1" in output
        assert "task-2" in output

    @pytest.mark.django_db
    def test_detect_integration_risks__no_conflicts(self, agent, req_a, req_c):
        """Tasks with no overlap produce a clean report."""
        task_1 = AgentTask.objects.create(
            external_id="task-1",
            title="Task 1",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
            scope_in=["src/auth/"],
        )
        task_1.requirements.add(req_a)

        task_2 = AgentTask.objects.create(
            external_id="task-2",
            title="Task 2",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
            scope_in=["src/billing/"],
        )
        task_2.requirements.add(req_c)

        out = StringIO()
        call_command("detect_integration_risks", stdout=out)
        output = out.getvalue()

        assert "No integration risks detected" in output

    @pytest.mark.django_db
    def test_detect_integration_risks__json_format(self, agent, req_a):
        """JSON output contains expected structure."""
        task_1 = AgentTask.objects.create(
            external_id="task-1",
            title="Task 1",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
        )
        task_1.requirements.add(req_a)

        task_2 = AgentTask.objects.create(
            external_id="task-2",
            title="Task 2",
            status=AgentTaskStatus.IN_PROGRESS,
            claimed_by=agent,
        )
        task_2.requirements.add(req_a)

        out = StringIO()
        call_command("detect_integration_risks", "--format", "json", stdout=out)
        data = json.loads(out.getvalue())

        assert "active_tasks" in data
        assert "risks" in data
        assert "summary" in data
        assert data["summary"]["high"] >= 1
        assert len(data["risks"]) >= 1

        risk = data["risks"][0]
        assert "task_a_id" in risk
        assert "risk_type" in risk
        assert "risk_level" in risk
        assert "recommendation" in risk

    @pytest.mark.django_db
    def test_detect_integration_risks__no_active_tasks(self, db):
        """No active tasks produce a clean message."""
        out = StringIO()
        call_command("detect_integration_risks", stdout=out)
        output = out.getvalue()

        assert "No integration risks detected" in output

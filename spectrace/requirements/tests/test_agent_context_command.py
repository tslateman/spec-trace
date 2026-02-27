"""Tests for agent_context management command."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from requirements.models import (
    Agent,
    AgentRole,
    AgentTask,
    AgentTaskStatus,
    Requirement,
    TestRequirementLink,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def coder_agent(db):
    """Create a coder agent."""
    return Agent.objects.create(
        agent_id="coder-1",
        role=AgentRole.CODER,
        is_active=True,
    )


@pytest.fixture
def sample_task(db, coder_agent):
    """Create a task with full metadata."""
    return AgentTask.objects.create(
        external_id="task-001",
        title="Implement login flow",
        description="Build the authentication login endpoint.",
        status=AgentTaskStatus.IN_PROGRESS,
        claimed_by=coder_agent,
        done_when=["pytest exits 0", "lint passes"],
        scope_in=["src/auth/"],
        scope_out=["src/legacy/"],
    )


@pytest.fixture
def sample_requirement(db):
    """Create a requirement with FRET fields."""
    return Requirement.add_root(
        external_id="REQ-AUTH-001",
        title="Login endpoint returns JWT",
        source_file="specs/auth.md",
        verification_status="passing",
        priority="high",
        scope="when user is unauthenticated",
        component="auth_service",
        response="return valid JWT token",
    )


# =============================================================================
# Test: agent_context command
# =============================================================================


class TestAgentContextCommand:
    """Tests for agent_context command."""

    def test_agent_context__outputs_markdown_for_task(self, sample_task):
        """Outputs markdown with all task sections."""
        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "# Task: Implement login flow" in output
        assert "## Description" in output
        assert "Build the authentication login endpoint." in output
        assert "## Done When" in output
        assert "## Scope" in output
        assert "**In scope:** src/auth/" in output
        assert "**Out of scope:** src/legacy/" in output

    def test_agent_context__includes_verification_status(self, sample_task, sample_requirement):
        """Includes requirement verification status in output."""
        sample_task.requirements.add(sample_requirement)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "REQ-AUTH-001" in output
        assert "Login endpoint returns JWT" in output
        assert "- Status: passing" in output

    def test_agent_context__includes_done_when(self, sample_task):
        """Renders done_when as checkboxes."""
        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "- [ ] pytest exits 0" in output
        assert "- [ ] lint passes" in output

    def test_agent_context__includes_dependency_tree(self, sample_task, db):
        """Shows requirement dependencies."""
        req_a = Requirement.add_root(
            external_id="REQ-DEP-001",
            title="Base auth module",
            source_file="specs/auth.md",
        )
        req_b = Requirement.add_root(
            external_id="REQ-DEP-002",
            title="Login depends on base",
            source_file="specs/auth.md",
        )
        req_b.depends_on.add(req_a)

        sample_task.requirements.add(req_a, req_b)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "#### Dependencies" in output
        assert "Depends on: REQ-DEP-001" in output
        assert "Depended by: REQ-DEP-002" in output

    def test_agent_context__task_with_no_requirements(self, sample_task):
        """Produces minimal output when task has no linked requirements."""
        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "# Task: Implement login flow" in output
        assert "## Description" in output
        assert "## Done When" in output
        assert "## Linked Requirements" not in output

    def test_agent_context__json_format(self, sample_task, sample_requirement):
        """JSON output is valid and contains expected keys."""
        sample_task.requirements.add(sample_requirement)

        TestRequirementLink.objects.create(
            test_nodeid="tests/test_auth.py::test_login",
            requirement=sample_requirement,
            last_status="passed",
        )

        out = StringIO()
        call_command("agent_context", "task-001", format="json", stdout=out)
        data = json.loads(out.getvalue())

        assert data["task_id"] == "task-001"
        assert data["title"] == "Implement login flow"
        assert data["done_when"] == ["pytest exits 0", "lint passes"]
        assert len(data["requirements"]) == 1

        req = data["requirements"][0]
        assert req["external_id"] == "REQ-AUTH-001"
        assert req["verification_status"] == "passing"
        assert req["fret"]["component"] == "auth_service"
        assert req["test_results"][0]["last_status"] == "passed"

    def test_agent_context__task_not_found(self, db):
        """Raises CommandError for nonexistent task."""
        with pytest.raises(CommandError, match="Task not found: nonexistent"):
            call_command("agent_context", "nonexistent")

    def test_agent_context__fret_fields_omitted_when_empty(self, sample_task, db):
        """FRET line omitted when no FRET fields populated."""
        req = Requirement.add_root(
            external_id="REQ-EMPTY-001",
            title="No structured fields",
            source_file="specs/test.md",
        )
        sample_task.requirements.add(req)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "REQ-EMPTY-001" in output
        assert "- FRET:" not in output

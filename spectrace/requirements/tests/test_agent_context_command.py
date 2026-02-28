"""Tests for agent_context management command."""

import json
import os
from io import StringIO
from unittest.mock import patch

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
        description="The login endpoint must return a valid JWT token.",
        source_file="specs/auth.md",
        verification_status="passing",
        priority="high",
        tags=["auth", "security"],
        scope="when user is unauthenticated",
        component="auth_service",
        response="return valid JWT token",
    )


# =============================================================================
# Test: Markdown output
# =============================================================================


class TestAgentContextMarkdown:
    """Tests for agent_context markdown output."""

    def test_agent_context__outputs_bundle_heading(self, sample_task):
        """Outputs '# Agent Context Bundle' as top-level heading."""
        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "# Agent Context Bundle" in output

    def test_agent_context__outputs_task_metadata(self, sample_task):
        """Renders task ID, status, done_when, and scope."""
        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "## Task: Implement login flow" in output
        assert "- ID: task-001" in output
        assert "- Status: in_progress" in output
        assert "- [ ] pytest exits 0" in output
        assert "- [ ] lint passes" in output
        assert "Scope In: src/auth/" in output
        assert "Scope Out: src/legacy/" in output

    def test_agent_context__outputs_description(self, sample_task):
        """Renders task description."""
        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "Build the authentication login endpoint." in output

    def test_agent_context__includes_linked_specs(self, sample_task, sample_requirement):
        """Renders linked specs with metadata and FRET fields."""
        sample_task.requirements.add(sample_requirement)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "## Linked Specs" in output
        assert "### Spec: Login endpoint returns JWT" in output
        assert "- ID: REQ-AUTH-001" in output
        assert "- Status: passing" in output
        assert "- Priority: high" in output
        assert "- Tags: auth, security" in output
        assert "- Source: specs/auth.md" in output
        assert "- FRET:" in output
        assert "component=auth_service" in output

    def test_agent_context__includes_spec_description(self, sample_task, sample_requirement):
        """Renders requirement description body."""
        sample_task.requirements.add(sample_requirement)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "The login endpoint must return a valid JWT token." in output

    def test_agent_context__fret_omitted_when_empty(self, sample_task, db):
        """FRET line omitted when no structured fields populated."""
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

    def test_agent_context__no_linked_specs_section_when_empty(self, sample_task):
        """Omits 'Linked Specs' section when task has no requirements."""
        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "## Linked Specs" not in output


# =============================================================================
# Test: Tree hierarchy
# =============================================================================


class TestAgentContextTreeHierarchy:
    """Tests for tree hierarchy output."""

    def test_agent_context__shows_parent(self, sample_task, db):
        """Shows parent requirement in tree hierarchy."""
        parent = Requirement.add_root(
            external_id="REQ-PARENT-001",
            title="Authentication module",
            source_file="specs/auth.md",
        )
        child = parent.add_child(
            external_id="REQ-CHILD-001",
            title="Login endpoint",
            source_file="specs/auth.md",
        )
        sample_task.requirements.add(child)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "#### Tree Hierarchy" in output
        assert "- Parent: REQ-PARENT-001: Authentication module" in output

    def test_agent_context__shows_children(self, sample_task, db):
        """Shows child requirements in tree hierarchy."""
        parent = Requirement.add_root(
            external_id="REQ-PARENT-002",
            title="Auth module",
            source_file="specs/auth.md",
        )
        parent.add_child(
            external_id="REQ-CHILD-A",
            title="Login",
            source_file="specs/auth.md",
        )
        parent.add_child(
            external_id="REQ-CHILD-B",
            title="Logout",
            source_file="specs/auth.md",
        )
        sample_task.requirements.add(parent)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "#### Tree Hierarchy" in output
        assert "- Children:" in output
        assert "  - REQ-CHILD-A: Login" in output
        assert "  - REQ-CHILD-B: Logout" in output

    def test_agent_context__omits_tree_when_root_leaf(self, sample_task, sample_requirement):
        """Omits tree hierarchy when requirement is a root leaf (no parent, no children)."""
        sample_task.requirements.add(sample_requirement)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "#### Tree Hierarchy" not in output


# =============================================================================
# Test: Test results
# =============================================================================


class TestAgentContextTestResults:
    """Tests for test results in context output."""

    def test_agent_context__includes_test_results(self, sample_task, sample_requirement):
        """Shows test results for each linked spec."""
        sample_task.requirements.add(sample_requirement)
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_auth.py::test_login",
            requirement=sample_requirement,
            last_status="passed",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_auth.py::test_login_invalid",
            requirement=sample_requirement,
            last_status="failed",
        )

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "#### Test Results" in output
        assert "tests/test_auth.py::test_login: passed" in output
        assert "tests/test_auth.py::test_login_invalid: failed" in output


# =============================================================================
# Test: Drift detection
# =============================================================================


class TestAgentContextDrift:
    """Tests for inline drift detection."""

    @patch(
        "requirements.management.commands.agent_context.detect_stale_links",
        autospec=True,
    )
    @patch(
        "requirements.management.commands.agent_context.detect_orphan_requirements",
        autospec=True,
    )
    def test_agent_context__includes_drift_in_json(self, mock_orphans, mock_stale, sample_task):
        """JSON output includes drift detection results."""
        from requirements.validator import DriftResult

        mock_stale.return_value = DriftResult(items_checked=5)
        mock_orphans.return_value = DriftResult(items_checked=3)

        out = StringIO()
        call_command("agent_context", "task-001", format="json", stdout=out)
        data = json.loads(out.getvalue())

        assert "drift" in data
        assert "stale_links" in data["drift"]
        assert "orphan_requirements" in data["drift"]

    @patch(
        "requirements.management.commands.agent_context.detect_stale_links",
        autospec=True,
    )
    @patch(
        "requirements.management.commands.agent_context.detect_orphan_requirements",
        autospec=True,
    )
    def test_agent_context__renders_drift_issues_in_markdown(
        self, mock_orphans, mock_stale, sample_task
    ):
        """Markdown output includes drift issues when present."""
        from requirements.validator import DriftResult, ValidationIssue

        mock_stale.return_value = DriftResult(
            errors=[
                ValidationIssue(
                    type="stale_link",
                    id="tests/old.py::test_gone:REQ-001",
                    message="Link references test not in latest run",
                )
            ],
            items_checked=1,
        )
        mock_orphans.return_value = DriftResult(items_checked=0)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "## Drift" in output
        assert "[stale_link]" in output
        assert "Link references test not in latest run" in output

    @patch(
        "requirements.management.commands.agent_context.detect_stale_links",
        autospec=True,
    )
    @patch(
        "requirements.management.commands.agent_context.detect_orphan_requirements",
        autospec=True,
    )
    def test_agent_context__omits_drift_section_when_clean(
        self, mock_orphans, mock_stale, sample_task
    ):
        """Markdown output omits drift section when no issues found."""
        from requirements.validator import DriftResult

        mock_stale.return_value = DriftResult(items_checked=5)
        mock_orphans.return_value = DriftResult(items_checked=3)

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "## Drift" not in output


# =============================================================================
# Test: Lore overlay
# =============================================================================


class TestAgentContextLoreOverlay:
    """Tests for Lore CLI integration."""

    @patch(
        "requirements.management.commands.agent_context._find_lore_cli",
        autospec=True,
    )
    def test_agent_context__skips_lore_when_cli_missing(self, mock_find_cli, sample_task):
        """Emits warning and omits Lore section when CLI not found."""
        mock_find_cli.return_value = None

        out = StringIO()
        err = StringIO()
        call_command("agent_context", "task-001", stdout=out, stderr=err)

        assert "Lore CLI not found" in err.getvalue()
        assert "## Lore Context" not in out.getvalue()

    @patch(
        "requirements.management.commands.agent_context._lore_overlay",
        autospec=True,
    )
    @patch(
        "requirements.management.commands.agent_context._find_lore_cli",
        autospec=True,
    )
    def test_agent_context__includes_lore_when_available(
        self, mock_find_cli, mock_overlay, sample_task, sample_requirement
    ):
        """Includes Lore section when CLI is available and returns data."""
        sample_task.requirements.add(sample_requirement)
        mock_find_cli.return_value = "/usr/local/bin/lore"
        mock_overlay.return_value = [
            {"title": "Auth design decision", "content": "Use JWT for stateless auth"}
        ]

        out = StringIO()
        call_command("agent_context", "task-001", stdout=out)
        output = out.getvalue()

        assert "## Lore Context" in output
        assert "Auth design decision" in output

    @patch(
        "requirements.management.commands.agent_context._lore_overlay",
        autospec=True,
    )
    @patch(
        "requirements.management.commands.agent_context._find_lore_cli",
        autospec=True,
    )
    def test_agent_context__lore_query_combines_tags_and_titles(
        self, mock_find_cli, mock_overlay, sample_task, sample_requirement
    ):
        """Lore query includes sorted tags + titles from all requirements."""
        sample_task.requirements.add(sample_requirement)
        mock_find_cli.return_value = "/usr/local/bin/lore"
        mock_overlay.return_value = None

        call_command("agent_context", "task-001", stdout=StringIO())

        mock_overlay.assert_called_once()
        call_args = mock_overlay.call_args
        query = call_args[0][1]  # second positional arg
        assert "auth" in query
        assert "security" in query
        assert "Login endpoint returns JWT" in query

    @patch(
        "requirements.management.commands.agent_context._lore_overlay",
        autospec=True,
    )
    @patch(
        "requirements.management.commands.agent_context._find_lore_cli",
        autospec=True,
    )
    def test_agent_context__lore_in_json_output(
        self, mock_find_cli, mock_overlay, sample_task, sample_requirement
    ):
        """JSON output includes lore data."""
        sample_task.requirements.add(sample_requirement)
        mock_find_cli.return_value = "/usr/local/bin/lore"
        mock_overlay.return_value = [{"title": "Decision A"}]

        out = StringIO()
        call_command("agent_context", "task-001", format="json", stdout=out)
        data = json.loads(out.getvalue())

        assert "lore" in data
        assert data["lore"][0]["title"] == "Decision A"


# =============================================================================
# Test: _find_lore_cli
# =============================================================================


class TestFindLoreCli:
    """Tests for Lore CLI discovery."""

    @patch("requirements.management.commands.agent_context.shutil.which", autospec=True)
    @patch.dict(os.environ, {"LORE_CLI": ""})
    def test_find_lore_cli__returns_none_when_not_found(self, mock_which):
        """Returns None when LORE_CLI is empty and lore not on PATH."""
        mock_which.return_value = None

        from requirements.management.commands.agent_context import _find_lore_cli

        assert _find_lore_cli() is None

    @patch("requirements.management.commands.agent_context.os.path.isfile", autospec=True)
    @patch.dict(os.environ, {"LORE_CLI": "/custom/path/lore"})
    def test_find_lore_cli__prefers_env_var(self, mock_isfile):
        """Returns LORE_CLI env var path when it exists."""
        mock_isfile.return_value = True

        from requirements.management.commands.agent_context import _find_lore_cli

        assert _find_lore_cli() == "/custom/path/lore"

    @patch("requirements.management.commands.agent_context.shutil.which", autospec=True)
    @patch.dict(os.environ, {"LORE_CLI": ""})
    def test_find_lore_cli__falls_back_to_path(self, mock_which):
        """Falls back to PATH lookup when LORE_CLI is not set."""
        mock_which.return_value = "/usr/local/bin/lore"

        from requirements.management.commands.agent_context import _find_lore_cli

        assert _find_lore_cli() == "/usr/local/bin/lore"


# =============================================================================
# Test: _lore_overlay
# =============================================================================


class TestLoreOverlay:
    """Tests for Lore subprocess call."""

    @patch("requirements.management.commands.agent_context.subprocess.run", autospec=True)
    def test_lore_overlay__parses_json_on_success(self, mock_run):
        """Parses JSON stdout on successful subprocess."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps([{"title": "entry"}])

        from requirements.management.commands.agent_context import _lore_overlay

        result = _lore_overlay("/bin/lore", "test query")
        assert result == [{"title": "entry"}]

    @patch("requirements.management.commands.agent_context.subprocess.run", autospec=True)
    def test_lore_overlay__returns_none_on_failure(self, mock_run):
        """Returns None when subprocess exits non-zero."""
        mock_run.return_value.returncode = 1

        from requirements.management.commands.agent_context import _lore_overlay

        assert _lore_overlay("/bin/lore", "test query") is None

    @patch("requirements.management.commands.agent_context.subprocess.run", autospec=True)
    def test_lore_overlay__returns_none_on_timeout(self, mock_run):
        """Returns None when subprocess times out."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="lore", timeout=30)

        from requirements.management.commands.agent_context import _lore_overlay

        assert _lore_overlay("/bin/lore", "test query") is None

    @patch("requirements.management.commands.agent_context.subprocess.run", autospec=True)
    def test_lore_overlay__passes_30s_timeout(self, mock_run):
        """Passes 30-second timeout to subprocess."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "[]"

        from requirements.management.commands.agent_context import _lore_overlay

        _lore_overlay("/bin/lore", "query")
        assert mock_run.call_args.kwargs["timeout"] == 30


# =============================================================================
# Test: JSON format
# =============================================================================


class TestAgentContextJSON:
    """Tests for JSON output format."""

    @patch(
        "requirements.management.commands.agent_context._find_lore_cli",
        autospec=True,
    )
    def test_agent_context__json_includes_all_fields(
        self, mock_find_cli, sample_task, sample_requirement
    ):
        """JSON output contains task, requirements, tree, drift, and test results."""
        mock_find_cli.return_value = None

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
        assert data["scope_in"] == ["src/auth/"]
        assert data["scope_out"] == ["src/legacy/"]
        assert len(data["requirements"]) == 1

        req = data["requirements"][0]
        assert req["external_id"] == "REQ-AUTH-001"
        assert req["verification_status"] == "passing"
        assert req["tags"] == ["auth", "security"]
        assert req["source_file"] == "specs/auth.md"
        assert req["description"] == "The login endpoint must return a valid JWT token."
        assert req["fret"]["component"] == "auth_service"
        assert req["test_results"][0]["last_status"] == "passed"
        assert "tree" in req
        assert "drift" in data

    @patch(
        "requirements.management.commands.agent_context._find_lore_cli",
        autospec=True,
    )
    def test_agent_context__json_tree_with_parent_and_children(
        self, mock_find_cli, sample_task, db
    ):
        """JSON tree includes parent and children."""
        mock_find_cli.return_value = None

        parent = Requirement.add_root(
            external_id="REQ-P-001",
            title="Parent",
            source_file="specs/test.md",
        )
        child = parent.add_child(
            external_id="REQ-C-001",
            title="Child A",
            source_file="specs/test.md",
        )
        parent.add_child(
            external_id="REQ-C-002",
            title="Child B",
            source_file="specs/test.md",
        )
        sample_task.requirements.add(child)

        out = StringIO()
        call_command("agent_context", "task-001", format="json", stdout=out)
        data = json.loads(out.getvalue())

        req = data["requirements"][0]
        assert req["tree"]["parent"]["external_id"] == "REQ-P-001"
        assert req["tree"]["parent"]["title"] == "Parent"


# =============================================================================
# Test: --output flag
# =============================================================================


class TestAgentContextOutputFlag:
    """Tests for --output file writing."""

    @patch(
        "requirements.management.commands.agent_context._find_lore_cli",
        autospec=True,
    )
    def test_agent_context__writes_output_to_file(self, mock_find_cli, sample_task, tmp_path):
        """--output writes identical content to file."""
        mock_find_cli.return_value = None

        output_file = tmp_path / "context.md"
        out = StringIO()
        call_command("agent_context", "task-001", output=str(output_file), stdout=out)

        stdout_content = out.getvalue()
        file_content = output_file.read_text()
        assert file_content == stdout_content
        assert "# Agent Context Bundle" in file_content

    @patch(
        "requirements.management.commands.agent_context._find_lore_cli",
        autospec=True,
    )
    def test_agent_context__writes_json_to_file(self, mock_find_cli, sample_task, tmp_path):
        """--output with --format json writes valid JSON to file."""
        mock_find_cli.return_value = None

        output_file = tmp_path / "context.json"
        call_command(
            "agent_context",
            "task-001",
            format="json",
            output=str(output_file),
            stdout=StringIO(),
        )

        data = json.loads(output_file.read_text())
        assert data["task_id"] == "task-001"


# =============================================================================
# Test: Error handling
# =============================================================================


class TestAgentContextErrors:
    """Tests for error cases."""

    def test_agent_context__task_not_found(self, db):
        """Raises CommandError for nonexistent task."""
        with pytest.raises(CommandError, match="Task not found: nonexistent"):
            call_command("agent_context", "nonexistent")

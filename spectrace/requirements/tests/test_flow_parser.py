"""Tests for YAML flow parser and sync functionality.

Tests cover:
- YAMLFlowParser validation (required fields, step types, error handling)
- Directory scanning (file patterns, non-flow YAML handling)
- sync_yaml_flows_to_db (create, update, clear, metadata storage)
- parse_flows management command (dry-run, clear, error handling)
"""

import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from requirements.flows.definitions import FlowDef, FlowStepDef
from requirements.flows.parser import FlowParseError, YAMLFlowParser
from requirements.flows.sync import sync_yaml_flows_to_db
from requirements.models import Requirement, VerificationFlow

# ============================================================================
# YAMLFlowParser Tests
# ============================================================================


class TestYAMLFlowParser:
    """Tests for YAMLFlowParser class."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return YAMLFlowParser()

    @pytest.fixture
    def valid_yaml(self, tmp_path):
        """Create valid flow YAML file."""
        content = """
id: test-flow
title: Test Flow
description: A test flow
version: 2
requirements:
  - REQ-001
  - REQ-002
steps:
  - name: check
    type: handler
    display_name: Check Step
    description: Does a check
    handler: module.check_function
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(content)
        return yaml_file

    def test_parse_file__returns_flow_def(self, parser, valid_yaml):
        """Parse valid YAML returns FlowDef."""
        flow = parser.parse_file(valid_yaml)

        assert flow is not None
        assert flow.name == "test-flow"
        assert flow.display_name == "Test Flow"
        assert flow.description == "A test flow"
        assert flow.version == 2
        assert flow.requirements == ["REQ-001", "REQ-002"]
        assert flow.source_file == str(valid_yaml)
        assert len(flow.steps) == 1

    def test_parse_file__populates_step_fields(self, parser, valid_yaml):
        """Step fields are correctly populated."""
        flow = parser.parse_file(valid_yaml)

        step = flow.steps[0]
        assert step.name == "check"
        assert step.type == "handler"
        assert step.display_name == "Check Step"
        assert step.description == "Does a check"
        assert step.handler == "module.check_function"
        assert step.config == {}

    def test_parse_file__returns_none_for_non_flow_yaml(self, parser, tmp_path):
        """Returns None for YAML without id and steps."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("database:\n  host: localhost\n  port: 5432")

        result = parser.parse_file(yaml_file)

        assert result is None

    def test_parse_file__raises_for_missing_id(self, parser, tmp_path):
        """Raises FlowParseError when id is missing but steps present."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("steps:\n  - name: test\n    display_name: Test")

        with pytest.raises(FlowParseError) as exc_info:
            parser.parse_file(yaml_file)

        assert "Missing required field: id" in str(exc_info.value)

    def test_parse_file__raises_for_missing_steps(self, parser, tmp_path):
        """Raises FlowParseError when steps is missing but id present."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("id: test-flow\ntitle: Test")

        with pytest.raises(FlowParseError) as exc_info:
            parser.parse_file(yaml_file)

        assert "Missing required field: steps" in str(exc_info.value)

    def test_parse_file__raises_for_missing_title(self, parser, tmp_path):
        """Raises FlowParseError when title is missing."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("id: test-flow\nsteps:\n  - name: s\n    display_name: S")

        with pytest.raises(FlowParseError) as exc_info:
            parser.parse_file(yaml_file)

        assert "title" in str(exc_info.value)

    def test_parse_file__raises_for_empty_steps(self, parser, tmp_path):
        """Raises FlowParseError when steps list is empty."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("id: test-flow\ntitle: Test\nsteps: []")

        with pytest.raises(FlowParseError) as exc_info:
            parser.parse_file(yaml_file)

        assert "at least one step" in str(exc_info.value)

    def test_parse_file__raises_for_invalid_step_type(self, parser, tmp_path):
        """Raises FlowParseError for invalid step type."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("""
id: test-flow
title: Test
steps:
  - name: bad
    type: invalid_type
    display_name: Bad
""")

        with pytest.raises(FlowParseError) as exc_info:
            parser.parse_file(yaml_file)

        assert "invalid type" in str(exc_info.value)
        assert "invalid_type" in str(exc_info.value)

    def test_parse_file__raises_for_handler_without_handler_field(self, parser, tmp_path):
        """Raises FlowParseError when type=handler but no handler field."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("""
id: test-flow
title: Test
steps:
  - name: check
    type: handler
    display_name: Check
""")

        with pytest.raises(FlowParseError) as exc_info:
            parser.parse_file(yaml_file)

        assert "requires 'handler' field" in str(exc_info.value)

    def test_parse_file__allows_non_handler_without_handler_field(self, parser, tmp_path):
        """Non-handler step types don't require handler field."""
        yaml_file = tmp_path / "valid.yaml"
        yaml_file.write_text("""
id: test-flow
title: Test
steps:
  - name: check
    type: assertion
    display_name: Check
    config:
      field: status
      value: ok
""")

        flow = parser.parse_file(yaml_file)

        assert flow is not None
        assert flow.steps[0].type == "assertion"
        assert flow.steps[0].handler == ""  # Empty, not required

    def test_parse_file__defaults_optional_fields(self, parser, tmp_path):
        """Optional fields have correct defaults."""
        yaml_file = tmp_path / "minimal.yaml"
        yaml_file.write_text("""
id: minimal
title: Minimal Flow
steps:
  - name: step1
    type: assertion
    display_name: Step 1
""")

        flow = parser.parse_file(yaml_file)

        assert flow.description == ""
        assert flow.version == 1
        assert flow.requirements == []
        assert flow.steps[0].description == ""
        assert flow.steps[0].config == {}

    def test_parse_file__handles_null_requirements(self, parser, tmp_path):
        """Null requirements becomes empty list."""
        yaml_file = tmp_path / "null_reqs.yaml"
        yaml_file.write_text("""
id: test
title: Test
requirements: null
steps:
  - name: s
    type: assertion
    display_name: S
""")

        flow = parser.parse_file(yaml_file)

        assert flow.requirements == []

    def test_parse_file__handles_null_config(self, parser, tmp_path):
        """Null config becomes empty dict."""
        yaml_file = tmp_path / "null_config.yaml"
        yaml_file.write_text("""
id: test
title: Test
steps:
  - name: s
    type: assertion
    display_name: S
    config: null
""")

        flow = parser.parse_file(yaml_file)

        assert flow.steps[0].config == {}


class TestYAMLFlowParserDirectory:
    """Tests for parse_directory method."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return YAMLFlowParser()

    def test_parse_directory__finds_yaml_files(self, parser, tmp_path):
        """Finds and parses all YAML files in directory."""
        # Create two valid flow files
        (tmp_path / "flow1.yaml").write_text("""
id: flow-one
title: Flow One
steps:
  - name: s
    type: assertion
    display_name: S
""")
        (tmp_path / "flow2.yml").write_text("""
id: flow-two
title: Flow Two
steps:
  - name: s
    type: assertion
    display_name: S
""")

        flows = parser.parse_directory(tmp_path)

        assert len(flows) == 2
        names = [f.name for f in flows]
        assert "flow-one" in names
        assert "flow-two" in names

    def test_parse_directory__finds_nested_yaml_files(self, parser, tmp_path):
        """Finds YAML files in subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.yaml").write_text("""
id: nested-flow
title: Nested Flow
steps:
  - name: s
    type: assertion
    display_name: S
""")

        flows = parser.parse_directory(tmp_path)

        assert len(flows) == 1
        assert flows[0].name == "nested-flow"

    def test_parse_directory__skips_non_flow_yaml(self, parser, tmp_path):
        """Non-flow YAML files are skipped."""
        (tmp_path / "config.yaml").write_text("database: postgres")
        (tmp_path / "flow.yaml").write_text("""
id: real-flow
title: Real Flow
steps:
  - name: s
    type: assertion
    display_name: S
""")

        flows = parser.parse_directory(tmp_path)

        assert len(flows) == 1
        assert flows[0].name == "real-flow"

    def test_parse_directory__raises_on_malformed_flow(self, parser, tmp_path):
        """Raises FlowParseError for malformed flow files."""
        (tmp_path / "bad.yaml").write_text("""
id: incomplete
steps: []
""")

        with pytest.raises(FlowParseError):
            parser.parse_directory(tmp_path)

    def test_parse_directory__returns_sorted_by_path(self, parser, tmp_path):
        """Returns flows sorted by file path for deterministic order."""
        (tmp_path / "z_flow.yaml").write_text("""
id: z-flow
title: Z Flow
steps:
  - name: s
    type: assertion
    display_name: S
""")
        (tmp_path / "a_flow.yaml").write_text("""
id: a-flow
title: A Flow
steps:
  - name: s
    type: assertion
    display_name: S
""")

        flows = parser.parse_directory(tmp_path)

        assert len(flows) == 2
        # Should be sorted by filename
        assert flows[0].name == "a-flow"
        assert flows[1].name == "z-flow"


# ============================================================================
# sync_yaml_flows_to_db Tests
# ============================================================================


class TestSyncYAMLFlowsToDb:
    """Tests for sync_yaml_flows_to_db function."""

    @pytest.fixture
    def sample_flow(self):
        """Create a sample FlowDef."""
        return FlowDef(
            name="test-flow",
            display_name="Test Flow",
            description="A test flow",
            steps=[
                FlowStepDef(
                    name="step1",
                    handler="module.handler",
                    display_name="Step 1",
                    description="First step",
                )
            ],
            version=1,
            requirements=["REQ-001", "REQ-002"],
            source_file="/path/to/flow.yaml",
        )

    def test_creates_new_flow(self, db, sample_flow):
        """Creates flow when it doesn't exist."""
        result = sync_yaml_flows_to_db([sample_flow])

        assert result["test-flow"] == "created"
        flow = VerificationFlow.objects.get(name="test-flow")
        assert flow.display_name == "Test Flow"
        assert flow.description == "A test flow"
        assert flow.version == 1
        assert flow.synced_at is not None

    def test_stores_metadata_in_steps(self, db, sample_flow):
        """Stores source_file in steps JSON (requirements via M2M)."""
        sync_yaml_flows_to_db([sample_flow])

        flow = VerificationFlow.objects.get(name="test-flow")
        # First element should be metadata
        metadata = flow.steps[0]
        assert "_metadata" in metadata
        assert metadata["_metadata"]["source_file"] == "/path/to/flow.yaml"
        # Requirements no longer stored in metadata (now via M2M)
        assert "requirements" not in metadata["_metadata"]
        # Steps follow metadata
        assert len(flow.steps) == 2  # 1 metadata + 1 step
        assert flow.steps[1]["name"] == "step1"

    def test_updates_existing_flow(self, db, sample_flow):
        """Updates flow when it already exists."""
        # Create existing flow
        VerificationFlow.objects.create(
            name="test-flow",
            display_name="Old Name",
            steps=[],
            version=0,
        )

        result = sync_yaml_flows_to_db([sample_flow])

        assert result["test-flow"] == "updated"
        flow = VerificationFlow.objects.get(name="test-flow")
        assert flow.display_name == "Test Flow"
        assert flow.version == 1

    def test_clear_existing_deletes_by_name(self, db, sample_flow):
        """clear_existing=True deletes only matching flows."""
        # Create existing flows
        VerificationFlow.objects.create(name="test-flow", display_name="Old", steps=[])
        VerificationFlow.objects.create(name="other-flow", display_name="Other", steps=[])

        result = sync_yaml_flows_to_db([sample_flow], clear_existing=True)

        # test-flow should be recreated
        assert result["test-flow"] == "created"
        # other-flow should still exist
        assert VerificationFlow.objects.filter(name="other-flow").exists()

    def test_syncs_multiple_flows(self, db):
        """Syncs multiple flows at once."""
        flows = [
            FlowDef(
                name="flow-1",
                display_name="Flow 1",
                description="",
                steps=[FlowStepDef(name="s", handler="h", display_name="S")],
            ),
            FlowDef(
                name="flow-2",
                display_name="Flow 2",
                description="",
                steps=[FlowStepDef(name="s", handler="h", display_name="S")],
            ),
        ]

        result = sync_yaml_flows_to_db(flows)

        assert len(result) == 2
        assert result["flow-1"] == "created"
        assert result["flow-2"] == "created"
        assert VerificationFlow.objects.count() == 2

    def test_links_requirements_via_m2m(self, db):
        """Links requirements to flows via M2M relationship."""
        # Create requirements using treebeard's add_root (MP_Node)
        req1 = Requirement.add_root(external_id="REQ-001", title="Req 1")
        req2 = Requirement.add_root(external_id="REQ-002", title="Req 2")

        flow_def = FlowDef(
            name="linked-flow",
            display_name="Linked Flow",
            description="Flow with requirements",
            steps=[FlowStepDef(name="step1", handler="h", display_name="Step 1")],
            requirements=["REQ-001", "REQ-002"],
            source_file="/path/to/flow.yaml",
        )

        sync_yaml_flows_to_db([flow_def])

        flow = VerificationFlow.objects.get(name="linked-flow")
        # Requirements should be linked via M2M
        assert flow.requirements.count() == 2
        assert set(flow.requirements.values_list("external_id", flat=True)) == {
            "REQ-001",
            "REQ-002",
        }
        # Reverse access should also work
        assert req1.verification_flows.filter(name="linked-flow").exists()
        assert req2.verification_flows.filter(name="linked-flow").exists()

    def test_warns_on_missing_requirements(self, db, caplog):
        """Logs warnings for requirements that don't exist."""
        # Only create one requirement (using treebeard's add_root)
        Requirement.add_root(external_id="REQ-001", title="Req 1")

        flow_def = FlowDef(
            name="partial-flow",
            display_name="Partial Flow",
            description="Flow with some missing requirements",
            steps=[FlowStepDef(name="step1", handler="h", display_name="Step 1")],
            requirements=["REQ-001", "REQ-MISSING"],
            source_file="/path/to/flow.yaml",
        )

        sync_yaml_flows_to_db([flow_def])

        flow = VerificationFlow.objects.get(name="partial-flow")
        # Only the existing requirement should be linked
        assert flow.requirements.count() == 1
        assert flow.requirements.first().external_id == "REQ-001"
        # Warning should be logged for missing requirement
        assert "REQ-MISSING" in caplog.text
        assert "not found" in caplog.text

    def test_clears_requirements_when_none(self, db):
        """Clears M2M when flow has no requirements."""
        # Create requirement using treebeard's add_root
        req = Requirement.add_root(external_id="REQ-001", title="Req 1")
        flow = VerificationFlow.objects.create(
            name="clear-flow",
            display_name="Clear Flow",
            steps=[],
        )
        flow.requirements.add(req)
        assert flow.requirements.count() == 1

        # Sync with no requirements
        flow_def = FlowDef(
            name="clear-flow",
            display_name="Clear Flow Updated",
            description="",
            steps=[FlowStepDef(name="step1", handler="h", display_name="Step 1")],
            requirements=[],  # Empty list
            source_file="/path/to/flow.yaml",
        )

        sync_yaml_flows_to_db([flow_def])

        flow.refresh_from_db()
        assert flow.requirements.count() == 0


# ============================================================================
# parse_flows Management Command Tests
# ============================================================================


class TestParseFlowsCommand:
    """Tests for parse_flows management command."""

    def test_dry_run__shows_flows_without_saving(self, db, tmp_path):
        """--dry-run shows flows but doesn't save to database."""
        (tmp_path / "flow.yaml").write_text("""
id: dry-run-flow
title: Dry Run Flow
requirements:
  - REQ-001
steps:
  - name: check
    type: assertion
    display_name: Check
""")

        stdout = io.StringIO()
        call_command("parse_flows", str(tmp_path), "--dry-run", stdout=stdout)

        output = stdout.getvalue()
        assert "dry-run-flow" in output
        assert "Dry run complete" in output
        assert VerificationFlow.objects.filter(name="dry-run-flow").count() == 0

    def test_sync__creates_flows_in_database(self, db, tmp_path):
        """Command syncs flows to database."""
        (tmp_path / "flow.yaml").write_text("""
id: synced-flow
title: Synced Flow
steps:
  - name: check
    type: assertion
    display_name: Check
""")

        stdout = io.StringIO()
        call_command("parse_flows", str(tmp_path), stdout=stdout)

        assert VerificationFlow.objects.filter(name="synced-flow").exists()
        output = stdout.getvalue()
        assert "1 created" in output

    def test_clear__removes_existing_before_sync(self, db, tmp_path):
        """--clear removes existing flows before syncing."""
        # Create existing flow that will be cleared
        VerificationFlow.objects.create(
            name="will-replace",
            display_name="Will Replace",
            steps=[],
        )

        (tmp_path / "flow.yaml").write_text("""
id: will-replace
title: Replaced Flow
steps:
  - name: check
    type: assertion
    display_name: Check
""")

        stdout = io.StringIO()
        call_command("parse_flows", str(tmp_path), "--clear", stdout=stdout)

        flow = VerificationFlow.objects.get(name="will-replace")
        assert flow.display_name == "Replaced Flow"

    def test_missing_directory__raises_error(self, db):
        """Raises CommandError for non-existent directory."""
        stdout = io.StringIO()
        stderr = io.StringIO()

        with pytest.raises(CommandError) as exc_info:
            call_command("parse_flows", "/nonexistent/path", stdout=stdout, stderr=stderr)

        assert "not found" in str(exc_info.value)

    def test_empty_directory__shows_warning(self, db, tmp_path):
        """Shows warning when no flows found."""
        stdout = io.StringIO()
        call_command("parse_flows", str(tmp_path), stdout=stdout)

        output = stdout.getvalue()
        assert "No flow files found" in output

    def test_shows_flow_details(self, db, tmp_path):
        """Shows flow details including steps and requirements count."""
        (tmp_path / "flow.yaml").write_text("""
id: detailed-flow
title: Detailed Flow
requirements:
  - REQ-001
  - REQ-002
steps:
  - name: step1
    type: handler
    display_name: Step 1
    handler: mod.func
  - name: step2
    type: assertion
    display_name: Step 2
""")

        stdout = io.StringIO()
        call_command("parse_flows", str(tmp_path), "--dry-run", stdout=stdout)

        output = stdout.getvalue()
        assert "detailed-flow" in output
        assert "steps=2" in output
        assert "requirements=2" in output

    def test_accepts_single_file(self, db, tmp_path):
        """Command accepts a single YAML file path."""
        yaml_file = tmp_path / "single-flow.yaml"
        yaml_file.write_text("""
id: single-file-flow
title: Single File Flow
steps:
  - name: check
    type: assertion
    display_name: Check
""")

        stdout = io.StringIO()
        call_command("parse_flows", str(yaml_file), "--dry-run", stdout=stdout)

        output = stdout.getvalue()
        assert "single-file-flow" in output
        assert "Found 1 flow(s)" in output
        assert "Dry run complete" in output

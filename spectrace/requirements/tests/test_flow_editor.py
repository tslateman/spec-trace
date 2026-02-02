"""Tests for flow editor service module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from requirements.flow_editor import (
    FLOWS_DIR,
    FlowEditorError,
    get_flow_files,
    load_flow_for_editing,
    save_flow,
    validate_flow_path,
)
from requirements.flows.parser import FlowParseError


class TestValidateFlowPath:
    """Tests for validate_flow_path function."""

    def test_validate_flow_path__accepts_valid_yaml(self):
        """Valid YAML path returns resolved Path within FLOWS_DIR."""
        result = validate_flow_path("linear-connection.yaml")

        assert isinstance(result, Path)
        assert result.is_relative_to(FLOWS_DIR.resolve())
        assert result.name == "linear-connection.yaml"

    def test_validate_flow_path__blocks_path_traversal(self):
        """Path traversal attempts raise PermissionError."""
        with pytest.raises(PermissionError, match="Path traversal blocked"):
            validate_flow_path("../secrets.yaml")

    def test_validate_flow_path__blocks_deep_traversal(self):
        """Deep path traversal attempts also blocked."""
        with pytest.raises(PermissionError, match="Path traversal blocked"):
            validate_flow_path("subdir/../../secrets.yaml")

    def test_validate_flow_path__rejects_non_yaml(self):
        """Non-YAML extensions raise ValueError."""
        with pytest.raises(ValueError, match=r"\.yaml or \.yml extension"):
            validate_flow_path("readme.txt")

    def test_validate_flow_path__accepts_yml_extension(self):
        """Files with .yml extension are accepted."""
        result = validate_flow_path("test.yml")

        assert isinstance(result, Path)
        assert result.name == "test.yml"

    def test_validate_flow_path__accepts_subdirectory(self):
        """Subdirectory paths within FLOWS_DIR are accepted."""
        result = validate_flow_path("subdir/flow.yaml")

        assert isinstance(result, Path)
        assert result.is_relative_to(FLOWS_DIR.resolve())


class TestGetFlowFiles:
    """Tests for get_flow_files function."""

    def test_get_flow_files__returns_existing_flows(self):
        """Returns list of flow files with expected metadata."""
        result = get_flow_files()

        assert isinstance(result, list)
        assert len(result) >= 2  # linear-connection.yaml, example-api-check.yaml

        # Find linear-connection.yaml
        linear = next((f for f in result if f["name"] == "linear-connection"), None)
        assert linear is not None
        assert linear["valid"] is True
        assert linear["title"] == "Linear Connection Verification"
        assert linear["step_count"] == 3
        assert linear["error"] is None

        # Find example-api-check.yaml
        api_check = next((f for f in result if f["name"] == "example-api-check"), None)
        assert api_check is not None
        assert api_check["valid"] is True
        assert api_check["step_count"] == 2

    def test_get_flow_files__has_required_keys(self):
        """Each flow dict has all required keys."""
        result = get_flow_files()

        required_keys = {"path", "name", "title", "valid", "error", "step_count"}
        for flow in result:
            assert set(flow.keys()) == required_keys

    def test_get_flow_files__returns_empty_for_missing_dir(self):
        """Returns empty list if FLOWS_DIR doesn't exist."""
        with patch(
            "requirements.flow_editor.FLOWS_DIR", Path("/nonexistent/flows")
        ):
            result = get_flow_files()

        assert result == []


class TestLoadFlowForEditing:
    """Tests for load_flow_for_editing function."""

    def test_load_flow_for_editing__returns_dict(self):
        """Loading a valid flow returns dict with expected keys."""
        result = load_flow_for_editing("linear-connection.yaml")

        assert isinstance(result, dict)
        assert "id" in result
        assert "title" in result
        assert "steps" in result
        assert result["id"] == "linear-connection"
        assert result["title"] == "Linear Connection Verification"

    def test_load_flow_for_editing__blocks_path_traversal(self):
        """Path traversal attempts raise PermissionError."""
        with pytest.raises(PermissionError, match="Path traversal blocked"):
            load_flow_for_editing("../secrets.yaml")

    def test_load_flow_for_editing__raises_on_missing_file(self):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_flow_for_editing("nonexistent.yaml")


class TestSaveFlow:
    """Tests for save_flow function."""

    def test_save_flow__preserves_comments(self, tmp_path):
        """Comments in YAML file are preserved after save."""
        # Create temp flow file with comment
        flow_file = tmp_path / "test-flow.yaml"
        flow_file.write_text(
            """# This is a comment that should be preserved
id: test-flow
title: Test Flow
description: A test flow
version: 1
requirements: []
steps:
  - name: step1
    type: handler
    display_name: Step One
    handler: some.handler
"""
        )

        # Patch FLOWS_DIR to use tmp_path
        with patch("requirements.flow_editor.FLOWS_DIR", tmp_path):
            # Load the flow
            data = load_flow_for_editing("test-flow.yaml")

            # Modify title
            data["title"] = "Updated Test Flow"

            # Save back
            save_flow("test-flow.yaml", data)

        # Read raw file and verify comment preserved
        content = flow_file.read_text()
        assert "# This is a comment that should be preserved" in content
        assert "Updated Test Flow" in content

    def test_save_flow__validates_content(self, tmp_path):
        """Invalid flow data raises FlowParseError."""
        # Create temp flow file
        flow_file = tmp_path / "test.yaml"
        flow_file.write_text("id: test\ntitle: Test\nsteps: []")

        with patch("requirements.flow_editor.FLOWS_DIR", tmp_path):
            # Try saving invalid data (missing required 'id' field)
            invalid_data = {"title": "Missing ID", "steps": []}

            with pytest.raises(FlowParseError, match="Missing required fields"):
                save_flow("test.yaml", invalid_data)

    def test_save_flow__validates_steps(self, tmp_path):
        """Invalid steps raise FlowParseError."""
        flow_file = tmp_path / "test.yaml"
        flow_file.write_text("id: test\ntitle: Test\nsteps: []")

        with patch("requirements.flow_editor.FLOWS_DIR", tmp_path):
            # Empty steps list is invalid
            invalid_data = {"id": "test", "title": "Test", "steps": []}

            with pytest.raises(FlowParseError, match="at least one step"):
                save_flow("test.yaml", invalid_data)

    def test_save_flow__blocks_path_traversal(self, tmp_path):
        """Path traversal attempts raise PermissionError."""
        with patch("requirements.flow_editor.FLOWS_DIR", tmp_path):
            with pytest.raises(PermissionError, match="Path traversal blocked"):
                save_flow("../outside.yaml", {"id": "test"})

    def test_save_flow__creates_new_file(self, tmp_path):
        """Save creates new file if it doesn't exist."""
        with patch("requirements.flow_editor.FLOWS_DIR", tmp_path):
            valid_data = {
                "id": "new-flow",
                "title": "New Flow",
                "description": "A new flow",
                "version": 1,
                "requirements": [],
                "steps": [
                    {
                        "name": "step1",
                        "type": "handler",
                        "display_name": "Step One",
                        "handler": "some.handler",
                    }
                ],
            }

            save_flow("new-flow.yaml", valid_data)

        # Verify file created
        new_file = tmp_path / "new-flow.yaml"
        assert new_file.exists()
        content = new_file.read_text()
        assert "new-flow" in content
        assert "New Flow" in content

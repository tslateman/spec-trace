"""Integration tests for the validate_links management command."""

import json
import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from requirements.models import Requirement


@pytest.fixture
def sample_requirement(db):
    """Create a single active requirement."""
    return Requirement.add_root(
        external_id="REQ-TEST-001",
        title="Test Requirement",
        status="active",
        source_file="test.md",
    )


@pytest.fixture
def valid_links_file(sample_requirement):
    """Create a temporary links.json with valid data."""
    data = {
        "version": "1.0",
        "links": [
            {
                "test_nodeid": "tests/test_foo.py::test_example",
                "requirement_id": "REQ-TEST-001",
            }
        ],
        "summary": {"total_links": 1},
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


@pytest.fixture
def links_with_unknown_req_file(db):
    """Create a temporary links.json with unknown requirement."""
    data = {
        "version": "1.0",
        "links": [
            {
                "test_nodeid": "tests/test_foo.py::test_example",
                "requirement_id": "REQ-UNKNOWN",
            }
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


@pytest.fixture
def empty_links_file(db):
    """Create a temporary links.json with no links."""
    data = {"version": "1.0", "links": []}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


@pytest.fixture
def invalid_json_file():
    """Create a temporary file with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{not valid json")
        return Path(f.name)


@pytest.mark.requirement("REQ-CORE-005")
class TestValidateLinksCommand:
    """Integration tests for the validate_links management command."""

    @pytest.mark.django_db
    def test_command_with_valid_links(self, valid_links_file, capsys):
        """Valid file, no issues → exit 0."""
        # Should not raise SystemExit
        call_command("validate_links", str(valid_links_file))
        captured = capsys.readouterr()
        assert "No issues found" in captured.out

    @pytest.mark.django_db
    def test_command_with_errors_exits_1(self, links_with_unknown_req_file, capsys):
        """Has errors → exit 1."""
        with pytest.raises(SystemExit) as exc_info:
            call_command("validate_links", str(links_with_unknown_req_file))

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "REQ-UNKNOWN" in captured.out
        assert "ERRORS" in captured.out

    @pytest.mark.django_db
    def test_command_strict_mode(self, sample_requirement, empty_links_file, capsys):
        """--strict with warnings → exit 1."""
        # With active requirement and no links, should have a warning
        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "validate_links",
                str(empty_links_file),
                "--strict",
            )

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "WARNINGS" in captured.out

    @pytest.mark.django_db
    def test_command_json_output(self, valid_links_file, capsys):
        """--format json produces valid JSON."""
        call_command("validate_links", str(valid_links_file), "--format", "json")

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert "errors" in output
        assert "warnings" in output
        assert "summary" in output
        assert output["summary"]["links_checked"] == 1

    def test_command_missing_file(self):
        """Non-existent file → CommandError."""
        with pytest.raises(CommandError) as exc_info:
            call_command("validate_links", "/nonexistent/file.json")

        assert "not found" in str(exc_info.value).lower()

    def test_command_invalid_json(self, invalid_json_file):
        """Malformed JSON → CommandError."""
        with pytest.raises(CommandError) as exc_info:
            call_command("validate_links", str(invalid_json_file))

        assert "invalid json" in str(exc_info.value).lower()

    @pytest.mark.django_db
    def test_command_require_coverage_option(self, sample_requirement, empty_links_file, capsys):
        """--require-coverage option controls which statuses trigger warnings."""
        # With --require-coverage draft (not active), should not warn about active req
        call_command(
            "validate_links",
            str(empty_links_file),
            "--require-coverage",
            "draft",
        )
        captured = capsys.readouterr()
        assert "No issues found" in captured.out

    @pytest.mark.django_db
    def test_command_no_require_coverage(self, sample_requirement, empty_links_file, capsys):
        """Empty --require-coverage produces no warnings."""
        # Pass empty list by providing no values after the flag
        call_command(
            "validate_links",
            str(empty_links_file),
            "--require-coverage",
        )
        captured = capsys.readouterr()
        assert "No issues found" in captured.out

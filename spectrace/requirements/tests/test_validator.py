"""Unit tests for requirements validation logic."""
import pytest

from requirements.models import Requirement
from requirements.validator import ValidationResult, validate_links


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
def draft_requirement(db):
    """Create a draft requirement."""
    return Requirement.add_root(
        external_id="REQ-TEST-002",
        title="Draft Requirement",
        status="draft",
        source_file="test.md",
    )


@pytest.fixture
def sample_links_data():
    """Return valid links.json structure."""
    return {
        "version": "1.0",
        "links": [
            {
                "test_nodeid": "tests/test_foo.py::test_example",
                "requirement_id": "REQ-TEST-001",
            }
        ],
        "summary": {"total_links": 1},
    }


class TestValidateLinks:
    """Tests for the validate_links function."""

    @pytest.mark.django_db
    def test_valid_links_no_issues(self, sample_requirement, sample_links_data):
        """All links reference existing requirements → no errors/warnings."""
        result = validate_links(sample_links_data)

        assert not result.has_errors
        assert not result.has_warnings
        assert result.links_checked == 1

    @pytest.mark.django_db
    def test_unknown_requirement_error(self, db):
        """Link references non-existent requirement → error."""
        links_data = {
            "links": [
                {
                    "test_nodeid": "tests/test_foo.py::test_example",
                    "requirement_id": "REQ-UNKNOWN",
                }
            ]
        }

        result = validate_links(links_data, require_coverage_for=[])

        assert result.has_errors
        assert len(result.errors) == 1
        assert result.errors[0].type == "unknown_requirement"
        assert result.errors[0].id == "REQ-UNKNOWN"
        assert "tests/test_foo.py::test_example" in result.errors[0].details["referenced_by"]

    @pytest.mark.django_db
    def test_multiple_tests_same_unknown_req(self, db):
        """Multiple tests reference same unknown req → single consolidated error."""
        links_data = {
            "links": [
                {
                    "test_nodeid": "tests/test_foo.py::test_one",
                    "requirement_id": "REQ-UNKNOWN",
                },
                {
                    "test_nodeid": "tests/test_foo.py::test_two",
                    "requirement_id": "REQ-UNKNOWN",
                },
                {
                    "test_nodeid": "tests/test_bar.py::test_three",
                    "requirement_id": "REQ-UNKNOWN",
                },
            ]
        }

        result = validate_links(links_data, require_coverage_for=[])

        assert result.has_errors
        assert len(result.errors) == 1
        assert result.errors[0].id == "REQ-UNKNOWN"
        assert len(result.errors[0].details["referenced_by"]) == 3

    @pytest.mark.django_db
    def test_no_coverage_warning(self, sample_requirement):
        """Active requirement with no linked tests → warning."""
        links_data = {"links": []}

        result = validate_links(links_data, require_coverage_for=["active"])

        assert not result.has_errors
        assert result.has_warnings
        assert len(result.warnings) == 1
        assert result.warnings[0].type == "no_coverage"
        assert result.warnings[0].id == "REQ-TEST-001"

    @pytest.mark.django_db
    def test_no_coverage_respects_status_filter(self, sample_requirement, draft_requirement):
        """Only warns for specified statuses."""
        links_data = {"links": []}

        # Only require coverage for 'active' - draft should not trigger warning
        result = validate_links(links_data, require_coverage_for=["active"])

        assert len(result.warnings) == 1
        assert result.warnings[0].id == "REQ-TEST-001"

        # Now require coverage for 'draft' only
        result = validate_links(links_data, require_coverage_for=["draft"])

        assert len(result.warnings) == 1
        assert result.warnings[0].id == "REQ-TEST-002"

    @pytest.mark.django_db
    def test_empty_require_coverage_no_warnings(self, sample_requirement):
        """Empty status list → no coverage warnings."""
        links_data = {"links": []}

        result = validate_links(links_data, require_coverage_for=[])

        assert not result.has_warnings

    @pytest.mark.django_db
    def test_empty_links_data(self, db):
        """Empty links.json → no errors, just zero links checked."""
        links_data = {"links": []}

        result = validate_links(links_data, require_coverage_for=[])

        assert not result.has_errors
        assert not result.has_warnings
        assert result.links_checked == 0

    def test_result_to_dict(self):
        """ValidationResult serializes correctly to JSON-compatible dict."""
        from requirements.validator import ValidationIssue

        result = ValidationResult(
            errors=[
                ValidationIssue(
                    type="unknown_requirement",
                    id="REQ-001",
                    message="Not found",
                    details={"referenced_by": ["test_a.py::test"]},
                )
            ],
            warnings=[
                ValidationIssue(
                    type="no_coverage",
                    id="REQ-002",
                    message="No tests",
                    details={"status": "active"},
                )
            ],
            links_checked=5,
        )

        data = result.to_dict()

        assert "errors" in data
        assert "warnings" in data
        assert "summary" in data
        assert len(data["errors"]) == 1
        assert len(data["warnings"]) == 1
        assert data["errors"][0]["type"] == "unknown_requirement"
        assert data["errors"][0]["id"] == "REQ-001"
        assert data["errors"][0]["referenced_by"] == ["test_a.py::test"]
        assert data["warnings"][0]["type"] == "no_coverage"
        assert data["warnings"][0]["status"] == "active"
        assert data["summary"]["links_checked"] == 5
        assert data["summary"]["errors"] == 1
        assert data["summary"]["warnings"] == 1

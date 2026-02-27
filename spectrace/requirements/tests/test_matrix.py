"""Tests for matrix data layer."""

import pytest

from requirements.matrix import (
    get_cell_color,
    get_cell_css_class,
    get_matrix_data,
)
from requirements.models import (
    Requirement,
    TestResult,
    TestRun,
)


@pytest.fixture
def test_run(db):
    """Create a test run for test results."""
    return TestRun.objects.create(
        source_file="results.xml",
    )


@pytest.fixture
def sample_requirements(db):
    """Create sample requirements for testing."""
    req1 = Requirement.add_root(
        external_id="REQ-001",
        title="First Requirement",
        status="active",
        source_file="test.md",
        tags=["auth", "login"],
    )
    req2 = Requirement.add_root(
        external_id="REQ-002",
        title="Second Requirement",
        status="active",
        source_file="test.md",
        tags=["auth"],
    )
    req3 = Requirement.add_root(
        external_id="REQ-003",
        title="Third Requirement",
        status="active",
        source_file="test.md",
        tags=["dashboard"],
        verification_status="failing",
    )
    return [req1, req2, req3]


@pytest.fixture
def sample_test_results(db, test_run, sample_requirements):
    """Create test results linked to requirements."""
    req1, req2, req3 = sample_requirements

    # Test 1: Passes, linked to REQ-001
    result1 = TestResult.objects.create(
        test_run=test_run,
        test_nodeid="tests/test_auth.py::test_login",
        name="test_login",
        classname="tests.test_auth",
        status="passed",
    )
    result1.requirements.add(req1)

    # Test 2: Fails, linked to REQ-001 and REQ-002
    result2 = TestResult.objects.create(
        test_run=test_run,
        test_nodeid="tests/test_auth.py::test_logout",
        name="test_logout",
        classname="tests.test_auth",
        status="failed",
    )
    result2.requirements.add(req1, req2)

    # Test 3: Passes, linked to REQ-003
    result3 = TestResult.objects.create(
        test_run=test_run,
        test_nodeid="tests/test_dashboard.py::test_view",
        name="test_view",
        classname="tests.test_dashboard",
        status="passed",
    )
    result3.requirements.add(req3)

    return [result1, result2, result3]


class TestGetMatrixDataEmpty:
    """Tests for empty matrix scenarios."""

    @pytest.mark.django_db
    def test_empty_database(self):
        """Matrix with no requirements returns empty data."""
        data = get_matrix_data()

        assert data["requirements"] == []
        assert data["tests"] == []
        assert data["cells"] == {}
        assert data["pagination"]["total_requirements"] == 0
        assert data["pagination"]["total_pages"] == 1
        assert data["pagination"]["page"] == 1


class TestGetMatrixDataBasic:
    """Tests for basic matrix functionality."""

    @pytest.mark.django_db
    def test_returns_requirements(self, sample_requirements):
        """Matrix returns all requirements."""
        data = get_matrix_data()

        assert len(data["requirements"]) == 3
        external_ids = [r.external_id for r in data["requirements"]]
        assert "REQ-001" in external_ids
        assert "REQ-002" in external_ids
        assert "REQ-003" in external_ids

    @pytest.mark.django_db
    def test_returns_tests(self, sample_requirements, sample_test_results):
        """Matrix returns unique tests."""
        data = get_matrix_data()

        assert len(data["tests"]) == 3
        nodeids = [t["nodeid"] for t in data["tests"]]
        assert "tests/test_auth.py::test_login" in nodeids
        assert "tests/test_auth.py::test_logout" in nodeids
        assert "tests/test_dashboard.py::test_view" in nodeids

    @pytest.mark.django_db
    def test_tests_include_metadata(self, sample_requirements, sample_test_results):
        """Tests include name and file metadata."""
        data = get_matrix_data()

        test = next(t for t in data["tests"] if t["name"] == "test_login")
        assert test["file"] == "tests/test_auth.py"
        assert test["classname"] == "tests.test_auth"


class TestCellMatrix:
    """Tests for cell matrix building."""

    @pytest.mark.django_db
    def test_linked_cell_has_status(self, sample_requirements, sample_test_results):
        """Linked cells show test result status."""
        data = get_matrix_data()

        # REQ-001 + test_login = passed
        cell = data["cells"][("REQ-001", "tests/test_auth.py::test_login")]
        assert cell["status"] == "passed"
        assert cell["linked"] is True
        assert cell["test_result_id"] is not None

    @pytest.mark.django_db
    def test_unlinked_cell(self, sample_requirements, sample_test_results):
        """Unlinked cells have 'unlinked' status."""
        data = get_matrix_data()

        # REQ-002 is not linked to test_login
        cell = data["cells"][("REQ-002", "tests/test_auth.py::test_login")]
        assert cell["status"] == "unlinked"
        assert cell["linked"] is False
        assert cell["test_result_id"] is None

    @pytest.mark.django_db
    def test_failed_cell(self, sample_requirements, sample_test_results):
        """Failed test shows failed status."""
        data = get_matrix_data()

        # REQ-001 + test_logout = failed
        cell = data["cells"][("REQ-001", "tests/test_auth.py::test_logout")]
        assert cell["status"] == "failed"
        assert cell["linked"] is True


class TestPagination:
    """Tests for pagination functionality."""

    @pytest.mark.django_db
    def test_default_pagination(self, sample_requirements):
        """Default pagination values are correct."""
        data = get_matrix_data()

        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 25
        assert data["pagination"]["total_requirements"] == 3
        assert data["pagination"]["total_pages"] == 1
        assert data["pagination"]["has_next"] is False
        assert data["pagination"]["has_prev"] is False

    @pytest.mark.django_db
    def test_pagination_with_small_per_page(self, sample_requirements):
        """Pagination works with small per_page value."""
        data = get_matrix_data(page=1, per_page=2)

        assert len(data["requirements"]) == 2
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["per_page"] == 2
        assert data["pagination"]["total_pages"] == 2
        assert data["pagination"]["has_next"] is True
        assert data["pagination"]["has_prev"] is False

    @pytest.mark.django_db
    def test_pagination_page_2(self, sample_requirements):
        """Can navigate to page 2."""
        data = get_matrix_data(page=2, per_page=2)

        assert len(data["requirements"]) == 1
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["has_next"] is False
        assert data["pagination"]["has_prev"] is True

    @pytest.mark.django_db
    def test_pagination_clamps_page(self, sample_requirements):
        """Invalid page number is clamped to valid range."""
        data = get_matrix_data(page=100, per_page=25)

        # Should clamp to last page
        assert data["pagination"]["page"] == 1


class TestFilters:
    """Tests for filter functionality."""

    @pytest.mark.django_db
    def test_filter_by_status(self, sample_requirements):
        """Filter by verification status."""
        data = get_matrix_data(filters={"status": "failing"})

        assert len(data["requirements"]) == 1
        assert data["requirements"][0].external_id == "REQ-003"

    @pytest.mark.django_db
    def test_filter_by_tags(self, sample_requirements):
        """Filter by tags (any match)."""
        data = get_matrix_data(filters={"tags": ["dashboard"]})

        assert len(data["requirements"]) == 1
        assert data["requirements"][0].external_id == "REQ-003"

    @pytest.mark.django_db
    def test_filter_by_multiple_tags(self, sample_requirements):
        """Filter by multiple tags (OR logic)."""
        data = get_matrix_data(filters={"tags": ["login", "dashboard"]})

        assert len(data["requirements"]) == 2
        external_ids = [r.external_id for r in data["requirements"]]
        assert "REQ-001" in external_ids
        assert "REQ-003" in external_ids


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_cell_css_class_passed(self):
        """Passed status returns correct CSS class."""
        assert get_cell_css_class("passed") == "matrix-cell-passed"

    def test_get_cell_css_class_failed(self):
        """Failed status returns correct CSS class."""
        assert get_cell_css_class("failed") == "matrix-cell-failed"

    def test_get_cell_css_class_unlinked(self):
        """Unlinked status returns correct CSS class."""
        assert get_cell_css_class("unlinked") == "matrix-cell-unlinked"

    def test_get_cell_color_passed(self):
        """Passed status returns green color."""
        assert get_cell_color("passed") == "bg-green-500"

    def test_get_cell_color_failed(self):
        """Failed status returns red color."""
        assert get_cell_color("failed") == "bg-red-500"

    def test_get_cell_color_unlinked(self):
        """Unlinked status returns gray color."""
        assert get_cell_color("unlinked") == "bg-gray-200"

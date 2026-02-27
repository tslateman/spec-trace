"""Shared pytest fixtures for requirements test suite."""

import json
import tempfile
from pathlib import Path

import pytest
from django.core.cache import cache
from django.test import Client

from requirements.models import (
    SLO,
    Requirement,
    SLOStatus,
    TestResult,
    TestRun,
)

# ============================================================================
# Django Test Client
# ============================================================================


@pytest.fixture
def client():
    """Django test client."""
    return Client()


# ============================================================================
# Requirement Fixtures
# ============================================================================


@pytest.fixture
def sample_requirement(db):
    """Create a single active requirement.

    This is the standard requirement fixture used across most tests.
    Uses REQ-TEST-001 as the external_id.
    """
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
def sample_requirements(db):
    """Create multiple sample requirements for testing.

    Returns:
        List of 3 requirements with different tags and statuses.
    """
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


# ============================================================================
# SLO Fixtures
# ============================================================================


@pytest.fixture
def sample_slo(db):
    """Create a sample SLO."""
    return SLO.objects.create(
        name="test-slo",
        display_name="Test SLO",
        status=SLOStatus.NOT_LINKED,
    )


# ============================================================================
# Test Run / Test Result Fixtures
# ============================================================================


@pytest.fixture
def test_run(db):
    """Create a test run for test results."""
    return TestRun.objects.create(
        source_file="results.xml",
    )


@pytest.fixture
def sample_test_results(db, test_run, sample_requirements):
    """Create test results linked to requirements.

    Returns:
        List of 3 test results with various statuses and links.
    """
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


# ============================================================================
# Links Data Fixtures
# ============================================================================


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


# ============================================================================
# Temp File Helpers
# ============================================================================


@pytest.fixture
def make_temp_json_file():
    """Factory fixture for creating temporary JSON files.

    Usage:
        def test_something(make_temp_json_file):
            path = make_temp_json_file({"key": "value"})
            # use path...

    Automatically cleans up created files after test.
    """
    created_files = []

    def _make_file(data: dict) -> Path:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            created_files.append(f.name)
            return Path(f.name)

    yield _make_file

    # Cleanup
    for path in created_files:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


@pytest.fixture
def make_temp_yaml_file():
    """Factory fixture for creating temporary YAML files.

    Usage:
        def test_something(make_temp_yaml_file):
            path = make_temp_yaml_file("yaml: content")
            # use path...

    Automatically cleans up created files after test.
    """
    created_files = []

    def _make_file(content: str) -> Path:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            created_files.append(f.name)
            return Path(f.name)

    yield _make_file

    # Cleanup
    for path in created_files:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


# ============================================================================
# Cache Fixtures
# ============================================================================


@pytest.fixture
def clear_cache():
    """Clear Django cache before and after test.

    Use as autouse=True in test classes that need cache isolation.
    """
    cache.clear()
    yield
    cache.clear()

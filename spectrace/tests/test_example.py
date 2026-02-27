"""Example tests demonstrating requirement marker usage.

These tests showcase all supported linking patterns for the
@pytest.mark.requirement decorator.
"""

import pytest


# Single requirement link (LINK-01)
@pytest.mark.requirement("REQ-AUTH-001")
def test_login_success():
    """Test that verifies login works."""
    assert True


# Multiple requirements on one test (LINK-03)
@pytest.mark.requirement("REQ-AUTH-001", "REQ-AUTH-002", reason="tests full auth flow")
def test_login_with_mfa():
    """Test that links to multiple requirements."""
    assert True


# Same requirement linked from multiple tests (LINK-02)
@pytest.mark.requirement("REQ-AUTH-001")
def test_login_failure():
    """Another test linking to REQ-AUTH-001."""
    assert True


# Class-based test with marker
class TestAuthentication:
    """Test class demonstrating class-based requirement linking."""

    @pytest.mark.requirement("REQ-AUTH-003")
    def test_logout(self):
        """Test logout functionality."""
        assert True


# Parametrized test (each parameter variant links to requirement)
@pytest.mark.requirement("REQ-DATA-001")
@pytest.mark.parametrize("value", [1, 2, 3])
def test_data_processing(value):
    """Parametrized test - creates 3 test items, each linked to REQ-DATA-001."""
    assert value > 0


# Test linking to data import requirement
@pytest.mark.requirement("REQ-DATA-002")
def test_data_import():
    """Test that verifies data import works."""
    assert True


# Failing test to demonstrate failing status
@pytest.mark.requirement("REQ-DATA-002")
@pytest.mark.xfail(reason="Intentional failure for demo purposes")
def test_data_import_validation():
    """Test that fails to show failing requirement status."""
    # This test intentionally fails to demonstrate the failing state
    assert False, "Intentional failure for demo purposes"

"""Example tests demonstrating requirement marker usage.

These tests showcase all supported linking patterns for the
@pytest.mark.requirement decorator.
"""
import pytest


# Single requirement link (LINK-01)
@pytest.mark.requirement("REQ-AUTH-01")
def test_login_success():
    """Test that verifies login works."""
    assert True


# Multiple requirements on one test (LINK-03)
@pytest.mark.requirement("REQ-AUTH-01", "REQ-AUTH-02", reason="tests full auth flow")
def test_login_with_mfa():
    """Test that links to multiple requirements."""
    assert True


# Same requirement linked from multiple tests (LINK-02)
@pytest.mark.requirement("REQ-AUTH-01")
def test_login_failure():
    """Another test linking to REQ-AUTH-01."""
    assert True


# Class-based test with marker
class TestAuthentication:
    """Test class demonstrating class-based requirement linking."""

    @pytest.mark.requirement("REQ-AUTH-03")
    def test_logout(self):
        """Test logout functionality."""
        assert True


# Parametrized test (each parameter variant links to requirement)
@pytest.mark.requirement("REQ-DATA-01")
@pytest.mark.parametrize("value", [1, 2, 3])
def test_data_processing(value):
    """Parametrized test - creates 3 test items, each linked to REQ-DATA-01."""
    assert value > 0

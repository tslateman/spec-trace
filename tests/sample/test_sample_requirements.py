"""Sample tests demonstrating mixed verification status.

These tests link to sample requirements to show:
- Passing (green): Tests that pass
- Failing (red): Tests that intentionally fail
- Untested (gray): Requirements with no linked tests
"""

import pytest


@pytest.mark.requirement("SAMPLE-AUTH-001-001")
def test_user_login_success():
    """Passing test for user login."""
    # Simulates successful login validation
    assert True


@pytest.mark.requirement("SAMPLE-AUTH-001-001")
def test_user_login_with_email():
    """Additional passing test for login."""
    assert True


@pytest.mark.demo
@pytest.mark.requirement("SAMPLE-AUTH-001-002")
def test_password_reset_failure():
    """Failing test for password reset.

    This intentionally fails to demonstrate 'failing' status.
    Run with `pytest -m demo` to include demo tests.
    """
    pytest.fail("Password reset email not sent - simulated failure")


@pytest.mark.requirement("SAMPLE-API-001-001")
def test_create_resource_success():
    """Passing test for resource creation."""
    assert True


# Note: SAMPLE-API-001-002 has no linked tests -> untested status
# Note: SAMPLE-001, SAMPLE-AUTH-001, SAMPLE-API-001 have no direct tests -> status from children

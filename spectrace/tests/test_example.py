"""Example tests demonstrating requirement marker usage.

These tests showcase all supported linking patterns for the
@pytest.mark.requirement decorator.
"""

import pytest


# Single requirement link (LINK-01)
@pytest.mark.requirement("REQ-PLAT-001")
def test_tenant_isolation_middleware():
    """Links this test to REQ-PLAT-001"""
    assert True


# Multiple requirements on one test (LINK-03)
@pytest.mark.requirement(
    "REQ-PLAT-001", "REQ-PLAT-002", reason="tests full platform auth and audit"
)
def test_audit_logs_contain_tenant_id():
    """Test can link to multiple requirements with optional reason."""
    assert True


# Same requirement linked from multiple tests (LINK-02)
@pytest.mark.requirement("REQ-BILL-001")
def test_upgrade_tier():
    """Another test linking to REQ-BILL-001."""
    assert True


# Class-based test with marker
class TestBilling:
    """Test class demonstrating class-based requirement linking."""

    @pytest.mark.requirement("REQ-BILL-002")
    def test_overage_charges(self):
        """Method links to REQ-BILL-002."""
        assert True


# Parametrized test (each parameter variant links to requirement)
@pytest.mark.requirement("REQ-WRK-001")
@pytest.mark.parametrize("tier,max_workspaces", [("free", 1), ("pro", 5), ("enterprise", 999)])
def test_workspace_limits_by_tier(tier, max_workspaces):
    """Parametrized test - creates 3 test items, each linked to REQ-WRK-001."""
    assert max_workspaces > 0


# Test linking to workspaces
@pytest.mark.requirement("REQ-WRK-002")
def test_workspace_sharing_links():
    """Test that verifies data import works."""
    assert True


# Failing test to demonstrate failing status
@pytest.mark.requirement("REQ-IAM-001")
@pytest.mark.xfail(reason="Intentional failure for demo purposes")
def test_sso_jit_provisioning():
    """Test that fails to show failing requirement status."""
    # This test intentionally fails to demonstrate the failing state
    assert False, "Intentional failure for demo purposes"

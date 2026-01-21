"""Pytest configuration for spectrace test suite."""


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "requirement(*req_ids, reason=None): link test to requirement IDs"
    )

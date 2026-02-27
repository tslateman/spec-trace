"""Pytest plugin for extracting test-Linear issue links.

This plugin collects @pytest.mark.linear("CAN-1234") markers during test
collection and outputs them to .spectrace/links.json for import into Django.

Usage:
    pytest --collect-only -q -p requirements.pytest_plugin

    Or set it up as a conftest.py plugin:
    pytest_plugins = ["requirements.pytest_plugin"]

The output file format:
{
    "collected_at": "2025-01-15T12:00:00Z",
    "links": [
        {
            "test_nodeid": "tests/test_auth.py::test_login",
            "linear_issue_ids": ["CAN-1234", "CAN-5678"]
        }
    ]
}
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path


def pytest_configure(config):
    """Register the linear marker."""
    config.addinivalue_line(
        "markers", "linear(*issue_ids): link test to Linear issue IDs (e.g., CAN-1234)"
    )


def pytest_collection_finish(session):
    """After collection, extract linear markers and write to JSON."""
    # Only run if SPECTRACE_EXTRACT_LINKS env var is set or --spectrace-extract flag
    if not os.environ.get("SPECTRACE_EXTRACT_LINKS") and not getattr(
        session.config.option, "spectrace_extract", False
    ):
        return

    links = []

    for item in session.items:
        # Get all linear markers for this test
        linear_markers = list(item.iter_markers(name="linear"))
        if not linear_markers:
            continue

        # Collect all issue IDs from all markers
        issue_ids = []
        for marker in linear_markers:
            issue_ids.extend(marker.args)

        if issue_ids:
            links.append(
                {
                    "test_nodeid": item.nodeid,
                    "linear_issue_ids": list(issue_ids),  # Dedupe would lose order, keep as-is
                }
            )

    if not links:
        return

    # Create output directory
    output_dir = Path(".spectrace")
    output_dir.mkdir(exist_ok=True)

    # Write links to JSON
    output_file = output_dir / "links.json"
    data = {
        "collected_at": datetime.now(UTC).isoformat(),
        "links": links,
    }

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nSpectrace: Extracted {len(links)} test-Linear links to {output_file}")


def pytest_addoption(parser):
    """Add --spectrace-extract option."""
    parser.addoption(
        "--spectrace-extract",
        action="store_true",
        default=False,
        help="Extract test-Linear issue links to .spectrace/links.json",
    )

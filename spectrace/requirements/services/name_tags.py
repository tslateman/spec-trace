"""Requirement tags carried in test names, the link form every test runner can emit."""

import re
from pathlib import Path

from junitparser import JUnitXml

from requirements.services.junit_cases import case_nodeid, normalize_nodeid

REQUIREMENT_TAG = re.compile(r"\[([A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)*[-_][0-9]+)\]")


def requirement_ids_in_name(name: str) -> list[str]:
    """Return the requirement IDs a test name carries as `[REQ-AUTH-001]` tags.

    Tags normalize to upper case with hyphens, so `[req_auth_001]` from a Go or Rust
    identifier names the same requirement as `[REQ-AUTH-001]`. Order is preserved
    and repeats collapse.
    """
    ids: list[str] = []
    for tag in REQUIREMENT_TAG.findall(name):
        requirement_id = tag.upper().replace("_", "-")
        if requirement_id not in ids:
            ids.append(requirement_id)
    return ids


def junit_links(junit_file: Path) -> list[dict]:
    """Return one `{test_nodeid, requirement_id}` link per tag in each JUnit case name."""
    links = []
    for suite in JUnitXml.fromfile(str(junit_file)):
        for case in suite:
            nodeid = normalize_nodeid(case_nodeid(case))
            links.extend(
                {"test_nodeid": nodeid, "requirement_id": requirement_id}
                for requirement_id in requirement_ids_in_name(case.name or "")
            )
    return links

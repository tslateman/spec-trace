"""Validation payloads for POST /results/enforcement/ from JUnit XML or in-app JSON."""

import json
from pathlib import Path

from junitparser import JUnitXml

from requirements.services.junit_cases import case_nodeid, case_outcome, normalize_nodeid
from requirements.services.link_records import requirement_ids_of
from requirements.services.name_tags import requirement_ids_in_name

VALIDATION_STATUS = {
    "passed": "success",
    "failed": "failure",
    "error": "failure",
    "skipped": "unknown",
}


def validation_payload(results_file: Path, links_file: Path | None) -> dict:
    """Build the enforcement payload for a JUnit XML file or an in-app validations JSON file.

    JUnit results need `links_file` (extract_links output) to name the requirement each
    test verifies; the JSON shape import_inapp_validations reads is passed through.
    """
    if results_file.suffix.lower() == ".xml":
        if links_file is None:
            raise ValueError(
                "JUnit results need --links to name the requirement each test verifies"
            )
        return junit_payload(results_file, links_file)
    data = json.loads(results_file.read_text())
    return {
        "source": data.get("source", str(results_file)),
        "validations": data.get("validations", []),
    }


def test_run_payload(junit_file: Path, links_file: Path | None) -> dict:
    """Build the test-run payload for a JUnit XML file, naming what each case verifies.

    A case verifies the requirements its `links_file` entry names plus any `[REQ-X]`
    tags in its own name, so a runner with no link extractor still links by name.
    """
    linked = requirement_ids_by_nodeid(links_file) if links_file else {}
    results = []
    for suite in JUnitXml.fromfile(str(junit_file)):
        for case in suite:
            status, message = case_outcome(case)
            nodeid = normalize_nodeid(case_nodeid(case))
            results.append(
                {
                    "test_nodeid": nodeid,
                    "classname": case.classname or "",
                    "name": case.name or nodeid,
                    "time": case.time or 0.0,
                    "status": status,
                    "message": message,
                    "requirement_ids": _union(
                        linked.get(nodeid, []), requirement_ids_in_name(case.name or "")
                    ),
                }
            )
    return {"source_file": str(junit_file), "results": results}


def _union(first: list[str], second: list[str]) -> list[str]:
    return list(dict.fromkeys([*first, *second]))


def junit_payload(junit_file: Path, links_file: Path) -> dict:
    """Turn each linked JUnit test case into one validation per requirement it verifies."""
    requirement_ids = requirement_ids_by_nodeid(links_file)
    validations = []
    for suite in JUnitXml.fromfile(str(junit_file)):
        for case in suite:
            status, message = case_outcome(case)
            nodeid = case_nodeid(case)
            for requirement_id in requirement_ids.get(normalize_nodeid(nodeid), []):
                validations.append(
                    {
                        "requirement_id": requirement_id,
                        "name": nodeid,
                        "status": VALIDATION_STATUS[status],
                        "message": message,
                    }
                )
    return {"source": str(junit_file), "validations": validations}


def requirement_ids_by_nodeid(links_file: Path) -> dict[str, list[str]]:
    """Index an extract_links JSON file by normalized test nodeid."""
    data = json.loads(links_file.read_text())
    index: dict[str, list[str]] = {}
    for link in data.get("links", []):
        index.setdefault(normalize_nodeid(link["test_nodeid"]), []).extend(requirement_ids_of(link))
    return index

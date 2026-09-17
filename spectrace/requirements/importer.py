"""JUnit XML import logic for test results."""

import json

from django.utils import timezone
from junitparser import JUnitXml

from .models import Requirement, TestRequirementLink, TestResult, TestRun
from .services.junit_cases import case_nodeid, case_outcome, normalize_nodeid


def import_junit_xml(
    file_path: str,
    git_sha: str = "",
    git_branch: str = "",
    ci_job_url: str = "",
) -> TestRun:
    """Import pytest JUnit XML file into database.

    Parses the JUnit XML file and creates TestRun and TestResult records.
    Returns the created TestRun instance.

    Args:
        file_path: Path to the JUnit XML file.
        git_sha: Git commit SHA for this test run.
        git_branch: Git branch for this test run.
        ci_job_url: URL to CI job that produced this test run.

    Returns:
        TestRun instance with all test results.
    """
    xml = JUnitXml.fromfile(file_path)

    test_run = TestRun.objects.create(
        source_file=str(file_path),
        git_sha=git_sha,
        git_branch=git_branch,
        ci_job_url=ci_job_url,
        started_at=timezone.now(),
    )

    for suite in xml:
        for case in suite:
            status, message = case_outcome(case)
            TestResult.objects.create(
                test_run=test_run,
                test_nodeid=case_nodeid(case),
                classname=case.classname or "",
                name=case.name,
                time=case.time or 0.0,
                status=status,
                message=message,
            )

    # Mark test run as finished
    test_run.finished_at = timezone.now()
    test_run.save()

    return test_run


def link_results_to_requirements(test_run: TestRun, links_json_path: str) -> dict:
    """Link test results to requirements using extract_links JSON output.

    Reads the links JSON file produced by extract_links command and
    creates ManyToMany relationships between TestResult and Requirement.

    Args:
        test_run: TestRun instance whose results should be linked.
        links_json_path: Path to the extract_links JSON output file.

    Returns:
        Summary dict with:
        - linked_count: Number of test results that were linked
        - unlinked_tests: List of test nodeids with no requirement links
    """
    with open(links_json_path) as f:
        data = json.load(f)

    # Build normalized nodeid -> requirement_ids lookup
    nodeid_to_reqs = {}
    for link in data.get("links", []):
        nodeid = normalize_nodeid(link["test_nodeid"])
        req_id = link["requirement_id"]
        if nodeid not in nodeid_to_reqs:
            nodeid_to_reqs[nodeid] = []
        nodeid_to_reqs[nodeid].append(req_id)

    linked_count = 0
    unlinked_tests = []

    for result in test_run.results.all():
        # Normalize the result nodeid for comparison
        normalized_nodeid = normalize_nodeid(result.test_nodeid)
        req_ids = nodeid_to_reqs.get(normalized_nodeid, [])
        if req_ids:
            requirements = Requirement.objects.filter(external_id__in=req_ids)
            result.requirements.set(requirements)
            linked_count += 1
        else:
            unlinked_tests.append(result.test_nodeid)

    return {"linked_count": linked_count, "unlinked_tests": unlinked_tests}


def update_test_requirement_links(test_run: TestRun) -> dict:
    """Update TestRequirementLink records based on test results.

    Updates last_status and last_run_at for all TestRequirementLink records
    whose tests were included in this test run.

    Args:
        test_run: TestRun instance to process.

    Returns:
        Summary dict with:
        - updated_count: Number of links updated
        - status_changes: List of (nodeid, old_status, new_status)
    """
    updated_count = 0
    status_changes = []

    # Build a mapping of normalized nodeids to test results
    nodeid_to_result = {}
    for result in test_run.results.all():
        normalized = normalize_nodeid(result.test_nodeid)
        nodeid_to_result[normalized] = result

    # Update all matching TestRequirementLinks
    for link in TestRequirementLink.objects.all():
        normalized = normalize_nodeid(link.test_nodeid)
        result = nodeid_to_result.get(normalized)

        if result:
            old_status = link.last_status
            new_status = result.status

            link.last_status = new_status
            link.last_run_at = test_run.imported_at

            # Flag for review if status changed to failing
            if old_status == "passed" and new_status in ("failed", "error"):
                link.needs_review = True
                link.review_reason = f"status changed: {old_status} → {new_status}"
                status_changes.append((link.test_nodeid, old_status, new_status))

            link.save()
            updated_count += 1

    return {
        "updated_count": updated_count,
        "status_changes": status_changes,
    }

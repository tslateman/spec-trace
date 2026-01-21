"""JUnit XML import logic for test results."""
import json
from pathlib import Path

from junitparser import JUnitXml, Failure, Error, Skipped

from .models import TestRun, TestResult, Requirement


def import_junit_xml(file_path: str) -> TestRun:
    """Import pytest JUnit XML file into database.

    Parses the JUnit XML file and creates TestRun and TestResult records.
    Returns the created TestRun instance.

    Args:
        file_path: Path to the JUnit XML file.

    Returns:
        TestRun instance with all test results.
    """
    xml = JUnitXml.fromfile(file_path)

    test_run = TestRun.objects.create(
        source_file=str(file_path),
        total_tests=0,
        passed=0,
        failed=0,
        errors=0,
        skipped=0,
    )

    for suite in xml:
        for case in suite:
            # Determine status from result list
            # Default: no result element = passed
            status = 'passed'
            message = ''

            if case.result:
                for result in case.result:
                    if isinstance(result, Failure):
                        status = 'failed'
                        message = result.message or ''
                        break
                    elif isinstance(result, Error):
                        status = 'error'
                        message = result.message or ''
                        break
                    elif isinstance(result, Skipped):
                        status = 'skipped'
                        message = result.message or ''

            # Build nodeid from classname and name
            # pytest format: classname is "tests.test_module" or file path
            nodeid = f"{case.classname}::{case.name}" if case.classname else case.name

            TestResult.objects.create(
                test_run=test_run,
                test_nodeid=nodeid,
                classname=case.classname or '',
                name=case.name,
                time=case.time or 0.0,
                status=status,
                message=message,
            )

            # Update run counters
            test_run.total_tests += 1
            if status == 'passed':
                test_run.passed += 1
            elif status == 'failed':
                test_run.failed += 1
            elif status == 'error':
                test_run.errors += 1
            elif status == 'skipped':
                test_run.skipped += 1

    test_run.save()
    return test_run


def _normalize_nodeid(nodeid: str) -> str:
    """Normalize a test nodeid to a canonical format.

    JUnit XML uses dotted class paths (spectrace.tests.test_example::test_func)
    while extract_links uses file paths (spectrace/tests/test_example.py::test_func).

    This normalizes to the file path format.

    Args:
        nodeid: Test nodeid in either format.

    Returns:
        Normalized nodeid in file path format.
    """
    if '::' in nodeid:
        path_part, test_part = nodeid.split('::', 1)
    else:
        path_part = nodeid
        test_part = ''

    # If path part has dots and no slashes, convert to file path
    if '.' in path_part and '/' not in path_part and not path_part.endswith('.py'):
        # Convert dotted path to file path: spectrace.tests.test_example -> spectrace/tests/test_example.py
        path_part = path_part.replace('.', '/') + '.py'

    if test_part:
        return f"{path_part}::{test_part}"
    return path_part


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
    for link in data.get('links', []):
        nodeid = _normalize_nodeid(link['test_nodeid'])
        req_id = link['requirement_id']
        if nodeid not in nodeid_to_reqs:
            nodeid_to_reqs[nodeid] = []
        nodeid_to_reqs[nodeid].append(req_id)

    linked_count = 0
    unlinked_tests = []

    for result in test_run.results.all():
        # Normalize the result nodeid for comparison
        normalized_nodeid = _normalize_nodeid(result.test_nodeid)
        req_ids = nodeid_to_reqs.get(normalized_nodeid, [])
        if req_ids:
            requirements = Requirement.objects.filter(external_id__in=req_ids)
            result.requirements.set(requirements)
            linked_count += 1
        else:
            unlinked_tests.append(result.test_nodeid)

    return {'linked_count': linked_count, 'unlinked_tests': unlinked_tests}

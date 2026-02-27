"""Matrix data layer for traceability matrix view.

Provides efficient queries for rendering the requirement-test matrix grid.
"""

from collections import defaultdict

from django.db.models import Prefetch

from .models import Requirement, TestResult, TestRun


def get_matrix_data(page=1, per_page=25, filters=None):
    """
    Get matrix data for rendering the traceability grid.

    Args:
        page: Page number (1-indexed)
        per_page: Requirements per page (default 25)
        filters: Optional dict with filters:
            - status: 'passing', 'failing', 'untested' (requirement status)
            - tags: list of tags to filter by
            - parent_id: requirement ID to show children of

    Returns:
        dict with:
            - requirements: list of Requirement objects for current page
            - tests: list of test info dicts (nodeid, name, file)
            - cells: dict mapping (req_external_id, test_nodeid) -> cell data
            - pagination: pagination metadata
    """
    filters = filters or {}

    # Build base queryset with filters
    queryset = _build_requirement_queryset(filters)

    # Get total count for pagination
    total_count = queryset.count()
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    # Clamp page to valid range
    page = max(1, min(page, total_pages))

    # Calculate offset
    offset = (page - 1) * per_page

    # Get paginated requirements with prefetched test results
    requirements = list(
        queryset.prefetch_related(
            Prefetch(
                "test_results",
                queryset=TestResult.objects.select_related("test_run").order_by(
                    "-test_run__imported_at"
                ),
            )
        ).order_by("external_id")[offset : offset + per_page]
    )

    # Get unique tests for these requirements
    tests = _get_tests_for_requirements(requirements)

    # Build cell matrix
    cells = _build_cell_matrix(requirements, tests)

    return {
        "requirements": requirements,
        "tests": tests,
        "cells": cells,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "total_requirements": total_count,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


def _build_requirement_queryset(filters):
    """Build requirement queryset with filters applied."""
    queryset = Requirement.objects.all()

    # Status filter
    if filters.get("status"):
        queryset = queryset.filter(verification_status=filters["status"])

    # Tags filter (any tag matches)
    # Note: Using icontains on JSON field as SQLite doesn't support __contains
    if filters.get("tags"):
        from django.db.models import Q

        tag_q = Q()
        for tag in filters["tags"]:
            # Cast tags to string and check if tag is in the JSON array
            # This works because JSONField stores as text in SQLite
            tag_q |= Q(tags__icontains=tag)
        queryset = queryset.filter(tag_q)

    # Parent filter (show descendants of a requirement)
    if filters.get("parent_id"):
        try:
            parent = Requirement.objects.get(external_id=filters["parent_id"])
            # Get all descendants using treebeard
            queryset = parent.get_descendants()
        except Requirement.DoesNotExist:
            # Invalid parent, return empty queryset
            queryset = Requirement.objects.none()

    return queryset


def _get_tests_for_requirements(requirements):
    """Get unique tests linked to any of the given requirements.

    Returns list of dicts with test info, ordered by file then name.
    """
    if not requirements:
        return []

    # Get all test results linked to these requirements
    req_ids = [r.id for r in requirements]
    test_results = (
        TestResult.objects.filter(requirements__id__in=req_ids)
        .select_related("test_run")
        .order_by("-test_run__imported_at")
    )

    # Build unique test list (using dict to preserve order and dedupe)
    seen_nodeids = {}
    for result in test_results:
        if result.test_nodeid not in seen_nodeids:
            # Parse file from nodeid (format: path/to/test.py::test_name)
            parts = result.test_nodeid.split("::")
            file_path = parts[0] if parts else ""

            seen_nodeids[result.test_nodeid] = {
                "nodeid": result.test_nodeid,
                "name": result.name,
                "file": file_path,
                "classname": result.classname,
            }

    # Sort by file path, then by name
    tests = sorted(seen_nodeids.values(), key=lambda t: (t["file"], t["name"]))

    return tests


def _build_cell_matrix(requirements, tests):
    """Build the cell matrix mapping (req_external_id, test_nodeid) -> cell data.

    Cell data contains:
        - status: 'passed', 'failed', 'error', 'skipped', 'untested', or 'unlinked'
        - test_result_id: ID of the test result (if linked)
        - linked: boolean indicating if there's a link
    """
    if not requirements or not tests:
        return {}

    # Build a map of (requirement_id, test_nodeid) -> most recent test result
    # for efficient lookup
    result_map = defaultdict(dict)

    for req in requirements:
        # test_results is prefetched, so this doesn't hit DB
        for result in req.test_results.all():
            key = (req.external_id, result.test_nodeid)
            # Only keep the most recent result (they're ordered by -imported_at)
            if key not in result_map:
                result_map[key] = {
                    "status": result.status,
                    "test_result_id": result.id,
                    "linked": True,
                }

    # Build full matrix including unlinked cells
    cells = {}
    test_nodeids = {t["nodeid"] for t in tests}

    for req in requirements:
        for nodeid in test_nodeids:
            key = (req.external_id, nodeid)
            if key in result_map:
                cells[key] = result_map[key]
            else:
                cells[key] = {
                    "status": "unlinked",
                    "test_result_id": None,
                    "linked": False,
                }

    return cells


def get_cell_css_class(status):
    """Get CSS class for a cell based on its status.

    Args:
        status: Cell status string

    Returns:
        CSS class name for styling
    """
    css_classes = {
        "passed": "matrix-cell-passed",
        "failed": "matrix-cell-failed",
        "error": "matrix-cell-failed",
        "skipped": "matrix-cell-skipped",
        "untested": "matrix-cell-untested",
        "unlinked": "matrix-cell-unlinked",
    }
    return css_classes.get(status, "matrix-cell-unlinked")


def get_cell_color(status):
    """Get background color for a cell based on its status.

    Args:
        status: Cell status string

    Returns:
        Tailwind CSS color class
    """
    colors = {
        "passed": "bg-green-500",
        "failed": "bg-red-500",
        "error": "bg-red-500",
        "skipped": "bg-gray-400",
        "untested": "bg-yellow-500",
        "unlinked": "bg-gray-200",
    }
    return colors.get(status, "bg-gray-200")


def setup_matrix_demo(clear: bool = True) -> dict:
    """Set up demo data for the traceability matrix.

    Creates sample test results linked to existing requirements. Requirements
    must already exist in the database (run parse_specs first).

    Args:
        clear: Whether to clear existing demo test runs first

    Returns:
        {
            'requirements_count': int,
            'test_results_created': int,
            'test_runs_cleared': int,
        }
    """
    from pathlib import Path

    from django.conf import settings

    from .parser import SpecParser

    result = {
        "requirements_count": 0,
        "test_results_created": 0,
        "test_runs_cleared": 0,
    }

    # Clear existing demo test runs
    if clear:
        deleted, _ = TestRun.objects.filter(source_file__startswith="demo://").delete()
        result["test_runs_cleared"] = deleted

    # Parse specs if no requirements exist
    if Requirement.objects.count() == 0:
        specs_dir = Path(settings.BASE_DIR).parent / "specs"
        if specs_dir.exists():
            parser = SpecParser()
            parser.import_to_database(specs_dir, clear_existing=False)

    # Get requirements to link tests to
    requirements = list(Requirement.objects.all()[:12])
    result["requirements_count"] = len(requirements)
    if not requirements:
        return result

    # Create a demo test run
    test_run = TestRun.objects.create(
        source_file="demo://matrix-demo",
        git_sha="abc1234",
        git_branch="main",
    )

    # Create sample test results with various statuses
    demo_tests = [
        ("tests/test_auth.py::test_login_success", "test_login_success", "passed"),
        (
            "tests/test_auth.py::test_login_invalid_password",
            "test_login_invalid_password",
            "passed",
        ),
        (
            "tests/test_auth.py::test_login_user_not_found",
            "test_login_user_not_found",
            "failed",
        ),
        ("tests/test_auth.py::test_logout", "test_logout", "passed"),
        ("tests/test_upgrade.py::test_create_request", "test_create_request", "passed"),
        (
            "tests/test_upgrade.py::test_request_validation",
            "test_request_validation",
            "passed",
        ),
        (
            "tests/test_upgrade.py::test_duplicate_request",
            "test_duplicate_request",
            "failed",
        ),
        ("tests/test_wallet.py::test_provision_pass", "test_provision_pass", "passed"),
        (
            "tests/test_wallet.py::test_device_registration",
            "test_device_registration",
            "passed",
        ),
        ("tests/test_wallet.py::test_bundle_fetch", "test_bundle_fetch", "error"),
        ("tests/test_export.py::test_csv_export", "test_csv_export", "passed"),
        ("tests/test_export.py::test_pdf_export", "test_pdf_export", "skipped"),
    ]

    # Distribute tests across requirements
    for i, (nodeid, name, status) in enumerate(demo_tests):
        # Link to requirement(s) in a round-robin fashion
        req_index = i % len(requirements)

        test_result = TestResult.objects.create(
            test_run=test_run,
            test_nodeid=nodeid,
            name=name,
            classname=nodeid.split("::")[0].replace("/", ".").replace(".py", ""),
            status=status,
            time=0.1 + (i * 0.05),
        )
        # Link to primary requirement
        test_result.requirements.add(requirements[req_index])
        # Some tests cover multiple requirements
        if i % 3 == 0 and req_index + 1 < len(requirements):
            test_result.requirements.add(requirements[req_index + 1])

        result["test_results_created"] += 1

    # Update verification status on all requirements
    from .status import update_all_verification_statuses

    update_all_verification_statuses(test_run)

    return result

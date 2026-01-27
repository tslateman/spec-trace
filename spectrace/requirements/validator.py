"""
Validation logic for test-requirement links.

Detects drift between requirements, tests, and their linkages.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Requirement, TestRequirementLink, TestRun


@dataclass
class ValidationIssue:
    """A single validation issue (error or warning)."""

    type: str
    id: str
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of link validation."""

    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    links_checked: int = 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "errors": [
                {"type": e.type, "id": e.id, "message": e.message, **e.details}
                for e in self.errors
            ],
            "warnings": [
                {"type": w.type, "id": w.id, "message": w.message, **w.details}
                for w in self.warnings
            ],
            "summary": {
                "links_checked": self.links_checked,
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
        }


def validate_links(
    links_data: dict,
    require_coverage_for: Optional[list[str]] = None,
) -> ValidationResult:
    """
    Validate links.json against database state.

    Args:
        links_data: Parsed links.json content
        require_coverage_for: Requirement statuses that must have test coverage.
                              Defaults to ['active'] if None.

    Returns:
        ValidationResult with errors and warnings
    """
    if require_coverage_for is None:
        require_coverage_for = ["active"]

    result = ValidationResult()
    links = links_data.get("links", [])
    result.links_checked = len(links)

    # Get all requirement IDs from database
    db_requirements = {
        req.external_id: req for req in Requirement.objects.all()
    }

    # Track which requirements have linked tests
    requirements_with_tests: set[str] = set()
    # Track requirement IDs referenced in links.json
    referenced_requirement_ids: set[str] = set()

    # Validate each link
    for link in links:
        req_id = link.get("requirement_id")
        test_nodeid = link.get("test_nodeid", "unknown")

        if not req_id:
            continue

        referenced_requirement_ids.add(req_id)

        if req_id not in db_requirements:
            # Unknown requirement - referenced in test but not in database
            result.errors.append(
                ValidationIssue(
                    type="unknown_requirement",
                    id=req_id,
                    message=f"Referenced in tests but not in database",
                    details={"referenced_by": [test_nodeid]},
                )
            )
        else:
            requirements_with_tests.add(req_id)

    # Check for requirements that need coverage but don't have it
    if require_coverage_for:
        for req_id, req in db_requirements.items():
            if req.status in require_coverage_for and req_id not in requirements_with_tests:
                result.warnings.append(
                    ValidationIssue(
                        type="no_coverage",
                        id=req_id,
                        message=f"Requirement with status '{req.status}' has no test coverage",
                        details={"status": req.status},
                    )
                )

    # Consolidate duplicate unknown requirement errors (multiple tests referencing same unknown ID)
    result.errors = _consolidate_unknown_requirement_errors(result.errors)

    return result


def _consolidate_unknown_requirement_errors(
    errors: list[ValidationIssue],
) -> list[ValidationIssue]:
    """Consolidate multiple errors for the same unknown requirement ID."""
    unknown_req_tests: dict[str, list[str]] = {}
    other_errors: list[ValidationIssue] = []

    for error in errors:
        if error.type == "unknown_requirement":
            if error.id not in unknown_req_tests:
                unknown_req_tests[error.id] = []
            unknown_req_tests[error.id].extend(error.details.get("referenced_by", []))
        else:
            other_errors.append(error)

    # Create consolidated errors
    consolidated = []
    for req_id, tests in sorted(unknown_req_tests.items()):
        consolidated.append(
            ValidationIssue(
                type="unknown_requirement",
                id=req_id,
                message="Referenced in tests but not in database",
                details={"referenced_by": tests},
            )
        )

    return consolidated + other_errors


@dataclass
class DriftResult:
    """Result of drift detection."""

    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    items_checked: int = 0

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def merge(self, other: 'DriftResult') -> 'DriftResult':
        """Merge another DriftResult into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.items_checked += other.items_checked
        return self

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "errors": [
                {"type": e.type, "id": e.id, "message": e.message, **e.details}
                for e in self.errors
            ],
            "warnings": [
                {"type": w.type, "id": w.id, "message": w.message, **w.details}
                for w in self.warnings
            ],
            "summary": {
                "items_checked": self.items_checked,
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
        }


def detect_unmarked_tests(
    test_directory: Path,
    spec_marker_pattern: str = r'@pytest\.mark\.(spec|linear|requirement)',
) -> DriftResult:
    """Detect test files without spec markers.

    Args:
        test_directory: Directory to scan for test files.
        spec_marker_pattern: Regex pattern to match spec markers.

    Returns:
        DriftResult with unmarked test warnings.
    """
    result = DriftResult()
    marker_re = re.compile(spec_marker_pattern)

    if not test_directory.exists():
        return result

    for test_file in test_directory.rglob('test_*.py'):
        result.items_checked += 1
        content = test_file.read_text()

        # Check if file has any spec markers
        if not marker_re.search(content):
            # Check if file has any test functions
            if re.search(r'def test_', content):
                result.warnings.append(
                    ValidationIssue(
                        type='unmarked_test',
                        id=str(test_file),
                        message='Test file has no spec markers',
                        details={'path': str(test_file)},
                    )
                )

    return result


def detect_stale_links() -> DriftResult:
    """Detect TestRequirementLinks that reference deleted tests.

    A link is stale if its test_nodeid doesn't appear in any recent test run.

    Returns:
        DriftResult with stale link errors.
    """
    result = DriftResult()

    # Get all test nodeids from the most recent test run
    latest_run = TestRun.objects.order_by('-imported_at').first()
    if not latest_run:
        return result

    recent_nodeids = set(
        latest_run.results.values_list('test_nodeid', flat=True)
    )

    # Check each link
    for link in TestRequirementLink.objects.all():
        result.items_checked += 1

        if link.test_nodeid not in recent_nodeids:
            result.errors.append(
                ValidationIssue(
                    type='stale_link',
                    id=f'{link.test_nodeid}:{link.requirement.external_id}',
                    message='Link references test not in latest run',
                    details={
                        'test_nodeid': link.test_nodeid,
                        'requirement_id': link.requirement.external_id,
                        'last_status': link.last_status,
                        'last_run_at': (
                            link.last_run_at.isoformat() if link.last_run_at else None
                        ),
                    },
                )
            )

    return result


def detect_orphan_requirements() -> DriftResult:
    """Detect requirements with no linked tests and no children.

    An orphan is a leaf requirement (no children) that has no test coverage.

    Returns:
        DriftResult with orphan requirement warnings.
    """
    result = DriftResult()

    for req in Requirement.objects.filter(status='active'):
        result.items_checked += 1

        # Skip non-leaf nodes (they're covered by their children)
        if req.get_children().exists():
            continue

        # Check if requirement has any test links
        if not req.test_links.exists():
            result.warnings.append(
                ValidationIssue(
                    type='orphan_requirement',
                    id=req.external_id,
                    message='Active requirement has no test coverage and no children',
                    details={
                        'title': req.title,
                        'source_file': req.source_file,
                    },
                )
            )

    return result


def detect_spec_drift(specs_directory: Path) -> DriftResult:
    """Detect spec files modified after last test run.

    If a spec file was modified but tests haven't been re-run, the tests
    may be verifying outdated requirements.

    Args:
        specs_directory: Directory containing spec markdown files.

    Returns:
        DriftResult with spec drift warnings.
    """
    result = DriftResult()

    # Get latest test run timestamp
    latest_run = TestRun.objects.order_by('-imported_at').first()
    if not latest_run:
        return result

    last_run_time = latest_run.imported_at

    if not specs_directory.exists():
        return result

    for spec_file in specs_directory.rglob('*.md'):
        result.items_checked += 1

        # Get file modification time
        mtime = datetime.fromtimestamp(
            os.path.getmtime(spec_file),
            tz=last_run_time.tzinfo,
        )

        if mtime > last_run_time:
            # Find requirements from this file
            req_ids = list(
                Requirement.objects.filter(
                    source_file__endswith=spec_file.name
                ).values_list('external_id', flat=True)
            )

            result.warnings.append(
                ValidationIssue(
                    type='spec_drift',
                    id=str(spec_file),
                    message='Spec file modified after last test run',
                    details={
                        'path': str(spec_file),
                        'modified_at': mtime.isoformat(),
                        'last_test_run': last_run_time.isoformat(),
                        'affected_requirements': req_ids,
                    },
                )
            )

    return result


def detect_all_drift(
    test_directory: Optional[Path] = None,
    specs_directory: Optional[Path] = None,
) -> DriftResult:
    """Run all drift detection checks.

    Args:
        test_directory: Directory to scan for unmarked tests.
        specs_directory: Directory containing spec markdown files.

    Returns:
        Combined DriftResult from all checks.
    """
    result = DriftResult()

    # Always run database-based checks
    result.merge(detect_stale_links())
    result.merge(detect_orphan_requirements())

    # File-based checks only if directories provided
    if test_directory:
        result.merge(detect_unmarked_tests(test_directory))

    if specs_directory:
        result.merge(detect_spec_drift(specs_directory))

    return result

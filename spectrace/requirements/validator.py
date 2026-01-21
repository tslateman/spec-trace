"""
Validation logic for test-requirement links.

Detects drift between requirements, tests, and their linkages.
"""

from dataclasses import dataclass, field
from typing import Optional

from .models import Requirement


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

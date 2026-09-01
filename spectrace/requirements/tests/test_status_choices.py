"""The status columns a database consumer reads publish their legal values."""

from pathlib import Path

from requirements import models
from requirements.models import (
    LinkStatus,
    Requirement,
    RequirementStatus,
    TestRequirementLink,
)
from requirements.services.contract_snapshot import _extract_db_surfaces

REPO_ROOT = Path(models.__file__).resolve().parents[2]


def test_requirement_status__declares_the_stored_lifecycle_values():
    field = Requirement._meta.get_field("status")

    assert [value for value, _ in field.choices] == ["draft", "active", "deprecated"]
    assert field.default == RequirementStatus.DRAFT


def test_last_status__declares_the_stored_test_run_values():
    field = TestRequirementLink._meta.get_field("last_status")

    assert [value for value, _ in field.choices] == [
        "passed",
        "failed",
        "error",
        "skipped",
        "unknown",
    ]
    assert field.default == LinkStatus.UNKNOWN


def test_extract_db_surfaces__publishes_requirement_status():
    surface = _extract_db_surfaces(REPO_ROOT)["enum/requirements_requirement.status"]

    assert surface["fields"] == ["active", "deprecated", "draft"]
    assert surface["format"] == "db-enum"


def test_extract_db_surfaces__publishes_test_link_last_status():
    surface = _extract_db_surfaces(REPO_ROOT)["enum/requirements_testrequirementlink.last_status"]

    assert surface["fields"] == ["error", "failed", "passed", "skipped", "unknown"]
    assert surface["format"] == "db-enum"

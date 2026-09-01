"""The priority column a database consumer reads publishes its legal values."""

from pathlib import Path

from requirements import models
from requirements.linear import LinearClient
from requirements.models import Requirement, RequirementPriority
from requirements.services.contract_snapshot import _extract_db_surfaces

REPO_ROOT = Path(models.__file__).resolve().parents[2]


def test_requirement_priority__declares_the_stored_levels():
    field = Requirement._meta.get_field("priority")

    assert [value for value, _ in field.choices] == [
        "urgent",
        "critical",
        "high",
        "medium",
        "low",
    ]
    assert field.blank


def test_requirement_priority__declares_every_level_the_linear_importer_maps():
    imported = {value for value in LinearClient.PRIORITY_MAP.values() if value}

    assert imported <= set(RequirementPriority.values)


def test_extract_db_surfaces__publishes_requirement_priority():
    surface = _extract_db_surfaces(REPO_ROOT)["enum/requirements_requirement.priority"]

    assert surface["fields"] == ["critical", "high", "low", "medium", "urgent"]
    assert surface["format"] == "db-enum"

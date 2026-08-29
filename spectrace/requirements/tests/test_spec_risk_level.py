"""`risk_level` as an authored frontmatter field.

Every seed corpus entry asserts `risk_level in [critical, high]`, and until a
spec author could declare one the check was permanently red: the spec parser
read eleven frontmatter keys and `risk_level` was not among them, so every
requirement reached the review as `unclassified`.

A risk classification is an authoring decision. It is declared beside `priority`
and `verification_method`, and — unlike `verification_method`, which normalizes
an unknown value to `unspecified` and says nothing — a value outside the
`RiskLevel` choices raises rather than being quietly discarded.
"""

import pytest

from requirements.models import Requirement, RiskLevel
from requirements.parser import (
    InvalidRiskLevelError,
    SpecParser,
    import_requirements_to_database,
    resolve_risk_level,
)

SINGLE_SPEC = """---
id: REQ-RISK-001
title: Classified Requirement
status: active
risk_level: {risk_level}
---

Body prose.
"""

MULTI_SPEC = """---
title: Two Requirements
status: active
risk_level: medium
---

## REQ-RISK-010: First

First body.

## REQ-RISK-011: Second

Second body.
"""


@pytest.fixture
def spec_file(tmp_path):
    """Write a single-requirement spec declaring the given risk level."""

    def write(risk_level: str):
        path = tmp_path / "risk.md"
        path.write_text(SINGLE_SPEC.format(risk_level=risk_level))
        return path

    return write


class TestParsingAnAuthoredRiskLevel:
    """The frontmatter key reaches the requirement dict and then the row."""

    def test_parse_file__reads_the_declared_risk_level(self, spec_file):
        """The parser carries the frontmatter value through untouched."""
        parsed = SpecParser().parse_file(spec_file("critical"))

        assert parsed[0]["risk_level"] == "critical"

    def test_parse_file__reads_no_risk_level_when_the_spec_states_none(self, tmp_path):
        """A silent spec parses to None, which the import resolves to unclassified."""
        path = tmp_path / "silent.md"
        path.write_text("---\nid: REQ-RISK-002\ntitle: Silent\n---\n\nBody.\n")

        parsed = SpecParser().parse_file(path)

        assert parsed[0]["risk_level"] is None

    def test_parse_file__shares_one_risk_level_across_a_multi_requirement_file(self, tmp_path):
        """Frontmatter in a multi-requirement file applies to every heading in it."""
        path = tmp_path / "multi.md"
        path.write_text(MULTI_SPEC)

        parsed = SpecParser().parse_file(path)

        assert [item["risk_level"] for item in parsed] == ["medium", "medium"]

    def test_import_to_database__stores_the_declared_risk_level(self, db, spec_file):
        """The value the check evaluator reads comes off the imported row."""
        SpecParser().import_to_database(spec_file("high").parent)

        assert Requirement.objects.get(external_id="REQ-RISK-001").risk_level == RiskLevel.HIGH

    def test_import_to_database__updates_the_risk_level_of_an_existing_requirement(
        self, db, spec_file
    ):
        """Re-parsing a reclassified spec moves the stored row with it."""
        SpecParser().import_to_database(spec_file("low").parent)
        SpecParser().import_to_database(spec_file("critical").parent)

        assert Requirement.objects.get(external_id="REQ-RISK-001").risk_level == RiskLevel.CRITICAL

    def test_import_requirements_to_database__defaults_to_unclassified_when_unstated(self, db):
        """Silence is the default, not an error: most specs never classify."""
        import_requirements_to_database(
            [{"external_id": "REQ-RISK-003", "title": "Unstated", "source_file": "unstated.md"}]
        )

        assert (
            Requirement.objects.get(external_id="REQ-RISK-003").risk_level == RiskLevel.UNCLASSIFIED
        )


class TestRejectingAnUnknownRiskLevel:
    """An invalid value fails loudly rather than reaching the row as a default."""

    def test_import_to_database__rejects_a_risk_level_outside_the_choices(self, db, spec_file):
        """`severe` is not a RiskLevel, and the import says so."""
        with pytest.raises(InvalidRiskLevelError, match="risk_level 'severe' is not a RiskLevel"):
            SpecParser().import_to_database(spec_file("severe").parent)

    def test_import_to_database__names_the_file_and_the_allowed_values(self, db, spec_file):
        """The message is what an author fixing the frontmatter needs."""
        path = spec_file("Critical")

        with pytest.raises(InvalidRiskLevelError) as excinfo:
            SpecParser().import_to_database(path.parent)

        assert str(path) in str(excinfo.value)
        assert "critical, high, medium, low, unclassified" in str(excinfo.value)

    def test_import_to_database__stores_no_requirement_for_a_rejected_risk_level(
        self, db, spec_file
    ):
        """A refused value writes nothing, so no row claims a classification it lacks."""
        with pytest.raises(InvalidRiskLevelError):
            SpecParser().import_to_database(spec_file("sev1").parent)

        assert not Requirement.objects.filter(external_id="REQ-RISK-001").exists()

    @pytest.mark.parametrize("value", RiskLevel.values)
    def test_resolve_risk_level__accepts_every_risk_level_choice(self, value):
        """The validator admits the whole enum and nothing else."""
        assert resolve_risk_level(value, "spec.md") == value

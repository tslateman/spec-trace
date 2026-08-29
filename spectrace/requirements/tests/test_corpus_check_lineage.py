"""Tests for stable finding identifiers: check-id lineage across version bumps.

A finding is cited as `ENTRY-ID#check-id`, with the version reported beside it.
The parser is what holds that id still, so most of these tests drive
`CorpusParser.import_to_database` across a real version bump and assert what it
refuses.
"""

from pathlib import Path

import pytest

from requirements.models import CorpusEntryVersion
from requirements.services.corpus_checks import Finding, finding_identifier
from requirements.services.corpus_parser import (
    CorpusCheckLineageError,
    CorpusParseError,
    CorpusParser,
    resolve_check_id,
    validate_checks,
    validate_retired_checks,
)

CORPUS_DIR = Path(__file__).resolve().parents[3] / "corpus"
SEED_PATH = CORPUS_DIR / "security" / "tenant-isolation.md"
SEED_V4 = SEED_PATH.read_text()

SEED_CHECK_BLOCK = (
    "checks:\n"
    "  - id: risk-classified\n"
    "    assert: risk_level in [critical, high]\n"
    "  - id: has-isolation-test\n"
    "    assert: verification_method in [test, both]\n"
)

ENTRY_TEMPLATE = """---
id: STD-LINE-001
kind: standard
title: Lineage standard
version: {version}
status: active
effective: 2026-01-15
owner: platform
{block}---

{body}
"""

TWO_CHECKS = (
    "checks:\n"
    "  - id: risk-classified\n"
    "    assert: risk_level in [critical, high]\n"
    "  - id: has-isolation-test\n"
    "    assert: verification_method in [test, both]\n"
)

RENAMED_CHECKS = (
    "checks:\n"
    "  - id: risk-level-set\n"
    "    assert: risk_level in [critical, high]\n"
    "  - id: has-isolation-test\n"
    "    assert: verification_method in [test, both]\n"
)

DECLARED_RENAME_CHECKS = (
    "checks:\n"
    "  - id: risk-level-set\n"
    "    renamed_from: risk-classified\n"
    "    assert: risk_level in [critical, high]\n"
    "  - id: has-isolation-test\n"
    "    assert: verification_method in [test, both]\n"
)

DROPPED_CHECKS = "checks:\n  - id: risk-classified\n    assert: risk_level in [critical, high]\n"

RETIRED_DECLARATION = "retired_checks: [has-isolation-test]\n"


@pytest.fixture
def import_entry(tmp_path):
    """Factory writing one corpus entry into a temporary directory and importing it."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    parser = CorpusParser()

    def _import(version: int, block: str = TWO_CHECKS, body: str = "Lineage body text."):
        (corpus_dir / "lineage.md").write_text(
            ENTRY_TEMPLATE.format(version=version, block=block, body=body)
        )
        return parser.import_to_database(corpus_dir)

    return _import


@pytest.fixture
def import_seed(tmp_path):
    """Factory importing the real STD-SEC-001 file, at a chosen version and check block."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    parser = CorpusParser()

    def _import(text: str):
        (corpus_dir / "tenant-isolation.md").write_text(text)
        return parser.import_to_database(corpus_dir)

    return _import


def seed_text(version: int, block: str = SEED_CHECK_BLOCK, effective: str = "2026-08-29") -> str:
    """The real seed entry at a chosen version, check block, and effective date."""
    return (
        SEED_V4.replace("version: 4", f"version: {version}")
        .replace("effective: 2026-08-29", f"effective: {effective}")
        .replace(SEED_CHECK_BLOCK, block)
    )


def test_seed_entry__still_declares_the_check_ids_these_tests_rename():
    """The real-lineage tests below are worthless if the seed file drifts from them."""
    assert SEED_CHECK_BLOCK in SEED_V4
    assert "version: 4" in SEED_V4


class TestCheckLineage:
    """Tests for the parser refusing an undeclared check-id change."""

    def test_import_to_database__accepts_a_bump_that_keeps_every_check_id(self, db, import_entry):
        import_entry(version=1)

        counts = import_entry(version=2, body="Revised body text.")

        assert counts["versions_created"] == 1
        assert CorpusEntryVersion.objects.count() == 2

    def test_import_to_database__rejects_a_renamed_check_id_with_no_declaration(
        self, db, import_entry
    ):
        import_entry(version=1)

        with pytest.raises(CorpusCheckLineageError) as exc_info:
            import_entry(version=2, block=RENAMED_CHECKS)

        message = str(exc_info.value)
        assert "STD-LINE-001 version 2" in message
        assert "'risk-classified'" in message
        assert "'risk-level-set'" in message
        assert "renamed_from" in message
        assert CorpusEntryVersion.objects.count() == 1

    def test_import_to_database__accepts_a_rename_declared_with_renamed_from(
        self, db, import_entry
    ):
        import_entry(version=1)

        counts = import_entry(version=2, block=DECLARED_RENAME_CHECKS)

        assert counts["versions_created"] == 1
        stored = CorpusEntryVersion.objects.get(version=2)
        assert stored.checks[0]["id"] == "risk-level-set"
        assert stored.checks[0]["renamed_from"] == "risk-classified"

    def test_import_to_database__rejects_a_dropped_check_id_with_no_declaration(
        self, db, import_entry
    ):
        import_entry(version=1)

        with pytest.raises(CorpusCheckLineageError) as exc_info:
            import_entry(version=2, block=DROPPED_CHECKS)

        message = str(exc_info.value)
        assert "STD-LINE-001 version 2" in message
        assert "'has-isolation-test'" in message
        assert "retired_checks" in message
        assert CorpusEntryVersion.objects.count() == 1

    def test_import_to_database__accepts_a_drop_declared_in_retired_checks(self, db, import_entry):
        import_entry(version=1)

        counts = import_entry(version=2, block=RETIRED_DECLARATION + DROPPED_CHECKS)

        assert counts["versions_created"] == 1
        assert [check["id"] for check in CorpusEntryVersion.objects.get(version=2).checks] == [
            "risk-classified"
        ]

    def test_import_to_database__rejects_renamed_from_naming_an_unknown_check(
        self, db, import_entry
    ):
        import_entry(version=1)
        invented = DECLARED_RENAME_CHECKS.replace(
            "renamed_from: risk-classified", "renamed_from: never-existed"
        )

        with pytest.raises(CorpusCheckLineageError, match="never-existed"):
            import_entry(version=2, block=invented)

    def test_import_to_database__rejects_renamed_from_naming_a_live_check(self, db, import_entry):
        import_entry(version=1)
        self_rename = TWO_CHECKS.replace(
            "  - id: has-isolation-test\n",
            "  - id: has-isolation-test\n    renamed_from: risk-classified\n",
        )

        with pytest.raises(CorpusCheckLineageError, match="still defines"):
            import_entry(version=2, block=self_rename)

    def test_import_to_database__rejects_retired_checks_naming_an_unknown_check(
        self, db, import_entry
    ):
        import_entry(version=1)

        with pytest.raises(CorpusCheckLineageError, match="never-existed"):
            import_entry(version=2, block="retired_checks: [never-existed]\n" + TWO_CHECKS)

    def test_import_to_database__rejects_retiring_a_check_the_version_still_defines(
        self, db, import_entry
    ):
        with pytest.raises(CorpusParseError, match="still defines"):
            import_entry(version=1, block=RETIRED_DECLARATION + TWO_CHECKS)

    def test_import_to_database__leaves_the_first_version_free_of_lineage_rules(
        self, db, import_entry
    ):
        counts = import_entry(version=1, block=RENAMED_CHECKS)

        assert counts["versions_created"] == 1


class TestSeedEntryLineage:
    """Tests driving the real STD-SEC-001 lineage, v3 to v4 and on to v5."""

    def test_import_to_database__accepts_the_real_seed_bump_from_v3_to_v4(self, db, import_seed):
        import_seed(seed_text(version=3, effective="2026-01-15"))

        counts = import_seed(SEED_V4)

        assert counts["versions_created"] == 1
        versions = CorpusEntryVersion.objects.filter(entry__external_id="STD-SEC-001").order_by(
            "version"
        )
        assert [version.version for version in versions] == [3, 4]

    def test_import_to_database__rejects_renaming_a_real_seed_check_in_v5(self, db, import_seed):
        import_seed(seed_text(version=3, effective="2026-01-15"))
        import_seed(SEED_V4)

        with pytest.raises(CorpusCheckLineageError) as exc_info:
            import_seed(seed_text(version=5, block=RENAMED_CHECKS))

        message = str(exc_info.value)
        assert "STD-SEC-001 version 5" in message
        assert "'risk-classified'" in message
        assert "'risk-level-set'" in message
        assert CorpusEntryVersion.objects.filter(entry__external_id="STD-SEC-001").count() == 2

    def test_import_to_database__resolves_the_identifier_across_a_declared_seed_rename(
        self, db, import_seed
    ):
        import_seed(seed_text(version=3, effective="2026-01-15"))
        import_seed(SEED_V4)

        import_seed(seed_text(version=5, block=DECLARED_RENAME_CHECKS))

        assert resolve_check_id("STD-SEC-001", "risk-classified") == "risk-level-set"
        assert resolve_check_id("STD-SEC-001", "risk-level-set") == "risk-level-set"
        assert resolve_check_id("STD-SEC-001", "has-isolation-test") == "has-isolation-test"
        assert (
            CorpusEntryVersion.objects.get(entry__external_id="STD-SEC-001", version=4).checks[0][
                "id"
            ]
            == "risk-classified"
        )

    def test_import_to_database__rejects_dropping_a_real_seed_check_in_v5(self, db, import_seed):
        import_seed(seed_text(version=3, effective="2026-01-15"))
        import_seed(SEED_V4)

        with pytest.raises(CorpusCheckLineageError, match="has-isolation-test"):
            import_seed(seed_text(version=5, block=DROPPED_CHECKS))

    def test_import_to_database__accepts_a_declared_seed_retirement_in_v5(self, db, import_seed):
        import_seed(seed_text(version=3, effective="2026-01-15"))
        import_seed(SEED_V4)

        counts = import_seed(seed_text(version=5, block=RETIRED_DECLARATION + DROPPED_CHECKS))

        assert counts["versions_created"] == 1
        assert [
            check["id"]
            for check in CorpusEntryVersion.objects.get(
                entry__external_id="STD-SEC-001", version=5
            ).checks
        ] == ["risk-classified"]

    def test_import_to_database__stays_idempotent_on_the_whole_seed_corpus(self, db):
        parser = CorpusParser()
        parser.import_to_database(CORPUS_DIR)

        counts = parser.import_to_database(CORPUS_DIR)

        assert counts["versions_created"] == 0


class TestFindingIdentifier:
    """Tests for the version-independent identifier a finding is cited by."""

    def test_finding_identifier__joins_entry_id_and_check_id(self):
        assert finding_identifier("STD-SEC-001", "risk-classified") == (
            "STD-SEC-001#risk-classified"
        )

    def test_finding_identifier__is_the_entry_id_when_no_check_raised_it(self):
        assert finding_identifier("STD-SEC-001") == "STD-SEC-001"

    def test_finding_id__holds_across_two_versions_of_the_same_check(self):
        earlier = Finding(
            finding_type="unmet_check",
            entry_id="STD-SEC-001",
            entry_version=3,
            detail="",
            check_id="risk-classified",
        )
        later = Finding(
            finding_type="unmet_check",
            entry_id="STD-SEC-001",
            entry_version=4,
            detail="",
            check_id="risk-classified",
        )

        assert earlier.finding_id == later.finding_id == "STD-SEC-001#risk-classified"

    def test_resolve_check_id__returns_the_id_itself_when_the_corpus_holds_no_rename(self, db):
        assert resolve_check_id("STD-SEC-001", "risk-classified") == "risk-classified"


class TestCheckDeclarationGrammar:
    """Tests for the two declaration keys the frontmatter grammar now accepts."""

    def test_validate_checks__stores_renamed_from_on_the_check(self):
        parsed = validate_checks(
            [{"id": "risk-level-set", "assert": "risk_level is set", "renamed_from": "risk-flag"}],
            "STD-TEST-001",
        )

        assert parsed[0]["renamed_from"] == "risk-flag"

    def test_validate_checks__omits_renamed_from_when_undeclared(self):
        parsed = validate_checks([{"id": "risk-flag", "assert": "risk_level is set"}], "STD-TEST-1")

        assert "renamed_from" not in parsed[0]

    def test_validate_checks__rejects_an_empty_renamed_from(self):
        with pytest.raises(CorpusParseError, match="renamed_from"):
            validate_checks(
                [{"id": "risk-flag", "assert": "risk_level is set", "renamed_from": "  "}],
                "STD-TEST-001",
            )

    def test_validate_retired_checks__returns_empty_list_when_absent(self):
        assert validate_retired_checks(None, "STD-TEST-001") == []

    def test_validate_retired_checks__rejects_a_non_list(self):
        with pytest.raises(CorpusParseError, match="must be a list"):
            validate_retired_checks("risk-flag", "STD-TEST-001")

    def test_validate_retired_checks__rejects_a_duplicate_id(self):
        with pytest.raises(CorpusParseError, match="duplicate"):
            validate_retired_checks(["risk-flag", "risk-flag"], "STD-TEST-001")

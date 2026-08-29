"""Planted-failure canary: every defect the review path claims to catch, caught.

A gate that stops catching its own known defect has rotted, and rot is silent.
`fixtures/canary/` holds a corpus and a spec engineered to fail in seven named
ways, and every test here asserts one of those failures by finding type and by
the stable `entry_id#check_id` identifier. A count assertion would pass for the
wrong reasons, so nothing here counts.

The planted defects:

| Defect | Asserted as |
|---|---|
| Obligation the spec never cites | unaddressed_obligation CANARY-STD-UNADDRESSED |
| Citation of a superseded version | stale_citation CANARY-STD-STALE at version 2 |
| Citation of an entry that stopped applying | orphan_citation CANARY-STD-ORPHAN |
| Structural check the spec fails | unmet_check CANARY-STD-UNMET#timing-stated |
| Two applicable entries that contradict | conflicting_obligations on CONFLICT-A |
| Two versions of one entry in one snapshot | one applicable version, one coverage row |
| Undeclared check-id rename across versions | CorpusCheckLineageError from the parser |

The fixtures live under the test tree on purpose. `parse_corpus corpus/` and a
real review must never see them, and `TestFixtureInvisibility` asserts that
rather than trusting the directory layout.
"""

from pathlib import Path

import pytest

from requirements.constants import (
    FINDING_CONFLICTING_OBLIGATIONS,
    FINDING_ORPHAN_CITATION,
    FINDING_STALE_CITATION,
    FINDING_UNADDRESSED_OBLIGATION,
    FINDING_UNMET_CHECK,
)
from requirements.models import CorpusEntryVersion, Requirement
from requirements.parser import SpecParser
from requirements.services.corpus_parser import CorpusCheckLineageError, CorpusParser
from requirements.services.corpus_review import review_as_dict, review_target

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_CORPUS_DIR = REPO_ROOT / "corpus"
REAL_SPECS_DIR = REPO_ROOT / "specs"

CANARY_DIR = Path(__file__).resolve().parent / "fixtures" / "canary"
CANARY_CORPUS_V1 = CANARY_DIR / "corpus_v1"
CANARY_CORPUS_V2 = CANARY_DIR / "corpus_v2"
CANARY_CORPUS_UNDECLARED_RENAME = CANARY_DIR / "corpus_undeclared_rename"
CANARY_SPECS_DIR = CANARY_DIR / "specs"
CANARY_SPEC = CANARY_SPECS_DIR / "canary_spec.md"

CANARY_REQUIREMENT_ID = "REQ-CANARY-001"
CANARY_ENTRY_PREFIX = "CANARY-"

PLANTED_FINDINGS = {
    (FINDING_UNADDRESSED_OBLIGATION, "CANARY-STD-UNADDRESSED", 1),
    (FINDING_UNADDRESSED_OBLIGATION, "CANARY-STD-CONFLICT-A", 1),
    (FINDING_UNADDRESSED_OBLIGATION, "CANARY-STD-CONFLICT-B", 1),
    (FINDING_STALE_CITATION, "CANARY-STD-STALE", 2),
    (FINDING_ORPHAN_CITATION, "CANARY-STD-ORPHAN", 1),
    (FINDING_UNMET_CHECK, "CANARY-STD-UNMET#timing-stated", 1),
    (FINDING_CONFLICTING_OBLIGATIONS, "CANARY-STD-CONFLICT-A#component-is-storage", 1),
}


@pytest.fixture
def canary_corpus(db):
    """Import the fixture corpus, version 1 first and then the lawful bump to 2.

    Two imports, not one directory: `parse_directory` refuses one entry id twice,
    and the bump has to be genuine lineage for the snapshot to hold two versions
    of CANARY-STD-STALE.
    """
    parser = CorpusParser()
    parser.import_to_database(CANARY_CORPUS_V1)
    parser.import_to_database(CANARY_CORPUS_V2)


@pytest.fixture
def canary_requirement(db):
    """Import the fixture spec through the real spec parser."""
    SpecParser().import_to_database(CANARY_SPECS_DIR)
    return Requirement.objects.get(external_id=CANARY_REQUIREMENT_ID)


@pytest.fixture
def canary_review(canary_corpus, canary_requirement):
    """The serialized review of the fixture spec against the fixture corpus."""
    reviews = review_target(str(CANARY_SPEC))
    return review_as_dict(reviews[0])


def planted(review) -> set[tuple[str, str, int]]:
    """Every finding as (type, stable identifier, version) — never as a count."""
    return {
        (finding["finding_type"], finding["finding_id"], finding["entry_version"])
        for finding in review["findings"]
    }


class TestPlantedDefects:
    """One test per planted defect, asserted by type and stable identifier."""

    def test_review__catches_the_planted_unaddressed_obligation(self, canary_review):
        """CANARY-STD-UNADDRESSED applies and the spec omits it."""
        assert (
            FINDING_UNADDRESSED_OBLIGATION,
            "CANARY-STD-UNADDRESSED",
            1,
        ) in planted(canary_review)

    def test_review__catches_the_planted_stale_citation(self, canary_review):
        """The spec cites CANARY-STD-STALE@1 while version 2 applies."""
        assert (FINDING_STALE_CITATION, "CANARY-STD-STALE", 2) in planted(canary_review)

    def test_review__catches_the_planted_orphan_citation(self, canary_review):
        """The spec cites CANARY-STD-ORPHAN@1, whose scope binds to nothing."""
        assert (FINDING_ORPHAN_CITATION, "CANARY-STD-ORPHAN", 1) in planted(canary_review)

    def test_review__catches_the_planted_unmet_check(self, canary_review):
        """The spec states no timing and cites the entry that demands one."""
        assert (
            FINDING_UNMET_CHECK,
            "CANARY-STD-UNMET#timing-stated",
            1,
        ) in planted(canary_review)

    def test_review__catches_the_planted_conflicting_obligations(self, canary_review):
        """Two applicable entries contradict each other on component."""
        assert (
            FINDING_CONFLICTING_OBLIGATIONS,
            "CANARY-STD-CONFLICT-A#component-is-storage",
            1,
        ) in planted(canary_review)

    def test_review__raises_every_planted_finding_and_nothing_else(self, canary_review):
        """The canary is exact: an extra finding is rot as surely as a missing one."""
        assert planted(canary_review) == PLANTED_FINDINGS


class TestPlantedVersionBump:
    """The bug that shipped: a bump making every version apply at once."""

    def test_canary_corpus__holds_two_versions_of_one_entry(self, canary_corpus):
        """The fixture only tests a bump if the bump is really in the database."""
        versions = CorpusEntryVersion.objects.filter(
            entry__external_id="CANARY-STD-STALE"
        ).order_by("version")

        assert [version.version for version in versions] == [1, 2]

    def test_review__covers_a_bumped_entry_once_at_the_newest_version(self, canary_review):
        """Two versions in one snapshot yield one applicable version, one coverage row."""
        rows = [row for row in canary_review["coverage"] if row["entry_id"] == "CANARY-STD-STALE"]

        assert [row["entry_version"] for row in rows] == [2]

    def test_review__raises_one_finding_for_a_bumped_entry(self, canary_review):
        """The doubled-finding half of the same bug."""
        findings = [
            finding
            for finding in canary_review["findings"]
            if finding["entry_id"] == "CANARY-STD-STALE"
        ]

        assert [(f["finding_type"], f["entry_version"]) for f in findings] == [
            (FINDING_STALE_CITATION, 2)
        ]


class TestPlantedUndeclaredRename:
    """The M1 case: a check id that changes across versions without a declaration."""

    def test_import_to_database__rejects_the_planted_undeclared_rename(self, canary_corpus):
        """Version 3 renames spec-status-active and declares nothing."""
        with pytest.raises(CorpusCheckLineageError, match="spec-status-active"):
            CorpusParser().import_to_database(CANARY_CORPUS_UNDECLARED_RENAME)

    def test_import_to_database__stores_no_version_for_the_rejected_rename(self, canary_corpus):
        """A rejected file leaves the entry at the versions that were lawful."""
        with pytest.raises(CorpusCheckLineageError):
            CorpusParser().import_to_database(CANARY_CORPUS_UNDECLARED_RENAME)

        assert not CorpusEntryVersion.objects.filter(
            entry__external_id="CANARY-STD-STALE", version=3
        ).exists()


class TestFixtureInvisibility:
    """The fixtures must be unreachable from the real corpus and a real review."""

    def test_canary_fixtures__live_outside_the_real_corpus_and_specs_directories(self):
        """Path containment, asserted rather than assumed."""
        assert not CANARY_DIR.is_relative_to(REAL_CORPUS_DIR)
        assert not CANARY_DIR.is_relative_to(REAL_SPECS_DIR)

    def test_parse_corpus__finds_no_canary_entry_in_the_real_corpus(self):
        """`parse_corpus corpus/` never reads a planted entry."""
        entries = CorpusParser().parse_directory(REAL_CORPUS_DIR)

        assert [
            entry["external_id"]
            for entry in entries
            if entry["external_id"].startswith(CANARY_ENTRY_PREFIX)
        ] == []

    def test_parse_specs__finds_no_canary_requirement_in_the_real_specs(self):
        """`parse_specs specs/` never reads the planted spec."""
        parsed = SpecParser().parse_directory(REAL_SPECS_DIR)

        assert CANARY_REQUIREMENT_ID not in [item["external_id"] for item in parsed]

    def test_review_target__surfaces_no_canary_entry_for_a_real_spec(self, canary_corpus):
        """A real review with the fixtures loaded surfaces none of them."""
        CorpusParser().import_to_database(REAL_CORPUS_DIR)
        SpecParser().import_to_database(REAL_SPECS_DIR)

        reviews = review_target(str(REAL_SPECS_DIR / "platform" / "tenant_isolation.md"))

        payloads = [review_as_dict(review) for review in reviews]
        surfaced = [row["entry_id"] for payload in payloads for row in payload["coverage"]] + [
            finding["entry_id"] for payload in payloads for finding in payload["findings"]
        ]
        assert surfaced
        assert [entry_id for entry_id in surfaced if entry_id.startswith(CANARY_ENTRY_PREFIX)] == []

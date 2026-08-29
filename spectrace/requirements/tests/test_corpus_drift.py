"""Tests for derived corpus drift: stale reviews and newly applicable entries."""

import hashlib
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.db.models import ProtectedError

from requirements.models import (
    CorpusEntry,
    CorpusEntryKind,
    CorpusEntryStatus,
    CorpusEntryVersion,
    Requirement,
)
from requirements.services.corpus_drift import (
    added_entry_versions,
    covered_versions_by_entry,
    drift_as_dict,
    latest_reviews,
    newly_applicable_entries,
    stale_reviews,
)
from requirements.services.corpus_review import current_snapshot, review_requirement

BILLING_SPEC = "specs/billing/metering.md"
PLATFORM_SPEC = "specs/platform/tenant_isolation.md"


@pytest.fixture
def make_entry_version(db):
    """Factory creating one CorpusEntryVersion with given scope rules."""

    def _make(
        entry_id: str,
        applies_to: dict | None = None,
        version: int = 1,
        status: str = CorpusEntryStatus.ACTIVE,
        supersedes: CorpusEntryVersion | None = None,
        title: str = "",
    ) -> CorpusEntryVersion:
        entry, _ = CorpusEntry.objects.update_or_create(
            external_id=entry_id,
            defaults={
                "kind": CorpusEntryKind.DECISION,
                "title": title or f"{entry_id} title",
                "owner": "billing",
                "status": status,
                "source_file": f"corpus/{entry_id.lower()}.md",
            },
        )
        digest = hashlib.sha256(f"{entry_id}@{version}".encode()).hexdigest()
        return CorpusEntryVersion.objects.create(
            entry=entry,
            version=version,
            body=f"Body of {entry_id} at {version}.",
            content_hash=digest,
            applies_to=applies_to or {},
            checks=[],
            supersedes=supersedes,
            source_file=f"corpus/{entry_id.lower()}.md",
        )

    return _make


@pytest.fixture
def billing_requirement(db):
    """A billing requirement the metering entries bind to."""
    return Requirement.add_root(
        external_id="REQ-BILL-002",
        title="Usage metering",
        status="active",
        source_file=BILLING_SPEC,
        tags=["billing"],
        component="metering",
        risk_level="critical",
        verification_method="test",
    )


@pytest.fixture
def platform_requirement(db):
    """A platform requirement that no billing entry reaches."""
    return Requirement.add_root(
        external_id="REQ-CORP-001",
        title="Tenant isolation",
        status="active",
        source_file=PLATFORM_SPEC,
        tags=["platform"],
        component="storage",
        risk_level="critical",
        verification_method="test",
    )


@pytest.fixture
def review_now():
    """Review one requirement against the corpus as it stands."""

    def _review(requirement, spec_file, *citations: str):
        return review_requirement(requirement, current_snapshot(), citations, spec_file)

    return _review


def _drift():
    """Run both halves of the derivation against the current corpus."""
    current = current_snapshot()
    reviews = latest_reviews()
    return stale_reviews(reviews, current), newly_applicable_entries(reviews, current)


class TestAddedEntryVersions:
    """Tests for the snapshot diff that feeds the staleness derivation."""

    def test_added_entry_versions__is_empty_when_the_corpus_has_not_moved(self, make_entry_version):
        """Two captures of an unchanged corpus produce no additions."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        pinned = current_snapshot()

        assert added_entry_versions(pinned, current_snapshot()) == ()

    def test_added_entry_versions__names_a_version_the_pinned_snapshot_lacks(
        self, make_entry_version
    ):
        """A version present now and absent then is an addition."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        pinned = current_snapshot()
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)

        added = added_entry_versions(pinned, current_snapshot())

        assert [(item.entry_id, item.version) for item in added] == [("DEC-BILL-001", 2)]

    def test_added_entry_versions__carries_the_version_a_new_entry_supersedes(
        self, make_entry_version
    ):
        """A successor names the version it retires, across entry ids."""
        legacy = make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        pinned = current_snapshot()
        make_entry_version("DEC-BILL-002", applies_to={"tags": ["billing"]}, supersedes=legacy)

        added = added_entry_versions(pinned, current_snapshot())[0]

        assert added.entry_id == "DEC-BILL-002"
        assert added.supersedes == ("DEC-BILL-001", 1)
        assert added.supersedes_label == "DEC-BILL-001@1"

    def test_added_entry_versions__diffs_one_way_because_coverage_protects_its_versions(
        self, billing_requirement, make_entry_version, review_now
    ):
        """A covered version cannot leave the corpus, so drift is what entered."""
        entry_version = make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)

        with pytest.raises(ProtectedError):
            entry_version.delete()


class TestStaleReviews:
    """Tests for staleness derived from coverage, the pinned snapshot, and the corpus."""

    def test_stale_reviews__names_a_review_whose_covered_entry_gained_a_version(
        self, billing_requirement, make_entry_version, review_now
    ):
        """A new version of a covered entry invalidates the review that covered it."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)

        stale, _ = _drift()

        assert [item.review.requirement.external_id for item in stale] == ["REQ-BILL-002"]
        assert [(change.entry_id, change.version) for change in stale[0].additions] == [
            ("DEC-BILL-001", 2)
        ]

    def test_stale_reviews__omits_a_review_that_never_covered_the_changed_entry(
        self, billing_requirement, platform_requirement, make_entry_version, review_now
    ):
        """Precision: a change outside a review's own coverage leaves it standing."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        make_entry_version("STD-SEC-001", applies_to={"tags": ["platform"]})
        review_now(billing_requirement, BILLING_SPEC)
        review_now(platform_requirement, PLATFORM_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)

        stale, _ = _drift()

        assert [item.review.requirement.external_id for item in stale] == ["REQ-BILL-002"]
        assert "REQ-CORP-001" not in [item.review.requirement.external_id for item in stale]

    def test_stale_reviews__names_a_review_whose_covered_entry_a_new_entry_supersedes(
        self, billing_requirement, make_entry_version, review_now
    ):
        """The seed corpus chain: DEC-BILL-002 supersedes DEC-BILL-001@1."""
        legacy = make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version(
            "DEC-BILL-002", applies_to={"tags": ["subscriptions"]}, supersedes=legacy
        )

        stale, _ = _drift()

        assert len(stale) == 1
        change = stale[0].additions[0]
        assert change.entry_id == "DEC-BILL-002"
        assert change.supersedes_label == "DEC-BILL-001@1"

    def test_stale_reviews__is_empty_when_the_corpus_has_not_moved(
        self, billing_requirement, make_entry_version, review_now
    ):
        """A review pinned to the current snapshot is not stale."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)

        stale, _ = _drift()

        assert stale == []

    def test_stale_reviews__examines_only_the_latest_review_of_a_requirement(
        self, billing_requirement, make_entry_version, review_now
    ):
        """A re-review against the moved corpus clears the requirement."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)
        review_now(billing_requirement, BILLING_SPEC)

        stale, _ = _drift()

        assert stale == []

    def test_stale_reviews__reports_no_persisted_marker_on_the_review_row(
        self, billing_requirement, make_entry_version, review_now
    ):
        """Staleness is derived: re-deriving after a corpus revert clears it."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        second = make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)
        assert _drift()[0] != []

        second.delete()

        assert _drift()[0] == []

    def test_covered_versions_by_entry__groups_coverage_rows_by_entry(
        self, billing_requirement, make_entry_version, review_now
    ):
        """Coverage rows read back as entry id to version tuple."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        make_entry_version("COM-BILL-001", applies_to={"components": ["metering"]})
        review = review_now(billing_requirement, BILLING_SPEC)

        assert covered_versions_by_entry(review) == {
            "COM-BILL-001": (1,),
            "DEC-BILL-001": (1,),
        }


class TestNewlyApplicableEntries:
    """Tests for the inverse: obligations no review has ever surfaced."""

    def test_newly_applicable_entries__names_an_entry_whose_scope_now_reaches_the_spec(
        self, billing_requirement, make_entry_version, review_now
    ):
        """A new entry binding to a reviewed spec is reported per spec."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("COM-BILL-001", applies_to={"components": ["metering"]})

        _, gaps = _drift()

        assert [gap.review.requirement.external_id for gap in gaps] == ["REQ-BILL-002"]
        assert [item.entry_id for item in gaps[0].entries] == ["COM-BILL-001"]

    def test_newly_applicable_entries__omits_a_spec_the_new_entry_does_not_reach(
        self, billing_requirement, platform_requirement, make_entry_version, review_now
    ):
        """An entry scoped elsewhere leaves the other spec's applicable set alone."""
        make_entry_version("STD-SEC-001", applies_to={"tags": ["platform"]})
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        review_now(platform_requirement, PLATFORM_SPEC)
        make_entry_version("COM-BILL-001", applies_to={"components": ["metering"]})

        _, gaps = _drift()

        assert [gap.review.requirement.external_id for gap in gaps] == ["REQ-BILL-002"]

    def test_newly_applicable_entries__names_the_successor_of_a_superseded_entry(
        self, billing_requirement, make_entry_version, review_now
    ):
        """After DEC-BILL-002 lands, the spec has an obligation no review surfaced."""
        legacy = make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("DEC-BILL-002", applies_to={"tags": ["billing"]}, supersedes=legacy)

        _, gaps = _drift()

        assert [item.entry_id for item in gaps[0].entries] == ["DEC-BILL-002"]

    def test_newly_applicable_entries__is_empty_when_the_corpus_has_not_moved(
        self, billing_requirement, make_entry_version, review_now
    ):
        """A spec reviewed against the current corpus has no unreviewed obligation."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)

        _, gaps = _drift()

        assert gaps == []


class TestDriftAsDict:
    """Tests for the serialized drift report."""

    def test_drift_as_dict__names_the_entry_and_version_that_invalidated_each_review(
        self, billing_requirement, make_entry_version, review_now
    ):
        """Every stale review names the entry version that invalidated it."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)

        report = drift_as_dict()

        row = report["stale_reviews"][0]
        assert row["requirement_id"] == "REQ-BILL-002"
        assert row["spec_file"] == BILLING_SPEC
        assert row["invalidated_by"] == [
            {
                "entry_id": "DEC-BILL-001",
                "entry_version": 2,
                "title": "DEC-BILL-001 title",
                "supersedes": "",
                "covered_versions": [1],
                "detail": (
                    "DEC-BILL-001@2 entered the corpus after this review, "
                    "which covers DEC-BILL-001@1"
                ),
            }
        ]

    def test_drift_as_dict__details_a_supersession_across_entry_ids(
        self, billing_requirement, make_entry_version, review_now
    ):
        """The detail names both the successor and the covered version it retires."""
        legacy = make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version(
            "DEC-BILL-002", applies_to={"tags": ["subscriptions"]}, supersedes=legacy
        )

        report = drift_as_dict()

        assert report["stale_reviews"][0]["invalidated_by"][0]["detail"] == (
            "DEC-BILL-002@1 entered the corpus after this review and supersedes DEC-BILL-001@1"
        )

    def test_drift_as_dict__carries_match_reasons_for_newly_applicable_entries(
        self, billing_requirement, make_entry_version, review_now
    ):
        """A newly applicable entry reports why it binds, not just that it does."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("COM-BILL-001", applies_to={"components": ["metering"]})

        report = drift_as_dict()

        entry = report["newly_applicable"][0]["entries"][0]
        assert entry["entry_id"] == "COM-BILL-001"
        assert entry["matched_by"] == [
            {
                "scope_key": "components",
                "pattern": "metering",
                "matched_value": "metering",
                "matched_requirement_id": "REQ-BILL-002",
                "inherited": False,
            }
        ]

    def test_drift_as_dict__counts_reviews_examined_and_stale(
        self, billing_requirement, platform_requirement, make_entry_version, review_now
    ):
        """The summary counts both reviews and names only one as stale."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        make_entry_version("STD-SEC-001", applies_to={"tags": ["platform"]})
        review_now(billing_requirement, BILLING_SPEC)
        review_now(platform_requirement, PLATFORM_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)

        report = drift_as_dict()

        assert report["summary"] == {
            "reviews_examined": 2,
            "stale_reviews": 1,
            "specs_with_newly_applicable_entries": 1,
            "newly_applicable_entries": 1,
        }


class TestCorpusDriftCommand:
    """Tests for the corpus_drift management command."""

    def test_command__outputs_json_with_stale_reviews_and_new_entries(
        self, billing_requirement, make_entry_version, review_now
    ):
        """--format json emits the whole derivation."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)
        out = StringIO()

        call_command("corpus_drift", "--format", "json", stdout=out)

        payload = json.loads(out.getvalue())
        assert payload["stale_reviews"][0]["requirement_id"] == "REQ-BILL-002"
        assert payload["newly_applicable"][0]["entries"][0]["entry_version"] == 2
        assert payload["summary"]["stale_reviews"] == 1

    def test_command__outputs_text_naming_the_invalidating_entry(
        self, billing_requirement, make_entry_version, review_now
    ):
        """Text output names the review and the change that invalidated it."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)
        out = StringIO()

        call_command("corpus_drift", stdout=out)

        output = out.getvalue()
        assert "REQ-BILL-002" in output
        assert "DEC-BILL-001@2 entered the corpus after this review" in output
        assert "1 of 1 reviews stale" in output

    def test_command__reports_no_stale_reviews_when_the_corpus_has_not_moved(
        self, billing_requirement, make_entry_version, review_now
    ):
        """A corpus that has not moved reports clean."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        out = StringIO()

        call_command("corpus_drift", stdout=out)

        output = out.getvalue()
        assert "No stale reviews" in output
        assert "No newly applicable entries" in output

    def test_command__outputs_md_tables(self, billing_requirement, make_entry_version, review_now):
        """--format md emits a stale-review table and a newly-applicable table."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)
        out = StringIO()

        call_command("corpus_drift", "--format", "md", stdout=out)

        output = out.getvalue()
        assert "## 🌊 SpecTrace Corpus Drift" in output
        assert "| Requirement | Spec | Reviewed at | Invalidated by | Detail |" in output
        assert "| REQ-BILL-002 | `specs/billing/metering.md` |" in output
        assert "| Requirement | Spec | Entry | Kind | Title |" in output

    def test_command__strict_exits_nonzero_when_reviews_are_stale(
        self, billing_requirement, make_entry_version, review_now
    ):
        """--strict turns stale reviews into a nonzero exit code."""
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        review_now(billing_requirement, BILLING_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]}, version=2)

        with pytest.raises(SystemExit) as exit_info:
            call_command("corpus_drift", "--strict", stdout=StringIO())

        assert exit_info.value.code == 1

    def test_command__strict_exits_zero_when_only_new_entries_appeared(
        self, platform_requirement, make_entry_version, review_now
    ):
        """A spec that merely gained an obligation is not a stale review."""
        make_entry_version("STD-SEC-001", applies_to={"tags": ["platform"]})
        review_now(platform_requirement, PLATFORM_SPEC)
        make_entry_version("DEC-BILL-001", applies_to={"tags": ["billing"]})
        out = StringIO()

        call_command("corpus_drift", "--strict", stdout=out)

        assert "No stale reviews" in out.getvalue()

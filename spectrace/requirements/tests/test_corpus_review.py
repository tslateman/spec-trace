"""Tests for the corpus review runner, its audit ledger, and its commands."""

import hashlib
import json
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from requirements.models import (
    CorpusEnforcement,
    CorpusEntry,
    CorpusEntryKind,
    CorpusEntryStatus,
    CorpusEntryVersion,
    CorpusSnapshot,
    Requirement,
    ReviewCoverage,
    ReviewFinding,
    SpecReview,
    SpecReviewOutcome,
)
from requirements.services.corpus_review import (
    ReviewTargetError,
    UnknownCitationError,
    coverage_as_dicts,
    current_snapshot,
    has_blocking_finding,
    resolve_target,
    review_as_dict,
    review_requirement,
    review_target,
)

RISK_CHECK = {
    "id": "risk-classified",
    "assert": "risk_level in [critical, high]",
    "field": "risk_level",
    "operator": "in",
    "value": ["critical", "high"],
}

CONDITION_CHECK = {
    "id": "trigger-stated",
    "assert": "condition is set",
    "field": "condition",
    "operator": "is set",
    "value": None,
}

SPEC_BODY = """---
id: REQ-CORP-001
title: Tenant isolation
tags: [platform, security]
status: active
{extra}---

Tenant data stays isolated.
"""


@pytest.fixture
def make_entry_version(db):
    """Factory creating one CorpusEntryVersion with given scope rules and checks."""

    def _make(
        entry_id: str,
        applies_to: dict | None = None,
        checks: list | None = None,
        version: int = 1,
        status: str = CorpusEntryStatus.ACTIVE,
        supersedes: CorpusEntryVersion | None = None,
        enforcement: str = CorpusEnforcement.ADVISORY,
    ) -> CorpusEntryVersion:
        entry, _ = CorpusEntry.objects.update_or_create(
            external_id=entry_id,
            defaults={
                "kind": CorpusEntryKind.STANDARD,
                "title": f"{entry_id} title",
                "owner": "platform",
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
            checks=checks or [],
            enforcement=enforcement,
            supersedes=supersedes,
            source_file=f"corpus/{entry_id.lower()}.md",
        )

    return _make


@pytest.fixture
def platform_requirement(db):
    """A critical, test-verified requirement tagged platform and security."""
    return Requirement.add_root(
        external_id="REQ-CORP-001",
        title="Tenant isolation",
        status="active",
        source_file="specs/platform/tenant_isolation.md",
        tags=["platform", "security"],
        component="storage",
        risk_level="critical",
        verification_method="test",
        timing="within 4 hours",
    )


@pytest.fixture
def applicable_entry(make_entry_version):
    """One entry version that binds to the platform requirement and passes its check."""
    return make_entry_version(
        "STD-SEC-001",
        applies_to={"tags": ["platform"], "requirement_ids": ["REQ-CORP-*"]},
        checks=[RISK_CHECK],
    )


@pytest.fixture
def blocking_entry(make_entry_version):
    """One entry version whose owner marked it blocking."""
    return make_entry_version(
        "STD-SEC-002",
        applies_to={"tags": ["security"]},
        enforcement=CorpusEnforcement.BLOCKING,
    )


@pytest.fixture
def spec_file(tmp_path):
    """Factory writing a spec file whose frontmatter cites the given entries."""

    def _write(*citations: str):
        extra = ""
        if citations:
            rendered = ", ".join(citations)
            extra = f"complies_with: [{rendered}]\n"
        path = tmp_path / "tenant_isolation.md"
        path.write_text(SPEC_BODY.format(extra=extra))
        return path

    return _write


class TestReviewRequirement:
    """Tests for review_requirement, the writer of the audit ledger."""

    def test_review_requirement__writes_coverage_row_for_every_applicable_entry(
        self, platform_requirement, make_entry_version
    ):
        """Every applicable entry version gets a coverage row."""
        make_entry_version("STD-SEC-001", applies_to={"tags": ["platform"]})
        make_entry_version("STD-SEC-002", applies_to={"tags": ["security"]})
        make_entry_version("STD-OTHER-001", applies_to={"tags": ["billing"]})

        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        surfaced = [row.entry_version.entry.external_id for row in review.coverage.all()]
        assert surfaced == ["STD-SEC-001", "STD-SEC-002"]

    def test_review_requirement__writes_one_coverage_row_per_entry_after_a_version_bump(
        self, platform_requirement, make_entry_version
    ):
        """A bumped entry is covered once, at the version the bump made current."""
        make_entry_version(
            "STD-SEC-001",
            applies_to={"tags": ["platform"]},
            version=3,
            enforcement=CorpusEnforcement.ADVISORY,
        )
        make_entry_version(
            "STD-SEC-001",
            applies_to={"tags": ["platform"]},
            version=4,
            enforcement=CorpusEnforcement.BLOCKING,
        )

        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        assert [(row.entry_version.version, row.enforcement) for row in review.coverage.all()] == [
            (4, CorpusEnforcement.BLOCKING)
        ]

    def test_review_requirement__records_one_finding_per_entry_after_a_version_bump(
        self, platform_requirement, make_entry_version
    ):
        """A bumped entry faults once, so the ledger counts the standard once."""
        make_entry_version(
            "STD-SEC-001", applies_to={"tags": ["platform"]}, checks=[CONDITION_CHECK], version=3
        )
        make_entry_version(
            "STD-SEC-001", applies_to={"tags": ["platform"]}, checks=[CONDITION_CHECK], version=4
        )

        review = review_requirement(
            platform_requirement,
            current_snapshot(),
            ("STD-SEC-001@4",),
            "specs/platform/tenant_isolation.md",
        )

        assert [
            (finding.entry_version.version, finding.check_id) for finding in review.findings.all()
        ] == [(4, "trigger-stated")]

    def test_review_requirement__resolves_the_version_current_in_the_pinned_snapshot(
        self, platform_requirement, make_entry_version
    ):
        """A review pinned before a bump still covers the version current then."""
        make_entry_version("STD-SEC-001", applies_to={"tags": ["platform"]}, version=3)
        pinned = current_snapshot()
        make_entry_version("STD-SEC-001", applies_to={"tags": ["platform"]}, version=4)

        review = review_requirement(
            platform_requirement, pinned, (), "specs/platform/tenant_isolation.md"
        )

        assert [row.entry_version.version for row in review.coverage.all()] == [3]

    def test_review_requirement__writes_coverage_row_when_entry_produces_no_finding(
        self, platform_requirement, applicable_entry
    ):
        """A clean entry still gets its coverage row — that row is the audit claim."""
        review = review_requirement(
            platform_requirement,
            current_snapshot(),
            ("STD-SEC-001@1",),
            "specs/platform/tenant_isolation.md",
        )

        assert review.findings.count() == 0
        assert review.outcome == SpecReviewOutcome.CLEAN

        coverage = review.coverage.get()
        assert coverage.entry_version == applicable_entry
        assert coverage.cited is True

    def test_review_requirement__persists_match_reasons_into_matched_by(
        self, platform_requirement, applicable_entry
    ):
        """Coverage rows carry the matcher's structured reasons, not just a flag."""
        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        assert review.coverage.get().matched_by == [
            {
                "scope_key": "tags",
                "pattern": "platform",
                "matched_value": "platform",
                "matched_requirement_id": "REQ-CORP-001",
                "inherited": False,
            },
            {
                "scope_key": "requirement_ids",
                "pattern": "REQ-CORP-*",
                "matched_value": "REQ-CORP-001",
                "matched_requirement_id": "REQ-CORP-001",
                "inherited": False,
            },
        ]

    def test_review_requirement__marks_uncited_entry_as_not_cited(
        self, platform_requirement, applicable_entry
    ):
        """An applicable entry the spec never cites is recorded as uncited."""
        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        assert review.coverage.get().cited is False

    def test_review_requirement__writes_exactly_one_review(
        self, platform_requirement, applicable_entry
    ):
        """One run of one requirement writes one SpecReview."""
        review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        assert SpecReview.objects.count() == 1

    def test_review_requirement__records_findings_with_entry_and_check(
        self, platform_requirement, make_entry_version
    ):
        """An unmet structural check is persisted with its entry version and check id."""
        make_entry_version(
            "STD-SEC-001",
            applies_to={"tags": ["platform"]},
            checks=[CONDITION_CHECK],
        )

        review = review_requirement(
            platform_requirement,
            current_snapshot(),
            ("STD-SEC-001@1",),
            "specs/platform/tenant_isolation.md",
        )

        finding = review.findings.get()
        assert finding.finding_type == "unmet_check"
        assert finding.entry_version.entry.external_id == "STD-SEC-001"
        assert finding.check_id == "trigger-stated"
        assert review.outcome == SpecReviewOutcome.FINDINGS

    def test_review_requirement__records_stale_citation_against_current_version(
        self, platform_requirement, make_entry_version
    ):
        """Citing an old version records a stale citation naming the applicable version."""
        first = make_entry_version("STD-SEC-001", applies_to={"tags": ["platform"]}, version=1)
        make_entry_version(
            "STD-SEC-001", applies_to={"tags": ["platform"]}, version=2, supersedes=first
        )

        review = review_requirement(
            platform_requirement,
            current_snapshot(),
            ("STD-SEC-001@1",),
            "specs/platform/tenant_isolation.md",
        )

        finding = review.findings.get()
        assert finding.finding_type == "stale_citation"
        assert finding.entry_version.version == 2

    def test_review_requirement__records_orphan_citation_against_stored_version(
        self, platform_requirement, make_entry_version
    ):
        """An orphan citation resolves to the corpus version the spec named."""
        make_entry_version("STD-SEC-001", applies_to={"tags": ["platform"]})
        make_entry_version("STD-BILL-001", applies_to={"tags": ["billing"]})

        review = review_requirement(
            platform_requirement,
            current_snapshot(),
            ("STD-SEC-001@1", "STD-BILL-001@1"),
            "specs/platform/tenant_isolation.md",
        )

        orphan = review.findings.get(finding_type="orphan_citation")
        assert orphan.entry_version.entry.external_id == "STD-BILL-001"

    def test_review_requirement__raises_when_citation_names_unknown_entry(
        self, platform_requirement, applicable_entry
    ):
        """A citation the corpus does not contain stops the review."""
        with pytest.raises(UnknownCitationError, match="STD-GHOST-001@4"):
            review_requirement(
                platform_requirement,
                current_snapshot(),
                ("STD-SEC-001@1", "STD-GHOST-001@4"),
                "specs/platform/tenant_isolation.md",
            )

    def test_review_requirement__writes_nothing_when_a_citation_is_unknown(
        self, platform_requirement, applicable_entry
    ):
        """The whole review is atomic: a bad citation leaves no partial record."""
        with pytest.raises(UnknownCitationError):
            review_requirement(
                platform_requirement,
                current_snapshot(),
                ("STD-GHOST-001@4",),
                "specs/platform/tenant_isolation.md",
            )

        assert SpecReview.objects.count() == 0
        assert ReviewCoverage.objects.count() == 0
        assert ReviewFinding.objects.count() == 0

    def test_review_requirement__pins_the_snapshot_it_ran_against(
        self, platform_requirement, applicable_entry
    ):
        """The review points at the snapshot, so later corpus edits cannot rewrite it."""
        snapshot = current_snapshot()

        review = review_requirement(
            platform_requirement, snapshot, (), "specs/platform/tenant_isolation.md"
        )

        assert review.snapshot == snapshot
        assert applicable_entry in snapshot.entry_versions.all()


class TestCurrentSnapshot:
    """Tests for the snapshot the review path pins."""

    def test_current_snapshot__reuses_the_snapshot_for_an_unchanged_corpus(self, applicable_entry):
        """Two reviews of an unchanged corpus share one snapshot row."""
        assert current_snapshot() == current_snapshot()
        assert CorpusSnapshot.objects.count() == 1

    def test_current_snapshot__creates_a_new_snapshot_when_a_version_lands(
        self, applicable_entry, make_entry_version
    ):
        """Adding an entry version yields a different snapshot hash."""
        before = current_snapshot()
        make_entry_version("STD-SEC-002", applies_to={"tags": ["security"]})

        assert current_snapshot().snapshot_hash != before.snapshot_hash


class TestResolveTarget:
    """Tests for resolving a spec path or requirement id into a review target."""

    def test_resolve_target__reads_citations_from_spec_frontmatter(
        self, platform_requirement, spec_file
    ):
        """A spec path resolves to its requirements and its complies_with list."""
        path = spec_file("STD-SEC-001@1", "STD-SEC-002@2")

        resolved = resolve_target(str(path))

        assert resolved.requirements == (platform_requirement,)
        assert resolved.citations == ("STD-SEC-001@1", "STD-SEC-002@2")

    def test_resolve_target__returns_no_citations_when_frontmatter_omits_them(
        self, platform_requirement, spec_file
    ):
        """A spec with no complies_with resolves to an empty citation list."""
        assert resolve_target(str(spec_file())).citations == ()

    def test_resolve_target__resolves_a_requirement_id_through_its_source_file(self, db, spec_file):
        """A requirement id resolves through the spec file it was parsed from."""
        path = spec_file("STD-SEC-001@1")
        requirement = Requirement.add_root(
            external_id="REQ-CORP-001",
            title="Tenant isolation",
            status="active",
            source_file=str(path),
            tags=["platform"],
        )

        resolved = resolve_target("REQ-CORP-001")

        assert resolved.requirements == (requirement,)
        assert resolved.citations == ("STD-SEC-001@1",)

    def test_resolve_target__raises_for_an_unknown_target(self, db):
        """A target that is neither a file nor a requirement id is an error."""
        with pytest.raises(ReviewTargetError, match="neither a readable spec file"):
            resolve_target("REQ-NOT-HERE")

    def test_resolve_target__raises_when_the_spec_declares_an_unimported_requirement(
        self, db, spec_file
    ):
        """A spec whose requirement parse_specs never imported is an error."""
        with pytest.raises(ReviewTargetError, match="REQ-CORP-001"):
            resolve_target(str(spec_file()))


class TestReviewTarget:
    """Tests for reviewing every requirement in a spec file."""

    def test_review_target__reviews_each_requirement_in_the_spec(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """Reviewing a path writes one review per requirement the file declares."""
        reviews = review_target(str(spec_file("STD-SEC-001@1")), reviewer="tommy")

        assert len(reviews) == 1
        assert reviews[0].requirement == platform_requirement
        assert reviews[0].reviewer == "tommy"
        assert reviews[0].outcome == SpecReviewOutcome.CLEAN


class TestReviewAsDict:
    """Tests for the serialized review payload."""

    def test_review_as_dict__includes_entries_versions_reasons_and_findings(
        self, platform_requirement, applicable_entry
    ):
        """The JSON payload carries entry ids, versions, match reasons, and findings."""
        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        payload = review_as_dict(review)

        assert payload["requirement_id"] == "REQ-CORP-001"
        assert payload["spec_file"] == "specs/platform/tenant_isolation.md"
        assert payload["outcome"] == SpecReviewOutcome.FINDINGS
        assert payload["coverage"][0]["entry_id"] == "STD-SEC-001"
        assert payload["coverage"][0]["entry_version"] == 1
        assert payload["coverage"][0]["matched_by"][0]["scope_key"] == "tags"
        assert payload["findings"][0]["finding_type"] == "unaddressed_obligation"
        assert payload["snapshot_hash"] == current_snapshot().snapshot_hash


class TestCoverageAsDicts:
    """Tests for the audit ledger view."""

    def test_coverage_as_dicts__reports_a_requirement_that_was_never_reviewed(
        self, platform_requirement, applicable_entry
    ):
        """Never having been reviewed is itself an audit answer."""
        row = coverage_as_dicts()[0]

        assert row["requirement_id"] == "REQ-CORP-001"
        assert row["reviewed"] is False
        assert row["entries_surfaced"] == 0

    def test_coverage_as_dicts__reports_the_latest_review(
        self, platform_requirement, applicable_entry
    ):
        """The ledger reports the newest review of each requirement."""
        review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )
        review_requirement(
            platform_requirement,
            current_snapshot(),
            ("STD-SEC-001@1",),
            "specs/platform/tenant_isolation.md",
        )

        row = coverage_as_dicts()[0]

        assert row["reviewed"] is True
        assert row["outcome"] == SpecReviewOutcome.CLEAN
        assert row["entries_surfaced"] == 1
        assert row["unaddressed"] == []

    def test_coverage_as_dicts__names_unaddressed_entries(
        self, platform_requirement, applicable_entry
    ):
        """Entries the spec never cited are named in the ledger."""
        review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        assert coverage_as_dicts()[0]["unaddressed"] == ["STD-SEC-001@1"]

    def test_coverage_as_dicts__filters_to_one_requirement(
        self, platform_requirement, applicable_entry
    ):
        """The report narrows to a single requirement id."""
        Requirement.add_root(
            external_id="REQ-CORP-002",
            title="Other",
            status="active",
            source_file="specs/platform/other.md",
        )

        rows = coverage_as_dicts("REQ-CORP-002")

        assert [row["requirement_id"] for row in rows] == ["REQ-CORP-002"]


class TestEnforcementPosture:
    """Tests for the posture a review records and the exit contract it feeds."""

    def test_review_requirement__copies_owner_posture_onto_coverage_rows(
        self, platform_requirement, applicable_entry, blocking_entry
    ):
        """Each coverage row carries the posture its entry version declared."""
        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        postures = {
            row.entry_version.entry.external_id: row.enforcement for row in review.coverage.all()
        }
        assert postures == {
            "STD-SEC-001": CorpusEnforcement.ADVISORY,
            "STD-SEC-002": CorpusEnforcement.BLOCKING,
        }

    def test_review_requirement__copies_owner_posture_onto_findings(
        self, platform_requirement, applicable_entry, blocking_entry
    ):
        """Each finding carries the posture of the entry version it traces to."""
        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        postures = {
            finding.entry_version.entry.external_id: finding.enforcement
            for finding in review.findings.all()
        }
        assert postures == {
            "STD-SEC-001": CorpusEnforcement.ADVISORY,
            "STD-SEC-002": CorpusEnforcement.BLOCKING,
        }

    def test_review_requirement__keeps_the_posture_a_later_version_leaves_behind(
        self, platform_requirement, make_entry_version
    ):
        """A recorded finding keeps the posture that was in force when it ran."""
        version_one = make_entry_version(
            "STD-SEC-001",
            applies_to={"tags": ["platform"]},
            enforcement=CorpusEnforcement.ADVISORY,
        )
        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )
        make_entry_version(
            "STD-SEC-001",
            applies_to={"tags": ["platform"]},
            version=2,
            enforcement=CorpusEnforcement.BLOCKING,
            supersedes=version_one,
        )

        assert review.findings.get().enforcement == CorpusEnforcement.ADVISORY

    def test_has_blocking_finding__is_false_for_advisory_findings_alone(self):
        """Advisory findings report without blocking."""
        payloads = [{"findings": [{"enforcement": CorpusEnforcement.ADVISORY}]}]

        assert has_blocking_finding(payloads) is False

    def test_has_blocking_finding__is_true_when_one_finding_blocks(self):
        """One blocking finding among advisory ones blocks."""
        payloads = [
            {
                "findings": [
                    {"enforcement": CorpusEnforcement.ADVISORY},
                    {"enforcement": CorpusEnforcement.BLOCKING},
                ]
            }
        ]

        assert has_blocking_finding(payloads) is True

    def test_has_blocking_finding__is_false_when_there_are_no_findings(self):
        """A clean review never blocks, escalated or not."""
        payloads = [{"findings": []}]

        assert has_blocking_finding(payloads) is False
        assert has_blocking_finding(payloads, escalate_advisory=True) is False

    def test_has_blocking_finding__escalates_advisory_when_the_caller_overrides(self):
        """The caller's override treats an advisory finding as blocking for one run."""
        payloads = [{"findings": [{"enforcement": CorpusEnforcement.ADVISORY}]}]

        assert has_blocking_finding(payloads, escalate_advisory=True) is True

    def test_has_blocking_finding__ignores_how_many_advisory_findings_there_are(self):
        """Piling up advisory findings never crosses into blocking."""
        payloads = [{"findings": [{"enforcement": CorpusEnforcement.ADVISORY}] * 50}]

        assert has_blocking_finding(payloads) is False


class TestFindingIdentity:
    """Tests for the version-independent identifier review output cites."""

    def test_review_as_dict__cites_entry_and_check_without_the_version(
        self, platform_requirement, make_entry_version
    ):
        """A check finding is identified by entry and check id, version reported apart."""
        make_entry_version(
            "STD-SEC-001",
            applies_to={"tags": ["platform"]},
            checks=[CONDITION_CHECK],
            version=4,
        )
        review = review_requirement(
            platform_requirement,
            current_snapshot(),
            ("STD-SEC-001@4",),
            "specs/platform/tenant_isolation.md",
        )

        finding = next(
            row for row in review_as_dict(review)["findings"] if row["check_id"] == "trigger-stated"
        )
        assert finding["finding_id"] == "STD-SEC-001#trigger-stated"
        assert finding["entry_version"] == 4

    def test_review_as_dict__gives_a_check_free_finding_the_entry_id_alone(
        self, platform_requirement, applicable_entry
    ):
        """An unaddressed obligation names no check, so the entry id is the identifier."""
        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        finding = review_as_dict(review)["findings"][0]
        assert finding["finding_type"] == "unaddressed_obligation"
        assert finding["finding_id"] == "STD-SEC-001"

    def test_review_as_dict__keeps_one_identifier_across_a_version_bump(
        self, platform_requirement, make_entry_version
    ):
        """Bumping the entry that raised a finding leaves the finding id unchanged."""
        make_entry_version(
            "STD-SEC-001", applies_to={"tags": ["platform"]}, checks=[CONDITION_CHECK], version=3
        )
        earlier = review_requirement(
            platform_requirement,
            current_snapshot(),
            ("STD-SEC-001@3",),
            "specs/platform/tenant_isolation.md",
        )
        make_entry_version(
            "STD-SEC-001", applies_to={"tags": ["platform"]}, checks=[CONDITION_CHECK], version=4
        )

        later = review_requirement(
            platform_requirement,
            current_snapshot(),
            ("STD-SEC-001@4",),
            "specs/platform/tenant_isolation.md",
        )

        earlier_finding = review_as_dict(earlier)["findings"][0]
        later_finding = review_as_dict(later)["findings"][0]
        assert earlier_finding["finding_id"] == later_finding["finding_id"]
        assert (earlier_finding["entry_version"], later_finding["entry_version"]) == (3, 4)


class TestCorpusReviewCommand:
    """Tests for the corpus_review management command."""

    def test_command__outputs_json_with_coverage_and_findings(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """--format json emits entry ids, versions, match reasons, and findings."""
        out = StringIO()

        call_command("corpus_review", str(spec_file()), "--format", "json", stdout=out)

        payload = json.loads(out.getvalue())
        review = payload["reviews"][0]
        assert review["requirement_id"] == "REQ-CORP-001"
        assert review["coverage"][0]["entry_id"] == "STD-SEC-001"
        assert review["coverage"][0]["matched_by"][0]["pattern"] == "platform"
        assert review["findings"][0]["finding_type"] == "unaddressed_obligation"
        assert payload["summary"] == {
            "requirements_reviewed": 1,
            "entries_surfaced": 1,
            "findings": 1,
        }

    def test_command__outputs_text_coverage_for_a_clean_review(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """Text output lists the surfaced entry even when nothing was found."""
        out = StringIO()

        call_command("corpus_review", str(spec_file("STD-SEC-001@1")), stdout=out)

        output = out.getvalue()
        assert "STD-SEC-001@1 [cited]" in output
        assert "No findings" in output

    def test_command__outputs_md_tables(self, platform_requirement, applicable_entry, spec_file):
        """--format md emits a coverage table and a findings table."""
        out = StringIO()

        call_command("corpus_review", str(spec_file()), "--format", "md", stdout=out)

        output = out.getvalue()
        assert "## 📋 SpecTrace Corpus Review" in output
        assert "| Entry | Version | Kind | Enforcement | Cited | Matched by |" in output
        assert "| STD-SEC-001 | 1 | standard | advisory | no |" in output
        assert "| Type | Finding | Version | Enforcement | Detail |" in output
        assert "| Unaddressed obligation | STD-SEC-001 | 1 | advisory |" in output

    def test_command__names_the_finding_by_entry_and_check_in_text_output(
        self, platform_requirement, make_entry_version, spec_file
    ):
        """Text output cites the stable identifier and reports the version beside it."""
        make_entry_version(
            "STD-SEC-001",
            applies_to={"tags": ["platform"]},
            checks=[CONDITION_CHECK],
            version=4,
        )
        out = StringIO()

        call_command("corpus_review", str(spec_file("STD-SEC-001@4")), stdout=out)

        assert "STD-SEC-001#trigger-stated (version 4)" in out.getvalue()

    def test_command__emits_the_finding_identifier_in_json(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """--format json carries finding_id alongside the version it was raised at."""
        out = StringIO()

        call_command("corpus_review", str(spec_file()), "--format", "json", stdout=out)

        finding = json.loads(out.getvalue())["reviews"][0]["findings"][0]
        assert finding["finding_id"] == "STD-SEC-001"
        assert finding["entry_version"] == 1

    def test_command__exits_nonzero_when_a_blocking_finding_exists(
        self, platform_requirement, blocking_entry, spec_file
    ):
        """A finding against an entry the owner marked blocking fails the run by default."""
        with pytest.raises(SystemExit) as exit_info:
            call_command("corpus_review", str(spec_file()), stdout=StringIO())

        assert exit_info.value.code == 1

    def test_command__exits_zero_when_only_advisory_findings_exist(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """An advisory finding reports and passes."""
        out = StringIO()

        call_command("corpus_review", str(spec_file()), stdout=out)

        assert "Unaddressed obligation" in out.getvalue()
        assert SpecReview.objects.get().outcome == SpecReviewOutcome.FINDINGS

    def test_command__strict_escalates_an_advisory_finding_to_blocking(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """--strict is a caller override that fails the run on advisory findings."""
        with pytest.raises(SystemExit) as exit_info:
            call_command("corpus_review", str(spec_file()), "--strict", stdout=StringIO())

        assert exit_info.value.code == 1

    def test_command__strict_exits_zero_for_a_clean_review(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """--strict passes a review with no findings."""
        call_command(
            "corpus_review", str(spec_file("STD-SEC-001@1")), "--strict", stdout=StringIO()
        )

        assert SpecReview.objects.get().outcome == SpecReviewOutcome.CLEAN

    def test_command__strict_leaves_the_recorded_posture_advisory(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """The override changes the exit code, never the audit record."""
        with pytest.raises(SystemExit):
            call_command("corpus_review", str(spec_file()), "--strict", stdout=StringIO())

        assert ReviewFinding.objects.get().enforcement == CorpusEnforcement.ADVISORY

    def test_command__reports_the_posture_in_text_output(
        self, platform_requirement, blocking_entry, spec_file
    ):
        """Text output names the posture on both the coverage row and the finding."""
        out = StringIO()

        with pytest.raises(SystemExit):
            call_command("corpus_review", str(spec_file()), stdout=out)

        output = out.getvalue()
        assert "STD-SEC-002@1 [not cited] [blocking]" in output
        assert "✗ [blocking] Unaddressed obligation: STD-SEC-002 (version 1)" in output

    def test_command__reports_the_posture_in_json_output(
        self, platform_requirement, blocking_entry, spec_file
    ):
        """--format json carries the posture on coverage rows and findings."""
        out = StringIO()

        with pytest.raises(SystemExit):
            call_command("corpus_review", str(spec_file()), "--format", "json", stdout=out)

        review = json.loads(out.getvalue())["reviews"][0]
        assert review["coverage"][0]["enforcement"] == "blocking"
        assert review["findings"][0]["enforcement"] == "blocking"

    def test_command__records_the_reviewer(self, platform_requirement, applicable_entry, spec_file):
        """--reviewer lands on the review row."""
        call_command("corpus_review", str(spec_file()), "--reviewer", "tommy", stdout=StringIO())

        assert SpecReview.objects.get().reviewer == "tommy"

    def test_command__raises_command_error_for_an_unknown_target(self, db):
        """An unresolvable target reports a clean CLI error."""
        with pytest.raises(CommandError, match="neither a readable spec file"):
            call_command("corpus_review", "REQ-NOT-HERE", stdout=StringIO())

    def test_command__raises_command_error_for_a_malformed_citation(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """A citation without a version reports a clean CLI error."""
        with pytest.raises(CommandError, match="ENTRY-ID@VERSION"):
            call_command("corpus_review", str(spec_file("STD-SEC-001")), stdout=StringIO())


class TestCorpusCoverageCommand:
    """Tests for the corpus_coverage management command."""

    def test_command__outputs_json_ledger(self, platform_requirement, applicable_entry, spec_file):
        """--format json reports each requirement's latest review."""
        call_command("corpus_review", str(spec_file()), stdout=StringIO())
        out = StringIO()

        call_command("corpus_coverage", "--format", "json", stdout=out)

        payload = json.loads(out.getvalue())
        assert payload["summary"] == {
            "requirements": 1,
            "reviewed": 1,
            "unreviewed": 0,
            "entries_surfaced": 1,
        }
        assert payload["requirements"][0]["unaddressed"] == ["STD-SEC-001@1"]

    def test_command__reports_unreviewed_requirements_in_text(
        self, platform_requirement, applicable_entry
    ):
        """Text output names requirements never put in front of a reviewer."""
        out = StringIO()

        call_command("corpus_coverage", stdout=out)

        assert "never reviewed against the corpus" in out.getvalue()

    def test_command__outputs_md_table(self, platform_requirement, applicable_entry, spec_file):
        """--format md emits one ledger row per requirement."""
        call_command("corpus_review", str(spec_file()), stdout=StringIO())
        out = StringIO()

        call_command("corpus_coverage", "--format", "md", stdout=out)

        output = out.getvalue()
        assert "## 📒 SpecTrace Corpus Coverage" in output
        assert "REQ-CORP-001" in output
        assert "STD-SEC-001@1" in output

    def test_command__filters_to_one_requirement(
        self, platform_requirement, applicable_entry, spec_file
    ):
        """--requirement narrows the ledger."""
        call_command("corpus_review", str(spec_file()), stdout=StringIO())
        out = StringIO()

        call_command(
            "corpus_coverage", "--requirement", "REQ-CORP-001", "--format", "json", stdout=out
        )

        payload = json.loads(out.getvalue())
        assert payload["summary"]["requirements"] == 1


@pytest.fixture
def admin_client(db):
    """An authenticated superuser client."""
    User.objects.create_superuser(username="admin", email="admin@test.com", password="adminpass")
    client = Client()
    client.login(username="admin", password="adminpass")
    return client


class TestCorpusAdmin:
    """Tests for the admin registration of corpus entries, versions, and reviews."""

    def test_admin__lists_corpus_entries_and_versions(self, admin_client, applicable_entry):
        """The entry changelist and the version changelist render."""
        entries = admin_client.get("/admin/requirements/corpusentry/")
        versions = admin_client.get("/admin/requirements/corpusentryversion/")

        assert entries.status_code == 200
        assert b"STD-SEC-001" in entries.content
        assert versions.status_code == 200
        assert b"STD-SEC-001@1" in versions.content

    def test_admin__shows_review_coverage_and_findings_inline(
        self, admin_client, platform_requirement, applicable_entry
    ):
        """The review change page renders its coverage and finding rows."""
        review = review_requirement(
            platform_requirement, current_snapshot(), (), "specs/platform/tenant_isolation.md"
        )

        response = admin_client.get(f"/admin/requirements/specreview/{review.pk}/change/")

        assert response.status_code == 200
        assert b"Review Coverage" in response.content
        assert b"Review Findings" in response.content
        assert b"unaddressed_obligation" in response.content
        assert b"tags=platform (REQ-CORP-001)" in response.content

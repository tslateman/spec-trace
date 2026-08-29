"""Tests for the scope-rule suggestion service and its command.

The containment tests are the load-bearing ones. A suggestion is a proposal, so
it must never reach a review record, a finding, a coverage row, or an exit code.
"""

import hashlib
import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from requirements.models import (
    CorpusEntry,
    CorpusEntryKind,
    CorpusEntryStatus,
    CorpusEntryVersion,
    CorpusSnapshot,
    Requirement,
    ReviewCoverage,
    ReviewFinding,
    SpecReview,
)
from requirements.services.corpus_parser import CorpusParser
from requirements.services.corpus_suggest import (
    SUGGESTION_NEAR_MISS,
    SUGGESTION_TEXT_SIMILARITY,
    live_entry_versions,
    suggest_scope_rules,
    value_affinity,
    widened_id_glob,
)

CORPUS_DIR = Path(__file__).resolve().parents[3] / "corpus"

GATEWAY_PROSE = (
    "Every gateway route resolves its upstream service from the routing table "
    "and rejects an unresolved upstream with a 502 rather than a timeout."
)

SPEC_BODY = """---
id: REQ-GTW-001
title: Gateway route resolution
tags: [gateway]
status: active
---

{prose}
"""


@pytest.fixture
def make_entry_version(db):
    """Factory creating one CorpusEntryVersion with given scope rules and body."""

    def _make(
        entry_id: str,
        applies_to: dict | None = None,
        body: str = "",
        version: int = 1,
        status: str = CorpusEntryStatus.ACTIVE,
        supersedes: CorpusEntryVersion | None = None,
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
        return CorpusEntryVersion.objects.create(
            entry=entry,
            version=version,
            body=body or f"Body of {entry_id} at {version}.",
            content_hash=hashlib.sha256(f"{entry_id}@{version}".encode()).hexdigest(),
            applies_to=applies_to or {},
            checks=[],
            supersedes=supersedes,
            source_file=f"corpus/{entry_id.lower()}.md",
        )

    return _make


@pytest.fixture
def gateway_spec(tmp_path):
    """A spec file on disk for the gateway requirement."""
    path = tmp_path / "routing.md"
    path.write_text(SPEC_BODY.format(prose=GATEWAY_PROSE))
    return path


@pytest.fixture
def gateway_requirement(db, gateway_spec):
    """A requirement whose component is `api-gateway`, one segment off `api`."""
    return Requirement.add_root(
        external_id="REQ-GTW-001",
        title="Gateway route resolution",
        description=GATEWAY_PROSE,
        status="active",
        source_file=str(gateway_spec),
        tags=["gateway"],
        component="api-gateway",
        risk_level="critical",
        verification_method="test",
    )


@pytest.fixture
def seed_tenant_isolation(db):
    """The real STD-SEC-001 entry, imported from `corpus/security/`.

    Its `applies_to.components` is `[api, storage]`, which is the near miss the
    gateway requirement exercises.
    """
    CorpusParser().import_to_database(CORPUS_DIR / "security")
    return CorpusEntryVersion.objects.get(entry__external_id="STD-SEC-001")


class TestValueAffinity:
    """Tests for value_affinity, the near-miss score for exact-matched keys."""

    def test_value_affinity__scores_shared_segments_when_one_value_extends_the_other(self):
        """`api` against `api-gateway` is the near miss the matcher cannot see."""
        assert value_affinity("api", "api-gateway") == pytest.approx(0.5)

    def test_value_affinity__scores_a_plural_spelling_difference(self):
        """`workspaces` against `workspace` is one character off, not a new concept."""
        assert value_affinity("workspaces", "workspace") > 0.9

    def test_value_affinity__returns_zero_for_coincidental_character_overlap(self):
        """`compliance` and `collaboration` share letters and nothing else."""
        assert value_affinity("compliance", "collaboration") == 0.0

    def test_value_affinity__returns_zero_when_the_values_are_identical(self):
        """An exact match is the matcher's job, never a suggestion."""
        assert value_affinity("storage", "storage") == 0.0

    def test_value_affinity__returns_zero_when_the_requirement_value_is_empty(self):
        """A requirement with no component near-misses nothing."""
        assert value_affinity("api", "") == 0.0


class TestWidenedIdGlob:
    """Tests for widened_id_glob, the requirement_ids near-miss rule."""

    def test_widened_id_glob__widens_the_trailing_id_within_one_family(self):
        """A pinned id in the right family widens to cover the family."""
        assert widened_id_glob("REQ-PLAT-002", "REQ-PLAT-001") == (
            "REQ-PLAT-*",
            pytest.approx(2 / 3),
        )

    def test_widened_id_glob__returns_none_when_the_family_segment_differs(self):
        """`REQ-IAM-001` against `REQ-BILL-001` names a different family."""
        assert widened_id_glob("REQ-IAM-001", "REQ-BILL-001") is None

    def test_widened_id_glob__returns_none_when_the_pattern_already_globs_the_tail(self):
        """A pattern that failed to match despite globbing is not a near miss."""
        assert widened_id_glob("REQ-PLAT-*", "REQ-PLAT-001") is None

    def test_widened_id_glob__returns_none_when_segment_counts_differ(self):
        """Different segment counts describe different id schemes."""
        assert widened_id_glob("REQ-PLAT-002", "REQ-PLAT-SUB-001") is None


class TestNearMissRanking:
    """Tests that near-miss scope rules outrank text similarity."""

    def test_suggest_scope_rules__proposes_the_component_widening_for_a_seed_corpus_near_miss(
        self, gateway_requirement, seed_tenant_isolation
    ):
        """STD-SEC-001 scopes `components: [api]` and misses `api-gateway`."""
        suggestions = suggest_scope_rules()

        near_misses = [item for item in suggestions if item.entry_id == "STD-SEC-001"]
        assert len(near_misses) == 1

        suggestion = near_misses[0]
        assert suggestion.kind == SUGGESTION_NEAR_MISS
        assert suggestion.scope_key == "components"
        assert suggestion.existing_pattern == "api"
        assert suggestion.proposed_pattern == "api-gateway"
        assert suggestion.proposed_edit == "applies_to.components: [api-gateway]"
        assert suggestion.requirement_id == "REQ-GTW-001"
        assert suggestion.entry_version == seed_tenant_isolation.version

    def test_suggest_scope_rules__ranks_a_near_miss_above_a_higher_scoring_text_match(
        self, gateway_requirement, make_entry_version
    ):
        """A near miss is evidence of intent, so it leads however the cosine falls."""
        make_entry_version("STD-NEAR-001", applies_to={"components": ["api"]})
        make_entry_version(
            "STD-TEXT-001",
            applies_to={"components": ["billing"]},
            body=GATEWAY_PROSE,
        )

        suggestions = suggest_scope_rules()

        assert [item.entry_id for item in suggestions] == ["STD-NEAR-001", "STD-TEXT-001"]
        assert suggestions[0].kind == SUGGESTION_NEAR_MISS
        assert suggestions[1].kind == SUGGESTION_TEXT_SIMILARITY
        assert suggestions[1].score > suggestions[0].score

    def test_suggest_scope_rules__proposes_the_requirement_id_for_a_text_match(
        self, gateway_requirement, make_entry_version
    ):
        """Prose overlap says nothing about which axis to scope by, so it pins the id."""
        make_entry_version(
            "STD-TEXT-001", applies_to={"components": ["billing"]}, body=GATEWAY_PROSE
        )

        suggestion = suggest_scope_rules()[0]

        assert suggestion.kind == SUGGESTION_TEXT_SIMILARITY
        assert suggestion.scope_key == "requirement_ids"
        assert suggestion.proposed_pattern == "REQ-GTW-001"
        assert suggestion.existing_pattern == ""

    def test_suggest_scope_rules__reports_a_near_miss_instead_of_a_text_score_for_one_pair(
        self, gateway_requirement, make_entry_version
    ):
        """One entry yields one reason to widen, the strongest one."""
        make_entry_version("STD-BOTH-001", applies_to={"components": ["api"]}, body=GATEWAY_PROSE)

        kinds = [item.kind for item in suggest_scope_rules()]

        assert kinds == [SUGGESTION_NEAR_MISS]


class TestSuggestionScope:
    """Tests for which pairs and which entry versions produce suggestions."""

    def test_suggest_scope_rules__suggests_nothing_when_the_matcher_already_binds(
        self, gateway_requirement, make_entry_version
    ):
        """A bound entry has no gap to close."""
        make_entry_version(
            "STD-BOUND-001", applies_to={"components": ["api-gateway"]}, body=GATEWAY_PROSE
        )

        assert suggest_scope_rules() == []

    def test_suggest_scope_rules__skips_a_retired_entry(
        self, gateway_requirement, make_entry_version
    ):
        """Widening a retired entry would bind a spec to a dead obligation."""
        make_entry_version(
            "STD-DEAD-001",
            applies_to={"components": ["api"]},
            status=CorpusEntryStatus.RETIRED,
        )

        assert suggest_scope_rules() == []

    def test_suggest_scope_rules__skips_a_superseded_version(
        self, gateway_requirement, make_entry_version
    ):
        """Only the version a reader would edit is worth a proposal."""
        old = make_entry_version("STD-OLD-001", applies_to={"components": ["api"]}, version=1)
        make_entry_version("STD-NEW-001", applies_to={"tags": ["unrelated"]}, supersedes=old)

        assert [item.entry.external_id for item in live_entry_versions()] == ["STD-NEW-001"]
        assert suggest_scope_rules() == []

    def test_suggest_scope_rules__limits_the_report_to_one_requirement(
        self, gateway_requirement, make_entry_version
    ):
        """The requirement filter narrows the report without changing its content."""
        Requirement.add_root(
            external_id="REQ-OTHER-001",
            title="Other",
            status="active",
            source_file="specs/other.md",
            component="api-proxy",
        )
        make_entry_version("STD-NEAR-001", applies_to={"components": ["api"]})

        assert len(suggest_scope_rules()) == 2
        assert [item.requirement_id for item in suggest_scope_rules("REQ-GTW-001")] == [
            "REQ-GTW-001"
        ]

    def test_suggest_scope_rules__scores_a_filtered_requirement_the_same_as_the_full_run(
        self, gateway_requirement, make_entry_version
    ):
        """The filter narrows the report without moving any score.

        IDF spans the whole corpus either way, so a per-spec report reads the
        same as the row it would occupy in the full run.
        """
        Requirement.add_root(
            external_id="REQ-OTHER-001",
            title="Other",
            description="Billing invoices and credit notes across the metering pipeline.",
            status="active",
            source_file="specs/other.md",
            component="ledger",
        )
        make_entry_version(
            "STD-TEXT-001", applies_to={"components": ["billing"]}, body=GATEWAY_PROSE
        )

        full = [item for item in suggest_scope_rules() if item.requirement_id == "REQ-GTW-001"]
        filtered = suggest_scope_rules("REQ-GTW-001")

        assert filtered == full
        assert filtered[0].score > 0

    def test_suggest_scope_rules__drops_a_text_match_below_the_score_floor(
        self, gateway_requirement, make_entry_version
    ):
        """The cosine floor governs text similarity and nothing else."""
        make_entry_version(
            "STD-TEXT-001", applies_to={"components": ["billing"]}, body=GATEWAY_PROSE
        )

        assert suggest_scope_rules(min_score=0.99) == []
        assert len(suggest_scope_rules(min_score=0.01)) == 1


class TestContainment:
    """Tests that a suggestion never reaches a record, a finding, or an exit code."""

    def test_suggest_scope_rules__writes_no_row_of_any_kind(
        self, gateway_requirement, make_entry_version
    ):
        """The service reads. It does not write, not even a snapshot."""
        make_entry_version("STD-NEAR-001", applies_to={"components": ["api"]})

        assert len(suggest_scope_rules()) == 1
        assert SpecReview.objects.count() == 0
        assert ReviewCoverage.objects.count() == 0
        assert ReviewFinding.objects.count() == 0
        assert CorpusSnapshot.objects.count() == 0

    def test_suggest_scope_rules__suggested_pair_is_absent_from_corpus_review_output(
        self, gateway_requirement, seed_tenant_isolation, gateway_spec
    ):
        """The pair corpus suggest proposes gets no coverage row and no finding."""
        suggestion = next(item for item in suggest_scope_rules() if item.entry_id == "STD-SEC-001")
        assert suggestion.requirement_id == "REQ-GTW-001"

        stdout = StringIO()
        call_command("corpus_review", str(gateway_spec), format="json", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        review = payload["reviews"][0]
        assert review["requirement_id"] == "REQ-GTW-001"
        assert [row["entry_id"] for row in review["coverage"]] == []
        assert [finding["entry_id"] for finding in review["findings"]] == []
        assert "STD-SEC-001" not in stdout.getvalue()

        assert not ReviewCoverage.objects.filter(
            entry_version__entry__external_id="STD-SEC-001"
        ).exists()
        assert not ReviewFinding.objects.filter(
            entry_version__entry__external_id="STD-SEC-001"
        ).exists()

    def test_review_target__surfaces_only_the_entry_whose_scope_rule_was_widened(
        self, gateway_requirement, make_entry_version, gateway_spec
    ):
        """The suggested entry stays out of the review; an accepted rule gets in.

        Without this control, the empty coverage above would prove only that the
        review path found nothing for this requirement at all.
        """
        make_entry_version("STD-SUGGESTED-001", applies_to={"components": ["api"]})
        make_entry_version("STD-ACCEPTED-001", applies_to={"components": ["api-gateway"]})

        assert [item.entry_id for item in suggest_scope_rules()] == ["STD-SUGGESTED-001"]

        stdout = StringIO()
        call_command("corpus_review", str(gateway_spec), format="json", stdout=stdout)
        coverage = json.loads(stdout.getvalue())["reviews"][0]["coverage"]

        assert [row["entry_id"] for row in coverage] == ["STD-ACCEPTED-001"]

    def test_handle__exits_zero_when_suggestions_exist(
        self, gateway_requirement, make_entry_version
    ):
        """No suggestion count fails the command."""
        make_entry_version("STD-NEAR-001", applies_to={"components": ["api"]})
        make_entry_version("STD-NEAR-002", applies_to={"components": ["api"]})

        stdout = StringIO()
        call_command("corpus_suggest", format="json", stdout=stdout)

        assert json.loads(stdout.getvalue())["summary"]["suggestions"] == 2


class TestCorpusSuggestCommand:
    """Tests for the corpus_suggest management command output."""

    def test_handle__names_the_applies_to_edit_and_the_motivating_spec(
        self, gateway_requirement, make_entry_version
    ):
        """Text output is a curation report a human acts on."""
        make_entry_version("STD-NEAR-001", applies_to={"components": ["api"]})

        stdout = StringIO()
        call_command("corpus_suggest", format="text", stdout=stdout)
        output = stdout.getvalue()

        assert "Near-miss scope rule: STD-NEAR-001@1" in output
        assert "motivated by REQ-GTW-001" in output
        assert "add applies_to.components: [api-gateway]" in output
        assert "widens 'api'" in output
        assert "Nothing here is a review finding." in output

    def test_handle__emits_suggestions_and_a_kind_summary_as_json(
        self, gateway_requirement, make_entry_version
    ):
        """JSON output splits the summary by suggestion kind."""
        make_entry_version("STD-NEAR-001", applies_to={"components": ["api"]})
        make_entry_version(
            "STD-TEXT-001", applies_to={"components": ["billing"]}, body=GATEWAY_PROSE
        )

        stdout = StringIO()
        call_command("corpus_suggest", format="json", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        assert payload["summary"] == {
            "suggestions": 2,
            "near_misses": 1,
            "text_similarity": 1,
        }
        assert payload["suggestions"][0]["proposed_edit"] == "applies_to.components: [api-gateway]"
        assert payload["suggestions"][1]["scope_key"] == "requirement_ids"

    def test_handle__renders_a_markdown_table(self, gateway_requirement, make_entry_version):
        """Markdown output is a table a reviewer can paste into a PR."""
        make_entry_version("STD-NEAR-001", applies_to={"components": ["api"]})

        stdout = StringIO()
        call_command("corpus_suggest", format="md", stdout=stdout)
        output = stdout.getvalue()

        assert "## 🔎 SpecTrace Corpus Scope Suggestions" in output
        assert "No suggestion is a review finding." in output
        assert "`applies_to.components: [api-gateway]`" in output

    def test_handle__reports_a_clean_corpus_when_no_gap_is_open(
        self, gateway_requirement, make_entry_version
    ):
        """A well-scoped corpus produces an empty report, not a warning."""
        make_entry_version("STD-BOUND-001", applies_to={"components": ["api-gateway"]})

        stdout = StringIO()
        call_command("corpus_suggest", format="text", stdout=stdout)

        assert stdout.getvalue().strip() == "No scope-rule suggestions"

    def test_handle__limits_the_report_to_one_requirement(
        self, gateway_requirement, make_entry_version
    ):
        """The --requirement option narrows the report."""
        Requirement.add_root(
            external_id="REQ-OTHER-001",
            title="Other",
            status="active",
            source_file="specs/other.md",
            component="api-proxy",
        )
        make_entry_version("STD-NEAR-001", applies_to={"components": ["api"]})

        stdout = StringIO()
        call_command("corpus_suggest", requirement="REQ-GTW-001", format="json", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        assert [row["requirement_id"] for row in payload["suggestions"]] == ["REQ-GTW-001"]

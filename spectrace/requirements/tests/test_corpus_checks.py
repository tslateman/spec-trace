"""Tests for the corpus check evaluator and the five finding types."""

from pathlib import Path

import pytest

from requirements.constants import (
    FINDING_CONFLICTING_OBLIGATIONS,
    FINDING_ORPHAN_CITATION,
    FINDING_STALE_CITATION,
    FINDING_UNADDRESSED_OBLIGATION,
    FINDING_UNMET_CHECK,
)
from requirements.models import CorpusEntry, FindingType, Requirement
from requirements.services.corpus_checks import (
    ApplicableVersion,
    Citation,
    CitationFormatError,
    RequirementFacts,
    evaluate,
    evaluate_check,
    parse_citations,
    review_findings,
)
from requirements.services.corpus_parser import CorpusParser, parse_check_assertion

CORPUS_DIR = Path(__file__).resolve().parents[3] / "corpus"


@pytest.fixture
def seed_corpus(db):
    """Import the git-tracked seed corpus and return its versions by ENTRY-ID@N."""
    CorpusParser().import_to_database(CORPUS_DIR)
    return {
        f"{version.entry.external_id}@{version.version}": version
        for entry in CorpusEntry.objects.all()
        for version in entry.versions.all()
    }


@pytest.fixture
def billing_requirement(db):
    """A billing requirement the seed billing entries bind to."""
    return Requirement.add_root(
        external_id="REQ-BILL-002",
        title="Metered usage rollup",
        status="active",
        source_file="specs/billing/metering.md",
        tags=["billing", "finance"],
        risk_level="critical",
        verification_method="test",
        component="metering",
    )


def _applicable(entry_id, version, asserts=(), superseded_by=()):
    checks = [
        {"id": check_id, "assert": text, **parse_check_assertion(text, entry_id, check_id)}
        for check_id, text in asserts
    ]
    return ApplicableVersion(
        entry_id=entry_id,
        version=version,
        checks=tuple(checks),
        superseded_by=tuple(superseded_by),
    )


def _facts(**overrides):
    values = {
        "risk_level": "critical",
        "verification_method": "test",
        "verification_status": "passing",
        "slo_status": "met",
        "priority": "high",
        "status": "active",
        "component": "metering",
        "timing": "within 2 seconds",
        "scope": "",
        "condition": "",
        "response": "",
        "tags": ("billing", "finance"),
        "depends_on": (),
    }
    values.update(overrides)
    return RequirementFacts(external_id="REQ-BILL-002", fields=values)


def test_parse_citations__reads_entry_id_and_version():
    assert parse_citations(["STD-SEC-001@3", "DEC-BILL-002@1"]) == (
        Citation("STD-SEC-001", 3),
        Citation("DEC-BILL-002", 1),
    )


def test_parse_citations__rejects_a_citation_without_a_version():
    with pytest.raises(CitationFormatError, match="ENTRY-ID@VERSION"):
        parse_citations(["STD-SEC-001"])


def test_finding_type_constants__match_the_model_choices():
    assert {
        FINDING_UNADDRESSED_OBLIGATION,
        FINDING_STALE_CITATION,
        FINDING_ORPHAN_CITATION,
        FINDING_UNMET_CHECK,
        FINDING_CONFLICTING_OBLIGATIONS,
    } == set(FindingType.values)


def test_evaluate__reports_unaddressed_obligation_when_an_applicable_entry_is_uncited():
    applicable = [_applicable("STD-SEC-001", 3, [("risk-classified", "risk_level in [critical]")])]

    findings = evaluate(_facts(), applicable, ())

    assert [(f.finding_type, f.entry_id, f.entry_version) for f in findings] == [
        (FINDING_UNADDRESSED_OBLIGATION, "STD-SEC-001", 3)
    ]
    assert "does not cite it" in findings[0].detail


def test_evaluate__reports_stale_citation_when_a_newer_version_applies():
    applicable = [_applicable("STD-SEC-001", 3)]

    findings = evaluate(_facts(), applicable, parse_citations(["STD-SEC-001@2"]))

    assert [f.finding_type for f in findings] == [FINDING_STALE_CITATION]
    assert findings[0].entry_id == "STD-SEC-001"
    assert findings[0].entry_version == 3
    assert "spec cites STD-SEC-001@2" in findings[0].detail


def test_review_findings__reports_stale_citation_for_the_seeded_supersession_chain(
    seed_corpus, billing_requirement
):
    superseded = seed_corpus["DEC-BILL-001@1"]
    successor = seed_corpus["DEC-BILL-002@1"]

    findings = review_findings(
        billing_requirement,
        [superseded, successor],
        ["DEC-BILL-001@1", "DEC-BILL-002@1"],
    )

    stale = [f for f in findings if f.finding_type == FINDING_STALE_CITATION]
    assert len(stale) == 1
    assert stale[0].entry_id == "DEC-BILL-001"
    assert stale[0].entry_version == 1
    assert stale[0].entry_version_pk == superseded.pk
    assert "DEC-BILL-002@1 supersedes" in stale[0].detail


def test_evaluate__reports_orphan_citation_when_the_cited_entry_does_not_apply():
    applicable = [_applicable("DEC-BILL-002", 1)]

    findings = evaluate(_facts(), applicable, parse_citations(["DEC-BILL-002@1", "DEC-IAM-001@2"]))

    assert [(f.finding_type, f.entry_id, f.entry_version) for f in findings] == [
        (FINDING_ORPHAN_CITATION, "DEC-IAM-001", 2)
    ]
    assert findings[0].entry_version_pk is None
    assert "does not apply to REQ-BILL-002" in findings[0].detail


def test_evaluate__reports_unmet_check_naming_the_check_id():
    applicable = [
        _applicable(
            "DEC-BILL-002",
            1,
            [
                ("risk-classified", "risk_level in [critical, high]"),
                ("no-batch-dependency", "component != metering"),
            ],
        )
    ]

    findings = evaluate(_facts(), applicable, parse_citations(["DEC-BILL-002@1"]))

    assert [(f.finding_type, f.check_id) for f in findings] == [
        (FINDING_UNMET_CHECK, "no-batch-dependency")
    ]
    assert findings[0].entry_id == "DEC-BILL-002"
    assert findings[0].entry_version == 1
    assert "component='metering'" in findings[0].detail


def test_evaluate__reports_conflicting_obligations_for_contradictory_predicates():
    applicable = [
        _applicable("DEC-BILL-002", 1, [("owner-named", "component is set")]),
        _applicable("STD-SEC-001", 3, [("no-owner", "component is not set")]),
    ]

    findings = evaluate(_facts(), applicable, parse_citations(["DEC-BILL-002@1", "STD-SEC-001@3"]))

    conflicts = [f for f in findings if f.finding_type == FINDING_CONFLICTING_OBLIGATIONS]
    assert len(conflicts) == 1
    assert conflicts[0].entry_id == "DEC-BILL-002"
    assert conflicts[0].entry_version == 1
    assert conflicts[0].check_id == "owner-named"
    assert "STD-SEC-001@3 check 'no-owner'" in conflicts[0].detail


def test_evaluate__reports_conflicting_obligations_for_disjoint_allowed_sets():
    applicable = [
        _applicable("DEC-BILL-002", 1, [("tested", "verification_method in [test, both]")]),
        _applicable("STD-SEC-001", 3, [("inspected", "verification_method == inspection")]),
    ]

    findings = evaluate(_facts(), applicable, parse_citations(["DEC-BILL-002@1", "STD-SEC-001@3"]))

    assert [f.check_id for f in findings if f.finding_type == FINDING_CONFLICTING_OBLIGATIONS] == [
        "tested"
    ]


def test_evaluate__leaves_narrowing_predicates_alone():
    applicable = [
        _applicable("DEC-BILL-002", 1, [("broad", "risk_level in [critical, high, medium]")]),
        _applicable("STD-SEC-001", 3, [("narrow", "risk_level in [critical]")]),
    ]

    findings = evaluate(_facts(), applicable, parse_citations(["DEC-BILL-002@1", "STD-SEC-001@3"]))

    assert findings == []


def test_evaluate__returns_nothing_when_every_applicable_entry_is_cited_and_passes():
    applicable = [
        _applicable(
            "DEC-BILL-002",
            1,
            [
                ("risk-classified", "risk_level in [critical, high]"),
                ("metering-tested", "verification_method in [test, both]"),
                ("no-batch-dependency", "component != nightly_batch"),
            ],
        )
    ]

    assert evaluate(_facts(), applicable, parse_citations(["DEC-BILL-002@1"])) == []


def test_evaluate__runs_without_touching_the_database(
    seed_corpus, billing_requirement, django_assert_num_queries
):
    facts = RequirementFacts.from_requirement(billing_requirement)
    applicable = [
        ApplicableVersion.from_entry_version(seed_corpus["DEC-BILL-001@1"]),
        ApplicableVersion.from_entry_version(seed_corpus["DEC-BILL-002@1"]),
    ]
    citations = parse_citations(["DEC-BILL-001@1"])

    with django_assert_num_queries(0):
        findings = evaluate(facts, applicable, citations)

    assert {f.finding_type for f in findings} == {
        FINDING_STALE_CITATION,
        FINDING_UNADDRESSED_OBLIGATION,
    }


@pytest.mark.parametrize(
    ("assertion", "expected"),
    [
        ("risk_level in [critical, high]", True),
        ("risk_level in [low]", False),
        ("risk_level not in [low]", True),
        ("component == metering", True),
        ("component != metering", False),
        ("timing is set", True),
        ("scope is set", False),
        ("scope is not set", True),
        ("component contains meter", True),
        ("component not contains meter", False),
        ("tags in [finance, platform]", True),
        ("tags in [platform]", False),
        ("tags contains billing", True),
        ("depends_on is not set", True),
    ],
)
def test_evaluate_check__reads_the_parsed_predicate_structure(assertion, expected):
    check = parse_check_assertion(assertion, "STD-TEST-001", "grammar")

    assert evaluate_check(check, _facts()) is expected

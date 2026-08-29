"""Review runner: composes the matcher and the evaluator into an audit record.

One review answers two questions and records both. Which corpus entry versions
bound to this spec at this corpus snapshot — that is the coverage ledger — and
which of them the deterministic rules faulted — that is the finding list.

The coverage ledger is the load-bearing half. `ReviewCoverage` gets a row for
every applicable entry version, including the ones that produced no finding. A
row is the claim that the obligation was put in front of the reviewer at that
version on that date; a review that recorded only problems would prove nothing
about what was covered. Each row carries the matcher's structured reasons in
`matched_by`, so the record holds why the entry bound, not just that it did.

Nothing here decides anything. Applicability comes from `corpus_matcher`,
findings come from `corpus_checks`, and this module writes down what they said.
Enforcement posture is no exception: it is read off the entry version the owner
authored and copied onto every coverage row and finding, so a review record
still says what blocked on the day it ran after the owner changes their mind.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import frontmatter
from django.db import transaction

from requirements.constants import FINDING_UNADDRESSED_OBLIGATION
from requirements.models import (
    CorpusEnforcement,
    CorpusEntryVersion,
    CorpusSnapshot,
    Requirement,
    ReviewCoverage,
    ReviewFinding,
    SpecReview,
    SpecReviewOutcome,
)
from requirements.parser import SpecParser
from requirements.services.corpus_checks import (
    Citation,
    finding_identifier,
    parse_citations,
    review_findings,
)
from requirements.services.corpus_matcher import resolve_applicable_entries


class ReviewTargetError(ValueError):
    """A review target names no spec file and no known requirement."""


class UnknownCitationError(ValueError):
    """A `complies_with` citation names an entry version the corpus does not hold."""


@dataclass(frozen=True)
class ReviewTarget:
    """The spec file under review and the requirements parsed from it."""

    spec_file: str
    requirements: tuple[Requirement, ...]
    citations: tuple[str, ...]


def current_snapshot() -> CorpusSnapshot:
    """The snapshot of every stored entry version, created on first use.

    Superseded and retired members stay in the snapshot; the matcher decides
    which of them still apply. Keeping them makes the snapshot a faithful record
    of the corpus as it stood.
    """
    return CorpusSnapshot.capture(CorpusEntryVersion.objects.select_related("entry"))


def read_citations(spec_path: Path) -> tuple[str, ...]:
    """The raw `complies_with` list from a spec file's frontmatter."""
    return tuple(
        str(value) for value in frontmatter.load(spec_path).metadata.get("complies_with", [])
    )


def assert_citations_within_corpus(citations: Sequence[Citation]) -> None:
    """Raise UnknownCitationError for a citation naming a version the corpus outranks.

    Citing an unknown entry already aborts the review, and citing a version
    above every version that entry holds is the same authoring mistake: nothing
    downstream can fault it. The citation rules fault a citation for naming an
    older version than the one that applies and never for naming a newer one, so
    `STD-SEC-001@9` where the corpus holds 3 and 4 passes unexamined and the
    obligation reads as met.

    A cited version at or below the newest is left alone even when no row holds
    it. That citation is not silently accepted — it produces `stale_citation`
    naming the version that applies — and a corpus file bumped in place keeps no
    row for the version it replaced, so `specs/platform/tenant_isolation.md`
    citing `STD-SEC-001@3` is the ordinary stale case rather than a typo.

    The message names the entry, the cited version, and the versions the corpus
    holds, which is what an author fixing the digit needs.
    """
    stored: dict[str, set[int]] = {}
    for entry_id, version in CorpusEntryVersion.objects.filter(
        entry__external_id__in={citation.entry_id for citation in citations}
    ).values_list("entry__external_id", "version"):
        stored.setdefault(entry_id, set()).add(version)

    for citation in citations:
        held = stored.get(citation.entry_id, set())
        if held and citation.version <= max(held):
            continue
        rendered = f"versions {', '.join(str(version) for version in sorted(held))}"
        raise UnknownCitationError(
            f"spec cites {citation}, which the corpus does not contain; "
            f"{citation.entry_id} holds {rendered if held else 'no versions'}"
        )


def resolve_target(target: str) -> ReviewTarget:
    """Resolve a spec path or a requirement external id into a review target.

    A path is parsed with the spec parser, so single-requirement and
    multi-requirement files both resolve. A requirement id resolves through its
    stored `source_file`, which must still exist: citations live in the file.
    """
    path = Path(target)
    if path.is_file():
        external_ids = [parsed["external_id"] for parsed in SpecParser().parse_file(path)]
        requirements = _requirements_by_id(external_ids, target)
        return ReviewTarget(str(path), requirements, read_citations(path))

    requirement = Requirement.objects.filter(external_id=target).first()
    if requirement is None:
        raise ReviewTargetError(
            f"'{target}' is neither a readable spec file nor a known requirement id"
        )
    spec_path = Path(requirement.source_file)
    if not spec_path.is_file():
        raise ReviewTargetError(
            f"{requirement.external_id} points at spec file '{requirement.source_file}', "
            f"which does not exist"
        )
    return ReviewTarget(str(spec_path), (requirement,), read_citations(spec_path))


@transaction.atomic
def review_requirement(
    requirement: Requirement,
    snapshot: CorpusSnapshot,
    citations: tuple[str, ...],
    spec_file: str,
    reviewer: str = "",
) -> SpecReview:
    """Run one requirement against one snapshot and persist the whole outcome.

    Every citation is checked against the corpus before anything is evaluated,
    so a citation naming a version above the newest one raises
    UnknownCitationError instead of reading as a satisfied obligation.

    Writes one SpecReview, one ReviewCoverage row per applicable entry version,
    and one ReviewFinding per rule outcome.
    """
    parsed_citations = parse_citations(citations)
    assert_citations_within_corpus(parsed_citations)

    applicable = resolve_applicable_entries(requirement, snapshot)
    findings = review_findings(requirement, [item.entry_version for item in applicable], citations)
    cited_entry_ids = {citation.entry_id for citation in parsed_citations}

    review = SpecReview.objects.create(
        requirement=requirement,
        snapshot=snapshot,
        spec_file=spec_file,
        reviewer=reviewer,
        outcome=SpecReviewOutcome.FINDINGS if findings else SpecReviewOutcome.CLEAN,
    )

    ReviewCoverage.objects.bulk_create(
        [
            ReviewCoverage(
                review=review,
                entry_version=item.entry_version,
                matched_by=item.reasons_as_dicts(),
                cited=item.entry_id in cited_entry_ids,
                enforcement=item.entry_version.enforcement,
            )
            for item in applicable
        ]
    )

    versions_by_pk = {item.entry_version.pk: item.entry_version for item in applicable}
    finding_rows = []
    for finding in findings:
        entry_version = _finding_entry_version(finding, versions_by_pk)
        finding_rows.append(
            ReviewFinding(
                review=review,
                entry_version=entry_version,
                finding_type=finding.finding_type,
                check_id=finding.check_id,
                detail=finding.detail,
                enforcement=entry_version.enforcement,
            )
        )
    ReviewFinding.objects.bulk_create(finding_rows)
    return review


@transaction.atomic
def review_target(target: str, reviewer: str = "") -> list[SpecReview]:
    """Review every requirement in a spec file against the current snapshot.

    Atomic across the file: a spec whose citations fail on any one of its
    requirements records no review at all, rather than half a ledger.
    """
    resolved = resolve_target(target)
    snapshot = current_snapshot()
    return [
        review_requirement(requirement, snapshot, resolved.citations, resolved.spec_file, reviewer)
        for requirement in resolved.requirements
    ]


def review_as_dict(review: SpecReview) -> dict:
    """Serializable form of one persisted review, ordered for stable output.

    Each finding carries `finding_id`, the version-independent identifier, and
    reports `entry_version` as a separate field.
    """
    coverage = review.coverage.select_related("entry_version__entry").order_by(
        "entry_version__entry__external_id", "entry_version__version"
    )
    findings = review.findings.select_related("entry_version__entry").order_by(
        "entry_version__entry__external_id",
        "entry_version__version",
        "finding_type",
        "check_id",
    )
    return {
        "requirement_id": review.requirement.external_id,
        "spec_file": review.spec_file,
        "reviewer": review.reviewer,
        "outcome": review.outcome,
        "snapshot_hash": review.snapshot.snapshot_hash,
        "reviewed_at": review.created_at.isoformat(),
        "coverage": [
            {
                "entry_id": row.entry_version.entry.external_id,
                "entry_version": row.entry_version.version,
                "title": row.entry_version.entry.title,
                "kind": row.entry_version.entry.kind,
                "cited": row.cited,
                "matched_by": row.matched_by,
                "enforcement": row.enforcement,
            }
            for row in coverage
        ],
        "findings": [
            {
                "finding_type": finding.finding_type,
                "finding_id": finding_identifier(
                    finding.entry_version.entry.external_id, finding.check_id
                ),
                "entry_id": finding.entry_version.entry.external_id,
                "entry_version": finding.entry_version.version,
                "check_id": finding.check_id,
                "detail": finding.detail,
                "enforcement": finding.enforcement,
            }
            for finding in findings
        ],
    }


def has_blocking_finding(payloads: Sequence[dict], escalate_advisory: bool = False) -> bool:
    """Whether the reviewed specs hold a finding that blocks.

    A finding blocks when the standard's owner marked that entry version
    `enforcement: blocking`. `escalate_advisory` is the caller's `--strict`
    override, which treats every finding as blocking for one run and is recorded
    nowhere. Nothing here reads how many findings there are or what type they
    have.
    """
    return any(
        escalate_advisory or finding["enforcement"] == CorpusEnforcement.BLOCKING
        for payload in payloads
        for finding in payload["findings"]
    )


def coverage_as_dicts(requirement_id: str = "") -> list[dict]:
    """The audit view: for each requirement, its latest review and what it surfaced.

    A requirement with no review reports `reviewed: false` and empty coverage.
    Never having been reviewed is itself the audit answer.
    """
    requirements = Requirement.objects.all().order_by("external_id")
    if requirement_id:
        requirements = requirements.filter(external_id=requirement_id)

    rows = []
    for requirement in requirements:
        review = requirement.corpus_reviews.select_related("snapshot").first()
        if review is None:
            rows.append(
                {
                    "requirement_id": requirement.external_id,
                    "spec_file": requirement.source_file,
                    "reviewed": False,
                    "entries_surfaced": 0,
                    "coverage": [],
                    "unaddressed": [],
                    "findings": 0,
                }
            )
            continue
        serialized = review_as_dict(review)
        rows.append(
            {
                "requirement_id": requirement.external_id,
                "spec_file": serialized["spec_file"],
                "reviewed": True,
                "reviewed_at": serialized["reviewed_at"],
                "snapshot_hash": serialized["snapshot_hash"],
                "outcome": serialized["outcome"],
                "entries_surfaced": len(serialized["coverage"]),
                "coverage": serialized["coverage"],
                "unaddressed": [
                    f"{finding['entry_id']}@{finding['entry_version']}"
                    for finding in serialized["findings"]
                    if finding["finding_type"] == FINDING_UNADDRESSED_OBLIGATION
                ],
                "findings": len(serialized["findings"]),
            }
        )
    return rows


def _requirements_by_id(external_ids: list[str], target: str) -> tuple[Requirement, ...]:
    found = {
        requirement.external_id: requirement
        for requirement in Requirement.objects.filter(external_id__in=external_ids)
    }
    missing = [external_id for external_id in external_ids if external_id not in found]
    if missing:
        raise ReviewTargetError(
            f"spec file '{target}' declares {', '.join(missing)}, "
            f"which parse_specs has not imported"
        )
    return tuple(found[external_id] for external_id in external_ids)


def _finding_entry_version(finding, versions_by_pk: dict[int, CorpusEntryVersion]):
    if finding.entry_version_pk is not None:
        return versions_by_pk[finding.entry_version_pk]

    version = CorpusEntryVersion.objects.filter(
        entry__external_id=finding.entry_id, version=finding.entry_version
    ).first()
    if version is None:
        raise UnknownCitationError(
            f"spec cites {finding.entry_id}@{finding.entry_version}, which the corpus "
            f"does not contain"
        )
    return version

"""Corpus drift: which recorded reviews the corpus has since moved out from under.

Staleness is derived, never stored. A review pins a `CorpusSnapshot` and records
a `ReviewCoverage` row per entry version it surfaced; the corpus as it stands now
is another snapshot. Those three facts answer whether a review still holds, so no
flag, cache, or persisted marker can drift away from the truth.

The derivation runs in two steps:

1. Diff the review's pinned snapshot against the current one. Entry versions the
   current snapshot holds and the pinned one does not are what moved.
2. Keep only the changes that reach the review. A change reaches a review when
   its entry appears in that review's own coverage rows, or when the changed
   version supersedes a version those rows cover. Everything else leaves the
   review standing, so it stays out of the output.

The second step is the precision rule. A review that never covered the changed
entry is not stale, and naming it would train reviewers to re-run everything on
every corpus edit.

The diff runs one way only, because the current corpus is a superset of every
pinned snapshot. Versions are immutable, `parse_corpus` refuses to clear them,
and `ReviewCoverage.entry_version` protects on delete — a covered version cannot
leave. Drift is therefore what entered.

The inverse question — which obligations now reach a spec that no review ever put
in front of anyone — is `newly_applicable_entries`.

Both halves examine the latest review per requirement. An earlier review is
already superseded by the later one and makes no live claim.
"""

from dataclasses import dataclass

from requirements.models import CorpusSnapshot, SpecReview
from requirements.services.corpus_matcher import (
    ApplicableEntryVersion,
    resolve_applicable_entries,
)
from requirements.services.corpus_review import current_snapshot


@dataclass(frozen=True)
class AddedEntryVersion:
    """One entry version the corpus gained after a snapshot was pinned."""

    entry_id: str
    version: int
    title: str
    supersedes: tuple[str, int] | None = None

    def __str__(self) -> str:
        return f"{self.entry_id}@{self.version}"

    @property
    def supersedes_label(self) -> str:
        """The superseded version as `ENTRY-ID@VERSION`, empty when it supersedes nothing."""
        if self.supersedes is None:
            return ""
        return f"{self.supersedes[0]}@{self.supersedes[1]}"


@dataclass(frozen=True)
class StaleReview:
    """One review the corpus has moved out from under, and the additions that did it."""

    review: SpecReview
    additions: tuple[AddedEntryVersion, ...]
    covered_versions: dict[str, tuple[int, ...]]


@dataclass(frozen=True)
class NewlyApplicable:
    """Entry versions that apply to a reviewed requirement but no review has surfaced."""

    review: SpecReview
    entries: tuple[ApplicableEntryVersion, ...]


def latest_reviews() -> list[SpecReview]:
    """The most recent review of each requirement, ordered by requirement id."""
    reviews = SpecReview.objects.select_related("requirement", "snapshot").order_by(
        "requirement__external_id", "-created_at", "-pk"
    )
    latest: dict[int, SpecReview] = {}
    for review in reviews:
        latest.setdefault(review.requirement_id, review)
    return list(latest.values())


def added_entry_versions(
    pinned: CorpusSnapshot, current: CorpusSnapshot
) -> tuple[AddedEntryVersion, ...]:
    """Entry versions the corpus gained between a pinned snapshot and the current one.

    Ordered by entry id, then version.
    """
    pinned_pks = set(pinned.entry_versions.values_list("pk", flat=True))
    added = [
        AddedEntryVersion(
            entry_id=version.entry.external_id,
            version=version.version,
            title=version.entry.title,
            supersedes=None
            if version.supersedes is None
            else (version.supersedes.entry.external_id, version.supersedes.version),
        )
        for version in current.entry_versions.select_related("entry", "supersedes__entry")
        if version.pk not in pinned_pks
    ]
    return tuple(sorted(added, key=lambda item: (item.entry_id, item.version)))


def covered_versions_by_entry(review: SpecReview) -> dict[str, tuple[int, ...]]:
    """Entry versions the review surfaced, grouped by entry id and ordered by version."""
    rows = review.coverage.select_related("entry_version__entry").order_by(
        "entry_version__entry__external_id", "entry_version__version"
    )
    covered: dict[str, list[int]] = {}
    for row in rows:
        covered.setdefault(row.entry_version.entry.external_id, []).append(
            row.entry_version.version
        )
    return {entry_id: tuple(versions) for entry_id, versions in covered.items()}


def reaches_coverage(added: AddedEntryVersion, covered: dict[str, tuple[int, ...]]) -> bool:
    """Whether one corpus addition invalidates a review holding this coverage.

    True when the addition extends an entry the review covered, or when it
    supersedes one of the covered versions — the cross-entry supersession case,
    where the successor carries a different entry id than the version it retires.
    """
    if added.entry_id in covered:
        return True
    if added.supersedes is None:
        return False
    superseded_entry_id, superseded_version = added.supersedes
    return superseded_version in covered.get(superseded_entry_id, ())


def stale_reviews(reviews: list[SpecReview], current: CorpusSnapshot) -> list[StaleReview]:
    """Reviews whose own coverage a corpus addition has reached, in review order."""
    added_by_snapshot: dict[int, tuple[AddedEntryVersion, ...]] = {}
    stale: list[StaleReview] = []

    for review in reviews:
        if review.snapshot_id not in added_by_snapshot:
            added_by_snapshot[review.snapshot_id] = added_entry_versions(review.snapshot, current)
        covered = covered_versions_by_entry(review)
        reaching = tuple(
            added
            for added in added_by_snapshot[review.snapshot_id]
            if reaches_coverage(added, covered)
        )
        if reaching:
            stale.append(StaleReview(review=review, additions=reaching, covered_versions=covered))

    return stale


def newly_applicable_entries(
    reviews: list[SpecReview], current: CorpusSnapshot
) -> list[NewlyApplicable]:
    """Entry versions that now apply to a reviewed requirement but were never surfaced.

    The applicable set grows when a new entry's scope rules reach the spec, or
    when a rescoped version — a rescope is a version bump, since `applies_to`
    feeds the content hash — reaches it for the first time.
    """
    gaps: list[NewlyApplicable] = []
    for review in reviews:
        covered_pks = set(review.coverage.values_list("entry_version_id", flat=True))
        fresh = tuple(
            item
            for item in resolve_applicable_entries(review.requirement, current)
            if item.entry_version.pk not in covered_pks
        )
        if fresh:
            gaps.append(NewlyApplicable(review=review, entries=fresh))
    return gaps


def addition_detail(added: AddedEntryVersion, covered: dict[str, tuple[int, ...]]) -> str:
    """Why one corpus addition invalidated one review, naming both sides."""
    covered_versions = covered.get(added.entry_id, ())
    if covered_versions:
        held = ", ".join(f"{added.entry_id}@{version}" for version in covered_versions)
        return f"{added} entered the corpus after this review, which covers {held}"
    return f"{added} entered the corpus after this review and supersedes {added.supersedes_label}"


def stale_review_as_dict(stale: StaleReview) -> dict:
    """Serializable form of one stale review and the additions that invalidated it."""
    return {
        "requirement_id": stale.review.requirement.external_id,
        "spec_file": stale.review.spec_file,
        "reviewer": stale.review.reviewer,
        "outcome": stale.review.outcome,
        "reviewed_at": stale.review.created_at.isoformat(),
        "snapshot_hash": stale.review.snapshot.snapshot_hash,
        "invalidated_by": [
            {
                "entry_id": added.entry_id,
                "entry_version": added.version,
                "title": added.title,
                "supersedes": added.supersedes_label,
                "covered_versions": list(stale.covered_versions.get(added.entry_id, ())),
                "detail": addition_detail(added, stale.covered_versions),
            }
            for added in stale.additions
        ],
    }


def newly_applicable_as_dict(gap: NewlyApplicable) -> dict:
    """Serializable form of one spec's newly applicable entry versions."""
    return {
        "requirement_id": gap.review.requirement.external_id,
        "spec_file": gap.review.spec_file,
        "reviewed_at": gap.review.created_at.isoformat(),
        "snapshot_hash": gap.review.snapshot.snapshot_hash,
        "entries": [
            {
                "entry_id": item.entry_id,
                "entry_version": item.entry_version.version,
                "title": item.entry_version.entry.title,
                "kind": item.entry_version.entry.kind,
                "matched_by": item.reasons_as_dicts(),
            }
            for item in gap.entries
        ],
    }


def drift_as_dict() -> dict:
    """The whole drift report against the corpus as it stands now."""
    current = current_snapshot()
    reviews = latest_reviews()
    stale = stale_reviews(reviews, current)
    gaps = newly_applicable_entries(reviews, current)

    return {
        "current_snapshot": current.snapshot_hash,
        "stale_reviews": [stale_review_as_dict(item) for item in stale],
        "newly_applicable": [newly_applicable_as_dict(gap) for gap in gaps],
        "summary": {
            "reviews_examined": len(reviews),
            "stale_reviews": len(stale),
            "specs_with_newly_applicable_entries": len(gaps),
            "newly_applicable_entries": sum(len(gap.entries) for gap in gaps),
        },
    }

"""Applicability resolver: which corpus entry versions bind to a requirement.

`resolve_applicable_entries(requirement, snapshot)` returns an ordered list of
`ApplicableEntryVersion` rows. Each pairs a `CorpusEntryVersion` with the
structured reasons it matched — scope key, pattern, matched value, and the
requirement in the hierarchy the match came from. The review record persists
those reasons, so they are data rather than a log line.

Four rules the review path depends on:

1. An entry version with an empty `applies_to` binds to nothing. Never to
   everything: a half-written entry that fired on every spec would train
   reviewers to ignore output.
2. Applicability inherits down the requirement hierarchy. A match against an
   ancestor applies to its descendants and names the ancestor it came from.
3. At most one version of an entry applies. A snapshot holding two versions of
   one standard would otherwise give it two coverage rows and two findings, and
   the audit ledger would overstate coverage on every version bump.
4. Ordering is deterministic. The same requirement and snapshot always produce
   the same sequence.
"""

from dataclasses import dataclass
from fnmatch import fnmatchcase

from requirements.models import (
    CorpusEntryStatus,
    CorpusEntryVersion,
    CorpusSnapshot,
    Requirement,
)

SCOPE_KEYS = ("tags", "components", "paths", "requirement_ids")


@dataclass(frozen=True)
class MatchReason:
    """Why one scope rule bound an entry version to a requirement.

    `matched_requirement_id` names the requirement the rule matched. When
    `inherited` is true that requirement is an ancestor of the one under review.
    """

    scope_key: str
    pattern: str
    matched_value: str
    matched_requirement_id: str
    inherited: bool

    def to_dict(self) -> dict[str, str | bool]:
        """Serializable form for storage on a review record."""
        return {
            "scope_key": self.scope_key,
            "pattern": self.pattern,
            "matched_value": self.matched_value,
            "matched_requirement_id": self.matched_requirement_id,
            "inherited": self.inherited,
        }


@dataclass(frozen=True)
class ApplicableEntryVersion:
    """One corpus entry version that applies, with every reason it matched."""

    entry_version: CorpusEntryVersion
    reasons: tuple[MatchReason, ...]

    @property
    def entry_id(self) -> str:
        """External id of the owning corpus entry."""
        return self.entry_version.entry.external_id

    @property
    def matched_scope_keys(self) -> tuple[str, ...]:
        """Distinct scope keys that matched, in canonical key order."""
        matched = {reason.scope_key for reason in self.reasons}
        return tuple(key for key in SCOPE_KEYS if key in matched)

    def reasons_as_dicts(self) -> list[dict[str, str | bool]]:
        """Every match reason in serializable form, in match order."""
        return [reason.to_dict() for reason in self.reasons]


def build_lineage(requirement: Requirement) -> tuple[tuple[Requirement, bool], ...]:
    """The requirement itself, then its ancestors nearest first.

    The flag is true for ancestors, whose matches descendants inherit.
    """
    ancestors = list(requirement.get_ancestors())
    ancestors.reverse()
    return ((requirement, False), *((ancestor, True) for ancestor in ancestors))


def match_entry_version(
    entry_version: CorpusEntryVersion,
    lineage: tuple[tuple[Requirement, bool], ...],
) -> tuple[MatchReason, ...]:
    """Every scope-rule match between one entry version and a requirement lineage.

    Reasons come back nearest-requirement first, then in canonical scope key
    order, then in the order the patterns are authored. An empty `applies_to`
    yields no reasons, and an absent scope key matches nothing.
    """
    reasons: list[MatchReason] = []
    for node, inherited in lineage:
        for scope_key in SCOPE_KEYS:
            for pattern in entry_version.applies_to.get(scope_key, ()):
                matched_value = _matched_value(scope_key, pattern, node)
                if matched_value is not None:
                    reasons.append(
                        MatchReason(
                            scope_key=scope_key,
                            pattern=pattern,
                            matched_value=matched_value,
                            matched_requirement_id=node.external_id,
                            inherited=inherited,
                        )
                    )
    return tuple(reasons)


def current_versions(snapshot: CorpusSnapshot) -> list[CorpusEntryVersion]:
    """The one version of each entry in `snapshot` that a review may bind.

    Retired entries contribute nothing, and neither does a version another entry
    supersedes inside the same snapshot. Of what survives, an entry contributes
    its highest version alone: a bump replaces the version before it rather than
    joining it. Older versions stay in the snapshot, which records what the
    corpus held, and a review pinned to a snapshot taken before the bump still
    resolves the version current then.

    Ordered by entry external id.
    """
    versions = list(
        snapshot.entry_versions.select_related("entry")
        .prefetch_related("superseded_by")
        .order_by("entry__external_id", "version")
    )
    member_pks = {version.pk for version in versions}

    highest: dict[str, CorpusEntryVersion] = {}
    for version in versions:
        if version.entry.status == CorpusEntryStatus.RETIRED:
            continue
        if any(successor.pk in member_pks for successor in version.superseded_by.all()):
            continue
        held = highest.get(version.entry.external_id)
        if held is None or version.version > held.version:
            highest[version.entry.external_id] = version

    return [highest[external_id] for external_id in sorted(highest)]


def resolve_applicable_entries(
    requirement: Requirement, snapshot: CorpusSnapshot
) -> list[ApplicableEntryVersion]:
    """Corpus entry versions in `snapshot` that apply to `requirement`.

    Ordered by entry external id, one version per entry.

    Retired entries never apply. A version superseded by another member of the
    same snapshot never applies either; it resurfaces only when a review pins a
    snapshot taken before its replacement existed. Scope rules are read off the
    version `current_versions` selects, so a bump that narrows `applies_to`
    narrows what binds instead of leaving the older rules in force.
    """
    lineage = build_lineage(requirement)

    applicable: list[ApplicableEntryVersion] = []
    for version in current_versions(snapshot):
        reasons = match_entry_version(version, lineage)
        if reasons:
            applicable.append(ApplicableEntryVersion(entry_version=version, reasons=reasons))

    return applicable


def _matched_value(scope_key: str, pattern: str, node: Requirement) -> str | None:
    if scope_key == "tags":
        return pattern if pattern in node.tags else None
    if scope_key == "components":
        return pattern if node.component == pattern else None
    if scope_key == "paths":
        return node.source_file if fnmatchcase(node.source_file, pattern) else None
    return node.external_id if fnmatchcase(node.external_id, pattern) else None

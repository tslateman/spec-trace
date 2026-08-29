"""Check evaluator: turns corpus checks and citation state into typed findings.

`evaluate` is pure. It reads plain dataclasses and returns Findings; it never
touches the database, the filesystem, or the network, and it never evaluates a
predicate as an expression. The predicate structure comes from
`corpus_parser.parse_check_assertion`, which already validated the closed
grammar at parse time.

Callers holding model rows use `review_findings`, the thin adapter that reads
the Requirement and CorpusEntryVersion rows once and then calls `evaluate`.

Five finding types and the condition that fires each:

- unaddressed_obligation: an entry applies and the spec cites no version of it
- stale_citation: the spec cites version N while version M > N applies, or the
  cited version is one another entry version supersedes
- orphan_citation: the spec cites an entry that does not apply
- unmet_check: an applicable, cited entry has a check the requirement fails
- conflicting_obligations: two applicable entries assert contradictory
  predicates on one field
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from requirements.constants import (
    FINDING_CONFLICTING_OBLIGATIONS,
    FINDING_ORPHAN_CITATION,
    FINDING_STALE_CITATION,
    FINDING_UNADDRESSED_OBLIGATION,
    FINDING_UNMET_CHECK,
)
from requirements.services.corpus_parser import CHECK_FIELDS

LIST_VALUED_FIELDS = frozenset({"tags", "depends_on"})
SCALAR_CHECK_FIELDS = CHECK_FIELDS - LIST_VALUED_FIELDS

CITATION_PATTERN = re.compile(r"^(?P<entry_id>[A-Za-z0-9._-]+)@(?P<version>\d+)$")


class CitationFormatError(ValueError):
    """A `complies_with` citation does not match the ENTRY-ID@VERSION form."""


@dataclass(frozen=True)
class Citation:
    """One `complies_with` entry from spec frontmatter."""

    entry_id: str
    version: int

    def __str__(self) -> str:
        return f"{self.entry_id}@{self.version}"


@dataclass(frozen=True)
class ApplicableVersion:
    """One corpus entry version the applicability resolver bound to a spec."""

    entry_id: str
    version: int
    checks: tuple[dict[str, Any], ...] = ()
    superseded_by: tuple[str, ...] = ()
    pk: int | None = None

    def __str__(self) -> str:
        return f"{self.entry_id}@{self.version}"

    @classmethod
    def from_entry_version(cls, entry_version) -> "ApplicableVersion":
        """Read a CorpusEntryVersion row into the pure input shape."""
        return cls(
            entry_id=entry_version.entry.external_id,
            version=entry_version.version,
            checks=tuple(entry_version.checks),
            superseded_by=tuple(
                f"{successor.entry.external_id}@{successor.version}"
                for successor in entry_version.superseded_by.all()
            ),
            pk=entry_version.pk,
        )


@dataclass(frozen=True)
class RequirementFacts:
    """The requirement field values the check grammar can read."""

    external_id: str
    fields: Mapping[str, str | tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def from_requirement(cls, requirement) -> "RequirementFacts":
        """Read a Requirement row, including its depends_on ids, into field values."""
        values: dict[str, str | tuple[str, ...]] = {
            name: str(getattr(requirement, name)) for name in sorted(SCALAR_CHECK_FIELDS)
        }
        values["tags"] = tuple(str(tag) for tag in requirement.tags)
        values["depends_on"] = tuple(
            dependency.external_id for dependency in requirement.depends_on.all()
        )
        return cls(external_id=requirement.external_id, fields=values)


@dataclass(frozen=True)
class Finding:
    """One deterministic rule outcome, traceable to an entry version."""

    finding_type: str
    entry_id: str
    entry_version: int
    detail: str
    check_id: str = ""
    entry_version_pk: int | None = None


def parse_citations(values: Iterable[str]) -> tuple[Citation, ...]:
    """Parse a `complies_with` frontmatter list into Citations.

    Every citation must name a version: `STD-SEC-001@3`. A citation without one
    raises CitationFormatError.
    """
    citations = []
    for raw in values:
        match = CITATION_PATTERN.match(str(raw).strip())
        if not match:
            raise CitationFormatError(
                f"complies_with entry '{raw}' must look like ENTRY-ID@VERSION, e.g. STD-SEC-001@3"
            )
        citations.append(Citation(match.group("entry_id"), int(match.group("version"))))
    return tuple(citations)


def evaluate_check(check: Mapping[str, Any], facts: RequirementFacts) -> bool:
    """Evaluate one parsed check predicate against the requirement facts.

    List-valued fields (tags, depends_on) use set semantics for `in`/`not in`
    and membership for `contains`; scalar fields use equality and substring.
    """
    value = facts.fields[check["field"]]
    operator = check["operator"]
    expected = check["value"]

    if operator == "is set":
        return bool(value) if isinstance(value, tuple) else bool(value.strip())
    if operator == "is not set":
        return not (bool(value) if isinstance(value, tuple) else bool(value.strip()))
    if operator == "in":
        return bool(set(value) & set(expected)) if isinstance(value, tuple) else value in expected
    if operator == "not in":
        return not (
            bool(set(value) & set(expected)) if isinstance(value, tuple) else value in expected
        )
    if operator == "contains":
        return expected in value
    if operator == "not contains":
        return expected not in value
    if operator == "==":
        return list(value) == [expected] if isinstance(value, tuple) else value == expected
    if operator == "!=":
        return not (list(value) == [expected] if isinstance(value, tuple) else value == expected)
    raise ValueError(f"unknown check operator '{operator}'")


def evaluate(
    facts: RequirementFacts,
    applicable: Sequence[ApplicableVersion],
    citations: Sequence[Citation],
) -> list[Finding]:
    """Produce every finding for one requirement against one applicable set.

    Pure: no database access, no I/O. Findings come back in a stable order —
    entry id, entry version, finding type, check id.
    """
    findings = [
        *_citation_findings(facts, applicable, citations),
        *_unmet_check_findings(facts, applicable, citations),
        *_conflict_findings(applicable),
    ]
    return sorted(
        findings,
        key=lambda f: (f.entry_id, f.entry_version, f.finding_type, f.check_id),
    )


def review_findings(requirement, entry_versions: Iterable, complies_with: Iterable[str]):
    """Adapter for callers holding model rows and raw frontmatter citations."""
    return evaluate(
        RequirementFacts.from_requirement(requirement),
        [ApplicableVersion.from_entry_version(version) for version in entry_versions],
        parse_citations(complies_with),
    )


def _highest_applicable_by_entry(
    applicable: Sequence[ApplicableVersion],
) -> dict[str, ApplicableVersion]:
    highest: dict[str, ApplicableVersion] = {}
    for item in applicable:
        current = highest.get(item.entry_id)
        if current is None or item.version > current.version:
            highest[item.entry_id] = item
    return highest


def _citation_findings(
    facts: RequirementFacts,
    applicable: Sequence[ApplicableVersion],
    citations: Sequence[Citation],
) -> list[Finding]:
    highest = _highest_applicable_by_entry(applicable)
    cited_entry_ids = {citation.entry_id for citation in citations}

    findings = [
        Finding(
            finding_type=FINDING_UNADDRESSED_OBLIGATION,
            entry_id=item.entry_id,
            entry_version=item.version,
            entry_version_pk=item.pk,
            detail=(
                f"{item} applies to {facts.external_id} but the spec does not cite it "
                f"in complies_with"
            ),
        )
        for item in highest.values()
        if item.entry_id not in cited_entry_ids
    ]

    for citation in citations:
        item = highest.get(citation.entry_id)
        if item is None:
            findings.append(
                Finding(
                    finding_type=FINDING_ORPHAN_CITATION,
                    entry_id=citation.entry_id,
                    entry_version=citation.version,
                    detail=(f"spec cites {citation}, which does not apply to {facts.external_id}"),
                )
            )
        elif citation.version < item.version:
            findings.append(
                Finding(
                    finding_type=FINDING_STALE_CITATION,
                    entry_id=item.entry_id,
                    entry_version=item.version,
                    entry_version_pk=item.pk,
                    detail=(f"spec cites {citation}; version {item.version} is the applicable one"),
                )
            )
        elif item.superseded_by:
            findings.append(
                Finding(
                    finding_type=FINDING_STALE_CITATION,
                    entry_id=item.entry_id,
                    entry_version=item.version,
                    entry_version_pk=item.pk,
                    detail=(
                        f"spec cites {citation}, which {', '.join(sorted(item.superseded_by))} "
                        f"supersedes"
                    ),
                )
            )

    return findings


def _unmet_check_findings(
    facts: RequirementFacts,
    applicable: Sequence[ApplicableVersion],
    citations: Sequence[Citation],
) -> list[Finding]:
    cited_entry_ids = {citation.entry_id for citation in citations}
    return [
        Finding(
            finding_type=FINDING_UNMET_CHECK,
            entry_id=item.entry_id,
            entry_version=item.version,
            entry_version_pk=item.pk,
            check_id=check["id"],
            detail=(
                f"{item} check '{check['id']}' requires '{check['assert']}'; "
                f"{facts.external_id} has {check['field']}="
                f"{_rendered(facts.fields[check['field']])}"
            ),
        )
        for item in applicable
        if item.entry_id in cited_entry_ids
        for check in item.checks
        if not evaluate_check(check, facts)
    ]


def _rendered(value: str | tuple[str, ...]) -> str:
    if isinstance(value, tuple):
        return f"[{', '.join(value)}]"
    return f"'{value}'"


def _conflict_findings(applicable: Sequence[ApplicableVersion]) -> list[Finding]:
    findings = []
    ordered = sorted(applicable, key=lambda item: (item.entry_id, item.version))

    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            if left.entry_id == right.entry_id:
                continue
            for left_check in left.checks:
                for right_check in right.checks:
                    if left_check["field"] != right_check["field"]:
                        continue
                    if left_check["field"] in LIST_VALUED_FIELDS:
                        continue
                    if not _contradicts(_constraint(left_check), _constraint(right_check)):
                        continue
                    findings.append(
                        Finding(
                            finding_type=FINDING_CONFLICTING_OBLIGATIONS,
                            entry_id=left.entry_id,
                            entry_version=left.version,
                            entry_version_pk=left.pk,
                            check_id=left_check["id"],
                            detail=(
                                f"{left} check '{left_check['id']}' asserts "
                                f"'{left_check['assert']}' but {right} check "
                                f"'{right_check['id']}' asserts '{right_check['assert']}' "
                                f"on field '{left_check['field']}'"
                            ),
                        )
                    )
    return findings


def _constraint(check: Mapping[str, Any]) -> tuple[str, frozenset[str]]:
    operator = check["operator"]
    value = check["value"]
    if operator == "==":
        return "allow", frozenset({value})
    if operator == "in":
        return "allow", frozenset(value)
    if operator == "!=":
        return "deny", frozenset({value})
    if operator == "not in":
        return "deny", frozenset(value)
    if operator == "is set":
        return "set", frozenset()
    if operator == "is not set":
        return "unset", frozenset()
    if operator == "contains":
        return "contains", frozenset({value})
    if operator == "not contains":
        return "not_contains", frozenset({value})
    raise ValueError(f"unknown check operator '{operator}'")


def _contradicts(first: tuple[str, frozenset], second: tuple[str, frozenset]) -> bool:
    """Decide whether two predicates on one field can never hold together.

    Only provable contradictions count. Two predicates that merely narrow each
    other — `risk_level in [critical, high]` against `risk_level in [high]` —
    are satisfiable and produce nothing.
    """
    (kind, values), (other_kind, other_values) = sorted(
        (first, second), key=lambda constraint: constraint[0]
    )

    if kind == "allow" and other_kind == "allow":
        return not values & other_values
    if kind == "allow" and other_kind == "contains":
        return not any(needle in value for value in values for needle in other_values)
    if kind == "allow" and other_kind == "deny":
        return values <= other_values
    if kind == "allow" and other_kind == "not_contains":
        return all(any(needle in value for needle in other_values) for value in values)
    if kind == "allow" and other_kind == "unset":
        return True
    if kind == "contains" and other_kind == "not_contains":
        return any(forbidden in required for required in values for forbidden in other_values)
    if kind == "contains" and other_kind == "unset":
        return True
    return kind == "set" and other_kind == "unset"

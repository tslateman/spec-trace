"""Curation report: which `applies_to` edits would close a scope gap.

Nothing here is a finding. A suggestion is a proposal for a human to accept into
a corpus file, and the containment rule is absolute: this module writes no row,
no file, and no exit code. It reads the matcher and reports what the matcher
missed.

Two kinds of gap, reported in this order because they are not equally strong.

**Near-miss scope rules** come first. The matcher compares tags and components
by exact string equality, so an entry scoped `components: [api]` never binds to
a requirement whose component is `api-gateway`, and the author gets silence
rather than a warning. A near miss is evidence about authoring intent — the
value is already in the rule, spelled one segment or one plural off — so it
outranks any text score, however high.

`requirement_ids` gets one near-miss rule of its own: a pattern whose leading
segments already name the requirement's family and differ only in the trailing
id, `REQ-PLAT-002` against `REQ-PLAT-001`, widens to `REQ-PLAT-*`. A pattern
differing anywhere earlier names a different family, and `paths` patterns glob
across separators already, so neither produces a near miss.

**Text similarity** comes second, for entries whose prose is about the same
subject as a spec while no scope rule comes close. TF-IDF cosine over tokens,
computed here in plain Python: no new dependency, no model, no network call. A
text score proposes the narrowest edit that closes the gap, `requirement_ids`
naming the one spec, because prose overlap says nothing about which axis the
author meant to scope by.

Every suggestion names the `applies_to` key and the exact pattern to write,
alongside the existing pattern it widens and the spec that motivated it.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

from requirements.models import CorpusEntryStatus, CorpusEntryVersion, Requirement
from requirements.services.corpus_matcher import build_lineage, match_entry_version

SUGGESTION_NEAR_MISS = "near_miss"
SUGGESTION_TEXT_SIMILARITY = "text_similarity"

KIND_RANK = {SUGGESTION_NEAR_MISS: 0, SUGGESTION_TEXT_SIMILARITY: 1}

DEFAULT_MIN_SCORE = 0.12
SPELLING_MIN_RATIO = 0.8

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
SEGMENT_PATTERN = re.compile(r"[^a-z0-9]+")

STOP_WORDS = frozenset(
    {
        "and",
        "any",
        "are",
        "but",
        "for",
        "from",
        "has",
        "its",
        "must",
        "not",
        "que",
        "the",
        "that",
        "them",
        "then",
        "this",
        "was",
        "were",
        "which",
        "with",
    }
)


@dataclass(frozen=True)
class ScopeSuggestion:
    """One proposed `applies_to` edit, traceable to the spec that motivated it."""

    requirement_id: str
    spec_file: str
    entry_id: str
    entry_version: int
    entry_title: str
    kind: str
    scope_key: str
    proposed_pattern: str
    existing_pattern: str
    score: float
    rationale: str

    @property
    def proposed_edit(self) -> str:
        """The edit as it reads in a corpus file."""
        return f"applies_to.{self.scope_key}: [{self.proposed_pattern}]"

    def to_dict(self) -> dict:
        """Serializable form for the JSON report."""
        return {
            "requirement_id": self.requirement_id,
            "spec_file": self.spec_file,
            "entry_id": self.entry_id,
            "entry_version": self.entry_version,
            "entry_title": self.entry_title,
            "kind": self.kind,
            "scope_key": self.scope_key,
            "proposed_pattern": self.proposed_pattern,
            "existing_pattern": self.existing_pattern,
            "proposed_edit": self.proposed_edit,
            "score": round(self.score, 4),
            "rationale": self.rationale,
        }


def live_entry_versions() -> list[CorpusEntryVersion]:
    """Entry versions a scope-rule edit could still reach.

    A retired entry and a superseded version are history; widening their scope
    would bind a spec to an obligation nobody holds anymore.
    """
    return list(
        CorpusEntryVersion.objects.select_related("entry")
        .exclude(entry__status=CorpusEntryStatus.RETIRED)
        .filter(superseded_by__isnull=True)
        .order_by("entry__external_id", "version")
    )


def segments(value: str) -> frozenset[str]:
    """Lowercase alphanumeric segments of a scope value, split on separators."""
    return frozenset(part for part in SEGMENT_PATTERN.split(value.lower()) if part)


def value_affinity(pattern: str, value: str) -> float:
    """How near an exact-matched scope pattern comes to a requirement's value.

    Zero means unrelated. Two signals count, and only two: shared segments,
    which catch `api` against `api-gateway`, and near-identical spelling, which
    catches `workspaces` against `workspace`. Loose character overlap is left
    out — `compliance` against `collaboration` is a coincidence, not intent.
    """
    if pattern == value or not pattern or not value:
        return 0.0

    pattern_segments, value_segments = segments(pattern), segments(value)
    shared = pattern_segments & value_segments
    containment = len(shared) / max(len(pattern_segments), len(value_segments)) if shared else 0.0

    ratio = SequenceMatcher(None, pattern, value).ratio()
    spelling = ratio if ratio >= SPELLING_MIN_RATIO else 0.0

    return max(containment, spelling)


def widened_id_glob(pattern: str, external_id: str) -> tuple[str, float] | None:
    """Widen a requirement-id pattern that already names the right family.

    `REQ-PLAT-002` against `REQ-PLAT-001` widens to `REQ-PLAT-*`. Every leading
    segment must agree; only the trailing id may differ. `REQ-IAM-001` against
    `REQ-BILL-001` shares a trailing segment and nothing else, which names a
    different family rather than a near miss.
    """
    pattern_parts = pattern.split("-")
    id_parts = external_id.split("-")
    if len(pattern_parts) != len(id_parts) or len(pattern_parts) < 2:
        return None
    if pattern_parts[:-1] != id_parts[:-1] or pattern_parts[-1] == id_parts[-1]:
        return None
    if pattern_parts[-1] == "*":
        return None

    widened = "-".join([*pattern_parts[:-1], "*"])
    return widened, (len(pattern_parts) - 1) / len(pattern_parts)


def near_miss_suggestions(
    requirement: Requirement, entry_version: CorpusEntryVersion
) -> list[ScopeSuggestion]:
    """Every scope rule on `entry_version` that nearly reaches `requirement`."""
    return [
        *_value_near_misses(
            requirement, entry_version, "tags", tuple(str(tag) for tag in requirement.tags)
        ),
        *_value_near_misses(requirement, entry_version, "components", (requirement.component,)),
        *_id_near_misses(requirement, entry_version),
    ]


def requirement_text(requirement: Requirement) -> str:
    """Everything about a requirement a corpus entry's prose could echo."""
    return " ".join(
        [
            requirement.title,
            requirement.description,
            requirement.scope,
            requirement.condition,
            requirement.response,
            requirement.component,
            " ".join(str(tag) for tag in requirement.tags),
        ]
    )


def entry_text(entry_version: CorpusEntryVersion) -> str:
    """The prose of one entry version, title included."""
    return f"{entry_version.entry.title} {entry_version.body}"


def tokenize(text: str) -> tuple[str, ...]:
    """Lowercase alphanumeric tokens, minus stop words and one-letter noise."""
    return tuple(
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if len(token) > 2 and token not in STOP_WORDS
    )


def inverse_document_frequency(documents: list[tuple[str, ...]]) -> dict[str, float]:
    """Smoothed IDF over the documents in this run."""
    total = len(documents)
    frequencies: Counter[str] = Counter()
    for tokens in documents:
        frequencies.update(set(tokens))
    return {token: math.log((1 + total) / (1 + count)) + 1 for token, count in frequencies.items()}


def tf_idf(tokens: tuple[str, ...], idf: dict[str, float]) -> dict[str, float]:
    """TF-IDF weights for one document against a shared IDF table."""
    counts = Counter(tokens)
    total = sum(counts.values())
    if not total:
        return {}
    return {token: (count / total) * idf[token] for token, count in counts.items()}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    """Cosine similarity of two TF-IDF weight maps."""
    shared = set(left) & set(right)
    if not shared:
        return 0.0
    dot = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def suggest_scope_rules(
    requirement_id: str = "", min_score: float = DEFAULT_MIN_SCORE
) -> list[ScopeSuggestion]:
    """Propose `applies_to` edits for every gap the matcher leaves open.

    A gap is a (requirement, entry version) pair the matcher does not bind. Near
    misses are reported whatever their score; text similarity must clear
    `min_score`. Ordering is deterministic: near misses first, then score
    descending, then ids.

    `requirement_id` narrows which requirements are reported, never how they
    score. IDF spans every requirement and entry version either way, so one
    spec's report reads the same alone as it does inside the full run.
    """
    requirements = list(Requirement.objects.all().order_by("external_id"))
    versions = live_entry_versions()

    requirement_tokens = {item.pk: tokenize(requirement_text(item)) for item in requirements}
    version_tokens = {version.pk: tokenize(entry_text(version)) for version in versions}
    idf = inverse_document_frequency([*requirement_tokens.values(), *version_tokens.values()])
    requirement_weights = {pk: tf_idf(tokens, idf) for pk, tokens in requirement_tokens.items()}
    version_weights = {pk: tf_idf(tokens, idf) for pk, tokens in version_tokens.items()}

    targets = [
        item for item in requirements if not requirement_id or item.external_id == requirement_id
    ]

    suggestions: list[ScopeSuggestion] = []
    for requirement in targets:
        lineage = build_lineage(requirement)
        for version in versions:
            if match_entry_version(version, lineage):
                continue
            near_misses = near_miss_suggestions(requirement, version)
            if near_misses:
                suggestions.extend(near_misses)
                continue
            score = cosine(requirement_weights[requirement.pk], version_weights[version.pk])
            if score >= min_score:
                suggestions.append(_text_suggestion(requirement, version, score))

    return sorted(suggestions, key=_ordering)


def suggestions_as_dicts(
    requirement_id: str = "", min_score: float = DEFAULT_MIN_SCORE
) -> list[dict]:
    """The curation report in serializable form."""
    return [suggestion.to_dict() for suggestion in suggest_scope_rules(requirement_id, min_score)]


def _ordering(suggestion: ScopeSuggestion) -> tuple:
    return (
        KIND_RANK[suggestion.kind],
        -suggestion.score,
        suggestion.requirement_id,
        suggestion.entry_id,
        suggestion.entry_version,
        suggestion.scope_key,
        suggestion.proposed_pattern,
    )


def _value_near_misses(
    requirement: Requirement,
    entry_version: CorpusEntryVersion,
    scope_key: str,
    values: tuple[str, ...],
) -> list[ScopeSuggestion]:
    suggestions = []
    for pattern in entry_version.applies_to.get(scope_key, ()):
        for value in values:
            score = value_affinity(pattern, value)
            if not score:
                continue
            suggestions.append(
                _suggestion(
                    requirement,
                    entry_version,
                    scope_key=scope_key,
                    proposed_pattern=value,
                    existing_pattern=pattern,
                    score=score,
                    rationale=(
                        f"{scope_key} pattern '{pattern}' matches exactly, so it misses "
                        f"'{value}' on {requirement.external_id}"
                    ),
                )
            )
    return suggestions


def _id_near_misses(
    requirement: Requirement, entry_version: CorpusEntryVersion
) -> list[ScopeSuggestion]:
    suggestions = []
    for pattern in entry_version.applies_to.get("requirement_ids", ()):
        widened = widened_id_glob(pattern, requirement.external_id)
        if widened is None:
            continue
        proposed, score = widened
        suggestions.append(
            _suggestion(
                requirement,
                entry_version,
                scope_key="requirement_ids",
                proposed_pattern=proposed,
                existing_pattern=pattern,
                score=score,
                rationale=(
                    f"requirement_ids pattern '{pattern}' names the same family as "
                    f"{requirement.external_id} and pins one id"
                ),
            )
        )
    return suggestions


def _text_suggestion(
    requirement: Requirement, entry_version: CorpusEntryVersion, score: float
) -> ScopeSuggestion:
    return _suggestion(
        requirement,
        entry_version,
        scope_key="requirement_ids",
        proposed_pattern=requirement.external_id,
        existing_pattern="",
        score=score,
        kind=SUGGESTION_TEXT_SIMILARITY,
        rationale=(
            f"entry prose and {requirement.external_id} share vocabulary at cosine "
            f"{score:.2f}, and no scope rule comes near"
        ),
    )


def _suggestion(
    requirement: Requirement,
    entry_version: CorpusEntryVersion,
    scope_key: str,
    proposed_pattern: str,
    existing_pattern: str,
    score: float,
    rationale: str,
    kind: str = SUGGESTION_NEAR_MISS,
) -> ScopeSuggestion:
    return ScopeSuggestion(
        requirement_id=requirement.external_id,
        spec_file=requirement.source_file,
        entry_id=entry_version.entry.external_id,
        entry_version=entry_version.version,
        entry_title=entry_version.entry.title,
        kind=kind,
        scope_key=scope_key,
        proposed_pattern=proposed_pattern,
        existing_pattern=existing_pattern,
        score=score,
        rationale=rationale,
    )

"""Corpus file parser: reads corpus/**/*.md into CorpusEntry and CorpusEntryVersion.

The parser owns two contracts the rest of the milestone rests on:

1. Versions are immutable. Re-parsing a file whose content hash differs from the
   stored hash for the same version number raises CorpusVersionConflict.
2. The `checks` predicate grammar is closed and validated here, at parse time.
   Unknown fields or operators reject the file. Nothing is ever evaluated as an
   expression; the parsed structure is stored for the check evaluator to read.
"""

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

from requirements.models import (
    CorpusEnforcement,
    CorpusEntry,
    CorpusEntryKind,
    CorpusEntryStatus,
    CorpusEntryVersion,
)

APPLIES_TO_KEYS = frozenset({"tags", "components", "paths", "requirement_ids"})

CHECK_FIELDS = frozenset(
    {
        "risk_level",
        "verification_method",
        "verification_status",
        "slo_status",
        "priority",
        "status",
        "tags",
        "component",
        "timing",
        "scope",
        "condition",
        "response",
        "depends_on",
    }
)

LIST_OPERATORS = frozenset({"in", "not in"})
SCALAR_OPERATORS = frozenset({"==", "!=", "contains", "not contains"})
UNARY_OPERATORS = frozenset({"is set", "is not set"})
CHECK_OPERATORS = LIST_OPERATORS | SCALAR_OPERATORS | UNARY_OPERATORS

REQUIRED_FRONTMATTER_KEYS = ("id", "kind", "title", "version")

SUPERSEDES_PATTERN = re.compile(r"^(?P<entry_id>[A-Za-z0-9._-]+)@(?P<version>\d+)$")

_UNARY_PATTERN = re.compile(r"^(?P<field>[a-z_][a-z0-9_]*)\s+(?P<operator>is not set|is set)$")
_BINARY_PATTERN = re.compile(
    r"^(?P<field>[a-z_][a-z0-9_]*)\s+(?P<operator>not in|in|==|!=|not contains|contains)\s+"
    r"(?P<value>.+)$"
)
_LIST_PATTERN = re.compile(r"^\[(?P<items>.*)\]$")
_BARE_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class CorpusParseError(Exception):
    """A corpus file is malformed or violates the closed grammar."""


class CorpusVersionConflict(CorpusParseError):
    """A stored version number was reused for different content."""


def version_payload(
    *,
    kind: str,
    title: str,
    body: str,
    applies_to: dict[str, list[str]],
    checks: list[dict[str, Any]],
    enforcement: str,
    effective: date | None,
) -> dict[str, Any]:
    """The exact set of fields a version pins, for hashing.

    Enforcement belongs here: raising a standard from advisory to blocking changes
    what the version obliges, so it takes a version bump like any other edit.
    """
    return {
        "kind": kind,
        "title": title,
        "body": body,
        "applies_to": applies_to,
        "checks": checks,
        "enforcement": enforcement,
        "effective": effective,
    }


def compute_content_hash(payload: dict[str, Any]) -> str:
    """Hash the versioned content of an entry.

    The hash covers everything a version pins: body, scope rules, checks,
    enforcement posture, and the metadata that changes meaning (kind, title,
    effective date).
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_check_assertion(assertion: Any, entry_id: str, check_id: str) -> dict[str, Any]:
    """Parse one `assert` string into a stored predicate structure.

    Grammar (closed, never evaluated as an expression):
        <field> in [a, b]        <field> not in [a, b]
        <field> == value         <field> != value
        <field> contains value   <field> not contains value
        <field> is set           <field> is not set

    Returns a dict with field, operator, and value keys. `value` is a list for
    `in`/`not in`, a string for the scalar operators, and None for the unary ones.
    """
    if not isinstance(assertion, str):
        raise CorpusParseError(
            f"{entry_id}: check '{check_id}' assert must be a string, "
            f"got {type(assertion).__name__}"
        )

    text = assertion.strip()
    if not text:
        raise CorpusParseError(f"{entry_id}: check '{check_id}' has an empty assert")

    unary = _UNARY_PATTERN.match(text)
    if unary:
        field = _validated_field(unary.group("field"), entry_id, check_id)
        return {"field": field, "operator": unary.group("operator"), "value": None}

    binary = _BINARY_PATTERN.match(text)
    if not binary:
        raise CorpusParseError(
            f"{entry_id}: check '{check_id}' assert '{text}' does not match the check grammar. "
            f"Allowed operators: {', '.join(sorted(CHECK_OPERATORS))}"
        )

    field = _validated_field(binary.group("field"), entry_id, check_id)
    operator = binary.group("operator")
    raw_value = binary.group("value").strip()

    if operator in LIST_OPERATORS:
        return {
            "field": field,
            "operator": operator,
            "value": _parse_list_value(raw_value, entry_id, check_id, operator),
        }

    return {
        "field": field,
        "operator": operator,
        "value": _parse_scalar_value(raw_value, entry_id, check_id, operator),
    }


def _validated_field(field: str, entry_id: str, check_id: str) -> str:
    if field not in CHECK_FIELDS:
        raise CorpusParseError(
            f"{entry_id}: check '{check_id}' references unknown field '{field}'. "
            f"Allowed fields: {', '.join(sorted(CHECK_FIELDS))}"
        )
    return field


def _parse_list_value(raw: str, entry_id: str, check_id: str, operator: str) -> list[str]:
    match = _LIST_PATTERN.match(raw)
    if not match:
        raise CorpusParseError(
            f"{entry_id}: check '{check_id}' operator '{operator}' needs a bracketed list, "
            f"got '{raw}'"
        )
    raw_items = [item.strip() for item in match.group("items").split(",")]
    raw_items = [item for item in raw_items if item]
    if not raw_items:
        raise CorpusParseError(f"{entry_id}: check '{check_id}' has an empty list value")
    return [_unquoted_value(item, entry_id, check_id) for item in raw_items]


def _unquoted_value(raw: str, entry_id: str, check_id: str) -> str:
    """Accept a quoted string verbatim, or an unquoted bare value; reject anything else.

    Quoting is the only way to carry spaces, which keeps composed expressions such
    as `a and b` out of the grammar.
    """
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        inner = raw[1:-1]
        if not inner:
            raise CorpusParseError(f"{entry_id}: check '{check_id}' has an empty quoted value")
        return inner
    if not _BARE_VALUE_PATTERN.match(raw):
        raise CorpusParseError(
            f"{entry_id}: check '{check_id}' value '{raw}' is neither a quoted string nor a "
            f"bare value; the check grammar has no expressions"
        )
    return raw


def _parse_scalar_value(raw: str, entry_id: str, check_id: str, operator: str) -> str:
    if not raw:
        raise CorpusParseError(
            f"{entry_id}: check '{check_id}' operator '{operator}' needs a value"
        )
    if _LIST_PATTERN.match(raw):
        raise CorpusParseError(
            f"{entry_id}: check '{check_id}' operator '{operator}' takes a single value, not a list"
        )
    return _unquoted_value(raw, entry_id, check_id)


def validate_checks(raw_checks: Any, entry_id: str) -> list[dict[str, Any]]:
    """Validate and parse the whole `checks` block of an entry."""
    if raw_checks is None:
        return []
    if not isinstance(raw_checks, list):
        raise CorpusParseError(
            f"{entry_id}: checks must be a list, got {type(raw_checks).__name__}"
        )

    parsed: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for position, raw_check in enumerate(raw_checks):
        if not isinstance(raw_check, dict):
            raise CorpusParseError(
                f"{entry_id}: check at position {position} must be a mapping with id and assert"
            )
        unknown = set(raw_check) - {"id", "assert"}
        if unknown:
            raise CorpusParseError(
                f"{entry_id}: check at position {position} has unknown keys "
                f"{sorted(unknown)}; only 'id' and 'assert' are allowed"
            )
        check_id = raw_check.get("id")
        if not isinstance(check_id, str) or not check_id.strip():
            raise CorpusParseError(f"{entry_id}: check at position {position} is missing an id")
        check_id = check_id.strip()
        if check_id in seen_ids:
            raise CorpusParseError(f"{entry_id}: duplicate check id '{check_id}'")
        seen_ids.add(check_id)

        if "assert" not in raw_check:
            raise CorpusParseError(f"{entry_id}: check '{check_id}' is missing an assert")

        predicate = parse_check_assertion(raw_check["assert"], entry_id, check_id)
        parsed.append({"id": check_id, "assert": raw_check["assert"].strip(), **predicate})

    return parsed


def validate_applies_to(raw_applies_to: Any, entry_id: str) -> dict[str, list[str]]:
    """Validate the `applies_to` scope rules against the closed key set.

    An absent or empty block yields {}, which matches no spec.
    """
    if raw_applies_to is None:
        return {}
    if not isinstance(raw_applies_to, dict):
        raise CorpusParseError(
            f"{entry_id}: applies_to must be a mapping, got {type(raw_applies_to).__name__}"
        )

    unknown = set(raw_applies_to) - APPLIES_TO_KEYS
    if unknown:
        raise CorpusParseError(
            f"{entry_id}: applies_to has unknown keys {sorted(unknown)}; "
            f"allowed keys: {', '.join(sorted(APPLIES_TO_KEYS))}"
        )

    validated: dict[str, list[str]] = {}
    for key, values in raw_applies_to.items():
        if values is None:
            continue
        if not isinstance(values, list):
            raise CorpusParseError(
                f"{entry_id}: applies_to.{key} must be a list, got {type(values).__name__}"
            )
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        if cleaned:
            validated[key] = cleaned

    return validated


def parse_entry_file(file_path: Path) -> dict[str, Any]:
    """Parse one corpus markdown file into a validated entry dict."""
    post = frontmatter.load(file_path)
    metadata = post.metadata

    missing = [key for key in REQUIRED_FRONTMATTER_KEYS if metadata.get(key) in (None, "")]
    if missing:
        raise CorpusParseError(f"{file_path}: missing required frontmatter keys {missing}")

    entry_id = str(metadata["id"]).strip()

    kind = str(metadata["kind"]).strip()
    if kind not in CorpusEntryKind.values:
        raise CorpusParseError(
            f"{entry_id}: unknown kind '{kind}'; allowed: {', '.join(CorpusEntryKind.values)}"
        )

    status = str(metadata.get("status", CorpusEntryStatus.ACTIVE)).strip()
    if status not in CorpusEntryStatus.values:
        raise CorpusParseError(
            f"{entry_id}: unknown status '{status}'; allowed: {', '.join(CorpusEntryStatus.values)}"
        )

    enforcement = str(metadata.get("enforcement", CorpusEnforcement.ADVISORY)).strip()
    if enforcement not in CorpusEnforcement.values:
        raise CorpusParseError(
            f"{entry_id}: unknown enforcement '{enforcement}'; "
            f"allowed: {', '.join(CorpusEnforcement.values)}"
        )

    version = metadata["version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise CorpusParseError(f"{entry_id}: version must be a positive integer, got {version!r}")

    effective = metadata.get("effective")
    if effective is not None and not isinstance(effective, date):
        raise CorpusParseError(
            f"{entry_id}: effective must be a YYYY-MM-DD date, got {effective!r}"
        )

    supersedes = metadata.get("supersedes")
    if supersedes is not None:
        supersedes = str(supersedes).strip()
        if not SUPERSEDES_PATTERN.match(supersedes):
            raise CorpusParseError(
                f"{entry_id}: supersedes must look like ENTRY-ID@VERSION, got '{supersedes}'"
            )

    title = str(metadata["title"]).strip()
    body = post.content.strip()
    applies_to = validate_applies_to(metadata.get("applies_to"), entry_id)
    checks = validate_checks(metadata.get("checks"), entry_id)

    content_hash = compute_content_hash(
        version_payload(
            kind=kind,
            title=title,
            body=body,
            applies_to=applies_to,
            checks=checks,
            enforcement=enforcement,
            effective=effective,
        )
    )

    return {
        "external_id": entry_id,
        "kind": kind,
        "title": title,
        "owner": str(metadata.get("owner", "")).strip(),
        "status": status,
        "version": version,
        "body": body,
        "content_hash": content_hash,
        "applies_to": applies_to,
        "checks": checks,
        "enforcement": enforcement,
        "effective_date": effective,
        "supersedes": supersedes,
        "source_file": str(file_path),
    }


class CorpusParser:
    """Parses a corpus directory into immutable versioned entries."""

    def parse_directory(self, corpus_dir: Path) -> list[dict[str, Any]]:
        """Parse every .md file under corpus_dir, sorted by path.

        Raises CorpusParseError on the first malformed file. A corpus that does
        not parse is not partially imported.
        """
        entries = [parse_entry_file(md_file) for md_file in sorted(corpus_dir.glob("**/*.md"))]

        seen: dict[str, str] = {}
        for entry in entries:
            external_id = entry["external_id"]
            if external_id in seen:
                raise CorpusParseError(
                    f"{external_id}: declared in both {seen[external_id]} "
                    f"and {entry['source_file']}"
                )
            seen[external_id] = entry["source_file"]

        return entries

    def import_to_database(self, corpus_dir: Path) -> dict[str, int]:
        """Parse and import a corpus directory idempotently.

        Returns counts of entries created, versions created, and versions that
        already matched byte for byte.
        """
        parsed = self.parse_directory(corpus_dir)
        return import_corpus_entries(parsed)


def import_corpus_entries(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Write parsed entry dicts to the database, enforcing version immutability."""
    counts = {"entries_created": 0, "versions_created": 0, "versions_unchanged": 0}
    versions_by_key: dict[tuple[str, int], CorpusEntryVersion] = {}

    for data in entries:
        entry, entry_created = CorpusEntry.objects.update_or_create(
            external_id=data["external_id"],
            defaults={
                "kind": data["kind"],
                "title": data["title"],
                "owner": data["owner"],
                "status": data["status"],
                "source_file": data["source_file"],
            },
        )
        if entry_created:
            counts["entries_created"] += 1

        stored = entry.versions.filter(version=data["version"]).first()
        if stored is None:
            version = CorpusEntryVersion.objects.create(
                entry=entry,
                version=data["version"],
                body=data["body"],
                content_hash=data["content_hash"],
                applies_to=data["applies_to"],
                checks=data["checks"],
                enforcement=data["enforcement"],
                effective_date=data["effective_date"],
                source_file=data["source_file"],
            )
            counts["versions_created"] += 1
        elif stored.content_hash != data["content_hash"]:
            raise CorpusVersionConflict(
                f"{data['external_id']} version {data['version']} changed without a version bump. "
                f"Stored hash {stored.content_hash}, incoming hash {data['content_hash']} "
                f"from {data['source_file']}. Bump `version` to record the new content."
            )
        else:
            version = stored
            counts["versions_unchanged"] += 1

        versions_by_key[(data["external_id"], data["version"])] = version

    _resolve_supersedes(entries, versions_by_key)
    return counts


def _resolve_supersedes(
    entries: list[dict[str, Any]],
    versions_by_key: dict[tuple[str, int], CorpusEntryVersion],
) -> None:
    for data in entries:
        if data["supersedes"] is None:
            continue

        match = SUPERSEDES_PATTERN.match(data["supersedes"])
        target_key = (match.group("entry_id"), int(match.group("version")))
        target = versions_by_key.get(target_key)

        if target is None:
            target = CorpusEntryVersion.objects.filter(
                entry__external_id=target_key[0], version=target_key[1]
            ).first()

        if target is None:
            raise CorpusParseError(
                f"{data['external_id']}: supersedes '{data['supersedes']}' names a version "
                f"that does not exist in the corpus or the database"
            )

        version = versions_by_key[(data["external_id"], data["version"])]
        if version.supersedes_id != target.pk:
            version.supersedes = target
            version.save(update_fields=["supersedes"])

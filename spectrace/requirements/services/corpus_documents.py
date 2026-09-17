"""Reading corpus documents from disk, with no database attached.

`corpus_parser.py` re-exports every name here and adds the writes on top, so the
parse and validate half runs where there is no Django.
"""

import hashlib
import json
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

CORPUS_ENTRY_KINDS = ("standard", "decision", "commitment")
CORPUS_ENTRY_STATUSES = ("active", "superseded", "retired")
CORPUS_ENFORCEMENTS = ("advisory", "blocking")

APPLIES_TO_KEYS = frozenset({"tags", "components", "paths", "requirement_ids"})

CHECK_KEYS = frozenset({"id", "assert", "renamed_from"})

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


class CorpusCheckLineageError(CorpusParseError):
    """A new version dropped or renamed a check id without declaring the change."""


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
    """Validate and parse the whole `checks` block of an entry.

    A check may carry `renamed_from`, naming the id it held in the previous
    version. The key is stored on the check, so a consumer holding the old id can
    follow the rename forward with `resolve_check_id`.
    """
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
        unknown = set(raw_check) - CHECK_KEYS
        if unknown:
            raise CorpusParseError(
                f"{entry_id}: check at position {position} has unknown keys "
                f"{sorted(unknown)}; allowed keys: {', '.join(sorted(CHECK_KEYS))}"
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
        check = {"id": check_id, "assert": raw_check["assert"].strip(), **predicate}

        renamed_from = raw_check.get("renamed_from")
        if renamed_from is not None:
            if not isinstance(renamed_from, str) or not renamed_from.strip():
                raise CorpusParseError(
                    f"{entry_id}: check '{check_id}' renamed_from must be a non-empty check id, "
                    f"got {renamed_from!r}"
                )
            check["renamed_from"] = renamed_from.strip()

        parsed.append(check)

    return parsed


def validate_retired_checks(raw_retired: Any, entry_id: str) -> list[str]:
    """Validate the entry-level `retired_checks` block.

    Each id names a check the previous version defined and this version drops on
    purpose. An absent block yields [], which forbids dropping anything.
    """
    if raw_retired is None:
        return []
    if not isinstance(raw_retired, list):
        raise CorpusParseError(
            f"{entry_id}: retired_checks must be a list, got {type(raw_retired).__name__}"
        )

    retired: list[str] = []
    for position, raw_id in enumerate(raw_retired):
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise CorpusParseError(
                f"{entry_id}: retired_checks entry at position {position} must be a check id, "
                f"got {raw_id!r}"
            )
        retired_id = raw_id.strip()
        if retired_id in retired:
            raise CorpusParseError(f"{entry_id}: duplicate retired_checks entry '{retired_id}'")
        retired.append(retired_id)

    return retired


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


def validate_check_lineage(
    data: dict[str, Any], previous_version: int, previous_checks: Sequence[dict[str, Any]]
) -> None:
    """Hold check ids stable from one version of an entry to the next.

    A finding cites `ENTRY-ID#check-id` and carries the version beside it, never
    inside it, so a check id that disappears breaks every reference to it. This
    version must therefore account for each id the previous version defined:
    keep it, replace it with a check declaring `renamed_from`, or name it in
    `retired_checks`. Silence raises CorpusCheckLineageError.
    """
    entry_id = data["external_id"]
    version = data["version"]
    previous_ids = {check["id"] for check in previous_checks}
    current_ids = {check["id"] for check in data["checks"]}
    renames = {
        check["renamed_from"]: check["id"] for check in data["checks"] if "renamed_from" in check
    }
    retired = set(data["retired_checks"])

    for old_id, new_id in sorted(renames.items()):
        if old_id not in previous_ids:
            raise CorpusCheckLineageError(
                f"{entry_id} version {version}: check '{new_id}' declares renamed_from "
                f"'{old_id}', which version {previous_version} does not define"
            )
        if old_id in current_ids:
            raise CorpusCheckLineageError(
                f"{entry_id} version {version}: check '{new_id}' declares renamed_from "
                f"'{old_id}', which this version still defines as a check of its own"
            )

    unknown_retired = sorted(retired - previous_ids)
    if unknown_retired:
        raise CorpusCheckLineageError(
            f"{entry_id} version {version}: retired_checks names "
            f"{_rendered_ids(unknown_retired)}, which version {previous_version} does not define"
        )

    undeclared = sorted(previous_ids - current_ids - set(renames) - retired)
    if not undeclared:
        return

    added = sorted(current_ids - previous_ids - set(renames.values()))
    if added:
        raise CorpusCheckLineageError(
            f"{entry_id} version {version} drops check {_rendered_ids(undeclared)} while adding "
            f"{_rendered_ids(added)}. Findings cite {entry_id}#{undeclared[0]} without a version, "
            f"so declare `renamed_from: {undeclared[0]}` on check '{added[0]}', or list "
            f"{_rendered_ids(undeclared)} under `retired_checks`."
        )

    raise CorpusCheckLineageError(
        f"{entry_id} version {version} drops check {_rendered_ids(undeclared)}, which version "
        f"{previous_version} defines, and declares nothing. Findings cite "
        f"{entry_id}#{undeclared[0]} without a version, so list {_rendered_ids(undeclared)} under "
        f"`retired_checks`, or declare `renamed_from: {undeclared[0]}` on the replacing check."
    )


def _rendered_ids(check_ids: Sequence[str]) -> str:
    return ", ".join(f"'{check_id}'" for check_id in check_ids)


def parse_entry_file(file_path: Path) -> dict[str, Any]:
    """Parse one corpus markdown file into a validated entry dict."""
    post = frontmatter.load(file_path)
    metadata = post.metadata

    missing = [key for key in REQUIRED_FRONTMATTER_KEYS if metadata.get(key) in (None, "")]
    if missing:
        raise CorpusParseError(f"{file_path}: missing required frontmatter keys {missing}")

    entry_id = str(metadata["id"]).strip()

    kind = str(metadata["kind"]).strip()
    if kind not in CORPUS_ENTRY_KINDS:
        raise CorpusParseError(
            f"{entry_id}: unknown kind '{kind}'; allowed: {', '.join(CORPUS_ENTRY_KINDS)}"
        )

    status = str(metadata.get("status", "active")).strip()
    if status not in CORPUS_ENTRY_STATUSES:
        raise CorpusParseError(
            f"{entry_id}: unknown status '{status}'; allowed: {', '.join(CORPUS_ENTRY_STATUSES)}"
        )

    enforcement = str(metadata.get("enforcement", "advisory")).strip()
    if enforcement not in CORPUS_ENFORCEMENTS:
        raise CorpusParseError(
            f"{entry_id}: unknown enforcement '{enforcement}'; "
            f"allowed: {', '.join(CORPUS_ENFORCEMENTS)}"
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
    retired_checks = validate_retired_checks(metadata.get("retired_checks"), entry_id)

    still_defined = sorted({check["id"] for check in checks} & set(retired_checks))
    if still_defined:
        raise CorpusParseError(
            f"{entry_id}: retired_checks names {_rendered_ids(still_defined)}, "
            f"which this version still defines"
        )

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
        "retired_checks": retired_checks,
        "enforcement": enforcement,
        "effective_date": effective,
        "supersedes": supersedes,
        "source_file": str(file_path),
    }


def parse_corpus_directory(corpus_dir: Path) -> list[dict[str, Any]]:
    """Parse every .md file under corpus_dir, sorted by path.

    Raises CorpusParseError on the first malformed file, so a corpus that does
    not parse is never partially imported, and on an id declared twice.
    """
    entries = [parse_entry_file(md_file) for md_file in sorted(corpus_dir.glob("**/*.md"))]

    seen: dict[str, str] = {}
    for entry in entries:
        external_id = entry["external_id"]
        if external_id in seen:
            raise CorpusParseError(
                f"{external_id}: declared in both {seen[external_id]} and {entry['source_file']}"
            )
        seen[external_id] = entry["source_file"]

    return entries

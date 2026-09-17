"""Corpus file parser: reads corpus/**/*.md into CorpusEntry and CorpusEntryVersion.

The parser owns two contracts the rest of the milestone rests on:

1. Versions are immutable. Re-parsing a file whose content hash differs from the
   stored hash for the same version number raises CorpusVersionConflict.
2. The `checks` predicate grammar is closed and validated here, at parse time.
   Unknown fields or operators reject the file. Nothing is ever evaluated as an
   expression; the parsed structure is stored for the check evaluator to read.
3. Check ids are stable across versions. A finding cites `ENTRY-ID#check-id`
   with no version in it, so a new version that drops or renames a check id
   raises CorpusCheckLineageError unless the file declares the change —
   `renamed_from` on the replacing check, or `retired_checks` on the entry.
"""

from pathlib import Path
from typing import Any

from requirements.models import CorpusEntry, CorpusEntryVersion
from requirements.services.corpus_documents import (  # noqa: F401
    APPLIES_TO_KEYS,
    CHECK_FIELDS,
    CHECK_KEYS,
    CHECK_OPERATORS,
    REQUIRED_FRONTMATTER_KEYS,
    SUPERSEDES_PATTERN,
    CorpusCheckLineageError,
    CorpusParseError,
    CorpusVersionConflict,
    _rendered_ids,
    compute_content_hash,
    parse_check_assertion,
    parse_corpus_directory,
    parse_entry_file,
    validate_applies_to,
    validate_check_lineage,
    validate_checks,
    validate_retired_checks,
    version_payload,
)


def resolve_check_id(entry_id: str, check_id: str) -> str:
    """The id a check known as `check_id` carries in the newest stored version.

    Follows `renamed_from` declarations forward, so a consumer holding the
    identifier a finding cited before a rename lands on the current check.
    """
    current = check_id
    for version in CorpusEntryVersion.objects.filter(entry__external_id=entry_id).order_by(
        "version"
    ):
        for check in version.checks:
            if check.get("renamed_from") == current:
                current = check["id"]
    return current


class CorpusParser:
    """Parses a corpus directory into immutable versioned entries."""

    def parse_directory(self, corpus_dir: Path) -> list[dict[str, Any]]:
        """Parse every .md file under corpus_dir, sorted by path."""
        return parse_corpus_directory(corpus_dir)

    def import_to_database(self, corpus_dir: Path) -> dict[str, int]:
        """Parse and import a corpus directory idempotently.

        Returns counts of entries created, versions created, and versions that
        already matched byte for byte.
        """
        parsed = self.parse_directory(corpus_dir)
        return import_corpus_entries(parsed)


def import_corpus_entries(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Write parsed entry dicts to the database, enforcing version immutability.

    An incoming version with a stored predecessor must account for that
    predecessor's check ids before anything is written; see
    `validate_check_lineage`.
    """
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

        previous = entry.versions.filter(version__lt=data["version"]).order_by("-version").first()
        if previous is not None:
            validate_check_lineage(data, previous.version, previous.checks)

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

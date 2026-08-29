"""Tests for the corpus parser, its closed check grammar, and version immutability."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from requirements.models import (
    CorpusEntry,
    CorpusEntryKind,
    CorpusEntryStatus,
    CorpusEntryVersion,
    CorpusSnapshot,
)
from requirements.services.corpus_parser import (
    CorpusParseError,
    CorpusParser,
    CorpusVersionConflict,
    parse_check_assertion,
    validate_applies_to,
    validate_checks,
)

ENTRY_TEMPLATE = """---
id: {entry_id}
kind: {kind}
title: {title}
version: {version}
status: {status}
supersedes: {supersedes}
effective: 2026-01-15
owner: platform
applies_to:
  tags: [platform, security]
  paths: ["specs/platform/**"]
checks:
  - id: risk-classified
    assert: risk_level in [critical, high]
---

{body}
"""


@pytest.fixture
def make_corpus_dir(tmp_path):
    """Factory writing corpus markdown files into a temporary corpus directory."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()

    def _write(
        filename: str,
        entry_id: str = "STD-TEST-001",
        kind: str = "standard",
        title: str = "Test standard",
        version: int = 1,
        status: str = "active",
        supersedes: str = "null",
        body: str = "Original body text.",
        content: str | None = None,
    ):
        path = corpus_dir / filename
        path.write_text(
            content
            if content is not None
            else ENTRY_TEMPLATE.format(
                entry_id=entry_id,
                kind=kind,
                title=title,
                version=version,
                status=status,
                supersedes=supersedes,
                body=body,
            )
        )
        return corpus_dir

    return _write


def test_import_to_database__creates_entry_and_version(db, make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md")

    counts = CorpusParser().import_to_database(corpus_dir)

    assert counts == {"entries_created": 1, "versions_created": 1, "versions_unchanged": 0}
    entry = CorpusEntry.objects.get(external_id="STD-TEST-001")
    assert entry.kind == CorpusEntryKind.STANDARD
    assert entry.status == CorpusEntryStatus.ACTIVE
    assert entry.versions.count() == 1


def test_import_to_database__is_idempotent_on_second_run(db, make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md")
    parser = CorpusParser()
    parser.import_to_database(corpus_dir)

    counts = parser.import_to_database(corpus_dir)

    assert counts == {"entries_created": 0, "versions_created": 0, "versions_unchanged": 1}
    assert CorpusEntryVersion.objects.count() == 1


def test_import_to_database__raises_conflict_when_body_changes_without_version_bump(
    db, make_corpus_dir
):
    corpus_dir = make_corpus_dir("std.md", body="Original body text.")
    parser = CorpusParser()
    parser.import_to_database(corpus_dir)
    stored_hash = CorpusEntryVersion.objects.get().content_hash
    make_corpus_dir("std.md", body="Silently edited body text.")

    with pytest.raises(CorpusVersionConflict) as exc_info:
        parser.import_to_database(corpus_dir)

    message = str(exc_info.value)
    assert "STD-TEST-001" in message
    assert "version 1" in message
    assert stored_hash in message
    assert message.count(stored_hash) == 1
    assert CorpusEntryVersion.objects.count() == 1


def test_import_to_database__raises_conflict_when_checks_change_without_version_bump(
    db, make_corpus_dir
):
    corpus_dir = make_corpus_dir("std.md")
    parser = CorpusParser()
    parser.import_to_database(corpus_dir)
    edited = ENTRY_TEMPLATE.format(
        entry_id="STD-TEST-001",
        kind="standard",
        title="Test standard",
        version=1,
        status="active",
        supersedes="null",
        body="Original body text.",
    ).replace("risk_level in [critical, high]", "risk_level in [critical]")
    make_corpus_dir("std.md", content=edited)

    with pytest.raises(CorpusVersionConflict):
        parser.import_to_database(corpus_dir)


def test_import_to_database__version_bump_leaves_prior_version_intact(db, make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md", version=1, body="Original body text.")
    parser = CorpusParser()
    parser.import_to_database(corpus_dir)
    original_hash = CorpusEntryVersion.objects.get(version=1).content_hash
    make_corpus_dir("std.md", version=2, body="Revised body text.")

    counts = parser.import_to_database(corpus_dir)

    assert counts["versions_created"] == 1
    assert CorpusEntryVersion.objects.count() == 2
    first = CorpusEntryVersion.objects.get(version=1)
    assert first.content_hash == original_hash
    assert first.body == "Original body text."
    assert CorpusEntryVersion.objects.get(version=2).body == "Revised body text."


def test_import_to_database__resolves_supersedes_chain(db, make_corpus_dir):
    make_corpus_dir("old.md", entry_id="DEC-TEST-001", kind="decision", status="superseded")
    corpus_dir = make_corpus_dir(
        "new.md", entry_id="DEC-TEST-002", kind="decision", supersedes="DEC-TEST-001@1"
    )

    CorpusParser().import_to_database(corpus_dir)

    newer = CorpusEntryVersion.objects.get(entry__external_id="DEC-TEST-002")
    assert newer.supersedes.entry.external_id == "DEC-TEST-001"
    assert newer.supersedes.version == 1
    assert newer.supersedes.superseded_by.get() == newer


def test_import_to_database__raises_when_supersedes_target_missing(db, make_corpus_dir):
    corpus_dir = make_corpus_dir(
        "new.md", entry_id="DEC-TEST-002", kind="decision", supersedes="DEC-TEST-404@7"
    )

    with pytest.raises(CorpusParseError, match="DEC-TEST-404@7"):
        CorpusParser().import_to_database(corpus_dir)


def test_parse_directory__raises_when_entry_id_declared_twice(make_corpus_dir):
    make_corpus_dir("a.md", entry_id="STD-TEST-001")
    corpus_dir = make_corpus_dir("b.md", entry_id="STD-TEST-001")

    with pytest.raises(CorpusParseError, match="declared in both"):
        CorpusParser().parse_directory(corpus_dir)


def test_parse_directory__stores_parsed_predicate_structure(make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md")

    entries = CorpusParser().parse_directory(corpus_dir)

    assert entries[0]["checks"] == [
        {
            "id": "risk-classified",
            "assert": "risk_level in [critical, high]",
            "field": "risk_level",
            "operator": "in",
            "value": ["critical", "high"],
        }
    ]


def test_parse_directory__raises_when_kind_unknown(make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md", kind="policy")

    with pytest.raises(CorpusParseError, match="unknown kind 'policy'"):
        CorpusParser().parse_directory(corpus_dir)


def test_parse_directory__raises_when_version_missing(make_corpus_dir):
    corpus_dir = make_corpus_dir(
        "std.md",
        content="---\nid: STD-TEST-001\nkind: standard\ntitle: No version\n---\n\nBody.\n",
    )

    with pytest.raises(CorpusParseError, match="missing required frontmatter keys"):
        CorpusParser().parse_directory(corpus_dir)


def test_parse_directory__raises_when_version_not_positive_integer(make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md", version="one")

    with pytest.raises(CorpusParseError, match="version must be a positive integer"):
        CorpusParser().parse_directory(corpus_dir)


@pytest.mark.parametrize(
    "assertion,expected",
    [
        (
            "risk_level in [critical, high]",
            {"field": "risk_level", "operator": "in", "value": ["critical", "high"]},
        ),
        (
            "verification_method not in [unspecified]",
            {"field": "verification_method", "operator": "not in", "value": ["unspecified"]},
        ),
        ("component == auth", {"field": "component", "operator": "==", "value": "auth"}),
        (
            "component != nightly_batch",
            {"field": "component", "operator": "!=", "value": "nightly_batch"},
        ),
        ("tags contains billing", {"field": "tags", "operator": "contains", "value": "billing"}),
        (
            "tags not contains legacy",
            {"field": "tags", "operator": "not contains", "value": "legacy"},
        ),
        ("timing is set", {"field": "timing", "operator": "is set", "value": None}),
        (
            "depends_on is not set",
            {"field": "depends_on", "operator": "is not set", "value": None},
        ),
    ],
)
def test_parse_check_assertion__accepts_every_grammar_form(assertion, expected):
    assert parse_check_assertion(assertion, "STD-TEST-001", "check-1") == expected


def test_parse_check_assertion__rejects_unknown_field():
    with pytest.raises(CorpusParseError, match="unknown field 'blast_radius'"):
        parse_check_assertion("blast_radius in [high]", "STD-TEST-001", "check-1")


def test_parse_check_assertion__rejects_unknown_operator():
    with pytest.raises(CorpusParseError, match="does not match the check grammar"):
        parse_check_assertion("risk_level ~= critical", "STD-TEST-001", "check-1")


def test_parse_check_assertion__rejects_python_expression():
    with pytest.raises(CorpusParseError, match="does not match the check grammar"):
        parse_check_assertion("__import__('os').system('ls')", "STD-TEST-001", "check-1")


@pytest.mark.parametrize(
    "assertion",
    [
        "risk_level in [high] and component == auth",
        "component == auth and tags contains billing",
        "component == auth or component == api",
        "tags contains a and b",
    ],
)
def test_parse_check_assertion__rejects_boolean_composition(assertion):
    with pytest.raises(CorpusParseError):
        parse_check_assertion(assertion, "STD-TEST-001", "check-1")


def test_parse_check_assertion__accepts_quoted_value_with_spaces():
    assert parse_check_assertion('timing == "within 2 seconds"', "STD-TEST-001", "check-1") == {
        "field": "timing",
        "operator": "==",
        "value": "within 2 seconds",
    }


def test_parse_check_assertion__rejects_unquoted_value_with_spaces():
    with pytest.raises(CorpusParseError, match="neither a quoted string nor a bare value"):
        parse_check_assertion("timing == within 2 seconds", "STD-TEST-001", "check-1")


def test_parse_check_assertion__rejects_list_for_scalar_operator():
    with pytest.raises(CorpusParseError, match="takes a single value, not a list"):
        parse_check_assertion("component == [auth, api]", "STD-TEST-001", "check-1")


def test_parse_check_assertion__rejects_bare_value_for_list_operator():
    with pytest.raises(CorpusParseError, match="needs a bracketed list"):
        parse_check_assertion("risk_level in critical", "STD-TEST-001", "check-1")


def test_parse_check_assertion__rejects_empty_list():
    with pytest.raises(CorpusParseError, match="empty list value"):
        parse_check_assertion("risk_level in []", "STD-TEST-001", "check-1")


def test_parse_check_assertion__rejects_non_string_assertion():
    with pytest.raises(CorpusParseError, match="assert must be a string"):
        parse_check_assertion(42, "STD-TEST-001", "check-1")


def test_validate_checks__rejects_duplicate_check_id():
    raw = [
        {"id": "risk-classified", "assert": "risk_level in [high]"},
        {"id": "risk-classified", "assert": "risk_level in [critical]"},
    ]

    with pytest.raises(CorpusParseError, match="duplicate check id 'risk-classified'"):
        validate_checks(raw, "STD-TEST-001")


def test_validate_checks__rejects_unknown_check_key():
    raw = [{"id": "risk-classified", "assert": "risk_level in [high]", "severity": "blocker"}]

    with pytest.raises(CorpusParseError, match="unknown keys"):
        validate_checks(raw, "STD-TEST-001")


def test_validate_checks__rejects_check_without_id():
    with pytest.raises(CorpusParseError, match="missing an id"):
        validate_checks([{"assert": "risk_level in [high]"}], "STD-TEST-001")


def test_validate_checks__returns_empty_list_when_absent():
    assert validate_checks(None, "STD-TEST-001") == []


def test_validate_applies_to__rejects_unknown_scope_key():
    with pytest.raises(CorpusParseError, match="unknown keys"):
        validate_applies_to({"teams": ["platform"]}, "STD-TEST-001")


def test_validate_applies_to__returns_empty_dict_when_absent():
    assert validate_applies_to(None, "STD-TEST-001") == {}


def test_validate_applies_to__drops_empty_lists():
    assert validate_applies_to({"tags": ["platform"], "paths": []}, "STD-TEST-001") == {
        "tags": ["platform"]
    }


def test_validate_applies_to__rejects_non_list_value():
    with pytest.raises(CorpusParseError, match="applies_to.tags must be a list"):
        validate_applies_to({"tags": "platform"}, "STD-TEST-001")


def test_parse_corpus_command__imports_entries(db, make_corpus_dir, capsys):
    corpus_dir = make_corpus_dir("std.md")

    call_command("parse_corpus", str(corpus_dir))

    assert CorpusEntry.objects.count() == 1
    assert "Imported 1 new entries, 1 new versions" in capsys.readouterr().out


def test_parse_corpus_command__dry_run_writes_nothing(db, make_corpus_dir, capsys):
    corpus_dir = make_corpus_dir("std.md")

    call_command("parse_corpus", str(corpus_dir), "--dry-run")

    assert CorpusEntry.objects.count() == 0
    assert "STD-TEST-001@1 [standard/active]" in capsys.readouterr().out


def test_parse_corpus_command__raises_command_error_on_version_conflict(db, make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md", body="Original body text.")
    call_command("parse_corpus", str(corpus_dir))
    make_corpus_dir("std.md", body="Silently edited body text.")

    with pytest.raises(CommandError, match="without a version bump"):
        call_command("parse_corpus", str(corpus_dir))


def test_parse_corpus_command__rejects_clear_flag(db, make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md")

    with pytest.raises(CommandError, match="--clear is not supported"):
        call_command("parse_corpus", str(corpus_dir), "--clear")


def test_capture__is_deterministic_regardless_of_input_order(db, make_corpus_dir):
    make_corpus_dir("a.md", entry_id="STD-TEST-001")
    corpus_dir = make_corpus_dir("b.md", entry_id="STD-TEST-002")
    CorpusParser().import_to_database(corpus_dir)
    versions = list(CorpusEntryVersion.objects.all())

    first = CorpusSnapshot.capture(versions)
    second = CorpusSnapshot.capture(list(reversed(versions)))

    assert first.pk == second.pk
    assert CorpusSnapshot.objects.count() == 1
    assert first.entry_versions.count() == 2


def test_capture__changes_hash_when_a_version_changes(db, make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md", version=1)
    parser = CorpusParser()
    parser.import_to_database(corpus_dir)
    before = CorpusSnapshot.capture(CorpusEntryVersion.objects.all())
    make_corpus_dir("std.md", version=2, body="Revised body text.")
    parser.import_to_database(corpus_dir)

    after = CorpusSnapshot.capture(CorpusEntryVersion.objects.all())

    assert before.snapshot_hash != after.snapshot_hash


def test_current_version__returns_highest_version(db, make_corpus_dir):
    corpus_dir = make_corpus_dir("std.md", version=1)
    parser = CorpusParser()
    parser.import_to_database(corpus_dir)
    make_corpus_dir("std.md", version=2, body="Revised body text.")
    parser.import_to_database(corpus_dir)

    assert CorpusEntry.objects.get().current_version.version == 2

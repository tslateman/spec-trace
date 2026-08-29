"""Tests for the corpus applicability resolver."""

import hashlib

import pytest

from requirements.models import (
    CorpusEntry,
    CorpusEntryKind,
    CorpusEntryStatus,
    CorpusEntryVersion,
    CorpusSnapshot,
    Requirement,
)
from requirements.services.corpus_matcher import (
    SCOPE_KEYS,
    ApplicableEntryVersion,
    MatchReason,
    build_lineage,
    match_entry_version,
    resolve_applicable_entries,
)


@pytest.fixture
def make_entry_version(db):
    """Factory creating one CorpusEntryVersion with the given scope rules."""

    def _make(
        entry_id: str,
        applies_to: dict | None = None,
        version: int = 1,
        status: str = CorpusEntryStatus.ACTIVE,
        kind: str = CorpusEntryKind.STANDARD,
        supersedes: CorpusEntryVersion | None = None,
    ) -> CorpusEntryVersion:
        entry, _ = CorpusEntry.objects.update_or_create(
            external_id=entry_id,
            defaults={
                "kind": kind,
                "title": f"{entry_id} title",
                "owner": "platform",
                "status": status,
                "source_file": f"corpus/{entry_id.lower()}.md",
            },
        )
        digest = hashlib.sha256(f"{entry_id}@{version}".encode()).hexdigest()
        return CorpusEntryVersion.objects.create(
            entry=entry,
            version=version,
            body=f"Body of {entry_id} at {version}.",
            content_hash=digest,
            applies_to=applies_to or {},
            checks=[],
            supersedes=supersedes,
            source_file=f"corpus/{entry_id.lower()}.md",
        )

    return _make


@pytest.fixture
def platform_requirement(db):
    """A single requirement tagged platform, in specs/platform/."""
    return Requirement.add_root(
        external_id="REQ-PLAT-001",
        title="Tenant isolation",
        status="active",
        source_file="specs/platform/tenant_isolation.md",
        tags=["platform", "security"],
        component="storage",
    )


@pytest.fixture
def requirement_tree(db):
    """A three-level tree: only the root carries tags, path, and component."""
    root = Requirement.add_root(
        external_id="REQ-ROOT-001",
        title="Platform root",
        status="active",
        source_file="specs/platform/root.md",
        tags=["platform"],
        component="storage",
    )
    root.add_child(
        external_id="REQ-MID-001",
        title="Middle",
        status="active",
        source_file="specs/other/middle.md",
        tags=[],
    )
    middle = Requirement.objects.get(external_id="REQ-MID-001")
    middle.add_child(
        external_id="REQ-LEAF-001",
        title="Leaf",
        status="active",
        source_file="specs/other/leaf.md",
        tags=[],
    )
    leaf = Requirement.objects.get(external_id="REQ-LEAF-001")
    return Requirement.objects.get(external_id="REQ-ROOT-001"), middle, leaf


def test_resolve_applicable_entries__matches_on_tag(make_entry_version, platform_requirement):
    version = make_entry_version("STD-SEC-001", {"tags": ["security"]})
    snapshot = CorpusSnapshot.capture([version])

    applicable = resolve_applicable_entries(platform_requirement, snapshot)

    assert [item.entry_id for item in applicable] == ["STD-SEC-001"]
    reason = applicable[0].reasons[0]
    assert reason.scope_key == "tags"
    assert reason.pattern == "security"
    assert reason.matched_value == "security"
    assert reason.matched_requirement_id == "REQ-PLAT-001"
    assert reason.inherited is False


def test_resolve_applicable_entries__matches_nothing_when_applies_to_is_empty(
    make_entry_version, platform_requirement
):
    version = make_entry_version("STD-SEC-001", {})
    snapshot = CorpusSnapshot.capture([version])

    assert resolve_applicable_entries(platform_requirement, snapshot) == []


def test_resolve_applicable_entries__ignores_absent_scope_keys(
    make_entry_version, platform_requirement
):
    version = make_entry_version("STD-SEC-001", {"components": ["metering"]})
    snapshot = CorpusSnapshot.capture([version])

    assert resolve_applicable_entries(platform_requirement, snapshot) == []


def test_resolve_applicable_entries__matches_source_file_with_glob(
    make_entry_version, platform_requirement
):
    version = make_entry_version("STD-SEC-001", {"paths": ["specs/platform/**"]})
    snapshot = CorpusSnapshot.capture([version])

    applicable = resolve_applicable_entries(platform_requirement, snapshot)

    assert applicable[0].reasons[0].scope_key == "paths"
    assert applicable[0].reasons[0].matched_value == "specs/platform/tenant_isolation.md"


def test_resolve_applicable_entries__rejects_path_glob_outside_the_scope(
    make_entry_version, platform_requirement
):
    version = make_entry_version("STD-SEC-001", {"paths": ["specs/billing/**"]})
    snapshot = CorpusSnapshot.capture([version])

    assert resolve_applicable_entries(platform_requirement, snapshot) == []


def test_resolve_applicable_entries__matches_external_id_with_glob(
    make_entry_version, platform_requirement
):
    version = make_entry_version("STD-SEC-001", {"requirement_ids": ["REQ-PLAT-*"]})
    snapshot = CorpusSnapshot.capture([version])

    applicable = resolve_applicable_entries(platform_requirement, snapshot)

    assert applicable[0].reasons[0].scope_key == "requirement_ids"
    assert applicable[0].reasons[0].pattern == "REQ-PLAT-*"
    assert applicable[0].reasons[0].matched_value == "REQ-PLAT-001"


def test_resolve_applicable_entries__matches_component_exactly(
    make_entry_version, platform_requirement
):
    exact = make_entry_version("STD-SEC-001", {"components": ["storage"]})
    prefix = make_entry_version("STD-SEC-002", {"components": ["stor"]})
    snapshot = CorpusSnapshot.capture([exact, prefix])

    applicable = resolve_applicable_entries(platform_requirement, snapshot)

    assert [item.entry_id for item in applicable] == ["STD-SEC-001"]


def test_resolve_applicable_entries__records_every_matching_scope_key(
    make_entry_version, platform_requirement
):
    version = make_entry_version(
        "STD-SEC-001",
        {
            "tags": ["platform", "security", "absent"],
            "components": ["storage"],
            "paths": ["specs/platform/**"],
            "requirement_ids": ["REQ-PLAT-001"],
        },
    )
    snapshot = CorpusSnapshot.capture([version])

    applicable = resolve_applicable_entries(platform_requirement, snapshot)

    assert applicable[0].matched_scope_keys == SCOPE_KEYS
    assert [(reason.scope_key, reason.pattern) for reason in applicable[0].reasons] == [
        ("tags", "platform"),
        ("tags", "security"),
        ("components", "storage"),
        ("paths", "specs/platform/**"),
        ("requirement_ids", "REQ-PLAT-001"),
    ]


def test_resolve_applicable_entries__inherits_ancestor_match_down_the_tree(
    make_entry_version, requirement_tree
):
    _root, _middle, leaf = requirement_tree
    version = make_entry_version("STD-SEC-001", {"tags": ["platform"]})
    snapshot = CorpusSnapshot.capture([version])

    applicable = resolve_applicable_entries(leaf, snapshot)

    assert [item.entry_id for item in applicable] == ["STD-SEC-001"]
    reason = applicable[0].reasons[0]
    assert reason.inherited is True
    assert reason.matched_requirement_id == "REQ-ROOT-001"


def test_resolve_applicable_entries__orders_reasons_nearest_requirement_first(
    make_entry_version, requirement_tree
):
    _root, _middle, leaf = requirement_tree
    version = make_entry_version(
        "STD-SEC-001", {"requirement_ids": ["REQ-LEAF-001", "REQ-MID-001", "REQ-ROOT-001"]}
    )
    snapshot = CorpusSnapshot.capture([version])

    applicable = resolve_applicable_entries(leaf, snapshot)

    assert [reason.matched_requirement_id for reason in applicable[0].reasons] == [
        "REQ-LEAF-001",
        "REQ-MID-001",
        "REQ-ROOT-001",
    ]
    assert [reason.inherited for reason in applicable[0].reasons] == [False, True, True]


def test_resolve_applicable_entries__does_not_inherit_upward(make_entry_version, requirement_tree):
    root, _middle, _leaf = requirement_tree
    version = make_entry_version("STD-SEC-001", {"requirement_ids": ["REQ-LEAF-001"]})
    snapshot = CorpusSnapshot.capture([version])

    assert resolve_applicable_entries(root, snapshot) == []


def test_resolve_applicable_entries__skips_retired_entries(
    make_entry_version, platform_requirement
):
    retired = make_entry_version(
        "STD-SEC-001", {"tags": ["platform"]}, status=CorpusEntryStatus.RETIRED
    )
    active = make_entry_version("STD-SEC-002", {"tags": ["platform"]})
    snapshot = CorpusSnapshot.capture([retired, active])

    applicable = resolve_applicable_entries(platform_requirement, snapshot)

    assert [item.entry_id for item in applicable] == ["STD-SEC-002"]


def test_resolve_applicable_entries__skips_version_superseded_inside_the_snapshot(
    make_entry_version, platform_requirement
):
    old = make_entry_version(
        "DEC-BILL-001",
        {"tags": ["platform"]},
        status=CorpusEntryStatus.SUPERSEDED,
        kind=CorpusEntryKind.DECISION,
    )
    new = make_entry_version(
        "DEC-BILL-002",
        {"tags": ["platform"]},
        kind=CorpusEntryKind.DECISION,
        supersedes=old,
    )
    snapshot = CorpusSnapshot.capture([old, new])

    applicable = resolve_applicable_entries(platform_requirement, snapshot)

    assert [item.entry_id for item in applicable] == ["DEC-BILL-002"]


def test_resolve_applicable_entries__keeps_superseded_version_when_snapshot_predates_replacement(
    make_entry_version, platform_requirement
):
    old = make_entry_version(
        "DEC-BILL-001",
        {"tags": ["platform"]},
        status=CorpusEntryStatus.SUPERSEDED,
        kind=CorpusEntryKind.DECISION,
    )
    make_entry_version(
        "DEC-BILL-002",
        {"tags": ["platform"]},
        kind=CorpusEntryKind.DECISION,
        supersedes=old,
    )
    pinned = CorpusSnapshot.capture([old])

    applicable = resolve_applicable_entries(platform_requirement, pinned)

    assert [item.entry_id for item in applicable] == ["DEC-BILL-001"]


def test_resolve_applicable_entries__applies_only_the_highest_version_of_an_entry(
    make_entry_version, platform_requirement
):
    third = make_entry_version("STD-SEC-001", {"tags": ["platform"]}, version=3)
    fourth = make_entry_version("STD-SEC-001", {"tags": ["platform"]}, version=4)
    snapshot = CorpusSnapshot.capture([third, fourth])

    applicable = resolve_applicable_entries(platform_requirement, snapshot)

    assert [(item.entry_id, item.entry_version.version) for item in applicable] == [
        ("STD-SEC-001", 4)
    ]


def test_resolve_applicable_entries__resolves_the_version_current_in_a_pinned_snapshot(
    make_entry_version, platform_requirement
):
    third = make_entry_version("STD-SEC-001", {"tags": ["platform"]}, version=3)
    make_entry_version("STD-SEC-001", {"tags": ["platform"]}, version=4)
    pinned = CorpusSnapshot.capture([third])

    applicable = resolve_applicable_entries(platform_requirement, pinned)

    assert [(item.entry_id, item.entry_version.version) for item in applicable] == [
        ("STD-SEC-001", 3)
    ]


def test_resolve_applicable_entries__reads_scope_rules_off_the_highest_version(
    make_entry_version, platform_requirement
):
    third = make_entry_version("STD-SEC-001", {"tags": ["platform"]}, version=3)
    fourth = make_entry_version("STD-SEC-001", {"tags": ["billing"]}, version=4)
    snapshot = CorpusSnapshot.capture([third, fourth])

    assert resolve_applicable_entries(platform_requirement, snapshot) == []


def test_resolve_applicable_entries__orders_by_entry_id(make_entry_version, platform_requirement):
    third = make_entry_version("STD-SEC-002", {"tags": ["platform"]})
    second = make_entry_version("STD-SEC-001", {"tags": ["platform"]}, version=2)
    first = make_entry_version("STD-SEC-001", {"tags": ["platform"]}, version=1)
    snapshot = CorpusSnapshot.capture([third, second, first])

    applicable = resolve_applicable_entries(platform_requirement, snapshot)

    assert [(item.entry_id, item.entry_version.version) for item in applicable] == [
        ("STD-SEC-001", 2),
        ("STD-SEC-002", 1),
    ]


def test_resolve_applicable_entries__returns_the_same_sequence_on_every_call(
    make_entry_version, platform_requirement
):
    versions = [
        make_entry_version("STD-SEC-002", {"paths": ["specs/platform/**"]}),
        make_entry_version("COM-PLAT-001", {"tags": ["platform"]}, kind=CorpusEntryKind.COMMITMENT),
        make_entry_version("STD-SEC-001", {"requirement_ids": ["REQ-PLAT-*"]}),
        make_entry_version(
            "DEC-IAM-001", {"components": ["storage"]}, kind=CorpusEntryKind.DECISION
        ),
    ]
    snapshot = CorpusSnapshot.capture(versions)

    runs = [
        [
            (item.entry_id, item.entry_version.version, item.reasons)
            for item in resolve_applicable_entries(platform_requirement, snapshot)
        ]
        for _ in range(5)
    ]

    assert [entry_id for entry_id, _version, _reasons in runs[0]] == [
        "COM-PLAT-001",
        "DEC-IAM-001",
        "STD-SEC-001",
        "STD-SEC-002",
    ]
    assert all(run == runs[0] for run in runs)


def test_build_lineage__orders_self_then_ancestors_nearest_first(requirement_tree):
    _root, _middle, leaf = requirement_tree

    lineage = build_lineage(leaf)

    assert [(node.external_id, inherited) for node, inherited in lineage] == [
        ("REQ-LEAF-001", False),
        ("REQ-MID-001", True),
        ("REQ-ROOT-001", True),
    ]


def test_build_lineage__returns_only_self_for_a_root(platform_requirement):
    lineage = build_lineage(platform_requirement)

    assert [(node.external_id, inherited) for node, inherited in lineage] == [
        ("REQ-PLAT-001", False)
    ]


def test_match_entry_version__returns_no_reasons_for_empty_applies_to(
    make_entry_version, platform_requirement
):
    version = make_entry_version("STD-SEC-001", {})

    assert match_entry_version(version, build_lineage(platform_requirement)) == ()


def test_to_dict__carries_every_match_reason_field():
    reason = MatchReason(
        scope_key="tags",
        pattern="platform",
        matched_value="platform",
        matched_requirement_id="REQ-ROOT-001",
        inherited=True,
    )

    assert reason.to_dict() == {
        "scope_key": "tags",
        "pattern": "platform",
        "matched_value": "platform",
        "matched_requirement_id": "REQ-ROOT-001",
        "inherited": True,
    }


def test_matched_scope_keys__deduplicates_and_uses_canonical_order(make_entry_version):
    version = make_entry_version("STD-SEC-001", {"tags": ["a", "b"]})
    applicable = ApplicableEntryVersion(
        entry_version=version,
        reasons=(
            MatchReason("paths", "specs/**", "specs/a.md", "REQ-A", False),
            MatchReason("tags", "a", "a", "REQ-A", False),
            MatchReason("tags", "b", "b", "REQ-A", False),
        ),
    )

    assert applicable.matched_scope_keys == ("tags", "paths")
    assert len(applicable.reasons_as_dicts()) == 3

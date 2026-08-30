"""Tests for contract snapshots."""

import json

import pytest
import yaml

from requirements.services.contract_snapshot import (
    ContractChange,
    ContractDiffer,
    ContractSnapshot,
)


@pytest.fixture
def project_root(tmp_path):
    """Create a sample project with data files."""
    # JSONL file
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    jsonl = data_dir / "records.jsonl"
    records = [
        {"id": "1", "name": "Alice", "role": "admin"},
        {"id": "2", "name": "Bob", "role": "user"},
    ]
    with open(jsonl, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # YAML file
    config = tmp_path / "config.yaml"
    with open(config, "w") as f:
        yaml.dump({"version": "1.0", "settings": {"debug": True}}, f)

    # pyproject.toml
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "test"\n\n[project.scripts]\nmytool = "mymodule:main"\n'
    )

    return tmp_path


class TestContractSnapshotGenerate:
    def test_generates_from_project(self, project_root):
        snap = ContractSnapshot.generate(project_root, "test")
        assert snap.project == "test"
        assert len(snap.surfaces) > 0

    def test_extracts_jsonl_fields(self, project_root):
        snap = ContractSnapshot.generate(project_root, "test")
        jsonl_surface = snap.surfaces.get("data/records.jsonl")
        assert jsonl_surface is not None
        assert "id" in jsonl_surface["fields"]
        assert "name" in jsonl_surface["fields"]
        assert "role" in jsonl_surface["fields"]

    def test_extracts_yaml_keys(self, project_root):
        snap = ContractSnapshot.generate(project_root, "test")
        yaml_surface = snap.surfaces.get("config.yaml")
        assert yaml_surface is not None
        assert "version" in yaml_surface["fields"]
        assert "settings" in yaml_surface["fields"]

    def test_extracts_cli_surfaces(self, project_root):
        snap = ContractSnapshot.generate(project_root, "test")
        assert "cli/mytool" in snap.surfaces

    def test_generate__extracts_non_string_yaml_keys(self, tmp_path):
        workflow = tmp_path / "ci" / "release.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: release\non:\n  push:\n    branches: [main]\n")
        snap = ContractSnapshot.generate(tmp_path, "test")
        assert snap.surfaces["ci/release.yml"]["fields"] == ["True", "name"]

    def test_skips_hidden_dirs(self, tmp_path):
        hidden = tmp_path / ".git" / "data"
        hidden.mkdir(parents=True)
        (hidden / "internal.jsonl").write_text('{"secret": true}\n')
        snap = ContractSnapshot.generate(tmp_path, "test")
        assert not any(".git" in k for k in snap.surfaces)


class TestContractSnapshotLoadSave:
    def test_roundtrip(self, tmp_path):
        snap = ContractSnapshot(
            project="test",
            version="1.0",
            surfaces={"data/items.jsonl": {"format": "jsonl", "fields": ["id", "name"]}},
        )
        path = tmp_path / "contract.snapshot.json"
        snap.save(path)
        loaded = ContractSnapshot.load(path)
        assert loaded.project == "test"
        assert loaded.version == "1.0"
        assert loaded.surfaces == snap.surfaces


class TestContractDiffer:
    def test_no_changes(self):
        snap = ContractSnapshot("p", "1.0", {"s1": {"fields": ["a", "b"]}})
        differ = ContractDiffer()
        changes = differ.diff(snap, snap)
        assert changes == []

    def test_field_removed_is_breaking(self):
        old = ContractSnapshot("p", "1.0", {"s1": {"fields": ["a", "b", "c"]}})
        new = ContractSnapshot("p", "1.0", {"s1": {"fields": ["a", "b"]}})
        differ = ContractDiffer()
        changes = differ.diff(old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "field_removed"
        assert changes[0].breaking is True
        assert changes[0].field == "c"

    def test_field_added_is_non_breaking(self):
        old = ContractSnapshot("p", "1.0", {"s1": {"fields": ["a"]}})
        new = ContractSnapshot("p", "1.0", {"s1": {"fields": ["a", "b"]}})
        differ = ContractDiffer()
        changes = differ.diff(old, new)
        assert len(changes) == 1
        assert changes[0].change_type == "field_added"
        assert changes[0].breaking is False

    def test_surface_removed_is_breaking(self):
        old = ContractSnapshot("p", "1.0", {"s1": {"fields": ["a"]}, "s2": {"fields": ["b"]}})
        new = ContractSnapshot("p", "1.0", {"s1": {"fields": ["a"]}})
        differ = ContractDiffer()
        changes = differ.diff(old, new)
        assert any(c.change_type == "surface_removed" and c.breaking for c in changes)

    def test_surface_added_is_non_breaking(self):
        old = ContractSnapshot("p", "1.0", {"s1": {"fields": ["a"]}})
        new = ContractSnapshot("p", "1.0", {"s1": {"fields": ["a"]}, "s2": {"fields": ["b"]}})
        differ = ContractDiffer()
        changes = differ.diff(old, new)
        assert any(c.change_type == "surface_added" and not c.breaking for c in changes)


class TestContractChangeToEdges:
    def test_breaking_change_produces_edge(self):
        change = ContractChange(
            surface="data/items.jsonl",
            change_type="field_removed",
            breaking=True,
            field="id",
        )
        edges = change.to_edges()
        assert len(edges) == 1
        assert edges[0].weight == 0.8

    def test_non_breaking_produces_no_edge(self):
        change = ContractChange(
            surface="data/items.jsonl",
            change_type="field_added",
            breaking=False,
            field="new_field",
        )
        edges = change.to_edges()
        assert edges == []

    def test_surface_removed_produces_high_weight_edge(self):
        change = ContractChange(
            surface="data/items.jsonl",
            change_type="surface_removed",
            breaking=True,
        )
        edges = change.to_edges()
        assert len(edges) == 1
        assert edges[0].weight == 1.0

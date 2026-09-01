"""Tests for contract snapshots."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from requirements import models
from requirements.services.contract_snapshot import (
    ContractChange,
    ContractDiffer,
    ContractSnapshot,
    ModelsNotImportedError,
    _declares_django_models,
    _extract_db_surfaces,
)

REPO_ROOT = Path(models.__file__).resolve().parents[2]

DJANGO_MODELS_SOURCE = """
from django.db import models


class Thing(models.Model):
    name = models.CharField(max_length=10)
"""


@pytest.fixture
def root_declaring_models(tmp_path):
    """A checkout that declares Django models, with none of them imported here."""
    app = tmp_path / "app"
    app.mkdir()
    (app / "models.py").write_text(DJANGO_MODELS_SOURCE)
    return tmp_path


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

    def test_generate__reads_a_root_that_sits_under_a_hidden_directory(self, tmp_path):
        root = tmp_path / ".worktrees" / "checkout"
        root.mkdir(parents=True)
        (root / "flows.yaml").write_text("name: flow\nsteps: [one]\n")

        snap = ContractSnapshot.generate(root, "test")

        assert "flows.yaml" in snap.surfaces

    def test_generate__still_skips_a_hidden_directory_inside_the_root(self, tmp_path):
        root = tmp_path / ".worktrees" / "checkout"
        (root / ".cache").mkdir(parents=True)
        (root / ".cache" / "flows.yaml").write_text("name: flow\nsteps: [one]\n")

        snap = ContractSnapshot.generate(root, "test")

        assert snap.surfaces == {}


class TestDatabaseSurfacesPerRoot:
    @patch("requirements.services.contract_snapshot.apps.get_models", autospec=True)
    def test_extract_db_surfaces__raises_for_a_root_whose_models_this_process_never_imported(
        self, mock_get_models, root_declaring_models
    ):
        mock_get_models.return_value = []

        with pytest.raises(ModelsNotImportedError) as raised:
            _extract_db_surfaces(root_declaring_models)

        assert str(root_declaring_models.resolve()) in str(raised.value)

    @patch("requirements.services.contract_snapshot.apps.get_models", autospec=True)
    def test_generate__raises_rather_than_publishing_a_root_as_having_no_database(
        self, mock_get_models, root_declaring_models
    ):
        mock_get_models.return_value = []

        with pytest.raises(ModelsNotImportedError):
            ContractSnapshot.generate(root_declaring_models, "test")

    @patch("requirements.services.contract_snapshot.apps.get_models", autospec=True)
    def test_extract_db_surfaces__reports_no_surfaces_for_a_root_declaring_no_models(
        self, mock_get_models, tmp_path
    ):
        mock_get_models.return_value = []
        (tmp_path / "main.py").write_text("print('hello')\n")

        assert _extract_db_surfaces(tmp_path) == {}

    def test_extract_db_surfaces__names_the_tables_of_the_root_it_imported(self):
        surfaces = _extract_db_surfaces(REPO_ROOT)

        assert "db/requirements_requirement" in surfaces

    def test_declares_django_models__reads_a_models_module_it_never_imports(
        self, root_declaring_models
    ):
        assert _declares_django_models(root_declaring_models) is True

    def test_declares_django_models__ignores_a_models_module_free_of_django(self, tmp_path):
        (tmp_path / "models.py").write_text(
            "from pydantic import BaseModel as Model\n\n\nclass Thing(Model):\n    name: str\n"
        )

        assert _declares_django_models(tmp_path) is False

    def test_declares_django_models__ignores_a_hidden_directory_inside_the_root(self, tmp_path):
        vendored = tmp_path / ".venv" / "app"
        vendored.mkdir(parents=True)
        (vendored / "models.py").write_text(DJANGO_MODELS_SOURCE)

        assert _declares_django_models(tmp_path) is False

    def test_declares_django_models__reads_a_root_that_sits_under_a_hidden_directory(
        self, tmp_path
    ):
        root = tmp_path / ".worktrees" / "checkout" / "app"
        root.mkdir(parents=True)
        (root / "models.py").write_text(DJANGO_MODELS_SOURCE)

        assert _declares_django_models(root.parent) is True

    def test_declares_django_models__reads_a_models_package(self, tmp_path):
        package = tmp_path / "app" / "models"
        package.mkdir(parents=True)
        (package / "thing.py").write_text(DJANGO_MODELS_SOURCE)

        assert _declares_django_models(tmp_path) is True


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

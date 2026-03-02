"""Tests for spectrace-map.yaml reader."""

import yaml

from requirements.services.map_reader import MapReader


def _make_project_root(tmp_path, name, map_data):
    """Create a project root with a spectrace-map.yaml."""
    root = tmp_path / name
    root.mkdir()
    with open(root / "spectrace-map.yaml", "w") as f:
        yaml.dump(map_data, f)
    return root


class TestMapReader:
    def test_read_map_valid(self, tmp_path):
        root = _make_project_root(
            tmp_path,
            "lore",
            {
                "project": "lore",
                "modules": {
                    "src/lore/reader.py": {"requirements": ["REQ-LORE-001", "REQ-LORE-002"]},
                    "src/lore/writer.py": {"requirements": ["REQ-LORE-003"]},
                },
            },
        )
        reader = MapReader({"lore": root})
        pairs = reader.read_map("lore")
        assert ("src/lore/reader.py", "REQ-LORE-001") in pairs
        assert ("src/lore/reader.py", "REQ-LORE-002") in pairs
        assert ("src/lore/writer.py", "REQ-LORE-003") in pairs

    def test_read_map_missing_file(self, tmp_path):
        reader = MapReader({"empty": tmp_path / "nonexistent"})
        assert reader.read_map("empty") == []

    def test_read_map_unknown_project(self, tmp_path):
        reader = MapReader({"lore": tmp_path})
        assert reader.read_map("nonexistent") == []

    def test_read_map_invalid_yaml(self, tmp_path):
        root = tmp_path / "bad"
        root.mkdir()
        (root / "spectrace-map.yaml").write_text(": invalid: yaml: [")
        reader = MapReader({"bad": root})
        assert reader.read_map("bad") == []

    def test_read_all_multi_project(self, tmp_path):
        lore_root = _make_project_root(
            tmp_path,
            "lore",
            {"project": "lore", "modules": {"mod.py": {"requirements": ["REQ-L1"]}}},
        )
        praxis_root = _make_project_root(
            tmp_path,
            "praxis",
            {"project": "praxis", "modules": {"mod.py": {"requirements": ["REQ-P1"]}}},
        )
        reader = MapReader({"lore": lore_root, "praxis": praxis_root})
        edges = reader.read_all()
        assert len(edges) == 2
        projects = {e.project for e in edges}
        assert projects == {"lore", "praxis"}

    def test_validate_map_valid(self):
        data = {
            "project": "lore",
            "modules": {"src/mod.py": {"requirements": ["REQ-1"]}},
        }
        reader = MapReader({})
        errors = reader.validate_map(data)
        assert errors == []

    def test_validate_map_missing_project(self):
        reader = MapReader({})
        errors = reader.validate_map({"modules": {}})
        assert any("project" in e for e in errors)

    def test_validate_map_missing_modules(self):
        reader = MapReader({})
        errors = reader.validate_map({"project": "x"})
        assert any("modules" in e for e in errors)

    def test_validate_map_bad_requirements_type(self):
        reader = MapReader({})
        data = {"project": "x", "modules": {"a.py": {"requirements": "not-a-list"}}}
        errors = reader.validate_map(data)
        assert any("list" in e for e in errors)

"""Tests for spectrace-map.yaml reader."""

import yaml

from requirements.services.impact_graph import EdgeSource
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


def _praxis_root(tmp_path):
    return _make_project_root(
        tmp_path,
        "praxis",
        {
            "project": "praxis",
            "modules": {
                "src/praxis/spectrace.py": {
                    "requirements": ["REQ-PRX-004"],
                    "depends_on": [
                        "spectrace:db/requirements_requirement",
                        "spectrace:db/requirements_testrun",
                    ],
                },
                "src/praxis/lore.py": {"requirements": ["REQ-PRX-001"]},
            },
        },
    )


def test_read_dependencies__returns_module_and_provider_surface_pairs(tmp_path):
    reader = MapReader({"praxis": _praxis_root(tmp_path)})

    assert reader.read_dependencies("praxis") == [
        ("src/praxis/spectrace.py", "spectrace:db/requirements_requirement"),
        ("src/praxis/spectrace.py", "spectrace:db/requirements_testrun"),
    ]


def test_read_all_dependencies__emits_dependency_edges_into_provider_surface_nodes(tmp_path):
    reader = MapReader({"praxis": _praxis_root(tmp_path)})

    edges = reader.read_all_dependencies()

    assert [(e.source_id, e.target_id, e.source, e.project) for e in edges] == [
        (
            "praxis:src/praxis/spectrace.py",
            "spectrace:db/requirements_requirement",
            EdgeSource.DEPENDENCY,
            "praxis",
        ),
        (
            "praxis:src/praxis/spectrace.py",
            "spectrace:db/requirements_testrun",
            EdgeSource.DEPENDENCY,
            "praxis",
        ),
    ]


def test_read_all__leaves_dependencies_out_of_the_annotated_edges(tmp_path):
    reader = MapReader({"praxis": _praxis_root(tmp_path)})

    assert {e.source for e in reader.read_all()} == {EdgeSource.ANNOTATED}


def test_validate_map__accepts_a_well_formed_depends_on_list():
    data = {
        "project": "praxis",
        "modules": {
            "src/praxis/spectrace.py": {
                "requirements": ["REQ-PRX-004"],
                "depends_on": ["spectrace:db/requirements_requirement"],
            }
        },
    }

    assert MapReader({}).validate_map(data) == []


def test_validate_map__rejects_a_dependency_without_a_provider_prefix():
    data = {
        "project": "praxis",
        "modules": {
            "src/praxis/spectrace.py": {
                "requirements": ["REQ-PRX-004"],
                "depends_on": ["db/requirements_requirement"],
            }
        },
    }

    errors = MapReader({}).validate_map(data)

    assert errors == [
        "Module 'src/praxis/spectrace.py': dependency 'db/requirements_requirement'"
        " must name a provider and a surface as 'project:surface'"
    ]


def test_validate_map__rejects_a_depends_on_that_is_not_a_list():
    data = {
        "project": "praxis",
        "modules": {
            "src/praxis/spectrace.py": {
                "requirements": ["REQ-PRX-004"],
                "depends_on": "spectrace:db/requirements_requirement",
            }
        },
    }

    errors = MapReader({}).validate_map(data)

    assert errors == ["Module 'src/praxis/spectrace.py': 'depends_on' must be a list"]


def test_validate_map__rejects_a_dependency_that_is_not_a_string():
    data = {
        "project": "praxis",
        "modules": {
            "src/praxis/spectrace.py": {
                "requirements": ["REQ-PRX-004"],
                "depends_on": [{"project": "spectrace"}],
            }
        },
    }

    errors = MapReader({}).validate_map(data)

    assert errors == ["Module 'src/praxis/spectrace.py': dependency must be a string, got dict"]

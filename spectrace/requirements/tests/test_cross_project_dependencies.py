"""Tests for dependencies declared across project boundaries."""

import json

import pytest
import yaml

from requirements.services.contract_snapshot import contract_edges, surface_origin
from requirements.services.impact_graph import EdgeSource, ImpactGraphBuilder
from requirements.services.map_reader import (
    MalformedDependencyError,
    MapReader,
    UnknownSurfaceError,
)


def write_map(root, project, modules):
    root.mkdir(parents=True, exist_ok=True)
    (root / "spectrace-map.yaml").write_text(yaml.dump({"project": project, "modules": modules}))


def write_snapshot(root, project, surfaces):
    root.mkdir(parents=True, exist_ok=True)
    (root / "contract.snapshot.json").write_text(
        json.dumps({"project": project, "version": "1.0", "surfaces": surfaces})
    )


@pytest.fixture
def two_projects(tmp_path):
    provider = tmp_path / "provider"
    consumer = tmp_path / "consumer"
    write_map(provider, "prov", {"src/models.py": {"requirements": ["REQ-P-001"]}})
    write_snapshot(
        provider,
        "prov",
        {
            "db/prov_thing": {
                "format": "db-table",
                "fields": ["id", "name"],
                "origin": "src/models.py",
            }
        },
    )
    write_map(
        consumer,
        "cons",
        {
            "src/reader.py": {
                "requirements": ["REQ-C-001"],
                "depends_on": ["prov:db/prov_thing"],
            }
        },
    )
    return {"provider": provider, "consumer": consumer}


def build_graph(roots):
    reader = MapReader(roots)
    dependency_edges, _ = reader.read_all_dependencies()
    contract = []
    for key, root in roots.items():
        contract.extend(contract_edges(reader.project_name(key), root))
    return ImpactGraphBuilder(roots).build(reader.read_all(), [], contract, dependency_edges)


class TestReadAllDependencies:
    def test_read_all_dependencies__builds_a_directed_provider_to_consumer_edge(self, two_projects):
        edges, unresolved = MapReader(two_projects).read_all_dependencies()

        assert unresolved == []
        assert len(edges) == 1
        assert edges[0].source_id == "prov:db/prov_thing"
        assert edges[0].target_id == "cons:src/reader.py"
        assert edges[0].source is EdgeSource.DEPENDENCY
        assert edges[0].directed is True

    def test_read_all_dependencies__accepts_a_module_path_as_a_surface(self, tmp_path):
        provider = tmp_path / "provider"
        consumer = tmp_path / "consumer"
        write_map(provider, "prov", {"schema.yaml": {"requirements": ["REQ-P-001"]}})
        write_map(
            consumer,
            "cons",
            {"src/reader.py": {"requirements": ["REQ-C-001"], "depends_on": ["prov:schema.yaml"]}},
        )

        edges, _ = MapReader({"p": provider, "c": consumer}).read_all_dependencies()

        assert [edge.source_id for edge in edges] == ["prov:schema.yaml"]

    def test_read_all_dependencies__raises_when_the_provider_lacks_the_surface(self, two_projects):
        write_map(
            two_projects["consumer"],
            "cons",
            {
                "src/reader.py": {
                    "requirements": ["REQ-C-001"],
                    "depends_on": ["prov:db/prov_missing"],
                }
            },
        )

        with pytest.raises(UnknownSurfaceError, match="db/prov_missing"):
            MapReader(two_projects).read_all_dependencies()

    def test_read_all_dependencies__raises_when_a_declaration_names_no_project(self, two_projects):
        write_map(
            two_projects["consumer"],
            "cons",
            {"src/reader.py": {"requirements": ["REQ-C-001"], "depends_on": ["db/prov_thing"]}},
        )

        with pytest.raises(MalformedDependencyError, match="db/prov_thing"):
            MapReader(two_projects).read_all_dependencies()

    def test_read_all_dependencies__reports_a_provider_absent_from_the_roots(self, two_projects):
        reader = MapReader({"consumer": two_projects["consumer"]})

        edges, unresolved = reader.read_all_dependencies()

        assert edges == []
        assert len(unresolved) == 1
        assert unresolved[0].provider == "prov"
        assert unresolved[0].surface == "db/prov_thing"
        assert unresolved[0].consumer == "cons"


class TestCrossProjectBlastRadius:
    def test_blast_radius__reaches_a_consumer_module_in_another_project(self, two_projects):
        graph = build_graph(two_projects)

        blast = graph.blast_radius(["prov:src/models.py"])

        assert "cons:src/reader.py" in blast.affected_modules
        assert blast.affected_projects == {"prov", "cons"}
        assert len(blast.cross_project_edges) == 1

    def test_blast_radius__does_not_report_the_provider_when_the_consumer_changes(
        self, two_projects
    ):
        graph = build_graph(two_projects)

        blast = graph.blast_radius(["cons:src/reader.py"])

        assert blast.affected_projects == {"cons"}
        assert blast.cross_project_edges == []


class TestValidateMap:
    def test_validate_map__rejects_a_dependency_that_names_no_project(self):
        errors = MapReader({}).validate_map(
            {
                "project": "cons",
                "modules": {"src/reader.py": {"requirements": [], "depends_on": ["thing"]}},
            }
        )

        assert any("must name a project" in error for error in errors)

    def test_validate_map__rejects_a_dependency_list_that_is_not_a_list(self):
        errors = MapReader({}).validate_map(
            {
                "project": "cons",
                "modules": {"src/reader.py": {"requirements": [], "depends_on": "prov:thing"}},
            }
        )

        assert any("'depends_on' must be a list" in error for error in errors)


class TestSurfaceOrigin:
    def test_surface_origin__is_none_when_the_surface_is_its_own_file(self):
        assert surface_origin("flows/example.yaml", {"format": "yaml"}) is None

    def test_surface_origin__names_pyproject_for_a_cli_surface(self):
        assert surface_origin("cli/spectrace", {"format": "cli"}) == "pyproject.toml"

    def test_surface_origin__prefers_a_recorded_origin(self):
        spec = {"format": "db-table", "origin": "src/models.py"}

        assert surface_origin("db/thing", spec) == "src/models.py"

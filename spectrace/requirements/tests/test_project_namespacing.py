"""Two projects share one database without contaminating each other.

Seeding a second project's requirements alongside this one's is the case these
tests hold to: the rows carry their own project, coverage reports one project at
a time, and two projects' identically-named modules and test node ids stay apart.
"""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import IntegrityError

from requirements.models import Requirement, TestRequirementLink
from requirements.parser import SpecParser, import_requirements_to_database
from requirements.projects import (
    AmbiguousProjectError,
    default_project,
    display_node,
    qualify,
    resolve_project,
    unqualify,
)
from requirements.services.impact_analyzer import ImpactAnalyzer
from requirements.services.map_reader import MapReader, project_for_path

HOST = "spectrace"
GUEST = "praxis"


def make_requirement(external_id, project, **fields):
    return Requirement.add_root(
        external_id=external_id,
        title=external_id,
        project=project,
        source_file="test.md",
        **fields,
    )


@pytest.fixture
def two_projects(db):
    """Seed one host project and one guest project, as the incident did."""
    host = [
        make_requirement("REQ-HOST-1", HOST, status="active", verification_status="passing"),
        make_requirement("REQ-HOST-2", HOST, status="active", verification_status="passing"),
        make_requirement("REQ-HOST-3", HOST, status="draft"),
        make_requirement("REQ-HOST-4", HOST, status="draft"),
    ]
    guest = [
        make_requirement("REQ-GUEST-1", GUEST, status="active", verification_status="failing"),
        make_requirement("REQ-GUEST-2", GUEST, status="active", verification_status="failing"),
    ]
    return host, guest


def write_map(root, project, modules):
    root.mkdir(parents=True, exist_ok=True)
    (root / "spectrace-map.yaml").write_text(
        yaml.dump(
            {
                "project": project,
                "modules": {path: {"requirements": reqs} for path, reqs in modules.items()},
            }
        )
    )
    return root


class TestProjectNames:
    def test_qualify__prefixes_a_name_with_its_project(self):
        assert qualify("praxis", "tests/conftest.py") == "praxis:tests/conftest.py"

    def test_unqualify__splits_a_node_id_back_apart(self):
        assert unqualify("praxis:tests/conftest.py") == ("praxis", "tests/conftest.py")

    def test_unqualify__leaves_an_unprefixed_node_id_whole(self):
        assert unqualify("tests/conftest.py") == ("", "tests/conftest.py")

    def test_display_node__names_the_project_a_node_belongs_to(self):
        assert display_node("praxis:REQ-1") == "[praxis] REQ-1"

    def test_display_node__renders_an_unprefixed_node_bare(self):
        assert display_node("REQ-1") == "REQ-1"

    def test_resolve_project__returns_the_project_the_caller_named(self):
        assert resolve_project(GUEST, [HOST, GUEST]) == GUEST

    def test_resolve_project__prefers_the_installations_own_project(self):
        assert resolve_project(None, [HOST, GUEST]) == HOST

    def test_resolve_project__falls_back_to_the_only_project_stored(self):
        assert resolve_project(None, ["lore"]) == "lore"

    def test_resolve_project__falls_back_to_the_installation_when_nothing_is_stored(self):
        assert resolve_project(None, []) == default_project()

    def test_resolve_project__raises_rather_than_blend_several_foreign_projects(self):
        with pytest.raises(AmbiguousProjectError) as excinfo:
            resolve_project(None, ["lore", "praxis"])

        assert excinfo.value.projects == ["lore", "praxis"]


class TestRequirementProjectColumn:
    @pytest.mark.django_db
    def test_requirement__adopts_the_installations_project_by_default(self):
        req = Requirement.add_root(external_id="REQ-D-1", title="D", source_file="test.md")

        assert req.project == default_project()

    @pytest.mark.django_db
    def test_requirement__refuses_to_be_stored_without_a_project(self):
        with pytest.raises(IntegrityError):
            make_requirement("REQ-BLANK-1", "")

    @pytest.mark.django_db
    def test_project_names__lists_every_project_stored(self, two_projects):
        assert Requirement.project_names() == [GUEST, HOST]


class TestImportKeepsProjectsApart:
    @pytest.mark.django_db
    def test_import_requirements_to_database__labels_rows_with_their_project(self):
        import_requirements_to_database(
            [{"external_id": "REQ-G-1", "title": "Guest", "source_file": "praxis.md"}],
            project=GUEST,
        )

        assert Requirement.objects.get(external_id="REQ-G-1").project == GUEST

    @pytest.mark.django_db
    def test_import_requirements_to_database__leaves_another_projects_rows_untouched(
        self, two_projects
    ):
        import_requirements_to_database(
            [{"external_id": "REQ-G-3", "title": "Guest", "source_file": "praxis.md"}],
            project=GUEST,
        )

        assert Requirement.objects.filter(project=HOST).count() == 4
        assert Requirement.objects.filter(project=GUEST).count() == 3

    @pytest.mark.django_db
    def test_import_requirements_to_database__clears_only_the_project_it_imports(
        self, two_projects
    ):
        import_requirements_to_database(
            [{"external_id": "REQ-G-9", "title": "Guest", "source_file": "praxis.md"}],
            clear_existing=True,
            project=GUEST,
        )

        assert Requirement.objects.filter(project=HOST).count() == 4
        assert list(
            Requirement.objects.filter(project=GUEST).values_list("external_id", flat=True)
        ) == ["REQ-G-9"]

    @pytest.mark.django_db
    def test_import_to_database__takes_the_project_from_the_map_above_the_specs(self, tmp_path):
        guest_root = write_map(tmp_path / GUEST, GUEST, {"src/mod.py": ["REQ-G-1"]})
        specs_dir = guest_root / "specs"
        specs_dir.mkdir()
        (specs_dir / "guest.md").write_text("---\nid: REQ-G-1\ntitle: Guest\n---\n\nBody.\n")

        SpecParser().import_to_database(specs_dir)

        assert Requirement.objects.get(external_id="REQ-G-1").project == GUEST

    @pytest.mark.django_db
    def test_parse_specs__labels_another_projects_specs_with_that_project(self, tmp_path):
        guest_root = write_map(tmp_path / GUEST, GUEST, {"src/mod.py": ["REQ-G-2"]})
        specs_dir = guest_root / "specs"
        specs_dir.mkdir()
        (specs_dir / "guest.md").write_text("---\nid: REQ-G-2\ntitle: Guest\n---\n\nBody.\n")
        out = StringIO()

        call_command("parse_specs", str(specs_dir), stdout=out)

        assert Requirement.objects.get(external_id="REQ-G-2").project == GUEST
        assert GUEST in out.getvalue()

    def test_project_for_path__reads_the_nearest_map_above_a_directory(self, tmp_path):
        guest_root = write_map(tmp_path / GUEST, GUEST, {"src/mod.py": ["REQ-G-1"]})
        specs_dir = guest_root / "specs" / "nested"
        specs_dir.mkdir(parents=True)

        assert project_for_path(specs_dir) == GUEST

    def test_project_for_path__names_no_project_when_no_map_stands_above(self, tmp_path):
        bare = tmp_path / "bare"
        bare.mkdir()

        assert project_for_path(bare) is None


class TestCoverageReportsOneProject:
    @pytest.mark.django_db
    def test_spec_coverage__counts_only_the_host_project(self, two_projects):
        out = StringIO()

        call_command("spec_coverage", "--format", "json", stdout=out)
        data = json.loads(out.getvalue())

        assert data["project"] == HOST
        assert data["counts"] == {"total": 4, "non_draft": 2, "passing": 2}

    @pytest.mark.django_db
    def test_spec_coverage__counts_only_the_guest_project_when_asked(self, two_projects):
        out = StringIO()

        call_command("spec_coverage", "--project", GUEST, "--format", "json", stdout=out)
        data = json.loads(out.getvalue())

        assert data["project"] == GUEST
        assert data["counts"] == {"total": 2, "non_draft": 2, "passing": 0}

    @pytest.mark.django_db
    def test_spec_coverage__names_the_project_it_reported_on(self, two_projects):
        out = StringIO()

        call_command("spec_coverage", stdout=out)

        assert f"Project: {HOST}" in out.getvalue()

    @pytest.mark.django_db
    def test_spec_coverage__refuses_to_blend_projects_it_cannot_choose_between(self, db):
        make_requirement("REQ-L-1", "lore")
        make_requirement("REQ-P-1", "praxis")

        with pytest.raises(CommandError, match="lore, praxis"):
            call_command("spec_coverage")

    @pytest.mark.django_db
    @patch("requirements.api_v1.detect_spec_drift", autospec=True)
    @patch("requirements.api_v1.detect_stale_links", autospec=True)
    def test_specs_coverage_view__counts_only_the_host_project(
        self, mock_stale, mock_drift, client, two_projects
    ):
        mock_stale.return_value = MagicMock(errors=[])
        mock_drift.return_value = MagicMock(warnings=[])

        data = client.get("/api/v1/specs/coverage/").json()["data"]

        assert data["project"] == HOST
        assert data["metrics"]["total"] == 4
        assert data["metrics"]["failing"] == 0

    @pytest.mark.django_db
    @patch("requirements.api_v1.detect_spec_drift", autospec=True)
    @patch("requirements.api_v1.detect_stale_links", autospec=True)
    def test_specs_coverage_view__counts_the_guest_project_when_asked(
        self, mock_stale, mock_drift, client, two_projects
    ):
        mock_stale.return_value = MagicMock(errors=[])
        mock_drift.return_value = MagicMock(warnings=[])

        data = client.get(f"/api/v1/specs/coverage/?project={GUEST}").json()["data"]

        assert data["project"] == GUEST
        assert data["metrics"]["total"] == 2
        assert data["metrics"]["failing"] == 2

    @pytest.mark.django_db
    @patch("requirements.api_v1.detect_spec_drift", autospec=True)
    @patch("requirements.api_v1.detect_stale_links", autospec=True)
    def test_specs_coverage_view__refuses_to_blend_projects_it_cannot_choose_between(
        self, mock_stale, mock_drift, client, db
    ):
        mock_stale.return_value = MagicMock(errors=[])
        mock_drift.return_value = MagicMock(warnings=[])
        make_requirement("REQ-L-1", "lore")
        make_requirement("REQ-P-1", "praxis")

        resp = client.get("/api/v1/specs/coverage/")

        assert resp.status_code == 400
        assert resp.json()["error"]["details"]["projects"] == ["lore", "praxis"]

    @pytest.mark.django_db
    def test_dashboard_callback__counts_only_the_host_project(self, rf, two_projects):
        from requirements.dashboard import dashboard_callback

        context = dashboard_callback(rf.get("/admin/"), {})

        assert context["current_project"] == HOST
        assert context["total_requirements"] == 4
        assert context["available_projects"] == [GUEST, HOST]


class TestGraphKeepsProjectsApart:
    def test_read_all__keys_two_projects_identical_module_paths_apart(self, tmp_path):
        write_map(tmp_path / "lore", "lore", {"tests/conftest.py": ["REQ-L-1"]})
        write_map(tmp_path / "praxis", "praxis", {"tests/conftest.py": ["REQ-P-1"]})
        reader = MapReader({"lore": tmp_path / "lore", "praxis": tmp_path / "praxis"})

        sources = {edge.source_id for edge in reader.read_all()}

        assert sources == {"lore:tests/conftest.py", "praxis:tests/conftest.py"}

    def test_read_all__keys_nodes_by_the_project_the_map_declares(self, tmp_path):
        write_map(tmp_path / "checkout", "praxis", {"src/mod.py": ["REQ-P-1"]})
        reader = MapReader({"checkout": tmp_path / "checkout"})

        edge = reader.read_all()[0]

        assert (edge.source_id, edge.target_id) == ("praxis:src/mod.py", "praxis:REQ-P-1")
        assert edge.project == "praxis"

    def test_project_name__falls_back_to_the_key_when_no_map_declares_one(self, tmp_path):
        bare = tmp_path / "bare"
        bare.mkdir()

        assert MapReader({"bare": bare}).project_name("bare") == "bare"

    @pytest.mark.django_db
    def test_code_analyze__leaves_another_projects_conftest_out_of_the_blast(self, tmp_path):
        roots = {
            "lore": write_map(tmp_path / "lore", "lore", {"tests/conftest.py": ["REQ-L-1"]}),
            "praxis": write_map(tmp_path / "praxis", "praxis", {"tests/conftest.py": ["REQ-P-1"]}),
        }
        diff_lore = MagicMock(stdout="tests/conftest.py\n")
        empty = MagicMock(stdout="")

        with patch("subprocess.run", autospec=True, side_effect=[diff_lore, empty, empty, empty]):
            result = ImpactAnalyzer().code_analyze("HEAD~1", "HEAD", project_roots=roots)

        assert result.blast["affected_requirements"] == ["lore:REQ-L-1"]
        assert result.blast["affected_projects"] == ["lore"]
        assert result.changed_files == {"lore": ["tests/conftest.py"]}


class TestAffectedTestsCarryTheirProject:
    @pytest.mark.django_db
    def test_group_tests_by_project__names_the_project_each_test_verifies(self, two_projects):
        host, guest = two_projects
        shared_nodeid = "tests/conftest.py::test_smoke"
        TestRequirementLink.objects.create(test_nodeid=shared_nodeid, requirement=host[0])
        TestRequirementLink.objects.create(test_nodeid=shared_nodeid, requirement=guest[0])
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_host.py::test_only", requirement=host[1]
        )

        grouped = ImpactAnalyzer().group_tests_by_project(
            [shared_nodeid, "tests/test_host.py::test_only"]
        )

        assert grouped == {
            GUEST: [shared_nodeid],
            HOST: [shared_nodeid, "tests/test_host.py::test_only"],
        }

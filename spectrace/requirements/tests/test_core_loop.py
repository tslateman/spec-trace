"""The traceability loop, exercised end to end against real files.

SpecTrace claims that a requirement written in markdown reaches a verification
status derived from the tests that cover it. These tests run that claim: specs
parse from disk, markers become links, a JUnit report lands, and status follows.
"""

import io
import json
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.management import call_command

from requirements.importer import (
    import_junit_xml,
    link_results_to_requirements,
    update_test_requirement_links,
)
from requirements.management.commands.extract_links import RequirementCollector
from requirements.models import Requirement, TestRequirementLink, VerificationStatus
from requirements.status import compute_verification_status

SPEC_FILE = """---
tags: [loop]
priority: high
status: active
risk_level: high
---

# Loop fixture

## REQ-LOOP-000: Parent requirement

The root of the fixture tree.

## REQ-LOOP-001: Child requirement

A child the tests link to.
"""

JUNIT_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="2" failures="1">
    <testcase classname="tests.test_loop" name="test_covered" time="0.01"
              file="tests/test_loop.py"/>
    <testcase classname="tests.test_loop" name="test_broken" time="0.02"
              file="tests/test_loop.py">
      <failure message="assert False">assert False</failure>
    </testcase>
  </testsuite>
</testsuites>
"""


@pytest.fixture
def spec_dir(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "loop.md").write_text(SPEC_FILE)
    return specs


@pytest.fixture
def junit_file(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(JUNIT_XML)
    return report


def _links_file(tmp_path, links):
    path = tmp_path / "links.json"
    path.write_text(json.dumps({"version": "1.0", "links": links, "summary": {}}))
    return path


MULTI_CHILD_SPEC = """---
status: active
---

# Many children

## REQ-MANY-000: Parent

## REQ-MANY-001: First child

## REQ-MANY-002: Second child

## REQ-MANY-003: Third child
"""

SECOND_TREE_SPEC = """---
status: active
---

# Another tree

## REQ-OTHER-000: Other parent

## REQ-OTHER-001: Other first child

## REQ-OTHER-002: Other second child
"""


@pytest.mark.requirement("REQ-CORE-001")
class TestParsingHierarchies:
    """A parent keeps its own children, however many files declare them."""

    def test_parse_specs__attaches_every_child_to_its_declared_parent(self, db, tmp_path):
        (tmp_path / "many.md").write_text(MULTI_CHILD_SPEC)
        call_command("parse_specs", str(tmp_path))

        parent = Requirement.objects.get(external_id="REQ-MANY-000")
        assert sorted(child.external_id for child in parent.get_children()) == [
            "REQ-MANY-001",
            "REQ-MANY-002",
            "REQ-MANY-003",
        ]

    def test_parse_specs__keeps_trees_separate_across_files(self, db, tmp_path):
        (tmp_path / "many.md").write_text(MULTI_CHILD_SPEC)
        (tmp_path / "other.md").write_text(SECOND_TREE_SPEC)
        call_command("parse_specs", str(tmp_path))

        other = Requirement.objects.get(external_id="REQ-OTHER-000")
        assert sorted(child.external_id for child in other.get_children()) == [
            "REQ-OTHER-001",
            "REQ-OTHER-002",
        ]

    def test_parse_specs__leaves_the_tree_without_structural_problems(self, db, tmp_path):
        (tmp_path / "many.md").write_text(MULTI_CHILD_SPEC)
        (tmp_path / "other.md").write_text(SECOND_TREE_SPEC)
        call_command("parse_specs", str(tmp_path))

        assert Requirement.find_problems() == ([], [], [], [], [])

    def test_parse_specs__updates_rather_than_duplicates_on_a_second_run(self, db, tmp_path):
        (tmp_path / "many.md").write_text(MULTI_CHILD_SPEC)
        call_command("parse_specs", str(tmp_path))
        call_command("parse_specs", str(tmp_path))

        assert Requirement.objects.filter(external_id="REQ-MANY-001").count() == 1


@pytest.mark.requirement("REQ-CORE-002")
class TestExtractingRequirementLinks:
    """`extract_links` turns @pytest.mark.requirement markers into link records."""

    def _collect(self, tmp_path, source, monkeypatch):
        module = f"test_collected_{uuid4().hex}.py"
        (tmp_path / module).write_text(source)
        monkeypatch.chdir(tmp_path)
        collector = RequirementCollector()
        stdout, stderr = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
            pytest.main(
                ["--collect-only", "-p", "no:cacheprovider", "-p", "no:django", "."],
                plugins=[collector],
            )
        finally:
            sys.stdout, sys.stderr = stdout, stderr
        return collector.links

    def test_collect__records_one_link_per_requirement_id(self, tmp_path, monkeypatch):
        links = self._collect(
            tmp_path,
            "import pytest\n\n"
            '@pytest.mark.requirement("REQ-LOOP-001")\n'
            "def test_one():\n    pass\n\n"
            '@pytest.mark.requirement("REQ-LOOP-001", "REQ-LOOP-000")\n'
            "def test_two():\n    pass\n",
            monkeypatch,
        )

        assert [link["requirement_id"] for link in links] == [
            "REQ-LOOP-001",
            "REQ-LOOP-001",
            "REQ-LOOP-000",
        ]

    def test_collect__records_no_links_when_no_test_declares_a_requirement(
        self, tmp_path, monkeypatch
    ):
        links = self._collect(tmp_path, "def test_one():\n    pass\n", monkeypatch)

        assert links == []

    def test_collect__carries_the_marker_reason(self, tmp_path, monkeypatch):
        links = self._collect(
            tmp_path,
            "import pytest\n\n"
            '@pytest.mark.requirement("REQ-LOOP-001", reason="covers the happy path")\n'
            "def test_one():\n    pass\n",
            monkeypatch,
        )

        assert links[0]["reason"] == "covers the happy path"

    def test_collect__names_the_test_function(self, tmp_path, monkeypatch):
        links = self._collect(
            tmp_path,
            "import pytest\n\n"
            '@pytest.mark.requirement("REQ-LOOP-001")\n'
            "def test_one():\n    pass\n",
            monkeypatch,
        )

        assert links[0]["test_function"] == "test_one"


@pytest.mark.requirement("REQ-CORE-003")
class TestImportingTestResults:
    """`import_results` reads a JUnit report into TestRun and TestResult records."""

    def test_import_junit_xml__records_every_testcase(self, db, junit_file):
        run = import_junit_xml(str(junit_file))

        assert run.results.count() == 2

    def test_import_junit_xml__separates_passing_from_failing(self, db, junit_file):
        run = import_junit_xml(str(junit_file))
        outcomes = {result.test_nodeid: result.status for result in run.results.all()}

        assert outcomes["tests.test_loop::test_covered"] == "passed"
        assert outcomes["tests.test_loop::test_broken"] == "failed"

    def test_import_junit_xml__keeps_the_git_metadata_it_is_given(self, db, junit_file):
        run = import_junit_xml(str(junit_file), git_sha="abc123", git_branch="main")

        assert run.git_sha == "abc123"
        assert run.git_branch == "main"


@pytest.mark.requirement("REQ-CORE-000")
class TestTheTraceabilityLoop:
    """Markdown to verification status, through every stage in order."""

    def test_loop__derives_passing_status_from_a_passing_linked_test(
        self, db, spec_dir, junit_file, tmp_path
    ):
        call_command("parse_specs", str(spec_dir))
        links = _links_file(
            tmp_path,
            [
                {
                    "test_nodeid": "tests/test_loop.py::test_covered",
                    "requirement_id": "REQ-LOOP-001",
                }
            ],
        )
        call_command("import_test_links", str(links))
        run = import_junit_xml(str(junit_file))
        link_results_to_requirements(run, str(links))
        update_test_requirement_links(run)

        requirement = Requirement.objects.get(external_id="REQ-LOOP-001")
        assert compute_verification_status(requirement) == VerificationStatus.PASSING

    def test_loop__derives_failing_status_from_a_failing_linked_test(
        self, db, spec_dir, junit_file, tmp_path
    ):
        call_command("parse_specs", str(spec_dir))
        links = _links_file(
            tmp_path,
            [
                {
                    "test_nodeid": "tests/test_loop.py::test_broken",
                    "requirement_id": "REQ-LOOP-001",
                }
            ],
        )
        call_command("import_test_links", str(links))
        run = import_junit_xml(str(junit_file))
        link_results_to_requirements(run, str(links))
        update_test_requirement_links(run)

        requirement = Requirement.objects.get(external_id="REQ-LOOP-001")
        assert compute_verification_status(requirement) == VerificationStatus.FAILING

    def test_loop__leaves_an_unlinked_requirement_untested(self, db, spec_dir):
        call_command("parse_specs", str(spec_dir))

        requirement = Requirement.objects.get(external_id="REQ-LOOP-000")
        assert compute_verification_status(requirement) == VerificationStatus.UNTESTED

    def test_loop__parses_the_declared_hierarchy(self, db, spec_dir):
        call_command("parse_specs", str(spec_dir))

        child = Requirement.objects.get(external_id="REQ-LOOP-001")
        assert child.get_parent().external_id == "REQ-LOOP-000"

    def test_loop__imports_links_the_extract_links_command_writes(self, db, spec_dir, tmp_path):
        call_command("parse_specs", str(spec_dir))
        links = _links_file(
            tmp_path,
            [
                {
                    "test_nodeid": "tests/test_loop.py::test_covered",
                    "requirement_id": "REQ-LOOP-001",
                }
            ],
        )
        call_command("import_test_links", str(links))

        assert TestRequirementLink.objects.filter(requirement__external_id="REQ-LOOP-001").exists()

    def test_loop__rejects_a_links_file_naming_no_known_requirement(self, db, spec_dir, tmp_path):
        call_command("parse_specs", str(spec_dir))
        links = _links_file(
            tmp_path,
            [{"test_nodeid": "tests/test_loop.py::test_covered", "requirement_id": "REQ-GHOST-1"}],
        )

        with pytest.raises(Exception, match="resolved to no requirement"):
            call_command("import_test_links", str(links))


def test_spec_tree__is_parsed_by_the_repository_gate(db):
    """The gate parses `meta/specs/`, so that tree must stay importable."""
    tree = Path(__file__).resolve().parents[3] / "meta" / "specs"
    call_command("parse_specs", str(tree))

    assert Requirement.objects.filter(external_id="REQ-CORE-000").exists()

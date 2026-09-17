"""Tests for the planner, which drafts tasks from a roadmap item or the untested requirements."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import responses

from requirements.services.task_planner import (
    PlannerRefusal,
    criteria,
    find_item,
    gap_drafts,
    named_paths,
    read_roadmap,
    roadmap_draft,
    untested_requirements,
)
from spectrace_client.client import ValidationClient

URL = "http://worker.test"

ROADMAP = """# Roadmap

## Now

### 4. Link tests in every language the repo tests in

REQ-TASK-002 covers the pytest marker. README.md shows a linked test and
spectrace/cli.py parses the rest.

**Done when:** README.md shows a linked test for each runner, and an example
project per language pushes its links in CI.

### 5. Refresh the planning record

Nothing here names a requirement or a path.

**Done when:** the record matches the code.
"""


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "spectrace").mkdir(parents=True)
    (root / ".planning").mkdir()
    (root / ".planning" / "STATE.md").write_text("state\n")
    (root / "README.md").write_text("readme\n")
    (root / "spectrace" / "cli.py").write_text("cli\n")
    (root / "ROADMAP.md").write_text(ROADMAP)
    return root


@pytest.fixture
def items(repo):
    return read_roadmap(repo / "ROADMAP.md")


def gap_row(external_id: str = "REQ-AUTH-001") -> dict:
    return {
        "external_id": external_id,
        "title": "User login",
        "description": "# User login\n\nUsers log in with email and password.\n\n## Criteria",
        "verification_status": "untested",
        "source_file": "specs/auth/login.md",
    }


def test_read_roadmap__separates_each_item_from_its_done_when(items):
    assert [item.number for item in items] == ["4", "5"]
    assert items[0].title == "Link tests in every language the repo tests in"
    assert items[0].done_when.startswith("README.md shows a linked test")
    assert "Done when" not in items[0].body
    assert items[0].source == "ROADMAP.md"


def test_find_item__matches_a_number_or_text_from_the_title(items):
    assert find_item(items, "4").number == "4"
    assert find_item(items, "planning record").number == "5"


def test_find_item__refuses_a_name_no_item_carries(items):
    with pytest.raises(PlannerRefusal, match="no item matching 'rewrite'"):
        find_item(items, "rewrite")


def test_criteria__splits_a_completion_sentence_on_its_conjunction():
    assert criteria("The report lands, and the dashboard charts it.") == [
        "The report lands",
        "The dashboard charts it",
    ]


def test_named_paths__keeps_only_the_paths_the_checkout_holds(repo):
    body = "README.md shows it, spectrace/cli.py parses it, and specs/ghost.md does not exist."

    assert named_paths(body, repo) == ["README.md", "spectrace/cli.py"]


def test_named_paths__keeps_a_path_under_a_dot_directory(repo):
    assert named_paths("`.planning/STATE.md` stops at v9.", repo) == [".planning/STATE.md"]


def test_roadmap_draft__fills_the_three_fields_the_spec_gate_reads(repo, items):
    draft = roadmap_draft(find_item(items, "4"), "planner-1", repo)

    assert draft["requirements"] == ["REQ-TASK-002"]
    assert draft["scope_in"] == ["README.md", "spectrace/cli.py"]
    assert draft["done_when"] == [
        "README.md shows a linked test for each runner",
        "An example project per language pushes its links in CI",
    ]
    assert draft["task_id"] == "plan-4-link-tests-in-every-language-the-repo-tests-in"
    assert draft["agent_id"] == "planner-1"
    assert draft["spec_ref"] == "ROADMAP.md#4-link-tests-in-every-language-the-repo-tests-in"


def test_roadmap_draft__adds_the_requirements_and_scope_the_caller_names(repo, items):
    draft = roadmap_draft(
        find_item(items, "5"),
        "planner-1",
        repo,
        requirements=("REQ-DOC-001",),
        scope_in=("docs/current-state.md",),
        scope_out=("worker/",),
    )

    assert draft["requirements"] == ["REQ-DOC-001"]
    assert draft["scope_in"] == ["docs/current-state.md"]
    assert draft["scope_out"] == ["worker/"]


def test_roadmap_draft__refuses_an_item_that_names_no_requirement_or_path(repo, items):
    with pytest.raises(PlannerRefusal, match="names requirements, scope_in"):
        roadmap_draft(find_item(items, "5"), "planner-1", repo)


def test_gap_drafts__drafts_one_task_per_untested_requirement():
    drafts = gap_drafts([gap_row("REQ-AUTH-001"), gap_row("REQ-AUTH-002")], "planner-1")

    assert [draft["task_id"] for draft in drafts] == ["plan-req-auth-001", "plan-req-auth-002"]
    assert drafts[0]["requirements"] == ["REQ-AUTH-001"]
    assert drafts[0]["scope_in"] == ["specs/auth/login.md"]
    assert drafts[0]["done_when"] == [
        "A test links to REQ-AUTH-001 and passes",
        "The Worker reports REQ-AUTH-001 as passing",
    ]
    assert drafts[0]["spec_ref"] == "specs/auth/login.md#REQ-AUTH-001"


def test_gap_draft__describes_the_gap_with_the_spec_prose_under_its_heading():
    draft = gap_drafts([gap_row()], "planner-1")[0]

    assert draft["description"] == (
        "REQ-AUTH-001 User login is untested: no test claims it."
        " Users log in with email and password."
    )


def test_gap_drafts__refuses_an_empty_gap_list():
    with pytest.raises(PlannerRefusal, match="no untested requirement"):
        gap_drafts([], "planner-1")


@responses.activate
def test_untested_requirements__asks_the_worker_for_the_untested_page():
    responses.add(
        responses.GET,
        f"{URL}/api/v1/specs/",
        json={"data": {"project": "spectrace", "requirements": [gap_row()]}},
    )

    rows = untested_requirements(ValidationClient(api_url=URL, api_key="secret"), "spectrace", 3)

    assert rows == [gap_row()]
    request = responses.calls[0].request
    assert request.headers["X-API-Key"] == "secret"
    assert "verification_status=untested" in request.url
    assert "per_page=3" in request.url
    assert "project=spectrace" in request.url


def test_tasks_plan__drafts_from_a_roadmap_item_in_a_fresh_interpreter(repo):
    root = Path(__file__).resolve().parents[2]
    probe = textwrap.dedent(
        """
        import sys

        sys.path.insert(0, %r)
        import spectrace.cli as module
        from click.testing import CliRunner

        result = CliRunner().invoke(
            module.cli,
            ["tasks", "plan", "--agent", "planner-1", "--item", "4", "--dry-run",
             "--roadmap", %r, "--repo", %r,
             "--url", "http://worker.test", "--api-key", "secret"],
        )
        if result.exception and not isinstance(result.exception, SystemExit):
            raise result.exception
        print(result.output)
        """
    ) % (str(root), str(repo / "ROADMAP.md"), str(repo))

    finished = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, cwd=repo
    )

    assert finished.returncode == 0, finished.stdout + finished.stderr
    drafts = json.loads(finished.stdout)
    assert [draft["task_id"] for draft in drafts] == [
        "plan-4-link-tests-in-every-language-the-repo-tests-in"
    ]
    assert drafts[0]["requirements"] == ["REQ-TASK-002"]

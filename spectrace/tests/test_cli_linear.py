"""Tests for the spectrace linear commands, which reach Linear without a server."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import responses
from click.testing import CliRunner

from cli import cli
from requirements.services.linear_reporter import outcomes_by_requirement

URL = "http://worker.test"
AUTH = ["--url", URL, "--api-key", "secret"]
LINEAR = "https://api.linear.app/graphql"
KEY = ["--linear-api-key", "lin_api_test"]

PUSH_SUMMARY = {
    "project": "spectrace",
    "requirements": {"created": 1, "updated": 0, "deleted": 0},
    "links": {"created": 0, "updated": 0, "deleted": 0},
    "flows": {"created": 0, "updated": 0, "deleted": 0},
    "unresolved": [],
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def junit(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text(
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="tests.test_login" name="test_login" time="0.1"/>'
        '<testcase classname="tests.test_logout" name="test_logout" time="0.2">'
        '<failure message="assert 1 == 2"/></testcase>'
        "</testsuite></testsuites>"
    )
    return path


@pytest.fixture
def links_file(tmp_path):
    path = tmp_path / "links.json"
    path.write_text(
        json.dumps(
            {
                "links": [
                    {"test_nodeid": "tests/test_login.py::test_login", "requirement_id": "PROJ-1"},
                    {
                        "test_nodeid": "tests/test_logout.py::test_logout",
                        "requirement_id": "PROJ-1",
                    },
                ]
            }
        )
    )
    return path


def _issues_response(nodes):
    return {"data": {"issues": {"pageInfo": {"hasNextPage": False}, "nodes": nodes}}}


ISSUE = {
    "identifier": "PROJ-1",
    "title": "Log in",
    "description": "Users log in",
    "priority": 2,
    "state": {"name": "In Progress", "type": "started"},
    "labels": {"nodes": [{"name": "requirement"}, {"name": "verify:test"}]},
    "parent": None,
    "team": {"key": "PROJ"},
}


@responses.activate
def test_linear_pull__pushes_fetched_issues_as_requirements(runner):
    responses.add(responses.POST, LINEAR, json=_issues_response([ISSUE]))
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": PUSH_SUMMARY})

    result = runner.invoke(cli, ["linear", "pull", "--project", "spectrace", *KEY, *AUTH])

    assert result.exit_code == 0, result.output
    sent = json.loads(responses.calls[1].request.body)
    assert sent["project"] == "spectrace"
    assert sent["links"] == []
    assert sent["requirements"] == [
        {
            "external_id": "PROJ-1",
            "title": "Log in",
            "description": "Users log in",
            "tags": [],
            "priority": "high",
            "status": "active",
            "parent_id": None,
            "source_file": "linear://PROJ/PROJ-1",
            "verification_method": "test",
            "scope": "",
            "condition": "",
            "component": "",
            "timing": "",
            "response": "",
        }
    ]


@responses.activate
def test_linear_pull__lists_and_pushes_nothing_on_a_dry_run(runner):
    responses.add(responses.POST, LINEAR, json=_issues_response([ISSUE]))

    result = runner.invoke(
        cli, ["linear", "pull", "--project", "spectrace", "--dry-run", *KEY, *AUTH]
    )

    assert result.exit_code == 0, result.output
    assert result.output == "PROJ-1: Log in\n"
    assert len(responses.calls) == 1


@responses.activate
def test_linear_pull__reports_an_empty_label(runner):
    responses.add(responses.POST, LINEAR, json=_issues_response([]))

    result = runner.invoke(
        cli, ["linear", "pull", "--project", "spectrace", "--label", "spec", *KEY, *AUTH]
    )

    assert result.exit_code == 0, result.output
    assert result.output == "No issues labeled spec\n"


def test_outcomes_by_requirement__tallies_each_requirements_cases():
    outcomes = outcomes_by_requirement(
        [
            {"status": "passed", "requirement_ids": ["REQ-1"]},
            {"status": "failed", "requirement_ids": ["REQ-1", "REQ-2"]},
            {"status": "error", "requirement_ids": ["REQ-2"]},
            {"status": "skipped", "requirement_ids": ["REQ-2"]},
            {"status": "passed", "requirement_ids": []},
        ]
    )

    first, second = outcomes["REQ-1"], outcomes["REQ-2"]
    assert (first.passed, first.failed, first.total) == (1, 1, 2)
    assert (second.passed, second.failed, second.total) == (0, 2, 3)


@responses.activate
def test_linear_report__tallies_each_requirement_on_a_dry_run(runner, junit, links_file):
    result = runner.invoke(
        cli,
        ["linear", "report", str(junit), "--links", str(links_file), "--dry-run", *KEY],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "PROJ-1: 1 passed, 1 failed, 2 total\n"
    assert len(responses.calls) == 0


@responses.activate
def test_linear_report__comments_the_tally_on_the_issue(runner, junit, links_file):
    responses.add(
        responses.POST,
        LINEAR,
        json={
            "data": {
                "issue": {
                    "id": "issue-uuid",
                    "identifier": "PROJ-1",
                    "title": "Log in",
                    "state": {"type": "started"},
                    "team": {"id": "team-uuid"},
                    "labels": {"nodes": []},
                }
            }
        },
    )
    responses.add(responses.POST, LINEAR, json={"data": {"commentCreate": {"success": True}}})

    result = runner.invoke(
        cli,
        [
            "linear",
            "report",
            str(junit),
            "--links",
            str(links_file),
            "--no-labels",
            "--git-sha",
            "abc1234567",
            *KEY,
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "Updated 1 issues, skipped 0\n"
    comment = json.loads(responses.calls[1].request.body)["variables"]["body"]
    assert "| Passed | 1 |" in comment
    assert "| Failed | 1 |" in comment
    assert "Commit: `abc12345`" in comment


@responses.activate
def test_linear_report__skips_a_completed_issue(runner, junit, links_file):
    responses.add(
        responses.POST,
        LINEAR,
        json={
            "data": {
                "issue": {
                    "id": "issue-uuid",
                    "identifier": "PROJ-1",
                    "state": {"type": "completed"},
                    "team": {"id": "team-uuid"},
                    "labels": {"nodes": []},
                }
            }
        },
    )

    result = runner.invoke(cli, ["linear", "report", str(junit), "--links", str(links_file), *KEY])

    assert result.exit_code == 0, result.output
    assert result.output == "Updated 0 issues, skipped 1\n"


@responses.activate
def test_linear_check__passes_when_the_token_answers(runner):
    responses.add(responses.POST, LINEAR, json={"data": {"viewer": {"id": "u1", "name": "Ada"}}})
    responses.add(responses.POST, LINEAR, json={"data": {"issues": {"nodes": [{"id": "i1"}]}}})

    result = runner.invoke(cli, ["linear", "check", "--workspace", "acme", "--team", "PROJ", *KEY])

    assert result.exit_code == 0, result.output
    assert "FAILED" not in result.output


def test_linear_check__refuses_a_key_with_the_wrong_shape(runner):
    result = runner.invoke(cli, ["linear", "check", "--linear-api-key", "nope"])

    assert result.exit_code == 1
    assert "FAILED" in result.output


def test_linear_commands__run_without_django(tmp_path):
    root = Path(__file__).resolve().parents[2]
    probe = textwrap.dedent(
        """
        import sys

        sys.path.insert(0, %r)
        import spectrace.cli as module
        from click.testing import CliRunner

        CliRunner().invoke(module.cli, ["linear", "--help"])
        print("django" in sys.modules)
        """
    ) % str(root)

    finished = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, cwd=tmp_path
    )

    assert finished.stdout.strip() == "False", finished.stdout + finished.stderr

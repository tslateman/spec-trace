"""Tests for the spectrace CLI commands that push to the Worker."""

import json
from unittest.mock import patch

import pytest
import responses
from click.testing import CliRunner
from freezegun import freeze_time
from responses import matchers

from cli import cli
from requirements.models import Requirement
from requirements.services.impact_analyzer import ImpactResult

URL = "http://worker.test"
AUTH = ["--url", URL, "--api-key", "secret"]
COUNTS = {
    "project": "spectrace",
    "requirements": {"created": 2, "updated": 0, "deleted": 0},
    "links": {"created": 3, "updated": 0, "deleted": 0},
    "flows": {"created": 1, "updated": 0, "deleted": 0},
    "unresolved": [{"kind": "link", "source": "tests/test_x.py::test_x", "ref": "REQ-GONE"}],
}
SUMMARY = {
    "success": True,
    "imported": 2,
    "skipped": 0,
    "created_validations": 2,
    "successful": 1,
    "failed": 1,
}
TEST_RUN_SUMMARY = {
    "success": True,
    "run_id": 7,
    "imported": 3,
    "linked": 2,
    "passed": 2,
    "failed": 1,
    "errors": 0,
    "skipped": 0,
}
OUTCOME = {
    "cursor": "1",
    "task_id": "task-auth-001",
    "title": "Add login",
    "status": "merged",
    "done_when_results": [{"criterion": "tests pass", "passed": True, "notes": ""}],
    "reason": None,
    "commit_sha": "abc123",
    "attempt_count": 1,
    "max_attempts": 2,
    "occurred_at": "2026-08-31T12:00:00+00:00",
    "task_created_at": "2026-08-30T12:00:00+00:00",
    "drained": False,
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def specs_dir(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "root.md").write_text(
        "---\nid: REQ-001\ntitle: Root\nstatus: active\nrisk_level: high\n---\n\nThe root.\n"
    )
    (specs / "child.md").write_text(
        "---\nid: REQ-002\ntitle: Child\nparent: REQ-001\ndepends_on: [REQ-001]\n---\n\n"
        "The child.\n"
    )
    return specs


@pytest.fixture
def links_file(tmp_path):
    path = tmp_path / "links.json"
    path.write_text(
        json.dumps(
            {
                "links": [
                    {"test_nodeid": "tests/test_root.py::test_root", "requirement_id": "REQ-001"},
                    {
                        "test_nodeid": "tests/test_both.py::test_both",
                        "linear_issue_ids": ["REQ-001", "REQ-002"],
                    },
                ]
            }
        )
    )
    return path


@pytest.fixture
def vitest_junit(tmp_path):
    path = tmp_path / "vitest-junit.xml"
    path.write_text(
        '<testsuites name="vitest tests"><testsuite name="worker/test/ledger.test.ts">'
        '<testcase classname="worker/test/ledger.test.ts" '
        'name="TaskLedger claims &gt; [REQ-TASK-002] claim grants one" time="0.02"/>'
        '<testcase classname="worker/test/ledger.test.ts" '
        'name="TaskLedger lease alarm &gt; alarm releases leases" time="0.01"/>'
        "</testsuite></testsuites>"
    )
    return path


@pytest.fixture
def flows_dir(tmp_path):
    flows = tmp_path / "flows"
    flows.mkdir()
    (flows / "checkout.yaml").write_text(
        "id: checkout\n"
        "title: Checkout\n"
        "description: Buy a thing\n"
        "requirements: [REQ-002]\n"
        "steps:\n"
        "  - name: load\n"
        "    type: handler\n"
        "    display_name: Load\n"
        "    handler: flows.load\n"
    )
    return flows


def _sent(call_index: int = 0) -> dict:
    return json.loads(responses.calls[call_index].request.body)


@responses.activate
def test_push__sends_specs_links_and_flows(runner, specs_dir, links_file, flows_dir):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})

    result = runner.invoke(
        cli,
        [
            "push",
            "--specs",
            str(specs_dir),
            "--flows",
            str(flows_dir),
            "--links",
            str(links_file),
            "--replace",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    sent = _sent()
    assert sent["project"] == "spectrace"
    assert sent["replace"] is True
    assert {r["external_id"]: r["parent_id"] for r in sent["requirements"]} == {
        "REQ-001": None,
        "REQ-002": "REQ-001",
    }
    child = next(r for r in sent["requirements"] if r["external_id"] == "REQ-002")
    assert child["depends_on"] == ["REQ-001"]
    assert sent["links"] == [
        {"test_nodeid": "tests/test_root.py::test_root", "requirement_id": "REQ-001"},
        {"test_nodeid": "tests/test_both.py::test_both", "requirement_id": "REQ-001"},
        {"test_nodeid": "tests/test_both.py::test_both", "requirement_id": "REQ-002"},
    ]
    assert sent["flows"] == [
        {
            "name": "checkout",
            "display_name": "Checkout",
            "description": "Buy a thing",
            "version": 1,
            "requirements": ["REQ-002"],
            "source_file": str(flows_dir / "checkout.yaml"),
            "steps": [
                {
                    "name": "load",
                    "handler": "flows.load",
                    "display_name": "Load",
                    "description": "",
                    "type": "handler",
                    "config": {},
                }
            ],
        }
    ]
    assert responses.calls[0].request.headers["X-API-Key"] == "secret"
    assert "requirements: 2 created, 0 updated, 0 deleted" in result.output
    assert "unresolved link REQ-GONE in tests/test_x.py::test_x" in result.output


@responses.activate
def test_push__reads_url_and_key_from_environment(runner, specs_dir):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})

    result = runner.invoke(
        cli,
        ["push", "--specs", str(specs_dir)],
        env={"SPECTRACE_URL": URL, "SPECTRACE_API_KEY": "from-env"},
    )

    assert result.exit_code == 0, result.output
    assert responses.calls[0].request.headers["X-API-Key"] == "from-env"
    assert _sent()["replace"] is False
    assert _sent()["links"] == []
    assert _sent()["flows"] == []


@responses.activate
def test_push__reports_the_server_error(runner, specs_dir):
    responses.add(
        responses.PUT,
        f"{URL}/api/v1/specs/",
        status=400,
        json={"error": {"code": "validation_error", "message": "risk_level 'extreme'"}},
    )

    result = runner.invoke(cli, ["push", "--specs", str(specs_dir), *AUTH])

    assert result.exit_code == 1
    assert "400 from" in result.output
    assert "risk_level 'extreme'" in result.output


@responses.activate
def test_results_push__posts_inapp_validations(runner, tmp_path):
    responses.add(responses.POST, f"{URL}/api/v1/results/enforcement/", json=SUMMARY)
    validations = [
        {"requirement_id": "REQ-001", "name": "Login", "status": "success"},
        {"requirement_id": "REQ-002", "name": "Logout", "status": "failure", "message": "boom"},
    ]
    inapp = tmp_path / "inapp.json"
    inapp.write_text(json.dumps({"source": "production-app", "validations": validations}))

    result = runner.invoke(cli, ["results", "push", str(inapp), *AUTH])

    assert result.exit_code == 0, result.output
    assert _sent() == {
        "source": "production-app",
        "validations": validations,
        "update_verification_status": True,
    }
    assert "Imported 2 validations (successful=1, failed=1, skipped=0)" in result.output


@responses.activate
def test_results_push__sends_junit_cases_as_a_test_run(runner, tmp_path, links_file):
    responses.add(responses.POST, f"{URL}/api/v1/results/test-runs/", json=TEST_RUN_SUMMARY)
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="tests.test_root" name="test_root" time="0.1"/>'
        '<testcase classname="tests.test_both" name="test_both" time="0.2">'
        '<failure message="assert 1 == 2"/></testcase>'
        '<testcase classname="tests.test_unlinked" name="test_other" time="0.3"/>'
        "</testsuite></testsuites>"
    )

    result = runner.invoke(cli, ["results", "push", str(junit), "--links", str(links_file), *AUTH])

    assert result.exit_code == 0, result.output
    assert _sent() == {
        "source_file": str(junit),
        "update_verification_status": True,
        "results": [
            {
                "test_nodeid": "tests/test_root.py::test_root",
                "classname": "tests.test_root",
                "name": "test_root",
                "time": 0.1,
                "status": "passed",
                "message": "",
                "requirement_ids": ["REQ-001"],
            },
            {
                "test_nodeid": "tests/test_both.py::test_both",
                "classname": "tests.test_both",
                "name": "test_both",
                "time": 0.2,
                "status": "failed",
                "message": "assert 1 == 2",
                "requirement_ids": ["REQ-001", "REQ-002"],
            },
            {
                "test_nodeid": "tests/test_unlinked.py::test_other",
                "classname": "tests.test_unlinked",
                "name": "test_other",
                "time": 0.3,
                "status": "passed",
                "message": "",
                "requirement_ids": [],
            },
        ],
    }
    assert "Imported 3 test results linked to 2 requirements" in result.output


@responses.activate
def test_results_push__links_junit_cases_by_the_tags_in_their_names(runner, vitest_junit):
    responses.add(responses.POST, f"{URL}/api/v1/results/test-runs/", json=TEST_RUN_SUMMARY)

    result = runner.invoke(cli, ["results", "push", str(vitest_junit), *AUTH])

    assert result.exit_code == 0, result.output
    assert [(r["test_nodeid"], r["requirement_ids"]) for r in _sent()["results"]] == [
        (
            "worker/test/ledger.test.ts::TaskLedger claims > [REQ-TASK-002] claim grants one",
            ["REQ-TASK-002"],
        ),
        ("worker/test/ledger.test.ts::TaskLedger lease alarm > alarm releases leases", []),
    ]


@responses.activate
def test_results_push__unions_tags_with_the_links_file(runner, tmp_path, links_file):
    responses.add(responses.POST, f"{URL}/api/v1/results/test-runs/", json=TEST_RUN_SUMMARY)
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="tests.test_root" name="test_root[REQ-001][REQ-003]" time="0.1"/>'
        "</testsuite></testsuites>"
    )

    result = runner.invoke(cli, ["results", "push", str(junit), "--links", str(links_file), *AUTH])

    assert result.exit_code == 0, result.output
    assert _sent()["results"][0]["requirement_ids"] == ["REQ-001", "REQ-003"]


@responses.activate
def test_push__derives_links_from_a_junit_report_alongside_extract_links(
    runner, specs_dir, links_file, vitest_junit
):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})

    result = runner.invoke(
        cli,
        [
            "push",
            "--specs",
            str(specs_dir),
            "--links",
            str(links_file),
            "--links",
            str(vitest_junit),
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    assert _sent()["links"] == [
        {"test_nodeid": "tests/test_root.py::test_root", "requirement_id": "REQ-001"},
        {"test_nodeid": "tests/test_both.py::test_both", "requirement_id": "REQ-001"},
        {"test_nodeid": "tests/test_both.py::test_both", "requirement_id": "REQ-002"},
        {
            "test_nodeid": (
                "worker/test/ledger.test.ts::TaskLedger claims > [REQ-TASK-002] claim grants one"
            ),
            "requirement_id": "REQ-TASK-002",
        },
    ]


@freeze_time("2026-08-31 12:00:00")
@responses.activate
@patch("requirements.services.impact_analyzer.ImpactAnalyzer", autospec=True)
def test_specs_impact_push__stores_the_report(mock_analyzer, runner, specs_dir):
    mock_analyzer.return_value.analyze.return_value = ImpactResult(
        changed_requirements=["REQ-001"],
        affected_tests=["tests/test_root.py::test_root"],
        hierarchy_expansion={"REQ-001": ["REQ-002"]},
        dependency_expansion={},
        risk_score=0.4,
        risk_level="medium",
    )
    receipt = {
        "project": "spectrace",
        "generated_at": "2026-08-31T12:00:00+00:00",
        "stored_at": "2026-08-31T12:00:01+00:00",
    }
    responses.add(
        responses.POST, f"{URL}/api/v1/results/impact/", status=201, json={"data": receipt}
    )

    result = runner.invoke(
        cli, ["specs", "impact", "main", "feature", "--spec-dir", str(specs_dir), "--push", *AUTH]
    )

    assert result.exit_code == 0, result.output
    mock_analyzer.assert_called_once_with(spec_dir=str(specs_dir))
    mock_analyzer.return_value.analyze.assert_called_once_with(
        "main", "feature", include_hierarchy=True
    )
    assert _sent() == {
        "project": "spectrace",
        "base": "main",
        "head": "feature",
        "generated_at": "2026-08-31T12:00:00+00:00",
        "changed_requirements": ["REQ-001"],
        "affected_tests": ["tests/test_root.py::test_root"],
        "hierarchy_expansion": {"REQ-001": ["REQ-002"]},
        "dependency_expansion": {},
        "risk_score": 0.4,
        "risk_level": "medium",
    }
    assert "Stored impact report for spectrace at 2026-08-31T12:00:01+00:00" in result.output


def test_specs_impact_push__rejects_code_mode(runner):
    result = runner.invoke(cli, ["specs", "impact", "main", "feature", "--code", "--push", *AUTH])

    assert result.exit_code == 2
    assert "drop --code" in result.output


@patch("cli._run", autospec=True)
def test_specs_impact__still_delegates_without_push(mock_run, runner):
    result = runner.invoke(cli, ["specs", "impact", "main", "feature"])

    assert result.exit_code == 0
    mock_run.assert_called_once()


@freeze_time("2026-08-31 12:00:00")
@responses.activate
@patch("requirements.validator.detect_all_drift", autospec=True)
def test_specs_drift_push__stores_the_report(mock_detect, runner, specs_dir, tmp_path):
    mock_detect.return_value.to_dict.return_value = {
        "errors": [],
        "warnings": [{"type": "spec_drift", "id": "REQ-001", "message": "changed"}],
        "summary": {"items_checked": 2, "errors": 0, "warnings": 1},
    }
    receipt = {
        "project": "spectrace",
        "generated_at": "2026-08-31T12:00:00+00:00",
        "stored_at": "2026-08-31T12:00:01+00:00",
    }
    responses.add(
        responses.POST, f"{URL}/api/v1/results/drift/", status=201, json={"data": receipt}
    )
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    result = runner.invoke(
        cli,
        ["specs", "drift", "--tests", str(tests_dir), "--specs", str(specs_dir), "--push", *AUTH],
    )

    assert result.exit_code == 0, result.output
    mock_detect.assert_called_once_with(tests_dir, specs_dir)
    assert _sent() == {
        "project": "spectrace",
        "generated_at": "2026-08-31T12:00:00+00:00",
        "errors": [],
        "warnings": [{"type": "spec_drift", "id": "REQ-001", "message": "changed"}],
        "summary": {"items_checked": 2, "errors": 0, "warnings": 1},
    }
    assert "Stored drift report for spectrace" in result.output


def test_specs_drift_push__needs_a_remote(runner):
    result = runner.invoke(cli, ["specs", "drift", "--push"], env={"SPECTRACE_URL": ""})

    assert result.exit_code == 2
    assert "--push needs --url and --api-key" in result.output


@responses.activate
def test_demo_load_vendor__posts_an_older_and_a_newer_run(runner, specs_dir):
    responses.add(responses.POST, f"{URL}/api/v1/results/enforcement/", json=SUMMARY)

    result = runner.invoke(cli, ["demo", "load", "vendor", "--specs", str(specs_dir), *AUTH])

    assert result.exit_code == 0, result.output
    older, newer = _sent(0), _sent(1)
    assert older["source"] == "demo://vendor/run-1"
    assert newer["source"] == "demo://vendor/run-2"
    assert len(older["validations"]) == len(newer["validations"]) == 16
    plaid = next(v for v in newer["validations"] if v["name"] == "Plaid - Validation 1")
    assert plaid["status"] == "failure"
    assert plaid["message"] == "Connection timeout - regression detected"
    assert plaid["context"] == {"vendor": "Plaid", "feature_flags": {"legacy_mode": True}}
    assert plaid["endpoint"] == "demo://vendor/plaid/v1"
    assert next(v for v in older["validations"] if v["name"] == "Plaid - Validation 1")[
        "status"
    ] == ("success")
    assert {v["requirement_id"] for v in older["validations"]} == {"REQ-001", "REQ-002"}


@responses.activate
def test_demo_load_matrix__pushes_specs_then_results(runner, specs_dir):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})
    responses.add(responses.POST, f"{URL}/api/v1/results/enforcement/", json=SUMMARY)

    result = runner.invoke(cli, ["demo", "load", "matrix", "--specs", str(specs_dir), *AUTH])

    assert result.exit_code == 0, result.output
    assert {r["external_id"] for r in _sent(0)["requirements"]} == {"REQ-001", "REQ-002"}
    run = _sent(1)
    assert run["source"] == "demo://matrix-demo"
    assert len(run["validations"]) == 14
    assert run["validations"][0]["name"] == "tests/test_auth.py::test_login_success"
    assert {v["status"] for v in run["validations"]} == {"success", "failure", "unknown"}


@responses.activate
@patch("requirements.services.impact_analyzer.prepare_impact_demo_branch", autospec=True)
def test_demo_load_impact__pushes_links_and_prepares_the_branch(mock_branch, runner, specs_dir):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})

    result = runner.invoke(cli, ["demo", "load", "impact", "--specs", str(specs_dir), *AUTH])

    assert result.exit_code == 0, result.output
    links = _sent()["links"]
    assert len(links) == 2
    assert {link["requirement_id"] for link in links} == {"REQ-001", "REQ-002"}
    assert all(link["test_nodeid"].startswith("tests/test_req_00") for link in links)
    mock_branch.assert_called_once()
    assert mock_branch.call_args.args[1] == specs_dir
    assert mock_branch.call_args.args[2] == "demo/impact-analysis"
    assert "spectrace specs impact main demo/impact-analysis --push" in result.output


@responses.activate
def test_demo_load_flow__pushes_the_registered_flows(runner, specs_dir):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})

    result = runner.invoke(cli, ["demo", "load", "flow", "--specs", str(specs_dir), *AUTH])

    assert result.exit_code == 0, result.output
    sent = _sent()
    assert sent["requirements"] == []
    assert [flow["name"] for flow in sent["flows"]] == ["linear-connection"]
    assert [step["name"] for step in sent["flows"][0]["steps"]] == ["config", "auth", "permissions"]


@responses.activate
@patch("requirements.services.lore_bridge.notify_lore", autospec=True)
def test_lore_sync__journals_every_page_then_acks_and_saves_the_cursor(
    mock_notify, runner, tmp_path
):
    mock_notify.return_value = True
    second = {
        **OUTCOME,
        "cursor": "2",
        "task_id": "task-auth-002",
        "status": "abandoned",
        "reason": "scope_in names no file the coder can open",
    }
    third = {**OUTCOME, "cursor": "3", "task_id": "task-auth-003", "done_when_results": None}
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/outcomes",
        json={"data": [OUTCOME, second], "meta": {"limit": 50, "next_cursor": "2"}},
        match=[matchers.query_param_matcher({"limit": "50"})],
    )
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/outcomes",
        json={"data": [third], "meta": {"limit": 50, "next_cursor": None}},
        match=[matchers.query_param_matcher({"limit": "50", "since": "2"})],
    )
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/outcomes/ack",
        json={"data": {"cursor": "3", "drained": 3}},
    )
    cursor_file = tmp_path / "state" / "lore-cursor"

    result = runner.invoke(cli, ["lore", "sync", "--cursor-file", str(cursor_file), *AUTH])

    assert result.exit_code == 0, result.output
    assert mock_notify.call_count == 3
    mock_notify.assert_any_call(
        task_id="task-auth-001",
        task_name="Add login",
        status="MERGED",
        done_when_results=[{"criterion": "tests pass", "passed": True, "notes": ""}],
        attempt_count=1,
        max_attempts=2,
        commit_sha="abc123",
        reason=None,
        merge_sha=None,
    )
    mock_notify.assert_any_call(
        task_id="task-auth-002",
        task_name="Add login",
        status="ABANDONED",
        done_when_results=[{"criterion": "tests pass", "passed": True, "notes": ""}],
        attempt_count=1,
        max_attempts=2,
        commit_sha="abc123",
        reason="scope_in names no file the coder can open",
        merge_sha=None,
    )
    mock_notify.assert_any_call(
        task_id="task-auth-003",
        task_name="Add login",
        status="MERGED",
        done_when_results=[],
        attempt_count=1,
        max_attempts=2,
        commit_sha="abc123",
        reason=None,
        merge_sha=None,
    )
    assert json.loads(responses.calls[-1].request.body) == {"cursor": "3"}
    assert cursor_file.read_text() == "3"
    assert "Journaled 3 outcomes" in result.output


@responses.activate
@patch("requirements.services.lore_bridge.notify_lore", autospec=True)
def test_lore_sync__passes_the_merge_sha_when_the_outcome_carries_one(
    mock_notify, runner, tmp_path
):
    mock_notify.return_value = True
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/outcomes",
        json={
            "data": [{**OUTCOME, "branch": "task/task-auth-001", "merge_sha": "99f0011"}],
            "meta": {"limit": 50, "next_cursor": None},
        },
    )
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/outcomes/ack",
        json={"data": {"cursor": "1", "drained": 1}},
    )

    result = runner.invoke(cli, ["lore", "sync", "--cursor-file", str(tmp_path / "cursor"), *AUTH])

    assert result.exit_code == 0, result.output
    assert mock_notify.call_args.kwargs["merge_sha"] == "99f0011"


@responses.activate
@patch("requirements.services.lore_bridge.notify_lore", autospec=True)
def test_lore_sync__acks_only_what_lore_accepted(mock_notify, runner, tmp_path):
    mock_notify.side_effect = [True, False]
    second = {**OUTCOME, "cursor": "2", "task_id": "task-auth-002"}
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/outcomes",
        json={"data": [OUTCOME, second], "meta": {"limit": 50, "next_cursor": None}},
    )
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/outcomes/ack",
        json={"data": {"cursor": "1", "drained": 1}},
    )
    cursor_file = tmp_path / "lore-cursor"

    result = runner.invoke(cli, ["lore", "sync", "--cursor-file", str(cursor_file), *AUTH])

    assert result.exit_code == 1
    assert json.loads(responses.calls[-1].request.body) == {"cursor": "1"}
    assert cursor_file.read_text() == "1"
    assert "Lore refused task-auth-002; acknowledged through 1" in result.output


@responses.activate
@patch("requirements.services.lore_bridge.notify_lore", autospec=True)
def test_lore_sync__resumes_from_the_saved_cursor(mock_notify, runner, tmp_path):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/outcomes",
        json={"data": [], "meta": {"limit": 50, "next_cursor": None}},
        match=[matchers.query_param_matcher({"limit": "50", "since": "7"})],
    )
    cursor_file = tmp_path / "lore-cursor"
    cursor_file.write_text("7\n")

    result = runner.invoke(cli, ["lore", "sync", "--cursor-file", str(cursor_file), *AUTH])

    assert result.exit_code == 0, result.output
    mock_notify.assert_not_called()
    assert len(responses.calls) == 1
    assert cursor_file.read_text() == "7\n"
    assert "Journaled 0 outcomes" in result.output


@pytest.fixture
def slos_dir(tmp_path):
    directory = tmp_path / "slos"
    directory.mkdir()
    (directory / "checkout.yaml").write_text(
        "apiVersion: openslo/v1\n"
        "kind: SLO\n"
        "metadata:\n"
        "  name: checkout-availability\n"
        "  displayName: Checkout availability\n"
        "  labels:\n"
        "    requirements: REQ-001, REQ-002\n"
        "spec:\n"
        "  service: checkout\n"
        "  description: Checkout answers\n"
        "  objectives:\n"
        "    - target: 0.999\n"
        "      timeWindow:\n"
        "        duration: 28d\n"
        "  budgetingMethod: Occurrences\n"
    )
    return directory


@responses.activate
def test_push__sends_openslo_documents_when_slos_is_given(runner, specs_dir, slos_dir):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})
    responses.add(
        responses.PUT,
        f"{URL}/api/v1/slos/",
        json={"data": {"created": 1, "updated": 0, "unresolved": ["REQ-002"]}},
    )

    result = runner.invoke(cli, ["push", "--specs", str(specs_dir), "--slos", str(slos_dir), *AUTH])

    assert result.exit_code == 0, result.output
    sent = json.loads(responses.calls[1].request.body)
    assert sent["slos"] == [
        {
            "name": "checkout-availability",
            "display_name": "Checkout availability",
            "description": "Checkout answers",
            "service": "checkout",
            "target": 0.999,
            "time_window": "28d",
            "budgeting_method": "Occurrences",
            "requirement_ids": ["REQ-001", "REQ-002"],
            "source_file": str(slos_dir / "checkout.yaml"),
        }
    ]
    assert "slos: 1 created, 0 updated" in result.output
    assert "unresolved requirement REQ-002" in result.output


@responses.activate
def test_push__leaves_slos_alone_when_the_flag_is_absent(runner, specs_dir):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})

    result = runner.invoke(cli, ["push", "--specs", str(specs_dir), *AUTH])

    assert result.exit_code == 0, result.output
    assert len(responses.calls) == 1


@pytest.fixture
def corpus_dir(tmp_path):
    directory = tmp_path / "corpus" / "identity"
    directory.mkdir(parents=True)
    (directory / "sso.md").write_text(
        "---\n"
        "id: DEC-IAM-001\n"
        "kind: decision\n"
        "title: SAML and OIDC only\n"
        "version: 1\n"
        "status: active\n"
        "owner: identity\n"
        "enforcement: advisory\n"
        "effective: 2026-01-08\n"
        "applies_to:\n"
        "  tags: [identity]\n"
        "checks:\n"
        "  - id: risk-classified\n"
        "    assert: risk_level in [critical, high]\n"
        "---\n\n"
        "We federate through SAML and OIDC.\n"
    )
    return tmp_path / "corpus"


@responses.activate
def test_push__sends_parsed_corpus_entries_when_corpus_is_given(runner, specs_dir, corpus_dir):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})
    responses.add(
        responses.PUT,
        f"{URL}/api/v1/corpus/entries/",
        json={"data": {"entries_created": 1, "versions_created": 1, "versions_unchanged": 0}},
    )

    result = runner.invoke(
        cli, ["push", "--specs", str(specs_dir), "--corpus", str(corpus_dir), *AUTH]
    )

    assert result.exit_code == 0, result.output
    sent = json.loads(responses.calls[1].request.body)["entries"]
    assert len(sent) == 1
    assert sent[0]["external_id"] == "DEC-IAM-001"
    assert sent[0]["version"] == 1
    assert sent[0]["enforcement"] == "advisory"
    assert sent[0]["checks"] == [
        {
            "id": "risk-classified",
            "assert": "risk_level in [critical, high]",
            "field": "risk_level",
            "operator": "in",
            "value": ["critical", "high"],
        }
    ]
    assert sent[0]["effective_date"] == "2026-01-08"
    assert len(sent[0]["content_hash"]) == 64
    assert "corpus: 1 entries created, 1 versions created, 0 unchanged" in result.output


@responses.activate
def test_push__leaves_the_corpus_alone_when_the_flag_is_absent(runner, specs_dir):
    responses.add(responses.PUT, f"{URL}/api/v1/specs/", json={"data": COUNTS})

    result = runner.invoke(cli, ["push", "--specs", str(specs_dir), *AUTH])

    assert result.exit_code == 0, result.output
    assert len(responses.calls) == 1


@pytest.fixture
def coverage_requirements(db):
    Requirement.add_root(
        external_id="REQ-DRAFT",
        title="Draft",
        status="draft",
        source_file="specs/draft.md",
        verification_status="untested",
    )
    Requirement.add_root(
        external_id="REQ-ACTIVE",
        title="Active",
        status="active",
        source_file="specs/active.md",
        verification_status="passing",
        scope="checkout",
        condition="always",
        component="billing",
        timing="immediate",
        response="charges the card",
    )


COVERAGE_RECEIPT = {
    "project": "spectrace",
    "generated_at": "2026-08-31T12:00:00+00:00",
    "stored_at": "2026-08-31T12:00:01+00:00",
}
EARLIER_SNAPSHOT = {
    "commit_sha": "aaaa111bbbb",
    "git_branch": "main",
    "generated_at": "2026-08-30T12:00:00.000000+00:00",
    "stored_at": "2026-08-30T12:00:01.000000+00:00",
    "specification_rate": 0.25,
    "structure_rate": 0.1,
    "verification_rate": 0.25,
    "total": 4,
    "non_draft": 1,
    "passing": 1,
}


@freeze_time("2026-08-31 12:00:00")
@responses.activate
@patch("requirements.services.git_head.head_revision", autospec=True)
def test_specs_coverage_push__stores_the_baseline_snapshot(
    mock_head, runner, coverage_requirements
):
    mock_head.return_value = ("cccc333dddd", "main")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/results/coverage/",
        status=201,
        json={"data": {**COVERAGE_RECEIPT, "previous": None}},
    )

    result = runner.invoke(cli, ["specs", "coverage", "--push", *AUTH])

    assert result.exit_code == 0, result.output
    assert _sent() == {
        "project": "spectrace",
        "commit_sha": "cccc333dddd",
        "git_branch": "main",
        "generated_at": "2026-08-31T12:00:00+00:00",
        "specification_rate": 0.5,
        "structure_rate": 0.5,
        "verification_rate": 0.5,
        "total": 2,
        "non_draft": 1,
        "passing": 1,
    }
    assert "Specification rate: 50.0% (1/2 non-draft)" in result.output
    assert "No earlier snapshot: this run is the baseline" in result.output
    assert "Stored snapshot for cccc333 at 2026-08-31T12:00:01+00:00" in result.output


@freeze_time("2026-08-31 12:00:00")
@responses.activate
@patch("requirements.services.git_head.head_revision", autospec=True)
def test_specs_coverage_push__reports_the_change_against_the_previous_snapshot(
    mock_head, runner, coverage_requirements
):
    mock_head.return_value = ("cccc333dddd", "main")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/results/coverage/",
        status=201,
        json={"data": {**COVERAGE_RECEIPT, "previous": EARLIER_SNAPSHOT}},
    )

    result = runner.invoke(cli, ["specs", "coverage", "--push", *AUTH])

    assert result.exit_code == 0, result.output
    assert "Specification rate: 50.0% (1/2 non-draft, +25.0 pts)" in result.output
    assert "Structure rate:     50.0% (avg FRET completeness, +40.0 pts)" in result.output
    assert "Verification rate:  50.0% (1/2 passing, +25.0 pts)" in result.output
    assert "Compared against aaaa111 on main from 2026-08-30T12:00:00.000000+00:00" in result.output


@freeze_time("2026-08-31 12:00:00")
@responses.activate
@patch("requirements.services.git_head.head_revision", autospec=True)
def test_specs_coverage_push__calls_an_unmoved_rate_unchanged(
    mock_head, runner, coverage_requirements
):
    mock_head.return_value = ("cccc333dddd", "main")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/results/coverage/",
        status=201,
        json={
            "data": {
                **COVERAGE_RECEIPT,
                "previous": {**EARLIER_SNAPSHOT, "verification_rate": 0.5},
            }
        },
    )

    result = runner.invoke(cli, ["specs", "coverage", "--push", *AUTH])

    assert result.exit_code == 0, result.output
    assert "Verification rate:  50.0% (1/2 passing, unchanged)" in result.output


@freeze_time("2026-08-31 12:00:00")
@responses.activate
@patch("requirements.services.git_head.head_revision", autospec=True)
def test_specs_coverage_push__emits_the_change_as_json(mock_head, runner, coverage_requirements):
    mock_head.return_value = ("cccc333dddd", "main")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/results/coverage/",
        status=201,
        json={"data": {**COVERAGE_RECEIPT, "previous": EARLIER_SNAPSHOT}},
    )

    result = runner.invoke(cli, ["specs", "coverage", "--push", "--format", "json", *AUTH])

    assert result.exit_code == 0, result.output
    reported = json.loads(result.output)
    assert reported["stored_at"] == "2026-08-31T12:00:01+00:00"
    assert reported["previous"] == EARLIER_SNAPSHOT
    assert reported["change"] == {
        "specification_rate": pytest.approx(0.25),
        "structure_rate": pytest.approx(0.4),
        "verification_rate": pytest.approx(0.25),
    }


def test_specs_coverage_push__needs_a_remote(runner):
    result = runner.invoke(cli, ["specs", "coverage", "--push"], env={"SPECTRACE_URL": ""})

    assert result.exit_code == 2
    assert "--push needs --url and --api-key" in result.output


@patch("cli._run", autospec=True)
def test_specs_coverage__still_delegates_without_push(mock_run, runner):
    result = runner.invoke(cli, ["specs", "coverage"])

    assert result.exit_code == 0
    mock_run.assert_called_once_with("spec_coverage", format="text", project=None)


CONTEXT_OK = '{"settings": {"workspace": "acme"}}'
CONTEXT_BAD = '{"settings": {"workspace": "other"}}'


@pytest.fixture
def flow_file(tmp_path):
    path = tmp_path / "ping.yaml"
    path.write_text(
        "id: ping\n"
        "title: Ping\n"
        "description: One assertion, no network\n"
        "version: 1\n"
        "steps:\n"
        "  - name: context_present\n"
        "    type: assertion\n"
        "    display_name: Context Present\n"
        "    description: The context carries a workspace\n"
        "    config:\n"
        "      source: settings\n"
        "      field: workspace\n"
        "      operator: equals\n"
        "      value: acme\n"
    )
    return path


@responses.activate
def test_flows_run__records_the_run_on_the_worker(runner, flow_file):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/flows/runs/",
        json={"data": {"run_id": 7, "flow": "ping", "status": "passed", "steps": 1}},
    )

    result = runner.invoke(
        cli,
        ["flows", "run", str(flow_file), "--context", CONTEXT_OK, *AUTH],
    )

    assert result.exit_code == 0, result.output
    sent = json.loads(responses.calls[0].request.body)
    assert sent["flow_name"] == "ping"
    assert sent["status"] == "passed"
    assert sent["source"] == "cli"
    assert sent["context"] == {"settings": {"workspace": "acme"}}
    assert [step["name"] for step in sent["steps"]] == ["context_present"]
    assert sent["steps"][0]["passed"] is True
    assert sent["steps"][0]["step_order"] == 0
    assert "Recorded run 7 with 1 steps" in result.output


@responses.activate
def test_flows_run__exits_one_and_still_records_a_failed_run(runner, flow_file):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/flows/runs/",
        json={"data": {"run_id": 8, "flow": "ping", "status": "failed", "steps": 1}},
    )

    result = runner.invoke(
        cli,
        ["flows", "run", str(flow_file), "--context", CONTEXT_BAD, *AUTH],
    )

    assert result.exit_code == 1
    sent = json.loads(responses.calls[0].request.body)
    assert sent["status"] == "failed"
    assert sent["steps"][0]["passed"] is False


@responses.activate
def test_flows_run__reaches_no_worker_with_no_push(runner, flow_file):
    result = runner.invoke(
        cli,
        ["flows", "run", str(flow_file), "--context", CONTEXT_OK, "--no-push"],
    )

    assert result.exit_code == 0, result.output
    assert len(responses.calls) == 0
    assert "Status: passed" in result.output

"""Tests for the unattended task runner, which drains the unclaimed queue one worktree per task."""

import json
import subprocess

import pytest
import responses

from requirements.services.task_runner import (
    Commands,
    GateRefusal,
    TaskRunner,
    linked_test_ids,
    requirement_ids_by_nodeid,
)
from spectrace_client.client import ValidationClient

URL = "http://worker.test"


def transition(task_id: str, to_status: str) -> dict:
    return {
        "data": {
            "success": True,
            "task_id": task_id,
            "from_status": "unclaimed",
            "to_status": to_status,
            "message": "ok",
        }
    }


def bundle(task_id: str, linked: tuple[str, ...] = ()) -> dict:
    return {
        "task_id": task_id,
        "title": "Add login",
        "description": "",
        "status": "in_progress",
        "done_when": ["tests pass"],
        "scope_in": ["auth/"],
        "scope_out": [],
        "requirements": [
            {
                "external_id": "REQ-AUTH-001",
                "title": "Login",
                "test_results": [
                    {"test_nodeid": nodeid, "last_status": "passed"} for nodeid in linked
                ],
            }
        ],
        "drift": {},
    }


def git(repo, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "runner@test")
    git(path, "config", "user.name", "Runner")
    (path / "README.md").write_text("seed\n")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "seed")
    return path


@pytest.fixture
def worktrees(tmp_path):
    return tmp_path / "tasks"


def runner_for(repo, worktrees, commands: Commands, log=None) -> TaskRunner:
    client = ValidationClient(api_url=URL, api_key="secret")
    return TaskRunner(client, repo, worktrees, "coder-1", commands, log=log or (lambda line: None))


def mock_pipeline(task_id: str, linked: tuple[str, ...] = ()) -> None:
    responses.add(
        responses.POST, f"{URL}/api/v1/tasks/{task_id}/claim", json=transition(task_id, "claimed")
    )
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/{task_id}/start",
        json=transition(task_id, "in_progress"),
    )
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/{task_id}/context",
        json={"data": bundle(task_id, linked)},
    )


def sent(index: int) -> dict:
    return json.loads(responses.calls[index].request.body)


@responses.activate
def test_drain__claims_works_and_submits_each_unclaimed_task(repo, worktrees):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/",
        json={"data": [{"id": "task-1"}, {"id": "task-2"}], "meta": {}},
    )
    for task_id in ("task-1", "task-2"):
        mock_pipeline(task_id)
        responses.add(
            responses.POST,
            f"{URL}/api/v1/tasks/{task_id}/complete",
            json=transition(task_id, "ready_for_review"),
        )
    lines = []
    runner = runner_for(
        repo,
        worktrees,
        Commands(coder="echo done > $SPECTRACE_OUT; cat > bundle.json", tests="true"),
        lines.append,
    )

    reports = runner.drain(limit=2)

    assert [report.task_id for report in reports] == ["task-1", "task-2"]
    assert responses.calls[0].request.url == (
        f"{URL}/api/v1/tasks/?page=1&status=unclaimed&per_page=2&sort=created_at"
    )
    for report in reports:
        assert report.worktree == worktrees / report.task_id
        assert report.branch == f"task/{report.task_id}"
        assert git(report.worktree, "rev-parse", "HEAD") == report.commit_sha
        assert (
            git(report.worktree, "log", "-1", "--format=%s") == f"task: {report.task_id} Add login"
        )
        assert (
            json.loads((report.worktree / "bundle.json").read_text())["task_id"] == report.task_id
        )
    assert sent(4) == {
        "agent_id": "coder-1",
        "commit_sha": reports[0].commit_sha,
        "branch": "task/task-1",
    }
    assert lines[-1] == f"task-2: submitted {reports[1].commit_sha[:7]} for review"


@responses.activate
def test_drain__stops_at_the_first_gate_refusal_and_names_the_reason(repo, worktrees):
    responses.add(
        responses.GET,
        f"{URL}/api/v1/tasks/",
        json={"data": [{"id": "task-1"}, {"id": "task-2"}], "meta": {}},
    )
    mock_pipeline("task-1")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/complete",
        status=409,
        json={
            "error": {
                "code": "transition_error",
                "message": "no intent validation",
                "details": {"reason": "INTENT_NOT_VALIDATED"},
            }
        },
    )
    runner = runner_for(repo, worktrees, Commands(coder="echo x > x.txt", tests="true"))

    with pytest.raises(GateRefusal) as refused:
        runner.drain(limit=2)

    assert (refused.value.task_id, refused.value.stage, refused.value.reason) == (
        "task-1",
        "complete",
        "INTENT_NOT_VALIDATED",
    )
    assert [call.request.url for call in responses.calls].count(
        f"{URL}/api/v1/tasks/task-2/claim"
    ) == 0


@responses.activate
def test_run__refuses_when_the_claim_is_refused(repo, worktrees):
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/claim",
        status=409,
        json={
            "error": {
                "code": "transition_error",
                "message": "claimed",
                "details": {"reason": "ALREADY_CLAIMED"},
            }
        },
    )
    runner = runner_for(repo, worktrees, Commands(coder="true", tests="true"))

    with pytest.raises(GateRefusal, match="task-1: claim refused: ALREADY_CLAIMED"):
        runner.run("task-1")

    assert not (worktrees / "task-1").exists()


@responses.activate
def test_run__refuses_when_the_coder_exits_nonzero(repo, worktrees):
    mock_pipeline("task-1")
    runner = runner_for(repo, worktrees, Commands(coder="echo boom >&2; exit 3", tests="true"))

    with pytest.raises(GateRefusal, match="task-1: coder refused: exit 3: boom"):
        runner.run("task-1")


@responses.activate
def test_run__refuses_when_the_coder_changes_nothing(repo, worktrees):
    mock_pipeline("task-1")
    runner = runner_for(repo, worktrees, Commands(coder="true", tests="true"))

    with pytest.raises(GateRefusal, match="task-1: commit refused: the coder changed nothing"):
        runner.run("task-1")


@responses.activate
def test_run__refuses_when_the_tests_fail(repo, worktrees):
    mock_pipeline("task-1")
    runner = runner_for(
        repo, worktrees, Commands(coder="echo x > x.txt", tests="echo 1 failed; exit 1")
    )

    with pytest.raises(GateRefusal, match="task-1: tests refused: exit 1: 1 failed"):
        runner.run("task-1")

    assert git(worktrees / "task-1", "log", "--oneline").count("\n") == 0


@responses.activate
def test_run__expands_linked_tests_into_the_test_command(repo, worktrees):
    mock_pipeline("task-1", linked=("tests/test_a.py::test_a", "tests/test_b.py::test_b"))
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/complete",
        json=transition("task-1", "ready_for_review"),
    )
    runner = runner_for(
        repo, worktrees, Commands(coder="echo x > x.txt", tests="echo {linked} > ran.txt")
    )

    runner.run("task-1")

    assert (
        worktrees / "task-1" / "ran.txt"
    ).read_text() == "tests/test_a.py::test_a tests/test_b.py::test_b\n"


@responses.activate
def test_run__refuses_when_the_command_wants_linked_tests_and_none_exist(repo, worktrees):
    mock_pipeline("task-1")
    runner = runner_for(repo, worktrees, Commands(coder="echo x > x.txt", tests="pytest {linked}"))

    with pytest.raises(GateRefusal, match="task-1: tests refused: no test is linked"):
        runner.run("task-1")


@responses.activate
def test_run__posts_the_scorer_verdict_before_submitting(repo, worktrees):
    mock_pipeline("task-1")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/intent-validations",
        json={"data": {"passed": True, "failure_reasons": []}},
    )
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/complete",
        json=transition("task-1", "ready_for_review"),
    )
    scorer = (
        'python3 -c "import json,sys; p=json.load(sys.stdin); '
        "assert 'x.txt' in p['diff'] and p['task']['task_id']=='task-1'; "
        "print(json.dumps({'strategic_score': 90, 'opportunity_score': 80, 'drift_score': 75}))\""
    )
    runner = runner_for(
        repo,
        worktrees,
        Commands(coder="echo x > x.txt", tests="true", scorer=scorer, scorer_agent="scorer-1"),
    )

    report = runner.run("task-1")

    assert sent(3) == {
        "validator_id": "scorer-1",
        "commit_sha": report.commit_sha,
        "strategic_score": 90,
        "opportunity_score": 80,
        "drift_score": 75,
        "failure_reasons": [],
    }
    assert responses.calls[4].request.url == f"{URL}/api/v1/tasks/task-1/complete"


@responses.activate
def test_run__refuses_when_the_scorer_verdict_fails(repo, worktrees):
    mock_pipeline("task-1")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/intent-validations",
        json={"data": {"passed": False, "failure_reasons": ["drifts from REQ-AUTH-001"]}},
    )
    scorer = 'echo \'{"strategic_score": 90, "opportunity_score": 80, "drift_score": 10}\''
    runner = runner_for(
        repo,
        worktrees,
        Commands(coder="echo x > x.txt", tests="true", scorer=scorer, scorer_agent="scorer-1"),
    )

    with pytest.raises(GateRefusal, match="task-1: intent refused: drifts from REQ-AUTH-001"):
        runner.run("task-1")

    assert len(responses.calls) == 4


@responses.activate
def test_run__surfaces_the_refusal_when_the_worker_rejects_the_coder_as_its_own_judge(
    repo, worktrees
):
    mock_pipeline("task-1")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/intent-validations",
        status=409,
        json={
            "error": {
                "code": "transition_error",
                "message": "Agent 'coder-1' claimed task 'task-1' and cannot score its own intent",
                "details": {"reason": "SELF_INTENT_NOT_ALLOWED"},
            }
        },
    )
    scorer = 'echo \'{"strategic_score": 90, "opportunity_score": 90, "drift_score": 90}\''
    runner = runner_for(
        repo,
        worktrees,
        Commands(coder="echo x > x.txt", tests="true", scorer=scorer, scorer_agent="coder-1"),
    )

    with pytest.raises(GateRefusal) as refused:
        runner.run("task-1")

    assert (refused.value.task_id, refused.value.stage, refused.value.reason) == (
        "task-1",
        "intent",
        "SELF_INTENT_NOT_ALLOWED",
    )
    assert f"{URL}/api/v1/tasks/task-1/complete" not in [
        call.request.url for call in responses.calls
    ]


@responses.activate
def test_run__reuses_the_worktree_from_an_earlier_attempt(repo, worktrees):
    mock_pipeline("task-1")
    runner = runner_for(repo, worktrees, Commands(coder="echo boom >&2; exit 1", tests="true"))
    with pytest.raises(GateRefusal):
        runner.run("task-1")
    responses.reset()
    mock_pipeline("task-1")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/complete",
        json=transition("task-1", "ready_for_review"),
    )
    (worktrees / "task-1" / "partial.txt").write_text("kept\n")
    runner = runner_for(repo, worktrees, Commands(coder="echo x > x.txt", tests="true"))

    report = runner.run("task-1")

    assert report.worktree == worktrees / "task-1"
    assert git(report.worktree, "show", "--stat", "--format=", "HEAD").count("|") == 2


def test_linked_test_ids__dedupes_across_requirements():
    context = bundle("task-1", linked=("t::a", "t::b"))
    context["requirements"].append(
        {"external_id": "REQ-2", "test_results": [{"test_nodeid": "t::a"}]}
    )

    assert linked_test_ids(context) == ["t::a", "t::b"]


@responses.activate
def test_run__refuses_when_the_scorer_prints_no_json(repo, worktrees):
    mock_pipeline("task-1")
    scorer = "echo {strategic_score:88}"
    runner = runner_for(
        repo, worktrees, Commands(coder="echo x > x.txt", tests="true", scorer=scorer)
    )

    with pytest.raises(
        GateRefusal, match=r"task-1: scorer refused: printed no JSON: '\{strategic_score:88\}'"
    ):
        runner.run("task-1")

    assert len(responses.calls) == 3


@responses.activate
def test_run__refuses_when_the_scorer_omits_a_score(repo, worktrees):
    mock_pipeline("task-1")
    scorer = "echo '{\"strategic_score\": 88}'"
    runner = runner_for(
        repo, worktrees, Commands(coder="echo x > x.txt", tests="true", scorer=scorer)
    )

    with pytest.raises(
        GateRefusal, match="task-1: scorer refused: output lacks opportunity_score, drift_score"
    ):
        runner.run("task-1")


JUNIT = (
    '<testsuites><testsuite name="pytest" tests="1">'
    '<testcase classname="tests.test_auth" name="test_login" time="0.1"/>'
    "</testsuite></testsuites>"
)


def mock_results_push() -> None:
    responses.add(
        responses.POST,
        f"{URL}/api/v1/results/test-runs/",
        json={"success": True, "run_id": 7, "imported": 1, "linked": 1},
    )


@responses.activate
def test_run__pushes_the_junit_results_tagged_with_the_task_commit(repo, worktrees):
    mock_pipeline("task-1", linked=("tests/test_auth.py::test_login",))
    mock_results_push()
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/complete",
        json=transition("task-1", "ready_for_review"),
    )
    lines = []
    runner = runner_for(
        repo,
        worktrees,
        Commands(coder="echo x > x.txt", tests=f"printf '%s' '{JUNIT}' > {{junit}}"),
        lines.append,
    )

    report = runner.run("task-1")

    pushed = sent(3)
    assert pushed["git_sha"] == report.commit_sha
    assert pushed["git_branch"] == "task/task-1"
    assert pushed["results"] == [
        {
            "test_nodeid": "tests/test_auth.py::test_login",
            "classname": "tests.test_auth",
            "name": "test_login",
            "time": 0.1,
            "status": "passed",
            "message": "",
            "requirement_ids": ["REQ-AUTH-001"],
        }
    ]
    assert responses.calls[4].request.url == f"{URL}/api/v1/tasks/task-1/complete"
    assert lines[-2] == f"task-1: pushed 1 results at {report.commit_sha[:7]}, 1 linked"


@responses.activate
def test_run__refuses_when_the_tests_command_writes_no_junit_xml(repo, worktrees):
    mock_pipeline("task-1")
    runner = runner_for(repo, worktrees, Commands(coder="echo x > x.txt", tests="true {junit}"))

    with pytest.raises(GateRefusal, match="task-1: results refused: the tests command wrote no"):
        runner.run("task-1")


@responses.activate
def test_run__keeps_the_junit_file_out_of_the_task_commit(repo, worktrees):
    mock_pipeline("task-1")
    mock_results_push()
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/complete",
        json=transition("task-1", "ready_for_review"),
    )
    runner = runner_for(
        repo,
        worktrees,
        Commands(coder="echo x > x.txt", tests=f"printf '%s' '{JUNIT}' > {{junit}}"),
    )

    report = runner.run("task-1")

    assert git(report.worktree, "show", "--stat", "--format=", "HEAD").count("|") == 1
    assert (worktrees / "task-1.junit.xml").exists()


def test_requirement_ids_by_nodeid__indexes_every_requirement_that_verifies_a_test():
    context = bundle("task-1", linked=("tests.test_auth::test_login",))
    context["requirements"].append(
        {
            "external_id": "REQ-2",
            "test_results": [{"test_nodeid": "tests/test_auth.py::test_login"}],
        }
    )

    assert requirement_ids_by_nodeid(context) == {
        "tests/test_auth.py::test_login": ["REQ-AUTH-001", "REQ-2"]
    }


@pytest.fixture
def remote(repo, tmp_path):
    bare = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(bare))
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "origin", "main")
    return bare


@responses.activate
def test_run__pushes_the_task_branch_to_the_remote(repo, worktrees, remote):
    mock_pipeline("task-1")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/complete",
        json=transition("task-1", "ready_for_review"),
    )
    runner = runner_for(repo, worktrees, Commands(coder="echo x > x.txt", tests="true"))
    runner.remote = "origin"

    report = runner.run("task-1")

    assert git(remote, "rev-parse", "refs/heads/task/task-1") == report.commit_sha


@responses.activate
def test_run__resumes_from_the_remote_branch_when_the_disk_is_gone(repo, worktrees, remote):
    git(repo, "checkout", "-q", "-b", "task/task-1")
    (repo / "earlier.txt").write_text("from a previous host\n")
    git(repo, "add", "earlier.txt")
    git(repo, "commit", "-q", "-m", "task: task-1 earlier attempt")
    git(repo, "push", "-q", "origin", "task/task-1")
    git(repo, "checkout", "-q", "main")
    git(repo, "branch", "-q", "-D", "task/task-1")
    mock_pipeline("task-1")
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/task-1/complete",
        json=transition("task-1", "ready_for_review"),
    )
    runner = runner_for(repo, worktrees, Commands(coder="echo x > x.txt", tests="true"))
    runner.remote = "origin"

    report = runner.run("task-1")

    assert (report.worktree / "earlier.txt").exists()
    assert git(report.worktree, "log", "--format=%s", "-2").splitlines() == [
        "task: task-1 Add login",
        "task: task-1 earlier attempt",
    ]

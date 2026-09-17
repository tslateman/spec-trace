"""Tests for the task merge, which merges an approved task's branch and records the merge."""

import subprocess

import pytest
import responses

from requirements.services.task_merge import MergeRefusal, TaskMerger
from spectrace_client.client import ValidationClient

URL = "http://worker.test"
TASK = "task-auth-001"


def git(repo, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "merger@test")
    git(path, "config", "user.name", "Merger")
    (path / "README.md").write_text("seed\n")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "seed")
    return path


@pytest.fixture
def branch(repo):
    git(repo, "checkout", "-q", "-b", f"task/{TASK}")
    (repo / "login.py").write_text("def login():\n    return True\n")
    git(repo, "add", "login.py")
    git(repo, "commit", "-q", "-m", "task: add login")
    git(repo, "checkout", "-q", "main")
    return f"task/{TASK}"


def detail(repo, branch, status="approved", commit_sha=None) -> dict:
    return {
        "id": TASK,
        "title": "Add login",
        "status": status,
        "branch": branch,
        "commit_sha": commit_sha if commit_sha is not None else git(repo, "rev-parse", branch),
        "merge_sha": "",
    }


def mock_detail(task: dict) -> None:
    responses.add(responses.GET, f"{URL}/api/v1/tasks/{TASK}", json={"data": task})


def mock_merge() -> None:
    responses.add(
        responses.POST,
        f"{URL}/api/v1/tasks/{TASK}/merge",
        json={
            "data": {
                "success": True,
                "task_id": TASK,
                "from_status": "approved",
                "to_status": "merged",
                "message": "Task merged",
            }
        },
    )


def merger_for(repo, remote=None) -> TaskMerger:
    client = ValidationClient(api_url=URL, api_key="secret")
    return TaskMerger(client, repo, base="main", remote=remote)


@responses.activate
def test_merge__refuses_when_the_branch_drifted_from_the_reviewed_commit(repo, branch):
    reviewed = git(repo, "rev-parse", branch)
    git(repo, "checkout", "-q", branch)
    (repo / "login.py").write_text("def login():\n    return False\n")
    git(repo, "commit", "-q", "-am", "task: drift past the review")
    git(repo, "checkout", "-q", "main")
    drifted = git(repo, "rev-parse", branch)
    mock_detail(detail(repo, branch, commit_sha=reviewed))
    mock_merge()
    before = git(repo, "rev-parse", "main")

    with pytest.raises(MergeRefusal) as refusal:
        merger_for(repo).merge(TASK)

    assert refusal.value.code == "BRANCH_DRIFTED"
    assert reviewed[:7] in refusal.value.reason
    assert drifted[:7] in refusal.value.reason
    assert git(repo, "rev-parse", "main") == before
    assert [call.request.method for call in responses.calls] == ["GET"]


@responses.activate
def test_merge__merges_the_branch_and_records_the_merge_sha(repo, branch):
    reviewed = git(repo, "rev-parse", branch)
    mock_detail(detail(repo, branch))
    mock_merge()

    report = merger_for(repo).merge(TASK)

    assert report.merge_sha == git(repo, "rev-parse", "main")
    assert report.reviewed_sha == reviewed
    assert report.branch == branch
    assert git(repo, "rev-parse", "main^2") == reviewed
    assert (repo / "login.py").exists()
    posted = responses.calls[-1].request
    assert posted.url == f"{URL}/api/v1/tasks/{TASK}/merge"
    assert posted.body is not None


@responses.activate
def test_merge__refuses_a_task_that_is_not_approved(repo, branch):
    mock_detail(detail(repo, branch, status="ready_for_review"))
    before = git(repo, "rev-parse", "main")

    with pytest.raises(MergeRefusal) as refusal:
        merger_for(repo).merge(TASK)

    assert refusal.value.code == "NOT_APPROVED"
    assert git(repo, "rev-parse", "main") == before


@responses.activate
def test_merge__refuses_when_the_ledger_records_no_branch(repo, branch):
    mock_detail(detail(repo, "", commit_sha=git(repo, "rev-parse", branch)))

    with pytest.raises(MergeRefusal) as refusal:
        merger_for(repo).merge(TASK)

    assert refusal.value.code == "BRANCH_UNKNOWN"


@responses.activate
def test_merge__refuses_when_the_named_branch_contradicts_the_ledger(repo, branch):
    mock_detail(detail(repo, branch))

    with pytest.raises(MergeRefusal) as refusal:
        merger_for(repo).merge(TASK, branch="task/other")

    assert refusal.value.code == "BRANCH_MISMATCH"


@responses.activate
def test_merge__refuses_when_the_repository_sits_on_another_branch(repo, branch):
    git(repo, "checkout", "-q", branch)
    mock_detail(detail(repo, branch))

    with pytest.raises(MergeRefusal) as refusal:
        merger_for(repo).merge(TASK)

    assert refusal.value.code == "NOT_ON_BASE"


@responses.activate
def test_merge__refuses_when_the_working_tree_is_dirty(repo, branch):
    (repo / "README.md").write_text("uncommitted\n")
    mock_detail(detail(repo, branch))

    with pytest.raises(MergeRefusal) as refusal:
        merger_for(repo).merge(TASK)

    assert refusal.value.code == "REPO_DIRTY"


@responses.activate
def test_merge__refuses_when_the_branch_is_gone(repo, branch):
    reviewed = git(repo, "rev-parse", branch)
    git(repo, "branch", "-D", branch)
    mock_detail(detail(repo, branch, commit_sha=reviewed))

    with pytest.raises(MergeRefusal) as refusal:
        merger_for(repo).merge(TASK)

    assert refusal.value.code == "BRANCH_NOT_FOUND"


@responses.activate
def test_merge__aborts_and_refuses_when_the_merge_conflicts(repo, branch):
    (repo / "login.py").write_text("def login():\n    return None\n")
    git(repo, "add", "login.py")
    git(repo, "commit", "-q", "-m", "main: a conflicting login")
    before = git(repo, "rev-parse", "main")
    mock_detail(detail(repo, branch))

    with pytest.raises(MergeRefusal) as refusal:
        merger_for(repo).merge(TASK)

    assert refusal.value.code == "MERGE_CONFLICT"
    assert git(repo, "rev-parse", "main") == before
    assert git(repo, "status", "--porcelain") == ""


@responses.activate
def test_merge__is_idempotent_when_the_branch_already_landed(repo, branch):
    reviewed = git(repo, "rev-parse", branch)
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "-m", "Merge by hand", branch)
    landed = git(repo, "rev-parse", "main")
    mock_detail(detail(repo, branch, commit_sha=reviewed))
    mock_merge()

    report = merger_for(repo).merge(TASK)

    assert report.merge_sha == landed


@responses.activate
def test_merge__pushes_the_base_branch_before_recording_the_merge(repo, branch, tmp_path):
    remote = tmp_path / "origin.git"
    git(repo, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main", branch)
    mock_detail(detail(repo, branch))
    mock_merge()

    report = merger_for(repo, remote="origin").merge(TASK)

    assert git(remote, "rev-parse", "main") == report.merge_sha

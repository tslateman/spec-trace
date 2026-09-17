"""Tests for reading the commit a coverage snapshot names."""

import subprocess

import pytest

from requirements.services.git_head import NotAGitCheckout, head_revision


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def checkout(tmp_path):
    repo = tmp_path / "checkout"
    repo.mkdir()
    _git(repo, "init", "-b", "trunk")
    _git(repo, "config", "user.email", "agent@example.com")
    _git(repo, "config", "user.name", "Agent")
    _git(repo, "commit", "--allow-empty", "-m", "first")
    return repo


def test_head_revision__names_the_commit_and_the_branch(checkout):
    commit_sha, git_branch = head_revision(checkout)

    assert len(commit_sha) == 40
    assert git_branch == "trunk"


def test_head_revision__reads_HEAD_as_the_branch_of_a_detached_checkout(checkout):
    _git(checkout, "commit", "--allow-empty", "-m", "second")
    _git(checkout, "checkout", "--detach", "HEAD")

    _, git_branch = head_revision(checkout)

    assert git_branch == "HEAD"


def test_head_revision__refuses_a_path_outside_a_checkout(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(NotAGitCheckout, match="outside a git checkout"):
        head_revision(outside)

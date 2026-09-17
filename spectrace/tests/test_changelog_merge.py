"""The Unreleased block is generated, so two branches carrying it must not conflict."""

import subprocess
from pathlib import Path

import pytest

ATTRIBUTES = Path(__file__).resolve().parents[2] / ".gitattributes"

BASE = """# Changelog

## [Unreleased]

<!-- changelog:auto since=v0.11.0 -->

### Added

- An earlier entry (`aaaaaaa`)

<!-- changelog:/auto -->

## [v0.11.0] - 2026-08-30
"""


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _entry(text, line):
    return text.replace("- An earlier entry (`aaaaaaa`)", f"- An earlier entry (`aaaaaaa`)\n{line}")


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "CHANGELOG.md").write_text(BASE)
    git(repo, "add", "CHANGELOG.md")
    git(repo, "commit", "-q", "-m", "base")
    return repo


def _two_branches(repo):
    """Give main and a side branch one changelog entry each, as two PRs would."""
    git(repo, "checkout", "-q", "-b", "side")
    (repo / "CHANGELOG.md").write_text(_entry(BASE, "- Side work (`bbbbbbb`)"))
    git(repo, "commit", "-q", "-am", "docs: Update the changelog")
    git(repo, "checkout", "-q", "main")
    (repo / "CHANGELOG.md").write_text(_entry(BASE, "- Main work (`ccccccc`)"))
    git(repo, "commit", "-q", "-am", "docs: Update the changelog")


def test_changelog_merge__conflicts_without_the_union_attribute(repo):
    _two_branches(repo)

    merge = subprocess.run(["git", "merge", "side"], cwd=repo, capture_output=True, text=True)

    assert merge.returncode != 0
    assert "<<<<<<<" in (repo / "CHANGELOG.md").read_text()


def test_changelog_merge__unions_both_entries_with_the_attribute(repo):
    (repo / ".gitattributes").write_text("CHANGELOG.md merge=union\n")
    git(repo, "add", ".gitattributes")
    git(repo, "commit", "-q", "-m", "chore: Union changelog merges")
    _two_branches(repo)

    merge = subprocess.run(["git", "merge", "side"], cwd=repo, capture_output=True, text=True)

    assert merge.returncode == 0, merge.stdout + merge.stderr
    merged = (repo / "CHANGELOG.md").read_text()
    assert "<<<<<<<" not in merged
    assert "- Side work (`bbbbbbb`)" in merged
    assert "- Main work (`ccccccc`)" in merged


def test_repository_declares_the_union_attribute():
    assert "CHANGELOG.md merge=union" in ATTRIBUTES.read_text()

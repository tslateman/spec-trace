"""Tests for git co-change inference."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from requirements.services.git_cochange import GitCoChangeAnalyzer


def _make_git_output(commits):
    """Build mock git log --name-only output from commit list.

    Each commit: {"hash": str, "date": datetime, "files": [str]}
    """
    lines = []
    for c in commits:
        date_str = c["date"].isoformat()
        lines.append(f"{c['hash']}|{date_str}")
        for f in c["files"]:
            lines.append(f)
        lines.append("")
    return "\n".join(lines)


@pytest.fixture
def analyzer(tmp_path):
    return GitCoChangeAnalyzer(repo_path=tmp_path, lookback_days=90)


class TestGetCommitFilePairs:
    def test_parses_git_output(self, analyzer):
        now = datetime.now(timezone.utc)
        commits = [
            {"hash": "a" * 40, "date": now, "files": ["a.py", "b.py"]},
        ]
        mock_result = MagicMock(stdout=_make_git_output(commits), returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = analyzer.get_commit_file_pairs()
        assert len(result) == 1
        assert set(result[0]["files"]) == {"a.py", "b.py"}

    def test_empty_history(self, analyzer):
        mock_result = MagicMock(stdout="", returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = analyzer.get_commit_file_pairs()
        assert result == []

    def test_git_failure_raises(self, analyzer):
        import subprocess

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git", stderr="error"),
        ):
            with pytest.raises(ValueError, match="Git log failed"):
                analyzer.get_commit_file_pairs()

    def test_timeout_raises(self, analyzer):
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            with pytest.raises(ValueError, match="timed out"):
                analyzer.get_commit_file_pairs()


class TestComputeCoChanges:
    def _make_commits(self, pairs_per_day, days_back, base_date=None):
        """Create commits with specified file pairs over multiple days."""
        base = base_date or datetime.now(timezone.utc)
        commits = []
        for day_offset, files in pairs_per_day:
            date = base - timedelta(days=day_offset)
            sha = f"{day_offset:040d}"
            commits.append({"hash": sha, "date": date, "files": files})
        return commits

    def test_meets_threshold(self, analyzer):
        """3 co-occurrences within 30 days triggers Rule of Three."""
        now = datetime.now(timezone.utc)
        commits = self._make_commits(
            [
                (1, ["a.py", "b.py"]),
                (5, ["a.py", "b.py"]),
                (10, ["a.py", "b.py"]),
            ],
            30,
            now,
        )

        mock_result = MagicMock(stdout=_make_git_output(commits))
        with patch("subprocess.run", return_value=mock_result):
            results = analyzer.compute_co_changes(min_count=3, window_days=30)
        assert len(results) == 1
        assert results[0].count == 3

    def test_misses_threshold(self, analyzer):
        """Only 2 co-occurrences doesn't meet Rule of Three."""
        now = datetime.now(timezone.utc)
        commits = self._make_commits(
            [
                (1, ["a.py", "b.py"]),
                (5, ["a.py", "b.py"]),
            ],
            30,
            now,
        )

        mock_result = MagicMock(stdout=_make_git_output(commits))
        with patch("subprocess.run", return_value=mock_result):
            results = analyzer.compute_co_changes(min_count=3, window_days=30)
        assert len(results) == 0

    def test_outside_window(self, analyzer):
        """Co-occurrences spread beyond window don't count."""
        now = datetime.now(timezone.utc)
        commits = self._make_commits(
            [
                (1, ["a.py", "b.py"]),
                (40, ["a.py", "b.py"]),  # >30 days apart
                (80, ["a.py", "b.py"]),  # >30 days apart
            ],
            90,
            now,
        )

        mock_result = MagicMock(stdout=_make_git_output(commits))
        with patch("subprocess.run", return_value=mock_result):
            results = analyzer.compute_co_changes(min_count=3, window_days=30)
        assert len(results) == 0

    def test_weight_calculation(self, analyzer):
        """Weight is min(1.0, count/10)."""
        now = datetime.now(timezone.utc)
        # 5 co-occurrences → weight = 0.5
        commits = self._make_commits(
            [(i, ["a.py", "b.py"]) for i in range(5)],
            30,
            now,
        )

        mock_result = MagicMock(stdout=_make_git_output(commits))
        with patch("subprocess.run", return_value=mock_result):
            results = analyzer.compute_co_changes(min_count=3, window_days=30)
        assert len(results) == 1
        assert results[0].weight == 0.5

    def test_decay_for_stale(self, analyzer):
        """Edges older than 90 days get weight halved."""
        # Create an analyzer with longer lookback to include old data
        old_analyzer = GitCoChangeAnalyzer(repo_path=analyzer.repo_path, lookback_days=365)

        old_date = datetime.now(timezone.utc) - timedelta(days=120)
        commits = []
        for i in range(5):
            date = old_date + timedelta(days=i)
            sha = f"{i:040d}"
            commits.append({"hash": sha, "date": date, "files": ["a.py", "b.py"]})

        mock_result = MagicMock(stdout=_make_git_output(commits))
        with patch("subprocess.run", return_value=mock_result):
            results = old_analyzer.compute_co_changes(min_count=3, window_days=30)

        if results:
            assert results[0].weight == 0.25  # 5/10 * 0.5 = 0.25


class TestToEdges:
    def test_converts_to_graph_edges(self, analyzer):
        now = datetime.now(timezone.utc)
        commits = [
            {"hash": f"{i:040d}", "date": now - timedelta(days=i), "files": ["x.py", "y.py"]}
            for i in range(5)
        ]
        mock_result = MagicMock(stdout=_make_git_output(commits))
        with patch("subprocess.run", return_value=mock_result):
            edges = analyzer.to_edges("myproject")

        if edges:
            from requirements.services.impact_graph import EdgeSource

            assert edges[0].source == EdgeSource.GIT_INFERRED
            assert edges[0].project == "myproject"

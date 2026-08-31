"""Git co-change inference — discover file coupling from commit history."""

import logging
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Valid git ref pattern (from impact_analyzer.py)
GIT_REF_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/:\-~^@{}]*$")


def validate_git_ref(ref: str) -> None:
    """Validate a git ref is safe to use in commands."""
    if not ref:
        raise ValueError("Git ref cannot be empty")
    if len(ref) > 256:
        raise ValueError("Git ref too long (max 256 characters)")
    if not GIT_REF_PATTERN.match(ref):
        raise ValueError("Invalid git ref format")
    if ref.startswith("-"):
        raise ValueError("Git ref cannot start with a hyphen")


@dataclass
class CoChange:
    """A pair of files that change together frequently."""

    file_a: str
    file_b: str
    count: int
    last_seen: datetime
    weight: float  # min(1.0, count/10), decayed if stale


class GitCoChangeAnalyzer:
    """Analyze git history to discover files that change together.

    Rule of Three: requires 3+ co-occurrences within a rolling 30-day window.
    Edges decay after 90 days without reinforcement.
    """

    def __init__(self, repo_path: Path, lookback_days: int = 90):
        self.repo_path = repo_path
        self.lookback_days = lookback_days

    def get_commit_file_pairs(self) -> list[dict]:
        """Get commit hashes with their changed files.

        Returns list of dicts with keys: hash, date, files
        Uses: git log --name-only --pretty=format:'%H|%aI' --since=...
        """
        since_date = (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).strftime(
            "%Y-%m-%d"
        )

        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--name-only",
                    "--pretty=format:%H|%aI",
                    f"--since={since_date}",
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as e:
            logger.error("Git log failed: %s", e.stderr)
            raise ValueError("Git log failed. Check that the repository is valid.") from e
        except subprocess.TimeoutExpired:
            raise ValueError("Git log timed out")

        commits = []
        current_commit: Optional[dict] = None

        for line in result.stdout.split("\n"):
            line = line.strip()
            if not line:
                continue
            if "|" in line and len(line.split("|")) == 2:
                parts = line.split("|")
                if len(parts[0]) == 40:  # SHA length
                    if current_commit:
                        commits.append(current_commit)
                    try:
                        date = datetime.fromisoformat(parts[1])
                        if date.tzinfo is None:
                            date = date.replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
                    current_commit = {"hash": parts[0], "date": date, "files": []}
                    continue
            if current_commit is not None:
                current_commit["files"].append(line)

        if current_commit:
            commits.append(current_commit)

        return commits

    def compute_co_changes(self, min_count: int = 3, window_days: int = 30) -> list[CoChange]:
        """Compute file pairs that change together, enforcing Rule of Three.

        Rule of Three: 3+ co-occurrences in rolling 30-day window.
        Weight: min(1.0, count/10).
        Decay: if last_seen > 90 days ago, weight *= 0.5.
        """
        commits = self.get_commit_file_pairs()

        # Track per-pair co-occurrence timestamps
        pair_dates: dict[tuple[str, str], list[datetime]] = defaultdict(list)

        for commit in commits:
            files = sorted(set(commit["files"]))  # Deduplicate within commit
            date = commit["date"]

            # Generate all unique pairs
            for i in range(len(files)):
                for j in range(i + 1, len(files)):
                    pair = (files[i], files[j])
                    pair_dates[pair].append(date)

        # Apply rolling window and Rule of Three
        now = datetime.now(timezone.utc)
        decay_threshold = now - timedelta(days=90)
        results: list[CoChange] = []

        for (file_a, file_b), dates in pair_dates.items():
            dates.sort()

            # Count occurrences within rolling window
            window_count = 0
            for date in dates:
                window_start = date - timedelta(days=window_days)
                # Count how many dates fall within [window_start, date]
                count_in_window = sum(1 for d in dates if window_start <= d <= date)
                window_count = max(window_count, count_in_window)

            if window_count < min_count:
                continue

            last_seen = max(dates)
            total_count = len(dates)
            weight = min(1.0, total_count / 10)

            # Decay if stale
            if last_seen < decay_threshold:
                weight *= 0.5

            results.append(
                CoChange(
                    file_a=file_a,
                    file_b=file_b,
                    count=total_count,
                    last_seen=last_seen,
                    weight=round(weight, 2),
                )
            )

        return results

    def to_edges(self, project: str) -> list:
        """Convert co-changes to GraphEdges keyed by project."""
        from ..projects import qualify
        from .impact_graph import EdgeSource, GraphEdge

        co_changes = self.compute_co_changes()
        edges = []
        for cc in co_changes:
            edges.append(
                GraphEdge(
                    source_id=qualify(project, cc.file_a),
                    target_id=qualify(project, cc.file_b),
                    source=EdgeSource.GIT_INFERRED,
                    weight=cc.weight,
                    project=project,
                )
            )
        return edges

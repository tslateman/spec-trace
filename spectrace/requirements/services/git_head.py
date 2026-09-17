"""The commit a measurement belongs to, read from the checkout that holds the specs."""

import subprocess
from pathlib import Path


class NotAGitCheckout(Exception):
    """The path sits outside a git repository, so no commit names the measurement."""


def head_revision(repo_path: Path) -> tuple[str, str]:
    """Name the commit and branch checked out at a path.

    Args:
        repo_path: Directory inside the checkout to read

    Returns:
        The full HEAD SHA and the branch name; the branch reads ``HEAD`` when the
        checkout is detached, as CI checkouts usually are.

    Raises:
        NotAGitCheckout: The path holds no git repository.
    """
    return _read(repo_path, "HEAD"), _read(repo_path, "--abbrev-ref", "HEAD")


def _read(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise NotAGitCheckout(f"{repo_path} is outside a git checkout: {result.stderr.strip()}")
    return result.stdout.strip()

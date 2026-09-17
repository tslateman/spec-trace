"""Merge an approved task's branch into the base branch, then record the merge.

The state follows the git fact. Every check runs before git is touched, so a task
that cannot merge leaves the repository exactly as it was.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests


class MergeRefusal(Exception):
    """The merge stopped: the ledger, the repository, or git refused it."""

    def __init__(self, task_id: str, code: str, reason: str):
        self.task_id = task_id
        self.code = code
        self.reason = reason
        super().__init__(f"{task_id}: {code}: {reason}")


@dataclass(frozen=True)
class MergeReport:
    task_id: str
    base: str
    branch: str
    reviewed_sha: str
    merge_sha: str
    pushed: bool
    result: dict


def refusal_reason(error: requests.HTTPError) -> str:
    response = error.response
    if response.headers.get("Content-Type", "").startswith("application/json"):
        envelope = response.json()["error"]
        details = envelope.get("details") or {}
        return details.get("reason", envelope["code"])
    return f"{response.status_code} {response.text}"


class TaskMerger:
    """Merge one approved task's branch into `base` and record the merge on the task."""

    def __init__(
        self,
        client,
        repo: Path,
        base: str = "main",
        remote: str | None = None,
        log=lambda line: None,
    ):
        self.client = client
        self.repo = repo
        self.base = base
        self.remote = remote
        self.log = log

    def merge(self, task_id: str, branch: str | None = None) -> MergeReport:
        task = self._gate(task_id, "task", lambda: self.client.get_task(task_id))
        if task["status"] != "approved":
            raise MergeRefusal(
                task_id, "NOT_APPROVED", f"the task is {task['status']}, not approved"
            )
        branch = self._branch(task_id, task, branch)
        reviewed = task["commit_sha"]
        if not reviewed:
            raise MergeRefusal(task_id, "NO_REVIEWED_COMMIT", "the task carries no reviewed commit")

        self._assert_on_clean_base(task_id)
        head = self._branch_head(task_id, branch)
        if head != reviewed:
            raise MergeRefusal(
                task_id,
                "BRANCH_DRIFTED",
                f"{branch} is at {head[:7]}; the review read {reviewed[:7]}",
            )

        merge_sha = self._merge_branch(task_id, branch, task["title"])
        self.log(f"{task_id}: merged {branch} into {self.base} as {merge_sha[:7]}")
        if self.remote:
            self._git("push", self.remote, self.base, check=True)
            self.log(f"{task_id}: pushed {self.base} to {self.remote}")
        result = self._gate(
            task_id,
            "merge",
            lambda: self.client.merge_task(task_id, merge_sha=merge_sha, branch_head_sha=head),
        )
        return MergeReport(
            task_id=task_id,
            base=self.base,
            branch=branch,
            reviewed_sha=reviewed,
            merge_sha=merge_sha,
            pushed=self.remote is not None,
            result=result,
        )

    def _gate(self, task_id: str, stage: str, request):
        try:
            return request()
        except requests.HTTPError as error:
            raise MergeRefusal(
                task_id, "WORKER_REFUSED", f"{stage}: {refusal_reason(error)}"
            ) from error

    def _branch(self, task_id: str, task: dict, named: str | None) -> str:
        recorded = task["branch"]
        if named and recorded and named != recorded:
            raise MergeRefusal(
                task_id, "BRANCH_MISMATCH", f"the ledger recorded {recorded}, not {named}"
            )
        branch = named or recorded
        if not branch:
            raise MergeRefusal(
                task_id, "BRANCH_UNKNOWN", "the ledger records no branch; name one with --branch"
            )
        return branch

    def _assert_on_clean_base(self, task_id: str) -> None:
        current = self._git("rev-parse", "--abbrev-ref", "HEAD", check=True).stdout.strip()
        if current != self.base:
            raise MergeRefusal(
                task_id, "NOT_ON_BASE", f"{self.repo} is on {current}, not {self.base}"
            )
        if self._git("status", "--porcelain", check=True).stdout.strip():
            raise MergeRefusal(task_id, "REPO_DIRTY", f"{self.repo} has uncommitted changes")

    def _branch_head(self, task_id: str, branch: str) -> str:
        if self.remote:
            fetched = self._git("fetch", self.remote, f"+refs/heads/{branch}:refs/heads/{branch}")
            if fetched.returncode != 0:
                raise MergeRefusal(
                    task_id, "BRANCH_NOT_FOUND", f"{self.remote} has no branch {branch}"
                )
        found = self._git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
        if found.returncode != 0:
            raise MergeRefusal(task_id, "BRANCH_NOT_FOUND", f"{self.repo} has no branch {branch}")
        return found.stdout.strip()

    def _merge_branch(self, task_id: str, branch: str, title: str) -> str:
        merge = self._git(
            "merge", "--no-ff", "--no-edit", "-m", f"Merge task {task_id}: {title}", branch
        )
        if merge.returncode != 0:
            conflicts = self._git("diff", "--name-only", "--diff-filter=U").stdout.split()
            self._git("merge", "--abort")
            detail = ", ".join(conflicts) or merge.stdout.strip().splitlines()[-1]
            raise MergeRefusal(
                task_id, "MERGE_CONFLICT", f"{branch} conflicts with {self.base}: {detail}"
            )
        return self._git("rev-parse", "HEAD", check=True).stdout.strip()

    def _git(self, *args: str, check: bool = False):
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, check=check
        )

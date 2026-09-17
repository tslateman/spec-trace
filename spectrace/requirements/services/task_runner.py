"""Drain the unclaimed task queue: claim each task, work it in its own worktree, submit it."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests

from requirements.services.junit_cases import normalize_nodeid
from requirements.services.results_payload import test_run_payload


class GateRefusal(Exception):
    """The loop stopped at one task: a Worker gate, the coder, the tests, or an empty commit."""

    def __init__(self, task_id: str, stage: str, reason: str):
        self.task_id = task_id
        self.stage = stage
        self.reason = reason
        super().__init__(f"{task_id}: {stage} refused: {reason}")


@dataclass(frozen=True)
class Commands:
    """Shell commands the runner executes inside a task's worktree.

    `coder` receives the context bundle as JSON on stdin. `tests` may contain
    `{linked}`, which expands to the space-joined ids of every test linked to the
    task's requirements, and `{junit}`, which expands to the path the run should
    write its JUnit XML to; the runner pushes that file to the Worker tagged with
    the commit the task produced. `scorer` receives the bundle, commit sha, and diff as JSON on
    stdin and prints strategic_score, opportunity_score, drift_score, and optional
    failure_reasons as JSON. `scorer_agent` names the agent its verdict is posted
    under, which the Worker requires to differ from the agent holding the claim.
    """

    coder: str
    tests: str
    scorer: str | None = None
    scorer_agent: str | None = None


@dataclass(frozen=True)
class RunReport:
    task_id: str
    branch: str
    worktree: Path
    commit_sha: str


def refusal_reason(error: requests.HTTPError) -> str:
    response = error.response
    if response.headers.get("Content-Type", "").startswith("application/json"):
        envelope = response.json()["error"]
        details = envelope.get("details") or {}
        return details.get("reason", envelope["code"])
    return f"{response.status_code} {response.text}"


def requirement_ids_by_nodeid(bundle: dict) -> dict[str, list[str]]:
    """Index the task's requirements by the normalized nodeid of each test that verifies them."""
    index: dict[str, list[str]] = {}
    for requirement in bundle["requirements"]:
        for result in requirement["test_results"]:
            index.setdefault(normalize_nodeid(result["test_nodeid"]), []).append(
                requirement["external_id"]
            )
    return index


def linked_test_ids(bundle: dict) -> list[str]:
    ids = []
    for requirement in bundle["requirements"]:
        for result in requirement["test_results"]:
            if result["test_nodeid"] not in ids:
                ids.append(result["test_nodeid"])
    return ids


SCORE_KEYS = ("strategic_score", "opportunity_score", "drift_score")


def parse_scores(task_id: str, output: str) -> dict:
    try:
        scores = json.loads(output)
    except json.JSONDecodeError:
        raise GateRefusal(task_id, "scorer", f"printed no JSON: {output.strip()[:80]!r}") from None
    missing = [key for key in SCORE_KEYS if key not in scores]
    if missing:
        raise GateRefusal(task_id, "scorer", f"output lacks {', '.join(missing)}")
    return scores


class TaskRunner:
    def __init__(
        self,
        client,
        repo: Path,
        worktrees: Path,
        agent_id: str,
        commands: Commands,
        base: str = "main",
        lease_minutes: int = 30,
        remote: str | None = None,
        log=lambda line: None,
    ):
        self.client = client
        self.repo = repo
        self.worktrees = worktrees
        self.agent_id = agent_id
        self.commands = commands
        self.base = base
        self.lease_minutes = lease_minutes
        self.remote = remote
        self.log = log

    def drain(self, limit: int) -> list[RunReport]:
        page = self.client.list_tasks(status="unclaimed", per_page=limit, sort="created_at")
        return [self.run(task["id"]) for task in page["data"]]

    def run(self, task_id: str) -> RunReport:
        self._gate(
            task_id,
            "claim",
            lambda: self.client.claim_task(task_id, self.agent_id, self.lease_minutes),
        )
        self._gate(task_id, "start", lambda: self.client.start_task(task_id, self.agent_id))
        bundle = self._gate(task_id, "context", lambda: self.client.task_context(task_id))
        worktree, branch = self._worktree(task_id)
        self.log(f"{task_id}: working in {worktree} on {branch}")
        self._shell(task_id, "coder", self.commands.coder, worktree, stdin=json.dumps(bundle))
        junit = self._fresh_junit_path(task_id)
        self._shell(task_id, "tests", self._tests_command(task_id, bundle, junit), worktree)
        commit_sha = self._commit(task_id, worktree, bundle["title"])
        if self.remote:
            self._git("push", "-u", self.remote, branch, cwd=worktree, check=True)
        if junit:
            self._push_results(task_id, bundle, junit, commit_sha, branch)
        if self.commands.scorer:
            self._score(task_id, worktree, bundle, commit_sha, self.commands.scorer)
        self._gate(
            task_id,
            "complete",
            lambda: self.client.complete_task(task_id, self.agent_id, commit_sha, branch),
        )
        self.log(f"{task_id}: submitted {commit_sha[:7]} for review")
        return RunReport(task_id=task_id, branch=branch, worktree=worktree, commit_sha=commit_sha)

    def _gate(self, task_id: str, stage: str, request):
        try:
            return request()
        except requests.HTTPError as error:
            raise GateRefusal(task_id, stage, refusal_reason(error)) from error

    def _worktree(self, task_id: str) -> tuple[Path, str]:
        path = self.worktrees / task_id
        branch = f"task/{task_id}"
        if path.is_dir():
            return path, branch
        self.worktrees.mkdir(parents=True, exist_ok=True)
        if self.remote:
            self._git("fetch", self.remote, f"+refs/heads/{branch}:refs/heads/{branch}")
        branch_exists = (
            self._git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
        )
        if branch_exists:
            self._git("worktree", "add", str(path), branch, check=True)
        else:
            self._git("worktree", "add", str(path), "-b", branch, self.base, check=True)
        return path, branch

    def _fresh_junit_path(self, task_id: str) -> Path | None:
        if "{junit}" not in self.commands.tests:
            return None
        path = self.worktrees / f"{task_id}.junit.xml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        return path

    def _tests_command(self, task_id: str, bundle: dict, junit: Path | None) -> str:
        command = self.commands.tests
        if junit:
            command = command.replace("{junit}", str(junit))
        if "{linked}" not in command:
            return command
        linked = linked_test_ids(bundle)
        if not linked:
            raise GateRefusal(task_id, "tests", "no test is linked to the task's requirements")
        return command.replace("{linked}", " ".join(linked))

    def _push_results(
        self, task_id: str, bundle: dict, junit: Path, commit_sha: str, branch: str
    ) -> None:
        if not junit.exists():
            raise GateRefusal(
                task_id, "results", f"the tests command wrote no JUnit XML at {junit}"
            )
        payload = test_run_payload(junit, None)
        linked = requirement_ids_by_nodeid(bundle)
        for result in payload["results"]:
            named = linked.get(result["test_nodeid"], [])
            result["requirement_ids"] = list(dict.fromkeys([*result["requirement_ids"], *named]))
        payload |= {"git_sha": commit_sha, "git_branch": branch}
        summary = self._gate(task_id, "results", lambda: self.client.push_test_run(payload))
        self.log(
            f"{task_id}: pushed {summary['imported']} results at {commit_sha[:7]},"
            f" {summary['linked']} linked"
        )

    def _shell(self, task_id: str, stage: str, command: str, cwd: Path, stdin: str = "") -> str:
        completed = subprocess.run(
            command, shell=True, cwd=cwd, input=stdin, capture_output=True, text=True, check=False
        )
        if completed.returncode != 0:
            tail = (
                completed.stderr.strip().splitlines()[-3:]
                or completed.stdout.strip().splitlines()[-3:]
            )
            raise GateRefusal(task_id, stage, f"exit {completed.returncode}: " + " | ".join(tail))
        return completed.stdout

    def _commit(self, task_id: str, worktree: Path, title: str) -> str:
        self._git("add", "-A", cwd=worktree, check=True)
        if self._git("diff", "--cached", "--quiet", cwd=worktree).returncode == 0:
            raise GateRefusal(task_id, "commit", "the coder changed nothing")
        self._git("commit", "-q", "-m", f"task: {task_id} {title}", cwd=worktree, check=True)
        return self._git("rev-parse", "HEAD", cwd=worktree, check=True).stdout.strip()

    def _score(
        self, task_id: str, worktree: Path, bundle: dict, commit_sha: str, scorer: str
    ) -> None:
        diff = self._git("diff", f"{self.base}...HEAD", cwd=worktree, check=True).stdout
        payload = json.dumps({"task": bundle, "commit_sha": commit_sha, "diff": diff})
        scores = parse_scores(
            task_id, self._shell(task_id, "scorer", scorer, worktree, stdin=payload)
        )
        verdict = self._gate(
            task_id,
            "intent",
            lambda: self.client.record_intent_validation(
                task_id,
                self.commands.scorer_agent,
                commit_sha,
                scores["strategic_score"],
                scores["opportunity_score"],
                scores["drift_score"],
                failure_reasons=scores.get("failure_reasons"),
            ),
        )
        if not verdict["passed"]:
            raise GateRefusal(
                task_id, "intent", "; ".join(verdict["failure_reasons"]) or "scores below 70"
            )

    def _git(self, *args: str, cwd: Path | None = None, check: bool = False):
        return subprocess.run(
            ["git", *args], cwd=cwd or self.repo, capture_output=True, text=True, check=check
        )

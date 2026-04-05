"""Bridge for writing spec-trace task outcomes to Lore's journal.

When a task reaches a terminal state (MERGED or ABANDONED), this module
formats the outcome and calls `lore journal record` via subprocess.

Fail-open: if Lore is unavailable, log a warning and continue.
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

DEV_ROOT = Path(os.environ.get("DEV_ROOT", Path.home() / "dev"))
LORE_SH = DEV_ROOT / "lore" / "lore.sh"


def _format_done_when(results: list[dict]) -> str:
    """Format done_when_results as readable text for the journal entry."""
    if not results:
        return "No criteria recorded."
    lines = []
    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        criterion = r.get("criterion", "unknown")
        line = f"  [{status}] {criterion}"
        if r.get("notes"):
            line += f" -- {r['notes']}"
        lines.append(line)
    return "\n".join(lines)


def _build_decision(task_id: str, task_name: str, status: str) -> str:
    """Build the decision string for the journal entry."""
    verb = "merged" if status == "MERGED" else "abandoned"
    return f"spec-trace task `{task_id}` {verb}: {task_name}"


def _build_rationale(
    status: str,
    done_when_results: list[dict],
    attempt_count: int,
    max_attempts: int,
) -> str:
    """Build the rationale string including done_when criteria verdicts."""
    parts = []
    if status == "MERGED":
        parts.append("All done_when criteria passed review.")
    else:
        parts.append(f"Task abandoned after {attempt_count}/{max_attempts} attempts.")

    parts.append(f"\ndone_when results:\n{_format_done_when(done_when_results)}")
    return "\n".join(parts)


def notify_lore(
    task_id: str,
    task_name: str,
    status: str,
    done_when_results: list[dict] | None = None,
    attempt_count: int = 0,
    max_attempts: int = 2,
    commit_sha: str | None = None,
) -> bool:
    """Write a task outcome to Lore's journal.

    Args:
        task_id: Task external ID (e.g., 'task-auth-001')
        task_name: Human-readable task name
        status: Terminal status ('MERGED' or 'ABANDONED')
        done_when_results: List of {criterion, passed, notes} dicts
        attempt_count: Number of attempts before terminal state
        max_attempts: Maximum attempts allowed
        commit_sha: Git commit SHA associated with the task

    Returns:
        True if journal write succeeded, False otherwise.
    """
    if status not in ("MERGED", "ABANDONED"):
        logger.warning("notify_lore called with non-terminal status: %s", status)
        return False

    if not LORE_SH.exists():
        logger.warning("Lore not found at %s -- skipping journal write", LORE_SH)
        return False

    decision = _build_decision(task_id, task_name, status)
    rationale = _build_rationale(
        status,
        done_when_results or [],
        attempt_count,
        max_attempts,
    )

    cmd = [
        str(LORE_SH),
        "journal",
        "record",
        decision,
        "--rationale",
        rationale,
        "--type",
        "process",
        "--tags",
        f"spec-trace,task-outcome,{status.lower()}",
    ]

    if commit_sha:
        cmd.extend(["--files", commit_sha])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(DEV_ROOT / "lore"),
        )
        if result.returncode == 0:
            logger.info("Lore journal write succeeded for task %s", task_id)
            return True
        else:
            logger.warning(
                "Lore journal write failed (rc=%d) for task %s: %s",
                result.returncode,
                task_id,
                result.stderr.strip(),
            )
            return False
    except subprocess.TimeoutExpired:
        logger.warning("Lore journal write timed out for task %s", task_id)
        return False
    except OSError as e:
        logger.warning("Lore journal write failed for task %s: %s", task_id, e)
        return False

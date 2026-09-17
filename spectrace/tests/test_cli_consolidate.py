"""Tests for `spectrace consolidate`, which regenerates docs/current-state.md."""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import responses
from click.testing import CliRunner
from freezegun import freeze_time

from cli import cli
from requirements.services.current_state import BLOCK_END, BLOCK_START, TASK_STATUSES

URL = "http://worker.test"
AUTH = ["--url", URL, "--api-key", "secret"]
COVERAGE = {
    "project": "spectrace",
    "metrics": {
        "total": 32,
        "non_draft": 30,
        "passing": 26,
        "failing": 0,
        "untested": 6,
        "stale": 2,
    },
    "stale_requirements": ["REQ-CLI-001", "REQ-CLI-002"],
}
MILESTONES = textwrap.dedent(
    """\
    # Project Milestones: SpecTrace

    ## Unreleased — Cloudflare Port (In progress)

    **Delivered:** The Worker serves production.

    ## v11 Corpus Review & Self-Verification (Shipped: 2026-08-30)

    **Delivered:** A corpus of standards.

    ## v10 Spec as Interface (Shipped: 2026-02-27)

    **Delivered:** Specs as the agent's interface.
    """
)
DOCUMENT = textwrap.dedent(
    f"""\
    # Current State

    > Last updated: 2026-01-01 (stale)

    ## What Exists

    {BLOCK_START}

    ### Live state

    Read from http://stale.test on 2026-01-01.

    | Project | Requirements |
    | ------- | ------------ |
    | old     | 1            |

    {BLOCK_END}

    ## Next Steps

    Prose a person maintains.
    """
)


@pytest.fixture
def runner():
    return CliRunner()


def _worker_holds(tasks: dict[str, int]) -> None:
    responses.add(responses.GET, f"{URL}/api/v1/specs/coverage", json={"data": COVERAGE})
    for status in TASK_STATUSES:
        responses.add(
            responses.GET,
            f"{URL}/api/v1/tasks/",
            match=[responses.matchers.query_param_matcher({"status": status, "per_page": "1"})],
            json={"data": [], "meta": {"total": tasks.get(status, 0)}},
        )


def _document_with(tmp_path: Path, text: str) -> tuple[Path, Path]:
    doc = tmp_path / "current-state.md"
    doc.write_text(text)
    record = tmp_path / "MILESTONES.md"
    record.write_text(MILESTONES)
    return doc, record


@responses.activate
@freeze_time("2026-09-15 12:00:00")
def test_consolidate__rewrites_the_block_from_the_workers_live_data(runner, tmp_path):
    _worker_holds({"unclaimed": 3, "merged": 1})
    doc, record = _document_with(tmp_path, DOCUMENT)

    result = runner.invoke(
        cli, ["consolidate", "--doc", str(doc), "--milestones", str(record), *AUTH]
    )

    assert result.exit_code == 0, result.output
    written = doc.read_text()
    assert "> Last updated: 2026-09-15 (stale)" in written
    assert f"Read from {URL} on 2026-09-15." in written
    assert (
        "| Project   | Requirements | Non-draft | Passing | Failing | Untested | Stale |" in written
    )
    assert (
        "| spectrace | 32           | 30        | 26      | 0       | 6        | 2     |" in written
    )
    assert "Task ledger: 3 unclaimed, 1 merged — 4 total." in written
    assert "- v11 Corpus Review & Self-Verification (2026-08-30)" in written
    assert "- v10 Spec as Interface (2026-02-27)" in written
    assert "Prose a person maintains." in written
    assert "Read from http://stale.test" not in written
    assert responses.calls[0].request.headers["X-API-Key"] == "secret"


@responses.activate
@freeze_time("2026-09-15 12:00:00")
def test_consolidate__reports_what_it_read(runner, tmp_path):
    _worker_holds({"unclaimed": 3, "merged": 1})
    doc, record = _document_with(tmp_path, DOCUMENT)

    result = runner.invoke(
        cli, ["consolidate", "--doc", str(doc), "--milestones", str(record), *AUTH]
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        f"Regenerated {doc} from {URL}\n"
        "  spectrace: 32 requirements, 26 passing, 0 failing, 6 untested, 2 stale\n"
        "  tasks: 4\n"
        "  milestones: 2\n"
    )


@responses.activate
def test_consolidate__leaves_the_ledger_line_empty_when_no_task_exists(runner, tmp_path):
    _worker_holds({})
    doc, record = _document_with(tmp_path, DOCUMENT)

    result = runner.invoke(
        cli, ["consolidate", "--doc", str(doc), "--milestones", str(record), *AUTH]
    )

    assert result.exit_code == 0, result.output
    assert "The task ledger is empty." in doc.read_text()


@responses.activate
def test_consolidate__refuses_a_document_with_no_generated_block(runner, tmp_path):
    _worker_holds({})
    doc, record = _document_with(tmp_path, "# Current State\n\nNo markers here.\n")

    result = runner.invoke(
        cli, ["consolidate", "--doc", str(doc), "--milestones", str(record), *AUTH]
    )

    assert result.exit_code == 1
    assert "No <!-- spectrace:auto start" in str(result.exception)
    assert doc.read_text() == "# Current State\n\nNo markers here.\n"


@responses.activate
def test_consolidate__passes_the_project_to_the_coverage_endpoint(runner, tmp_path):
    _worker_holds({})
    doc, record = _document_with(tmp_path, DOCUMENT)

    result = runner.invoke(
        cli,
        [
            "consolidate",
            "--doc",
            str(doc),
            "--milestones",
            str(record),
            "--project",
            "billing",
            *AUTH,
        ],
    )

    assert result.exit_code == 0, result.output
    assert responses.calls[0].request.params["project"] == "billing"


def test_consolidate__runs_from_a_fresh_interpreter():
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "-c", "from spectrace.cli import main; main()", "consolidate", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Regenerate the live-state block" in result.stdout

"""Tests for the CI job that reports a run to Linear."""

from pathlib import Path

import pytest
from ruamel.yaml import YAML

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "linear-report.yml"


@pytest.fixture
def workflow():
    return YAML(typ="safe").load(WORKFLOW.read_text())


@pytest.fixture
def steps(workflow):
    return workflow["jobs"]["report"]["steps"]


def _step(steps, fragment):
    return next(step for step in steps if fragment in step.get("run", ""))


def test_linear_report_workflow__triggers_when_the_worker_suite_finishes_on_main(workflow):
    triggers = workflow["on"]["workflow_run"]

    assert triggers["workflows"] == ["Worker"]
    assert triggers["types"] == ["completed"]
    assert triggers["branches"] == ["main"]


def test_linear_report_workflow__names_the_missing_secret_when_it_skips(steps):
    guard = _step(steps, "LINEAR_API_KEY")

    assert guard["id"] == "secret"
    assert 'if [ -z "$LINEAR_API_KEY" ]; then' in guard["run"]
    assert 'configured=false" >> "$GITHUB_OUTPUT"' in guard["run"]
    assert "::warning::LINEAR_API_KEY is not set; no run reaches Linear." in guard["run"]
    assert "exit 0" in guard["run"]


def test_linear_report_workflow__gates_every_later_step_on_the_secret(steps):
    guarded = steps[1:]

    assert [step["if"] for step in guarded] == ["steps.secret.outputs.configured == 'true'"] * len(
        guarded
    )


def test_linear_report_workflow__checks_the_token_before_reporting(steps):
    commands = [step.get("run", "") for step in steps]
    check = next(i for i, run in enumerate(commands) if "spectrace linear check" in run)
    report = next(i for i, run in enumerate(commands) if "spectrace linear report" in run)

    assert check < report


def test_linear_report_workflow__reports_the_junit_file_the_suite_writes(steps):
    suite = _step(steps, "--junitxml")
    report = _step(steps, "spectrace linear report")

    assert "--junitxml=test_results.xml" in suite["run"]
    assert suite["continue-on-error"] is True
    assert "spectrace linear report test_results.xml --links links.json" in report["run"]


def test_linear_report_workflow__fails_the_job_when_the_reporter_cannot_post(steps):
    report = _step(steps, "spectrace linear report")

    assert "continue-on-error" not in report

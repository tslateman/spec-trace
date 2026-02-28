"""Tests for the spectrace Click CLI wrapper."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner
from spectrace.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


# =============================================================================
# Help tests
# =============================================================================


def test_help__lists_commands(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "specs" in result.output
    assert "tasks" in result.output
    assert "results" in result.output
    # Deprecated commands should not show up
    assert "drift" not in result.output


def test_specs_help__lists_subcommands(runner):
    result = runner.invoke(cli, ["specs", "--help"])
    assert result.exit_code == 0
    assert "coverage" in result.output
    assert "impact" in result.output
    assert "drift" in result.output


def test_tasks_help__lists_subcommands(runner):
    result = runner.invoke(cli, ["tasks", "--help"])
    assert result.exit_code == 0
    assert "register" in result.output
    assert "list" in result.output
    assert "claim" in result.output
    assert "start" in result.output
    assert "context" in result.output
    assert "complete" in result.output
    assert "review" in result.output
    assert "merge" in result.output
    assert "expire-leases" in result.output


def test_results_help__lists_subcommands(runner):
    result = runner.invoke(cli, ["results", "--help"])
    assert result.exit_code == 0
    assert "conflicts" in result.output
    assert "verify" in result.output
    assert "invariants" in result.output


def test_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


# =============================================================================
# Delegation tests — each command delegates to the right management command
# =============================================================================


@patch("spectrace.cli._run")
def test_tasks_context__delegates(mock_run, runner):
    result = runner.invoke(cli, ["tasks", "context", "T-1"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with("agent_context", "T-1", format="text")


@patch("spectrace.cli._run")
def test_specs_coverage__delegates(mock_run, runner):
    result = runner.invoke(cli, ["specs", "coverage", "--format", "json"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with("spec_coverage", format="json")


@patch("spectrace.cli._run")
def test_specs_impact__delegates(mock_run, runner):
    result = runner.invoke(cli, ["specs", "impact", "main", "feature-x", "--spec-dir", "my-specs"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "impact_analysis",
        "main",
        "feature-x",
        format="text",
        include_hierarchy=True,
        no_hierarchy=False,
        spec_dir="my-specs",
    )


@patch("spectrace.cli._run")
def test_specs_impact__no_hierarchy(mock_run, runner):
    result = runner.invoke(cli, ["specs", "impact", "a", "b", "--no-hierarchy"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "impact_analysis",
        "a",
        "b",
        format="text",
        include_hierarchy=False,
        no_hierarchy=True,
        spec_dir="specs",
    )


@patch("spectrace.cli._run")
def test_specs_drift__delegates(mock_run, runner):
    result = runner.invoke(cli, ["specs", "drift", "--check", "orphan", "--strict"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "detect_drift",
        tests=None,
        specs=None,
        format="text",
        check="orphan",
        strict=True,
    )


@patch("spectrace.cli._run")
def test_results_conflicts__delegates(mock_run, runner):
    result = runner.invoke(
        cli, ["results", "conflicts", "--min-runs", "20", "--alert", "--dry-run"]
    )
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "detect_conflicts",
        min_runs=20,
        min_overlap=5,
        latest=False,
        alert=True,
        dry_run=True,
    )


@patch("spectrace.cli._run")
def test_results_invariants__delegates(mock_run, runner):
    result = runner.invoke(cli, ["results", "invariants", "--fix", "--check", "INV-A"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "check_invariants", fix=True, format="text", check="INV-A", strict=False
    )


@patch("spectrace.cli._run")
def test_results_verify__delegates(mock_run, runner):
    result = runner.invoke(
        cli, ["results", "verify", "links.json", "--strict", "--check-high-risk"]
    )
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "validate_links",
        "links.json",
        strict=True,
        format="text",
        require_coverage=["active"],
        check_high_risk=True,
    )


@patch("spectrace.cli._run")
def test_tasks_register__delegates(mock_run, runner):
    result = runner.invoke(cli, ["tasks", "register", "bot-1", "--role", "coder"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "agent_register",
        "bot-1",
        role="coder",
        config="{}",
        format="text",
    )


@patch("spectrace.cli._run")
def test_tasks_list__delegates(mock_run, runner):
    result = runner.invoke(cli, ["tasks", "list", "--format", "json"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "agent_tasks", status=None, sprint=None, agent=None, format="json"
    )


@patch("spectrace.cli._run")
def test_tasks_claim__delegates(mock_run, runner):
    result = runner.invoke(cli, ["tasks", "claim", "T-1", "--agent", "c-1"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "agent_claim",
        "T-1",
        agent="c-1",
        lease_minutes=30,
        format="text",
    )


@patch("spectrace.cli._run")
def test_tasks_start__delegates(mock_run, runner):
    result = runner.invoke(cli, ["tasks", "start", "T-1", "--agent", "c-1"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with("agent_start", "T-1", agent="c-1", format="text")


@patch("spectrace.cli._run")
def test_tasks_complete__delegates(mock_run, runner):
    result = runner.invoke(
        cli, ["tasks", "complete", "T-1", "--agent", "c-1", "--commit-sha", "abc123"]
    )
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "agent_submit",
        "T-1",
        agent="c-1",
        commit_sha="abc123",
        format="text",
    )


@patch("spectrace.cli._run")
def test_tasks_review__delegates(mock_run, runner):
    result = runner.invoke(
        cli,
        [
            "tasks",
            "review",
            "T-1",
            "--reviewer",
            "r-1",
            "--decision",
            "approved",
            "--feedback",
            "Looks good",
            "--blocking-issues",
            "issue-1",
            "--suggestions",
            "nit-1",
            "--suggestions",
            "nit-2",
        ],
    )
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "agent_review",
        "T-1",
        reviewer="r-1",
        decision="approved",
        feedback="Looks good",
        blocking_issues=["issue-1"],
        suggestions=["nit-1", "nit-2"],
        format="text",
    )


@patch("spectrace.cli._run")
def test_tasks_merge__delegates(mock_run, runner):
    result = runner.invoke(cli, ["tasks", "merge", "T-1"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with("agent_merge", "T-1", format="text")


@patch("spectrace.cli._run")
def test_tasks_expire_leases__delegates(mock_run, runner):
    result = runner.invoke(cli, ["tasks", "expire-leases", "--dry-run"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with("expire_leases", dry_run=True, format="text")


# =============================================================================
# Deprecation tests
# =============================================================================


@patch("spectrace.cli._run")
def test_deprecated_coverage(mock_run, runner):
    result = runner.invoke(cli, ["coverage"])
    assert result.exit_code == 0
    assert "DEPRECATED" in result.stderr
    mock_run.assert_called_once()


@patch("spectrace.cli._run")
def test_deprecated_agent_submit(mock_run, runner):
    result = runner.invoke(
        cli, ["agent", "submit", "T-1", "--agent", "c-1", "--commit-sha", "abc123"]
    )
    assert result.exit_code == 0
    assert "DEPRECATED" in result.stderr
    mock_run.assert_called_once()


# =============================================================================
# Error tests
# =============================================================================


@patch("django.core.management.call_command")
def test_command_error__exits_1(mock_call, runner):
    from django.core.management.base import CommandError

    mock_call.side_effect = CommandError("Links file not found: missing.json")
    result = runner.invoke(cli, ["results", "verify", "missing.json"])
    assert result.exit_code == 1
    assert "missing.json" in result.output


def test_missing_required_option__exits_2(runner):
    result = runner.invoke(cli, ["tasks", "claim", "T-1"])
    assert result.exit_code == 2
    assert "Missing option" in result.output or "--agent" in result.output


def test_invalid_choice__exits_2(runner):
    result = runner.invoke(cli, ["tasks", "register", "bot-1", "--role", "hacker"])
    assert result.exit_code == 2
    assert "Invalid value" in result.output or "hacker" in result.output


# =============================================================================
# Integration test
# =============================================================================


@pytest.mark.django_db
def test_agent_tasks_json__integration(runner):
    result = runner.invoke(cli, ["tasks", "list", "--format", "json"])
    assert result.exit_code == 0
    assert '"tasks"' in result.output

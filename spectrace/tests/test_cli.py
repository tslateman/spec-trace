"""Tests for the spectrace Click CLI wrapper."""

from importlib.metadata import version
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cli import cli


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
    for command in (
        "register",
        "create",
        "approve-spec",
        "list",
        "claim",
        "start",
        "validate-intent",
        "complete",
        "review",
        "merge",
        "release",
        "context",
    ):
        assert command in result.output
    assert "expire-leases" not in result.output


def test_results_help__lists_subcommands(runner):
    result = runner.invoke(cli, ["results", "--help"])
    assert result.exit_code == 0
    assert "conflicts" in result.output
    assert "verify" in result.output
    assert "invariants" in result.output


def test_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert version("spectrace") in result.output


# =============================================================================
# Delegation tests — each command delegates to the right management command
# =============================================================================


@patch("cli._run")
def test_specs_coverage__delegates(mock_run, runner):
    result = runner.invoke(cli, ["specs", "coverage", "--format", "json"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with("spec_coverage", format="json", project=None)


@patch("cli._run")
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


@patch("cli._run")
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


@patch("cli._run")
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


@patch("cli._run")
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


@patch("cli._run")
def test_results_invariants__delegates(mock_run, runner):
    result = runner.invoke(cli, ["results", "invariants", "--fix", "--check", "INV-A"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        "check_invariants", fix=True, format="text", check="INV-A", strict=False
    )


@patch("cli._run")
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


# =============================================================================
# Deprecation tests
# =============================================================================


@patch("cli._run")
def test_deprecated_coverage(mock_run, runner):
    result = runner.invoke(cli, ["coverage"])
    assert result.exit_code == 0
    assert "DEPRECATED" in result.stderr
    mock_run.assert_called_once()


@patch("cli._run")
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


def test_cli_group__leaves_django_unconfigured(runner):
    """Worker-only commands must not pay for the app registry."""
    with patch("cli._bootstrap_django", autospec=True) as bootstrap:
        result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    bootstrap.assert_not_called()


@patch("cli._bootstrap_django", autospec=True)
def test_tasks_list__starts_no_django(bootstrap, runner):
    """`tasks list` reaches the Worker and never touches the ORM."""
    with patch("cli._client", autospec=True) as client:
        client.return_value.list_tasks.return_value = {
            "data": [],
            "meta": {"page": 1, "total_pages": 1, "total": 0},
        }
        result = runner.invoke(cli, ["tasks", "list", "--url", "http://w", "--api-key", "k"])

    assert result.exit_code == 0, result.output
    bootstrap.assert_not_called()


@patch("cli._bootstrap_django", autospec=True)
def test_run__starts_django_before_the_management_command(bootstrap):
    """Every management-command bridge initializes the app registry first."""
    from cli import _run

    with patch("django.core.management.call_command", autospec=True) as call_command:
        _run("spec_coverage", format="json")

    bootstrap.assert_called_once_with()
    call_command.assert_called_once_with("spec_coverage", format="json")

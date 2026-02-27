"""Click CLI for spectrace — thin wrapper around Django management commands."""

import os
import sys

import click


def _bootstrap_django():
    """Initialize Django settings and apps.

    Two path adjustments mirror how ``manage.py`` and ``pytest`` resolve
    imports:

    1. Extend ``spectrace.__path__`` to include ``spectrace/spectrace/``
       so Django finds ``spectrace.settings`` (the project config package).
    2. Add ``spectrace/`` to ``sys.path`` so Django finds the bare
       ``requirements`` app (matches pyproject.toml ``pythonpath``).
    """
    import spectrace as _pkg

    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    inner = os.path.join(pkg_dir, "spectrace")
    if inner not in _pkg.__path__:
        _pkg.__path__ = [inner] + list(_pkg.__path__)
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spectrace.settings")
    import django

    django.setup()


def _run(command_name: str, *args, **kwargs) -> None:
    """Bridge a Click command to its Django management command.

    Positional arguments must be passed as ``*args`` (not kwargs)
    because ``call_command`` maps kwargs to options only.
    """
    from django.core.management import call_command
    from django.core.management.base import CommandError

    try:
        call_command(command_name, *args, **kwargs)
    except CommandError as e:
        raise click.ClickException(str(e))


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="spectrace")
def cli():
    """SpecTrace — requirements traceability from spec to verified test."""
    _bootstrap_django()


# ---------------------------------------------------------------------------
# v10 stubs (fail gracefully until management commands land)
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("task_id")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def context(task_id, format):
    """Show full context for a task."""
    _run("agent_context", task_id, format=format)


@cli.command()
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def coverage(format):
    """Show spec coverage summary."""
    _run("spec_coverage", format=format)


@cli.command()
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def risks(format):
    """Show integration risk analysis."""
    _run("detect_integration_risks", format=format)


# ---------------------------------------------------------------------------
# Analysis commands
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("base_ref")
@click.argument("head_ref")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option("--no-hierarchy", is_flag=True, default=False, help="Skip child requirements")
@click.option("--spec-dir", default="specs", help="Spec file directory")
def impact(base_ref, head_ref, format, no_hierarchy, spec_dir):
    """Analyze impact of spec changes between two git refs."""
    _run(
        "impact_analysis",
        base_ref,
        head_ref,
        format=format,
        include_hierarchy=not no_hierarchy,
        no_hierarchy=no_hierarchy,
        spec_dir=spec_dir,
    )


@cli.command()
@click.option("--min-runs", type=int, default=10, help="Minimum test runs (default: 10)")
@click.option("--min-overlap", type=int, default=5, help="Minimum overlapping runs (default: 5)")
@click.option("--latest", is_flag=True, default=False, help="Only analyze latest runs")
@click.option("--alert", is_flag=True, default=False, help="Log and print alerts")
@click.option("--dry-run", is_flag=True, default=False, help="Detect without logging")
def conflicts(min_runs, min_overlap, latest, alert, dry_run):
    """Detect conflicts between requirements."""
    _run(
        "detect_conflicts",
        min_runs=min_runs,
        min_overlap=min_overlap,
        latest=latest,
        alert=alert,
        dry_run=dry_run,
    )


@cli.command()
@click.option("--tests", type=str, default=None, help="Test directory path")
@click.option("--specs", type=str, default=None, help="Specs directory path")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option(
    "--check",
    type=click.Choice(["all", "unmarked", "stale", "orphan", "drift"]),
    default="all",
)
@click.option("--strict", is_flag=True, default=False, help="Warnings become errors")
def drift(tests, specs, format, check, strict):
    """Detect drift between specs, tests, and links."""
    _run(
        "detect_drift",
        tests=tests,
        specs=specs,
        format=format,
        check=check,
        strict=strict,
    )


@cli.command()
@click.option("--fix", is_flag=True, default=False, help="Fix auto-fixable violations")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option(
    "--check",
    type=click.Choice(
        [
            "all",
            "INV-A",
            "INV-B",
            "INV-D",
            "INV-E",
            "INV-F",
            "INV-G",
            "INV-H",
            "INV-I",
            "INV-J",
            "INV-K",
        ]
    ),
    default="all",
)
@click.option("--strict", is_flag=True, default=False, help="Warnings become errors")
def invariants(fix, format, check, strict):
    """Check data invariants for consistency."""
    _run("check_invariants", fix=fix, format=format, check=check, strict=strict)


@cli.command()
@click.argument("links_file")
@click.option("--strict", is_flag=True, default=False, help="Warnings become errors")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option(
    "--require-coverage",
    multiple=True,
    help="Statuses requiring coverage (default: active)",
)
@click.option(
    "--check-high-risk",
    is_flag=True,
    default=False,
    help="Validate high-risk requirements",
)
def validate(links_file, strict, format, require_coverage, check_high_risk):
    """Validate test-requirement links."""
    _run(
        "validate_links",
        links_file,
        strict=strict,
        format=format,
        require_coverage=list(require_coverage) if require_coverage else ["active"],
        check_high_risk=check_high_risk,
    )


# ---------------------------------------------------------------------------
# Agent subgroup
# ---------------------------------------------------------------------------


@cli.group()
def agent():
    """Agent task pipeline commands."""


@agent.command()
@click.argument("agent_id")
@click.option("--role", required=True, type=click.Choice(["planner", "coder", "reviewer"]))
@click.option("--config", default="{}", help="JSON config string")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def register(agent_id, role, config, format):
    """Register a new agent."""
    _run("agent_register", agent_id, role=role, config=config, format=format)


@agent.command()
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--sprint", type=int, default=None, help="Filter by sprint")
@click.option("--agent", type=str, default=None, help="Filter by agent ID")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def tasks(status, sprint, agent, format):
    """List agent tasks."""
    _run("agent_tasks", status=status, sprint=sprint, agent=agent, format=format)


@agent.command()
@click.argument("task_id")
@click.option("--agent", required=True, help="Agent ID")
@click.option("--lease-minutes", type=int, default=30, help="Lease duration (default: 30)")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def claim(task_id, agent, lease_minutes, format):
    """Claim a task for an agent."""
    _run(
        "agent_claim",
        task_id,
        agent=agent,
        lease_minutes=lease_minutes,
        format=format,
    )


@agent.command()
@click.argument("task_id")
@click.option("--agent", required=True, help="Agent ID")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def start(task_id, agent, format):
    """Start work on a claimed task."""
    _run("agent_start", task_id, agent=agent, format=format)


@agent.command()
@click.argument("task_id")
@click.option("--agent", required=True, help="Agent ID")
@click.option("--commit-sha", required=True, help="Commit SHA of submitted work")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def submit(task_id, agent, commit_sha, format):
    """Submit work for review."""
    _run(
        "agent_submit",
        task_id,
        agent=agent,
        commit_sha=commit_sha,
        format=format,
    )


@agent.command()
@click.argument("task_id")
@click.option("--reviewer", required=True, help="Reviewer agent ID")
@click.option(
    "--decision",
    required=True,
    type=click.Choice(["approved", "changes_requested", "rejected"]),
)
@click.option("--feedback", default="", help="Review feedback text")
@click.option("--blocking-issues", multiple=True, help="Blocking issues")
@click.option("--suggestions", multiple=True, help="Non-blocking suggestions")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def review(task_id, reviewer, decision, feedback, blocking_issues, suggestions, format):
    """Review submitted work."""
    _run(
        "agent_review",
        task_id,
        reviewer=reviewer,
        decision=decision,
        feedback=feedback,
        blocking_issues=list(blocking_issues),
        suggestions=list(suggestions),
        format=format,
    )


@agent.command()
@click.argument("task_id")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def merge(task_id, format):
    """Merge an approved task."""
    _run("agent_merge", task_id, format=format)


@agent.command("expire-leases")
@click.option("--dry-run", is_flag=True, default=False, help="Report without modifying")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def expire_leases(dry_run, format):
    """Expire stale task leases."""
    _run("expire_leases", dry_run=dry_run, format=format)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    cli()

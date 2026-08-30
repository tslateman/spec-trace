"""Click CLI for spectrace — thin wrapper around Django management commands."""

import os
import sys

import click


def _bootstrap_django():
    """Initialize Django settings and apps."""
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
    """Bridge a Click command to its Django management command."""
    from django.core.management import call_command
    from django.core.management.base import CommandError

    try:
        call_command(command_name, *args, **kwargs)
    except CommandError as e:
        raise click.ClickException(str(e))


@click.group()
@click.version_option(package_name="spectrace")
def cli():
    """SpecTrace — requirements traceability from spec to verified test."""
    _bootstrap_django()


# ---------------------------------------------------------------------------
# API Groups
# ---------------------------------------------------------------------------


@cli.group()
def specs():
    """Spec discovery and analysis commands."""


@cli.group()
def tasks():
    """Agent task lifecycle commands."""


@cli.group()
def results():
    """Verification and evidence commands."""


@cli.group()
def corpus():
    """Corpus-backed spec review commands."""


# ---------------------------------------------------------------------------
# Specs commands
# ---------------------------------------------------------------------------


@specs.command()
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def coverage(format):
    """Show spec coverage summary."""
    _run("spec_coverage", format=format)


@specs.command()
@click.argument("base_ref")
@click.argument("head_ref")
@click.option("--format", type=click.Choice(["text", "json", "md", "markdown"]), default="text")
@click.option("--no-hierarchy", is_flag=True, default=False, help="Skip child requirements")
@click.option("--spec-dir", default="specs", help="Spec file directory")
@click.option("--code", is_flag=True, default=False, help="Full code impact analysis")
@click.option("--project-roots", default=None, help="project=path pairs (comma-separated)")
@click.option("--output", default=None, help="Write the report to this file instead of stdout")
def impact(base_ref, head_ref, format, no_hierarchy, spec_dir, code, project_roots, output):
    """Analyze impact of spec changes between two git refs."""
    if code:
        kwargs = {"format": format}
        if project_roots:
            kwargs["project_roots"] = project_roots
        if output:
            kwargs["output"] = output
        _run("code_impact_analysis", base_ref, head_ref, **kwargs)
    else:
        _run(
            "impact_analysis",
            base_ref,
            head_ref,
            format="md" if format == "markdown" else format,
            include_hierarchy=not no_hierarchy,
            no_hierarchy=no_hierarchy,
            spec_dir=spec_dir,
        )


@specs.command()
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


# ---------------------------------------------------------------------------
# Corpus commands
# ---------------------------------------------------------------------------


@corpus.command(name="review")
@click.argument("target")
@click.option("--format", type=click.Choice(["text", "json", "md"]), default="text")
@click.option("--reviewer", default="", help="Who ran the review")
@click.option("--strict", is_flag=True, default=False, help="Exit nonzero when findings exist")
def corpus_review(target, format, reviewer, strict):
    """Review a spec against the corpus and record coverage and findings."""
    _run("corpus_review", target, format=format, reviewer=reviewer, strict=strict)


@corpus.command(name="coverage")
@click.option("--requirement", default="", help="Limit to one requirement external ID")
@click.option("--format", type=click.Choice(["text", "json", "md"]), default="text")
def corpus_coverage(requirement, format):
    """Show which corpus entries each requirement's latest review surfaced."""
    _run("corpus_coverage", requirement=requirement, format=format)


@corpus.command(name="suggest")
@click.option("--requirement", default="", help="Limit to one requirement external ID")
@click.option("--min-score", type=float, default=None, help="Cosine floor for text similarity")
@click.option("--format", type=click.Choice(["text", "json", "md"]), default="text")
def corpus_suggest(requirement, min_score, format):
    """Propose applies_to widenings that would close corpus scope gaps."""
    kwargs = {"requirement": requirement, "format": format}
    if min_score is not None:
        kwargs["min_score"] = min_score
    _run("corpus_suggest", **kwargs)


@corpus.command(name="drift")
@click.option("--format", type=click.Choice(["text", "json", "md"]), default="text")
@click.option("--strict", is_flag=True, default=False, help="Exit nonzero when reviews are stale")
def corpus_drift(format, strict):
    """Name the reviews the corpus has moved out from under."""
    _run("corpus_drift", format=format, strict=strict)


# ---------------------------------------------------------------------------
# Map commands (spectrace-map.yaml management)
# ---------------------------------------------------------------------------


@specs.group()
def map():
    """Manage spectrace-map.yaml files."""


@map.command()
@click.option("--project-root", default=".", help="Project root directory")
@click.option("--project-name", required=True, help="Project name")
@click.option("--output", default=None, help="Output path")
@click.option("--lookback-days", type=int, default=90, help="Git history lookback")
@click.option("--min-count", type=int, default=3, help="Min co-change count")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def init(project_root, project_name, output, lookback_days, min_count, format):
    """Generate spectrace-map.yaml from git co-change inference."""
    kwargs = {
        "project_root": project_root,
        "project_name": project_name,
        "lookback_days": lookback_days,
        "min_count": min_count,
        "format": format,
    }
    if output:
        kwargs["output"] = output
    _run("map_init", **kwargs)


@map.command()
@click.option("--project-root", default=".", help="Project root directory")
@click.option("--project-name", required=True, help="Project name")
@click.option("--check-requirements", is_flag=True, default=False, help="Verify IDs in DB")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def validate(project_root, project_name, check_requirements, format):
    """Validate spectrace-map.yaml syntax and references."""
    _run(
        "map_validate",
        project_root=project_root,
        project_name=project_name,
        check_requirements=check_requirements,
        format=format,
    )


@map.command()
@click.option("--project-root", default=".", help="Project root directory")
@click.argument("module")
@click.argument("requirement")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def promote(project_root, module, requirement, format):
    """Promote a confirmed inferred edge to annotated in YAML."""
    _run("map_promote", module, requirement, project_root=project_root, format=format)


# ---------------------------------------------------------------------------
# Contract commands
# ---------------------------------------------------------------------------


@specs.group()
def contract():
    """Manage contract snapshots."""


@contract.command(name="generate")
@click.argument("project_root")
@click.option("--project-name", required=True, help="Project name")
@click.option("--output", default=None, help="Output path")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def contract_generate(project_root, project_name, output, format):
    """Generate contract.snapshot.json for a project."""
    kwargs = {"project_name": project_name, "format": format}
    if output:
        kwargs["output"] = output
    _run("generate_contract", project_root, **kwargs)


@contract.command(name="diff")
@click.argument("old_snapshot")
@click.argument("new_snapshot")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def contract_diff(old_snapshot, new_snapshot, format):
    """Diff two contract snapshots for breaking changes."""
    from requirements.services.contract_snapshot import ContractDiffer, ContractSnapshot

    old = ContractSnapshot.load(old_snapshot)
    new = ContractSnapshot.load(new_snapshot)
    differ = ContractDiffer()
    changes = differ.diff(old, new)

    if format == "json":
        import json

        output = [
            {
                "surface": c.surface,
                "change_type": c.change_type,
                "breaking": c.breaking,
                "field": c.field,
                "detail": c.detail,
            }
            for c in changes
        ]
        click.echo(json.dumps(output, indent=2))
    else:
        if not changes:
            click.secho("No changes detected.", fg="green")
            return
        for c in changes:
            color = "red" if c.breaking else "green"
            label = "BREAKING" if c.breaking else "non-breaking"
            click.secho(f"  [{label}] {c.detail}", fg=color)


# ---------------------------------------------------------------------------
# Tasks commands
# ---------------------------------------------------------------------------


@tasks.command()
@click.argument("agent_id")
@click.option("--role", required=True, type=click.Choice(["planner", "coder", "reviewer"]))
@click.option("--config", default="{}", help="JSON config string")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def register(agent_id, role, config, format):
    """Register a new agent."""
    _run("agent_register", agent_id, role=role, config=config, format=format)


@tasks.command(name="list")
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--sprint", type=int, default=None, help="Filter by sprint")
@click.option("--agent", type=str, default=None, help="Filter by agent ID")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def list_tasks(status, sprint, agent, format):
    """List agent tasks."""
    _run("agent_tasks", status=status, sprint=sprint, agent=agent, format=format)


@tasks.command()
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


@tasks.command()
@click.argument("task_id")
@click.option("--agent", required=True, help="Agent ID")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def start(task_id, agent, format):
    """Start work on a claimed task."""
    _run("agent_start", task_id, agent=agent, format=format)


@tasks.command()
@click.argument("task_id")
@click.option("--agent", required=True, help="Agent ID")
@click.option("--commit-sha", required=True, help="Commit SHA of completed work")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def complete(task_id, agent, commit_sha, format):
    """Complete work for review."""
    _run(
        "agent_submit",
        task_id,
        agent=agent,
        commit_sha=commit_sha,
        format=format,
    )


@tasks.command()
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
    """Review completed work."""
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


@tasks.command()
@click.argument("task_id")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option("--output", type=click.Path(), default=None, help="Write output to file")
def context(task_id, format, output):
    """Show full context for a task."""
    kwargs = {"format": format}
    if output:
        kwargs["output"] = output
    _run("agent_context", task_id, **kwargs)


@tasks.command()
@click.argument("task_id")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def merge(task_id, format):
    """Merge an approved task."""
    _run("agent_merge", task_id, format=format)


@tasks.command(name="validate-intent")
@click.argument("task_id")
@click.option("--commit-sha", required=True, help="Commit SHA or diff hash evaluated")
@click.option("--eval-json", required=True, help="Path to JSON file containing evaluation results")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def validate_intent(task_id, commit_sha, eval_json, format):
    """Record an intent-to-execution validation result."""
    _run(
        "validate_intent",
        task_id,
        commit_sha=commit_sha,
        eval_json=eval_json,
        format=format,
    )


@tasks.command(name="validation-stats")
@click.option("--timeframe", default="30d", help="Timeframe to analyze (e.g., '30d', '7d')")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def validation_stats(timeframe, format):
    """View historical statistics for intent-to-execution validation."""
    _run("validation_stats", timeframe=timeframe, format=format)


@tasks.command("expire-leases")
@click.option("--dry-run", is_flag=True, default=False, help="Report without modifying")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def expire_leases(dry_run, format):
    """Expire stale task leases."""
    _run("expire_leases", dry_run=dry_run, format=format)


# ---------------------------------------------------------------------------
# Results commands
# ---------------------------------------------------------------------------


@results.command()
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


@results.command()
@click.argument("links_file")
@click.option("--strict", is_flag=True, default=False, help="Warnings become errors")
@click.option("--format", type=click.Choice(["text", "json", "md"]), default="text")
@click.option(
    "--require-coverage",
    multiple=True,
    help="Statuses requiring coverage (default: active)",
)
@click.option(
    "--check-high-risk",
    is_flag=True,
    default=False,
    help="Verify high-risk requirements",
)
def verify(links_file, strict, format, require_coverage, check_high_risk):
    """Verify test-requirement links."""
    _run(
        "validate_links",
        links_file,
        strict=strict,
        format=format,
        require_coverage=list(require_coverage) if require_coverage else ["active"],
        check_high_risk=check_high_risk,
    )


@results.command()
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


# ---------------------------------------------------------------------------
# Deprecated commands
# ---------------------------------------------------------------------------


@cli.command("coverage", hidden=True)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_coverage(format):
    click.secho("DEPRECATED: Use 'st specs coverage' instead.", fg="yellow", err=True)
    _run("spec_coverage", format=format)


@cli.command("risks", hidden=True)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_risks(format):
    click.secho("DEPRECATED: No longer supported as top-level.", fg="yellow", err=True)
    _run("detect_integration_risks", format=format)


@cli.command("impact", hidden=True)
@click.argument("base_ref")
@click.argument("head_ref")
@click.option("--format", type=click.Choice(["text", "json", "md"]), default="text")
@click.option("--no-hierarchy", is_flag=True, default=False)
@click.option("--spec-dir", default="specs")
def deprecated_impact(base_ref, head_ref, format, no_hierarchy, spec_dir):
    click.secho("DEPRECATED: Use 'st specs impact' instead.", fg="yellow", err=True)
    _run(
        "impact_analysis",
        base_ref,
        head_ref,
        format=format,
        include_hierarchy=not no_hierarchy,
        no_hierarchy=no_hierarchy,
        spec_dir=spec_dir,
    )


@cli.command("conflicts", hidden=True)
@click.option("--min-runs", type=int, default=10)
@click.option("--min-overlap", type=int, default=5)
@click.option("--latest", is_flag=True, default=False)
@click.option("--alert", is_flag=True, default=False)
@click.option("--dry-run", is_flag=True, default=False)
def deprecated_conflicts(min_runs, min_overlap, latest, alert, dry_run):
    click.secho("DEPRECATED: Use 'st results conflicts' instead.", fg="yellow", err=True)
    _run(
        "detect_conflicts",
        min_runs=min_runs,
        min_overlap=min_overlap,
        latest=latest,
        alert=alert,
        dry_run=dry_run,
    )


@cli.command("drift", hidden=True)
@click.option("--tests", type=str, default=None)
@click.option("--specs", type=str, default=None)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option(
    "--check", type=click.Choice(["all", "unmarked", "stale", "orphan", "drift"]), default="all"
)
@click.option("--strict", is_flag=True, default=False)
def deprecated_drift(tests, specs, format, check, strict):
    click.secho("DEPRECATED: Use 'st specs drift' instead.", fg="yellow", err=True)
    _run(
        "detect_drift",
        tests=tests,
        specs=specs,
        format=format,
        check=check,
        strict=strict,
    )


@cli.command("invariants", hidden=True)
@click.option("--fix", is_flag=True, default=False)
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
@click.option("--strict", is_flag=True, default=False)
def deprecated_invariants(fix, format, check, strict):
    click.secho("DEPRECATED: Use 'st results invariants' instead.", fg="yellow", err=True)
    _run("check_invariants", fix=fix, format=format, check=check, strict=strict)


@cli.command("validate", hidden=True)
@click.argument("links_file")
@click.option("--strict", is_flag=True, default=False)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option("--require-coverage", multiple=True)
@click.option("--check-high-risk", is_flag=True, default=False)
def deprecated_validate(links_file, strict, format, require_coverage, check_high_risk):
    click.secho("DEPRECATED: Use 'st results verify' instead.", fg="yellow", err=True)
    _run(
        "validate_links",
        links_file,
        strict=strict,
        format=format,
        require_coverage=list(require_coverage) if require_coverage else ["active"],
        check_high_risk=check_high_risk,
    )


@cli.group(hidden=True)
def agent():
    pass


@agent.command("register")
@click.argument("agent_id")
@click.option("--role", required=True, type=click.Choice(["planner", "coder", "reviewer"]))
@click.option("--config", default="{}", help="JSON config string")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_register(agent_id, role, config, format):
    click.secho("DEPRECATED: Use 'st tasks register' instead.", fg="yellow", err=True)
    _run("agent_register", agent_id, role=role, config=config, format=format)


@agent.command("tasks")
@click.option("--status", type=str, default=None)
@click.option("--sprint", type=int, default=None)
@click.option("--agent", type=str, default=None)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_tasks(status, sprint, agent, format):
    click.secho("DEPRECATED: Use 'st tasks list' instead.", fg="yellow", err=True)
    _run("agent_tasks", status=status, sprint=sprint, agent=agent, format=format)


@agent.command("claim")
@click.argument("task_id")
@click.option("--agent", required=True)
@click.option("--lease-minutes", type=int, default=30)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_claim(task_id, agent, lease_minutes, format):
    click.secho("DEPRECATED: Use 'st tasks claim' instead.", fg="yellow", err=True)
    _run(
        "agent_claim",
        task_id,
        agent=agent,
        lease_minutes=lease_minutes,
        format=format,
    )


@agent.command("start")
@click.argument("task_id")
@click.option("--agent", required=True)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_start(task_id, agent, format):
    click.secho("DEPRECATED: Use 'st tasks start' instead.", fg="yellow", err=True)
    _run("agent_start", task_id, agent=agent, format=format)


@agent.command("submit")
@click.argument("task_id")
@click.option("--agent", required=True)
@click.option("--commit-sha", required=True)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_submit(task_id, agent, commit_sha, format):
    click.secho("DEPRECATED: Use 'st tasks complete' instead.", fg="yellow", err=True)
    _run(
        "agent_submit",
        task_id,
        agent=agent,
        commit_sha=commit_sha,
        format=format,
    )


@agent.command("review")
@click.argument("task_id")
@click.option("--reviewer", required=True)
@click.option(
    "--decision", required=True, type=click.Choice(["approved", "changes_requested", "rejected"])
)
@click.option("--feedback", default="")
@click.option("--blocking-issues", multiple=True)
@click.option("--suggestions", multiple=True)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_review(task_id, reviewer, decision, feedback, blocking_issues, suggestions, format):
    click.secho("DEPRECATED: Use 'st tasks review' instead.", fg="yellow", err=True)
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


@agent.command("merge")
@click.argument("task_id")
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_merge(task_id, format):
    click.secho("DEPRECATED: Use 'st tasks merge' instead.", fg="yellow", err=True)
    _run("agent_merge", task_id, format=format)


@agent.command("expire-leases")
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
def deprecated_expire_leases(dry_run, format):
    click.secho("DEPRECATED: Use 'st tasks expire-leases' instead.", fg="yellow", err=True)
    _run("expire_leases", dry_run=dry_run, format=format)


# Demo commands


@cli.command()
@click.option("--step", type=int, default=5, help="Run through step N then stop")
@click.option("--skip-setup", is_flag=True, default=False, help="Skip setup on reruns")
def demo(step, skip_setup):
    """Run the impact demo: spec change -> impact -> tests -> coverage."""
    _run("demo_impact", step=step, skip_setup=skip_setup)


def main():
    cli()

"""Click CLI for spectrace — thin wrapper around Django management commands."""

import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import click


def _add_package_paths():
    """Put `requirements` and the inner settings package on the import path.

    Importing anything under `requirements` needs this. Importing a module that
    touches the ORM needs `_bootstrap_django` instead.
    """
    import spectrace as _pkg

    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    inner = os.path.join(pkg_dir, "spectrace")
    if inner not in _pkg.__path__:
        _pkg.__path__ = [inner] + list(_pkg.__path__)
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)


def _bootstrap_django():
    """Initialize Django settings and apps; safe to call more than once."""
    _add_package_paths()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spectrace.settings")
    from django.apps import apps

    if apps.ready:
        return
    import django

    django.setup()


def _run(command_name: str, *args, **kwargs) -> None:
    """Bridge a Click command to its Django management command."""
    _bootstrap_django()
    from django.core.management import call_command
    from django.core.management.base import CommandError

    try:
        call_command(command_name, *args, **kwargs)
    except CommandError as e:
        raise click.ClickException(str(e))


def _remote_options(required: bool = True):
    """Add --url and --api-key, read from SPECTRACE_URL and SPECTRACE_API_KEY when omitted."""

    def decorate(command):
        command = click.option(
            "--api-key",
            envvar="SPECTRACE_API_KEY",
            required=required,
            help="Worker API key [env: SPECTRACE_API_KEY]",
        )(command)
        return click.option(
            "--url",
            envvar="SPECTRACE_URL",
            required=required,
            help="Worker base URL [env: SPECTRACE_URL]",
        )(command)

    return decorate


def _require_remote(url, api_key) -> None:
    if not (url and api_key):
        raise click.UsageError(
            "--push needs --url and --api-key (or SPECTRACE_URL and SPECTRACE_API_KEY)"
        )


def _client(url: str, api_key: str):
    _add_package_paths()
    from spectrace_client.client import ValidationClient

    return ValidationClient(api_url=url, api_key=api_key)


class WorkerRefusal(click.ClickException):
    """A non-2xx Worker response, rendered in the command's --format."""

    def __init__(self, error, format: str):
        self.response = error.response
        self.format = format
        self.envelope = (
            self.response.json()["error"]
            if self.response.headers.get("Content-Type", "").startswith("application/json")
            else None
        )
        super().__init__(self._describe())

    def _describe(self) -> str:
        origin = f"{self.response.status_code} from {self.response.url}"
        if self.envelope is None:
            return f"{origin}: {self.response.text}"
        details = self.envelope.get("details") or {}
        reason = details.get("reason", self.envelope["code"])
        return f"{origin}: {self.envelope['message']} [{reason}]"

    def show(self, file=None) -> None:
        if self.format == "json" and self.envelope is not None:
            click.echo(json.dumps({"error": self.envelope}, indent=2))
            return
        super().show(file)


def _send(request, format: str = "text"):
    """Run one client call, turning a non-2xx response into a CLI error."""
    import requests

    try:
        return request()
    except requests.HTTPError as e:
        raise WorkerRefusal(e, format)


def _echo_slo_result(result: dict) -> None:
    click.echo(f"  slos: {result['created']} created, {result['updated']} updated")
    for requirement_id in result["unresolved"]:
        click.echo(f"  unresolved requirement {requirement_id}")


def _echo_corpus_result(result: dict) -> None:
    click.echo(
        f"  corpus: {result['entries_created']} entries created,"
        f" {result['versions_created']} versions created,"
        f" {result['versions_unchanged']} unchanged"
    )


def _echo_push_result(result: dict) -> None:
    click.echo(f"Project {result['project']}")
    for kind in ("requirements", "links", "flows"):
        counts = result[kind]
        click.echo(
            f"  {kind}: {counts['created']} created, {counts['updated']} updated,"
            f" {counts['deleted']} deleted"
        )
    for ref in result["unresolved"]:
        click.echo(f"  unresolved {ref['kind']} {ref['ref']} in {ref['source']}")


@click.group()
@click.version_option(package_name="spectrace")
def cli():
    """SpecTrace — requirements traceability from spec to verified test."""


# ---------------------------------------------------------------------------
# API Groups
# ---------------------------------------------------------------------------


@cli.group()
def specs():
    """Spec discovery and analysis commands."""


@cli.group()
def linear():
    """Linear integration, run from the CLI with no server involved."""


@cli.group()
def tasks():
    """Agent task lifecycle commands."""


@cli.group()
def results():
    """Verification and evidence commands."""


@cli.group()
def flows():
    """Verification flow commands."""


@cli.group()
def corpus():
    """Corpus-backed spec review commands."""


# ---------------------------------------------------------------------------
# Specs commands
# ---------------------------------------------------------------------------


@specs.command()
@click.option("--format", type=click.Choice(["text", "json"]), default="text")
@click.option("--project", default=None, help="Project to report on")
@click.option("--push", is_flag=True, default=False, help="Store the run as a snapshot")
@click.option(
    "--repo",
    default=".",
    type=click.Path(exists=True, file_okay=False),
    help="Checkout whose commit the snapshot names",
)
@_remote_options(required=False)
def coverage(format, project, push, repo, url, api_key):
    """Show spec coverage summary.

    With --push, store the run as a snapshot in the Worker and report the change
    against the snapshot stored before it.
    """
    if push:
        _push_coverage(project, format, repo, url, api_key)
        return
    _run("spec_coverage", format=format, project=project)


@specs.command()
@click.argument("base_ref", required=False)
@click.argument("head_ref", required=False)
@click.option("--format", type=click.Choice(["text", "json", "md", "markdown"]), default="text")
@click.option("--no-hierarchy", is_flag=True, default=False, help="Skip child requirements")
@click.option("--spec-dir", default="specs", help="Spec file directory")
@click.option("--code", is_flag=True, default=False, help="Full code impact analysis")
@click.option(
    "--project-roots",
    default=None,
    help="project=path pairs (comma-separated); with --code, replaces the positional refs",
)
@click.option(
    "--project-refs",
    default=None,
    help="project=base..head pairs (comma-separated), one per --project-roots entry",
)
@click.option("--output", default=None, help="Write the report to this file instead of stdout")
@click.option("--push", is_flag=True, default=False, help="Store the report in the Worker")
@_remote_options(required=False)
def impact(
    base_ref,
    head_ref,
    format,
    no_hierarchy,
    spec_dir,
    code,
    project_roots,
    project_refs,
    output,
    push,
    url,
    api_key,
):
    """Analyze impact of spec changes between two git refs.

    With --code, --project-roots and --project-refs diff several repositories,
    each across its own refs, in place of BASE_REF and HEAD_REF.
    """
    if code:
        kwargs = {"format": format}
        if project_roots:
            kwargs["project_roots"] = project_roots
        if project_refs:
            kwargs["project_refs"] = project_refs
        if output:
            kwargs["output"] = output
        if push:
            raise click.UsageError("--push sends the spec impact report; drop --code")
        _run("code_impact_analysis", *[ref for ref in (base_ref, head_ref) if ref], **kwargs)
        return
    if not (base_ref and head_ref):
        raise click.UsageError("BASE_REF and HEAD_REF are required")
    if push:
        _push_impact(base_ref, head_ref, spec_dir, no_hierarchy, url, api_key)
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
    type=click.Choice(["all", "unmarked", "stale", "orphan", "wide", "untested", "drift"]),
    default="all",
)
@click.option("--strict", is_flag=True, default=False, help="Warnings become errors")
@click.option("--push", is_flag=True, default=False, help="Store the report in the Worker")
@_remote_options(required=False)
def drift(tests, specs, format, check, strict, push, url, api_key):
    """Detect drift between specs, tests, and links."""
    if push:
        _push_drift(tests, specs, check, url, api_key)
        return
    _run(
        "detect_drift",
        tests=tests,
        specs=specs,
        format=format,
        check=check,
        strict=strict,
    )


def _push_impact(base_ref, head_ref, spec_dir, no_hierarchy, url, api_key):
    _bootstrap_django()
    from requirements.services.impact_analyzer import ImpactAnalyzer
    from requirements.services.push_payloads import impact_report, project_of

    _require_remote(url, api_key)
    try:
        result = ImpactAnalyzer(spec_dir=spec_dir).analyze(
            base_ref, head_ref, include_hierarchy=not no_hierarchy
        )
    except ValueError as e:
        raise click.ClickException(str(e))
    report = impact_report(result, base_ref, head_ref, project_of([Path(spec_dir)]))
    receipt = _send(lambda: _client(url, api_key).push_impact(report))
    click.echo(f"Stored impact report for {receipt['project']} at {receipt['stored_at']}")


def _push_coverage(project, format, repo, url, api_key):
    _require_remote(url, api_key)
    _bootstrap_django()
    from requirements.models import Requirement
    from requirements.projects import AmbiguousProjectError, resolve_project
    from requirements.services.coverage_metrics import coverage_metrics
    from requirements.services.git_head import NotAGitCheckout, head_revision
    from requirements.services.push_payloads import coverage_snapshot

    try:
        resolved = resolve_project(project, Requirement.project_names())
    except AmbiguousProjectError as e:
        raise click.ClickException(f"{e} Pass --project.")
    try:
        commit_sha, git_branch = head_revision(Path(repo))
    except NotAGitCheckout as e:
        raise click.ClickException(str(e))

    snapshot = coverage_snapshot(coverage_metrics(resolved), commit_sha, git_branch)
    receipt = _send(lambda: _client(url, api_key).push_coverage(snapshot), format)
    if format == "json":
        _echo_coverage_json(snapshot, receipt)
    else:
        _echo_coverage_text(snapshot, receipt)


COVERAGE_RATES = (
    ("specification_rate", "Specification rate"),
    ("structure_rate", "Structure rate"),
    ("verification_rate", "Verification rate"),
)


def _coverage_detail(snapshot: dict, rate: str) -> str:
    if rate == "specification_rate":
        return f"{snapshot['non_draft']}/{snapshot['total']} non-draft"
    if rate == "verification_rate":
        return f"{snapshot['passing']}/{snapshot['total']} passing"
    return "avg FRET completeness"


def _coverage_change(current: float, previous: float) -> str:
    points = (current - previous) * 100
    return "unchanged" if round(points, 1) == 0 else f"{points:+.1f} pts"


def _echo_coverage_text(snapshot: dict, receipt: dict) -> None:
    previous = receipt["previous"]
    click.echo(f"Project: {snapshot['project']}")
    for rate, label in COVERAGE_RATES:
        detail = _coverage_detail(snapshot, rate)
        if previous:
            detail += f", {_coverage_change(snapshot[rate], previous[rate])}"
        click.echo(f"{label + ':':<20}{snapshot[rate] * 100:.1f}% ({detail})")
    if previous:
        click.echo(
            f"Compared against {previous['commit_sha'][:7]} on {previous['git_branch']}"
            f" from {previous['generated_at']}"
        )
    else:
        click.echo("No earlier snapshot: this run is the baseline")
    click.echo(f"Stored snapshot for {snapshot['commit_sha'][:7]} at {receipt['stored_at']}")


def _echo_coverage_json(snapshot: dict, receipt: dict) -> None:
    previous = receipt["previous"]
    click.echo(
        json.dumps(
            {
                **snapshot,
                "stored_at": receipt["stored_at"],
                "previous": previous,
                "change": {rate: snapshot[rate] - previous[rate] for rate, _ in COVERAGE_RATES}
                if previous
                else None,
            },
            indent=2,
        )
    )


def _push_drift(tests, specs, check, url, api_key):
    _bootstrap_django()
    from requirements.services.push_payloads import drift_report, project_of
    from requirements.validator import detect_all_drift

    if check != "all":
        raise click.UsageError("--push sends the full drift report; drop --check")
    _require_remote(url, api_key)
    specs_dir = Path(specs) if specs else None
    result = detect_all_drift(Path(tests) if tests else None, specs_dir)
    report = drift_report(result, project_of([specs_dir] if specs_dir else []))
    receipt = _send(lambda: _client(url, api_key).push_drift(report))
    click.echo(f"Stored drift report for {receipt['project']} at {receipt['stored_at']}")


# ---------------------------------------------------------------------------
# Push commands
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--specs",
    "spec_dirs",
    multiple=True,
    type=click.Path(exists=True, file_okay=False),
    help="Spec directory; repeat for several",
)
@click.option(
    "--flows",
    "flows_path",
    default=None,
    type=click.Path(exists=True),
    help="Flow YAML file or directory",
)
@click.option(
    "--links",
    "links_files",
    multiple=True,
    type=click.Path(exists=True, dir_okay=False),
    help="extract_links JSON or a JUnit report with [REQ-X] tags in test names; repeatable",
)
@click.option(
    "--slos",
    "slos_dir",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="Directory of OpenSLO YAML documents",
)
@click.option(
    "--corpus",
    "corpus_dir",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="Corpus directory of standards, decisions, and commitments",
)
@click.option("--project", default=None, help="Owning project (default: from spectrace-map.yaml)")
@click.option(
    "--replace", is_flag=True, default=False, help="Delete the project's stored rows the push omits"
)
@_remote_options()
def push(spec_dirs, flows_path, links_files, slos_dir, corpus_dir, project, replace, url, api_key):
    """Push specs, flows, test links, SLO definitions, and the corpus to the Worker."""
    _bootstrap_django()
    from requirements.services import push_payloads

    dirs = [Path(spec_dir) for spec_dir in spec_dirs]
    project = project or push_payloads.project_of(dirs)
    requirements = push_payloads.requirement_payload(dirs)
    links = [
        link for links_file in links_files for link in push_payloads.link_payload(Path(links_file))
    ]
    flows = push_payloads.flow_payload(Path(flows_path)) if flows_path else []
    client = _client(url, api_key)
    _echo_push_result(
        _send(lambda: client.push_specs(project, requirements, links, flows, replace=replace))
    )
    if slos_dir:
        _echo_slo_result(_send(lambda: client.push_slos(push_payloads.slo_payload(Path(slos_dir)))))
    if corpus_dir:
        _echo_corpus_result(
            _send(lambda: client.push_corpus(push_payloads.corpus_payload(Path(corpus_dir))))
        )


@results.command(name="push")
@click.argument("results_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--links",
    "links_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="extract_links JSON naming the requirement each JUnit test verifies",
)
@_remote_options()
def results_push(results_file, links_file, url, api_key):
    """Push JUnit XML or in-app validation JSON results to the Worker.

    JUnit XML becomes a test run; each case verifies the requirements --links names
    for it plus any [REQ-X] tags in its own name. In-app validation JSON becomes an
    enforcement run.
    """
    _bootstrap_django()
    from requirements.services.results_payload import test_run_payload, validation_payload

    path = Path(results_file)
    client = _client(url, api_key)
    if path.suffix.lower() == ".xml":
        payload = test_run_payload(path, Path(links_file) if links_file else None)
        _echo_test_run_summary(
            _send(lambda: client.push_test_run(payload, update_verification_status=True))
        )
        return
    try:
        payload = validation_payload(path, Path(links_file) if links_file else None)
    except ValueError as e:
        raise click.UsageError(str(e))
    _echo_results_summary(
        _send(
            lambda: client.push_results(
                payload["source"], payload["validations"], update_verification_status=True
            )
        )
    )


def _echo_results_summary(summary: dict) -> None:
    click.echo(
        f"Imported {summary['imported']} validations (successful={summary['successful']},"
        f" failed={summary['failed']}, skipped={summary['skipped']})"
    )


def _echo_test_run_summary(summary: dict) -> None:
    click.echo(
        f"Imported {summary['imported']} test results linked to {summary['linked']} requirements"
        f" (passed={summary['passed']}, failed={summary['failed']}, errors={summary['errors']},"
        f" skipped={summary['skipped']})"
    )


@cli.command()
@click.option(
    "--doc",
    type=click.Path(exists=True, dir_okay=False),
    default="docs/current-state.md",
    show_default=True,
    help="Document whose generated block is rewritten",
)
@click.option(
    "--milestones",
    type=click.Path(exists=True, dir_okay=False),
    default=".planning/MILESTONES.md",
    show_default=True,
    help="Planning record the shipped-milestone list comes from",
)
@click.option("--project", default=None, help="Project to report coverage for")
@_remote_options()
def consolidate(doc, milestones, project, url, api_key):
    """Regenerate the live-state block of docs/current-state.md from the Worker."""
    _add_package_paths()
    from requirements.services import current_state

    client = _client(url, api_key)
    state = _send(lambda: current_state.read_live_state(client, project))
    today = datetime.now(UTC).date()
    shipped = current_state.milestones_from(Path(milestones).read_text())
    block = current_state.render_block(
        source_url=url,
        generated_on=today,
        coverage=state["coverage"],
        tasks=state["tasks"],
        milestones=shipped,
    )
    document = Path(doc)
    document.write_text(current_state.regenerate(document.read_text(), block, today))

    metrics = state["coverage"]["metrics"]
    click.echo(f"Regenerated {doc} from {url}")
    click.echo(
        f"  {state['coverage']['project']}: {metrics['total']} requirements,"
        f" {metrics['passing']} passing, {metrics['failing']} failing,"
        f" {metrics['untested']} untested, {metrics['stale']} stale"
    )
    click.echo(f"  tasks: {sum(state['tasks'].values())}")
    click.echo(f"  milestones: {len(shipped)}")


@cli.group(invoke_without_command=True)
@click.option("--step", type=int, default=5, help="Run through step N then stop")
@click.option("--skip-setup", is_flag=True, default=False, help="Skip setup on reruns")
@click.pass_context
def demo(ctx, step, skip_setup):
    """Run the impact demo (spec change -> impact -> tests -> coverage) or load demo data."""
    if ctx.invoked_subcommand is None:
        _run("demo_impact", step=step, skip_setup=skip_setup)


@demo.command(name="load")
@click.argument("name", type=click.Choice(["vendor", "matrix", "impact", "flow"]))
@click.option(
    "--specs",
    "spec_dirs",
    multiple=True,
    default=("specs",),
    show_default=True,
    type=click.Path(exists=True, file_okay=False),
    help="Spec directory the demo requirements come from",
)
@_remote_options()
def demo_load(name, spec_dirs, url, api_key):
    """Seed one demo's data through the API."""
    _bootstrap_django()
    from requirements.services import push_payloads

    dirs = [Path(spec_dir) for spec_dir in spec_dirs]
    project = push_payloads.project_of(dirs)
    requirements = push_payloads.requirement_payload(dirs)
    ids = [requirement["external_id"] for requirement in requirements]
    loaders = {
        "vendor": _load_vendor_demo,
        "matrix": _load_matrix_demo,
        "impact": _load_impact_demo,
        "flow": _load_flow_demo,
    }
    loaders[name](_client(url, api_key), project, requirements, ids, dirs)


def _load_vendor_demo(client, project, requirements, ids, dirs):
    from django.utils import timezone

    from requirements.services.demo_payloads import vendor_demo_runs

    for run in vendor_demo_runs(ids, timezone.now()):
        summary = _send(lambda: client.push_results(run["source"], run["validations"]))
        click.echo(f"{run['source']}: imported {summary['imported']} validations")


def _load_matrix_demo(client, project, requirements, ids, dirs):
    from requirements.services.demo_payloads import matrix_demo_run

    _echo_push_result(_send(lambda: client.push_specs(project, requirements, [], [])))
    run = matrix_demo_run(ids)
    _echo_results_summary(_send(lambda: client.push_results(run["source"], run["validations"])))


def _load_impact_demo(client, project, requirements, ids, dirs):
    from requirements.services.demo_payloads import IMPACT_DEMO_BRANCH, impact_demo_links
    from requirements.services.impact_analyzer import prepare_impact_demo_branch

    links = impact_demo_links(ids)
    _echo_push_result(_send(lambda: client.push_specs(project, requirements, links, [])))
    prepare_impact_demo_branch(Path.cwd(), dirs[0], IMPACT_DEMO_BRANCH)
    click.echo(f"Run: spectrace specs impact main {IMPACT_DEMO_BRANCH} --push")


def _load_flow_demo(client, project, requirements, ids, dirs):
    from requirements.services.demo_payloads import flow_demo_flows

    _echo_push_result(_send(lambda: client.push_specs(project, [], [], flow_demo_flows())))
    click.echo("Flow runs stay local: the API has no endpoint for them.")


@cli.group()
def lore():
    """Lore journal bridge."""


@lore.command(name="sync")
@click.option(
    "--cursor-file",
    type=click.Path(dir_okay=False),
    default=str(Path.home() / ".spectrace" / "lore-cursor"),
    show_default=True,
    help="Where the last acknowledged cursor is kept",
)
@_remote_options()
def lore_sync(cursor_file, url, api_key):
    """Drain task outcomes from the Worker into Lore's journal."""
    _add_package_paths()
    from requirements.services.lore_bridge import notify_lore

    client = _client(url, api_key)
    cursor_path = Path(cursor_file)
    cursor = cursor_path.read_text().strip() if cursor_path.exists() else None
    written = 0
    refused = None
    while refused is None:
        page = _send(lambda: client.task_outcomes(since=cursor))
        for outcome in page["data"]:
            if not notify_lore(**_lore_arguments(outcome)):
                refused = outcome
                break
            cursor = outcome["cursor"]
            written += 1
        if page["meta"]["next_cursor"] is None:
            break
    if written:
        _send(lambda: client.ack_task_outcomes(cursor))
        cursor_path.parent.mkdir(parents=True, exist_ok=True)
        cursor_path.write_text(cursor)
    click.echo(f"Journaled {written} outcomes")
    if refused:
        raise click.ClickException(
            f"Lore refused {refused['task_id']}; acknowledged through {cursor or 'nothing'}"
        )


def _lore_arguments(outcome: dict) -> dict:
    return {
        "task_id": outcome["task_id"],
        "task_name": outcome["title"],
        "status": outcome["status"].upper(),
        "done_when_results": outcome["done_when_results"] or [],
        "attempt_count": outcome["attempt_count"],
        "max_attempts": outcome["max_attempts"],
        "commit_sha": outcome["commit_sha"] or None,
        "reason": outcome.get("reason"),
        "merge_sha": outcome.get("merge_sha") or None,
    }


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
    _add_package_paths()
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


def _format_option(command):
    return click.option("--format", type=click.Choice(["text", "json"]), default="text")(command)


def _echo_task_result(result: dict, format: str, text: str) -> None:
    if format == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(text)


def _transition_text(result: dict) -> str:
    return (
        f"{result['task_id']}: {result['from_status']} -> {result['to_status']}"
        f"\n{result['message']}"
    )


@tasks.command()
@click.argument("agent_id")
@click.option("--role", required=True, type=click.Choice(["planner", "coder", "reviewer"]))
@click.option("--config", default="{}", help="JSON config string")
@_format_option
@_remote_options()
def register(agent_id, role, config, format, url, api_key):
    """Register an agent, or update its role and reactivate it."""
    client = _client(url, api_key)
    agent = _send(lambda: client.register_agent(agent_id, role, config=json.loads(config)), format)
    state = "active" if agent["is_active"] else "inactive"
    _echo_task_result(agent, format, f"Registered {agent['agent_id']} as {agent['role']} ({state})")


@tasks.command()
@click.argument("task_id")
@click.option("--agent", required=True, help="Planner agent ID")
@click.option("--title", required=True)
@click.option("--description", default="")
@click.option("--requirement", multiple=True, help="Requirement ID the task implements")
@click.option("--done-when", multiple=True, help="Falsifiable completion criterion")
@click.option("--scope-in", multiple=True, help="Path or area the task may touch")
@click.option("--scope-out", multiple=True, help="Path or area the task must leave alone")
@click.option("--spec-ref", default="", help="Spec section, e.g. specs/auth.md#REQ-AUTH-001")
@click.option("--max-attempts", type=int, default=2, show_default=True)
@_format_option
@_remote_options()
def create(
    task_id,
    agent,
    title,
    description,
    requirement,
    done_when,
    scope_in,
    scope_out,
    spec_ref,
    max_attempts,
    format,
    url,
    api_key,
):
    """Create a draft task; approve-spec moves it to unclaimed."""
    draft = {
        "agent_id": agent,
        "task_id": task_id,
        "title": title,
        "description": description,
        "requirements": list(requirement),
        "done_when": list(done_when),
        "scope_in": list(scope_in),
        "scope_out": list(scope_out),
        "spec_ref": spec_ref,
        "max_attempts": max_attempts,
    }
    task = _send(lambda: _client(url, api_key).create_task(draft), format)
    _echo_task_result(task, format, f"Created {task['id']} in {task['status']}")


@tasks.command()
@click.option("--agent", required=True, help="Planner agent ID")
@click.option("--item", default=None, help="Roadmap item, by its number or text from its title")
@click.option("--gaps", is_flag=True, default=False, help="Draft one task per untested requirement")
@click.option(
    "--roadmap",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default="ROADMAP.md",
    show_default=True,
    help="Roadmap file --item reads",
)
@click.option(
    "--repo",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
    help="Checkout the roadmap item's paths resolve against",
)
@click.option("--project", default=None, help="Project whose gaps become tasks")
@click.option("--requirement", multiple=True, help="Requirement ID the roadmap draft links")
@click.option("--scope-in", multiple=True, help="Path every draft may touch, beyond those found")
@click.option("--scope-out", multiple=True, help="Path every draft must leave alone")
@click.option("--limit", type=int, default=5, show_default=True, help="Gap tasks to draft")
@click.option("--prefix", default="plan", show_default=True, help="Task id prefix")
@click.option("--max-attempts", type=int, default=2, show_default=True)
@click.option("--dry-run", is_flag=True, default=False, help="Print the drafts and create none")
@_format_option
@_remote_options()
def plan(
    agent,
    item,
    gaps,
    roadmap,
    repo,
    project,
    requirement,
    scope_in,
    scope_out,
    limit,
    prefix,
    max_attempts,
    dry_run,
    format,
    url,
    api_key,
):
    """Draft tasks from a roadmap item or the untested requirements; a reviewer approves each."""
    if bool(item) == gaps:
        raise click.UsageError("plan takes --item or --gaps, one of the two")
    _add_package_paths()
    from requirements.services.task_planner import (
        PlannerRefusal,
        find_item,
        gap_drafts,
        read_roadmap,
        roadmap_draft,
        untested_requirements,
    )

    client = _client(url, api_key)
    try:
        if item:
            drafts = [
                roadmap_draft(
                    find_item(read_roadmap(roadmap), item),
                    agent,
                    repo,
                    requirement,
                    scope_in,
                    scope_out,
                    prefix,
                    max_attempts,
                )
            ]
        else:
            drafts = gap_drafts(
                _send(lambda: untested_requirements(client, project, limit), format),
                agent,
                scope_in,
                scope_out,
                prefix,
                max_attempts,
            )
    except PlannerRefusal as refusal:
        raise click.ClickException(str(refusal))
    if dry_run:
        click.echo(json.dumps(drafts, indent=2))
        return
    created = [_send(lambda draft=draft: client.create_task(draft), format) for draft in drafts]
    if format == "json":
        click.echo(json.dumps(created, indent=2))
        return
    for task in created:
        click.echo(f"Drafted {task['id']} in {task['status']}: {task['title']}")
    click.echo(f"{len(created)} awaiting spec approval")


@tasks.command(name="approve-spec")
@click.argument("task_id")
@click.option("--reviewer", required=True, help="Reviewer agent ID")
@click.option("--feedback", default="", help="Spec review notes")
@_format_option
@_remote_options()
def approve_spec(task_id, reviewer, feedback, format, url, api_key):
    """Approve a draft task's spec, moving it to unclaimed."""
    result = _send(lambda: _client(url, api_key).approve_spec(task_id, reviewer, feedback), format)
    _echo_task_result(result, format, _transition_text(result))


@tasks.command(name="list")
@click.option("--status", type=str, default=None, help="Filter by status")
@click.option("--page", type=int, default=1, show_default=True)
@click.option("--per-page", type=int, default=None, help="Page size")
@click.option("--sort", default=None, help="Comma-separated fields, `-` prefix for descending")
@_format_option
@_remote_options()
def list_tasks(status, page, per_page, sort, format, url, api_key):
    """List agent tasks."""
    client = _client(url, api_key)
    result = _send(
        lambda: client.list_tasks(status=status, page=page, per_page=per_page, sort=sort), format
    )
    if format == "json":
        click.echo(json.dumps(result, indent=2))
        return
    for task in result["data"]:
        owner = task["claimed_by"] or "-"
        click.echo(f"{task['id']}  {task['status']}  {owner}  {task['title']}")
    meta = result["meta"]
    click.echo(f"Page {meta['page']} of {meta['total_pages']} ({meta['total']} tasks)")


@tasks.command()
@click.argument("task_id")
@click.option("--agent", required=True, help="Agent ID")
@click.option("--lease-minutes", type=int, default=30, help="Lease duration (default: 30)")
@_format_option
@_remote_options()
def claim(task_id, agent, lease_minutes, format, url, api_key):
    """Claim a task for an agent."""
    result = _send(lambda: _client(url, api_key).claim_task(task_id, agent, lease_minutes), format)
    _echo_task_result(
        result, format, f"{_transition_text(result)}\nLease expires {result['lease_expires']}"
    )


@tasks.command()
@click.argument("task_id")
@click.option("--agent", required=True, help="Agent ID")
@_format_option
@_remote_options()
def start(task_id, agent, format, url, api_key):
    """Start work on a claimed task."""
    result = _send(lambda: _client(url, api_key).start_task(task_id, agent), format)
    _echo_task_result(result, format, _transition_text(result))


@tasks.command(name="validate-intent")
@click.argument("task_id")
@click.option(
    "--validator",
    required=True,
    help="Agent that judged the commit; the Worker refuses the agent that claimed the task",
)
@click.option("--commit-sha", required=True, help="Commit SHA or diff hash evaluated")
@click.option("--strategic-score", type=click.IntRange(0, 100), required=True)
@click.option("--opportunity-score", type=click.IntRange(0, 100), required=True)
@click.option("--drift-score", type=click.IntRange(0, 100), required=True)
@click.option(
    "--passed/--failed",
    default=None,
    help="Override the verdict; by default every score must reach 70",
)
@click.option("--failure-reason", multiple=True, help="Why the commit missed the intent")
@_format_option
@_remote_options()
def validate_intent(
    task_id,
    validator,
    commit_sha,
    strategic_score,
    opportunity_score,
    drift_score,
    passed,
    failure_reason,
    format,
    url,
    api_key,
):
    """Record an intent-to-execution validation result for a commit."""
    client = _client(url, api_key)
    result = _send(
        lambda: client.record_intent_validation(
            task_id,
            validator,
            commit_sha,
            strategic_score,
            opportunity_score,
            drift_score,
            passed=passed,
            failure_reasons=list(failure_reason),
        ),
        format,
    )
    verdict = "passed" if result["passed"] else "failed"
    reasons = "".join(f"\n  {reason}" for reason in result["failure_reasons"])
    _echo_task_result(
        result,
        format,
        f"Intent validation for {result['commit_sha']} on {result['task_id']}: {verdict}{reasons}",
    )


@tasks.command()
@click.argument("task_id")
@click.option("--agent", required=True, help="Agent ID")
@click.option("--commit-sha", required=True, help="Commit SHA of completed work")
@click.option("--branch", default="", help="Branch the commit sits on, recorded for the merge")
@_format_option
@_remote_options()
def complete(task_id, agent, commit_sha, branch, format, url, api_key):
    """Submit a commit for review; its latest intent validation must have passed."""
    result = _send(
        lambda: _client(url, api_key).complete_task(task_id, agent, commit_sha, branch), format
    )
    _echo_task_result(result, format, _transition_text(result))


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
@_format_option
@_remote_options()
def review(
    task_id, reviewer, decision, feedback, blocking_issues, suggestions, format, url, api_key
):
    """Review completed work."""
    client = _client(url, api_key)
    result = _send(
        lambda: client.review_task(
            task_id,
            reviewer,
            decision,
            feedback=feedback,
            blocking_issues=list(blocking_issues),
            suggestions=list(suggestions),
        ),
        format,
    )
    _echo_task_result(result, format, _transition_text(result))


@tasks.command()
@click.argument("task_id")
@_format_option
@click.option("--output", type=click.Path(), default=None, help="Write output to file")
@click.option("--no-lore", is_flag=True, default=False, help="Skip the Lore overlay")
@_remote_options()
def context(task_id, format, output, no_lore, url, api_key):
    """Assemble the context bundle an agent reads before it works a task."""
    _add_package_paths()
    from requirements.services.task_context import lore_overlay, render_markdown

    bundle = _send(lambda: _client(url, api_key).task_context(task_id), format)
    if not no_lore:
        overlay = lore_overlay(bundle)
        if overlay:
            bundle["lore"] = overlay

    content = json.dumps(bundle, indent=2) if format == "json" else render_markdown(bundle)
    click.echo(content)
    if output:
        Path(output).write_text(content)


@tasks.command()
@click.argument("task_id")
@click.option(
    "--repo",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
    help="Repository holding the base branch and the task branch",
)
@click.option("--base", default="main", show_default=True, help="Branch the task merges into")
@click.option(
    "--branch", default=None, help="Branch to merge [default: the one the ledger recorded]"
)
@click.option(
    "--remote", default=None, help="Fetch the task branch from and push the merge to this remote"
)
@_format_option
@_remote_options()
def merge(task_id, repo, base, branch, remote, format, url, api_key):
    """Merge an approved task's branch into the base branch and record the merge."""
    _add_package_paths()
    from requirements.services.task_merge import MergeRefusal, TaskMerger

    merger = TaskMerger(
        _client(url, api_key),
        repo.resolve(),
        base=base,
        remote=remote,
        log=click.echo if format == "text" else lambda line: None,
    )
    try:
        report = merger.merge(task_id, branch)
    except MergeRefusal as refusal:
        if format == "json":
            click.echo(
                json.dumps(
                    {"task_id": refusal.task_id, "code": refusal.code, "reason": refusal.reason},
                    indent=2,
                )
            )
            raise SystemExit(1)
        raise click.ClickException(str(refusal))
    _echo_task_result(report.result, format, _transition_text(report.result))


@tasks.command()
@click.argument("task_id")
@click.option("--reason", default="manual", show_default=True, help="Why the claim is dropped")
@_format_option
@_remote_options()
def release(task_id, reason, format, url, api_key):
    """Release a claimed task back to the pool."""
    result = _send(lambda: _client(url, api_key).release_task(task_id, reason), format)
    _echo_task_result(result, format, _transition_text(result))


@tasks.command()
@click.option("--agent", required=True, help="Coder agent ID that claims each task")
@click.option(
    "--repo",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
    help="Repository whose base branch every task branches from",
)
@click.option(
    "--worktrees",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory that holds one worktree per task [default: <repo>/../<repo name>-tasks]",
)
@click.option("--base", default="main", show_default=True, help="Branch each task branches from")
@click.option(
    "--remote",
    default=None,
    help="Fetch task/<id> from and push it to this remote; for hosts with no disk between runs",
)
@click.option(
    "--coder",
    required=True,
    help="Command run in the task's worktree with the context bundle as JSON on stdin",
)
@click.option(
    "--tests",
    required=True,
    help="Command run in the worktree after the coder; {linked} expands to the linked test ids",
)
@click.option(
    "--scorer",
    default=None,
    help="Command that reads the bundle, commit sha, and diff as JSON and prints intent scores",
)
@click.option(
    "--scorer-agent",
    default=None,
    help="Agent the scorer's verdict is posted under; required with --scorer and never --agent",
)
@click.option("--limit", type=int, default=1, show_default=True, help="Tasks to drain this run")
@click.option("--lease-minutes", type=int, default=30, show_default=True)
@_format_option
@_remote_options()
def run(
    agent,
    repo,
    worktrees,
    base,
    remote,
    coder,
    tests,
    scorer,
    scorer_agent,
    limit,
    lease_minutes,
    format,
    url,
    api_key,
):
    """Claim, work, test, and submit each unclaimed task; stop at the first refusal."""
    if scorer and not scorer_agent:
        raise click.UsageError("--scorer needs --scorer-agent, the agent that posts its verdict")
    if scorer_agent == agent:
        raise click.UsageError("--scorer-agent must name an agent other than --agent")
    _add_package_paths()
    from requirements.services.task_runner import Commands, GateRefusal, TaskRunner

    repo = repo.resolve()
    runner = TaskRunner(
        _client(url, api_key),
        repo,
        worktrees or repo.parent / f"{repo.name}-tasks",
        agent,
        Commands(coder=coder, tests=tests, scorer=scorer, scorer_agent=scorer_agent),
        base=base,
        lease_minutes=lease_minutes,
        remote=remote,
        log=click.echo if format == "text" else lambda line: None,
    )
    try:
        reports = runner.drain(limit)
    except GateRefusal as refusal:
        if format == "json":
            click.echo(
                json.dumps(
                    {"task_id": refusal.task_id, "stage": refusal.stage, "reason": refusal.reason},
                    indent=2,
                )
            )
            raise SystemExit(1)
        raise click.ClickException(str(refusal))
    if format == "json":
        click.echo(
            json.dumps(
                [asdict(report) | {"worktree": str(report.worktree)} for report in reports],
                indent=2,
            )
        )
    elif not reports:
        click.echo("No unclaimed tasks")


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


@linear.command(name="pull")
@click.option("--label", default="requirement", show_default=True, help="Label that marks an issue")
@click.option(
    "--linear-api-key",
    envvar="LINEAR_API_KEY",
    required=True,
    help="Linear API key [env: LINEAR_API_KEY]",
)
@click.option(
    "--project",
    envvar="SPECTRACE_PROJECT",
    required=True,
    help="Project that owns these issues [env: SPECTRACE_PROJECT]",
)
@click.option("--dry-run", is_flag=True, help="List what would be pushed and stop")
@_remote_options()
def linear_pull(label, linear_api_key, project, dry_run, url, api_key):
    """Pull labeled Linear issues and push them to the Worker as requirements."""
    _add_package_paths()
    from requirements.linear import LinearClient

    issues = LinearClient(linear_api_key).fetch_issues_by_label(label)
    if not issues:
        click.echo(f"No issues labeled {label}")
        return
    if dry_run:
        for issue in issues:
            parent = f" (parent: {issue['parent_id']})" if issue["parent_id"] else ""
            click.echo(f"{issue['external_id']}: {issue['title']}{parent}")
        return
    client = _client(url, api_key)
    _echo_push_result(_send(lambda: client.push_specs(project, issues, [], [])))


@linear.command(name="report")
@click.argument("results_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--links",
    "links_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="extract_links JSON naming the requirement each JUnit test verifies",
)
@click.option(
    "--linear-api-key",
    envvar="LINEAR_API_KEY",
    required=True,
    help="Linear API key [env: LINEAR_API_KEY]",
)
@click.option("--git-sha", default=None, help="Commit the run verified")
@click.option("--ci-job-url", default=None, help="Link the comment points back to")
@click.option("--no-comments", is_flag=True, help="Leave issue comments alone")
@click.option("--no-labels", is_flag=True, help="Leave issue labels alone")
@click.option("--include-closed", is_flag=True, help="Report on completed and canceled issues too")
@click.option("--dry-run", is_flag=True, help="Show each requirement's tally and stop")
def linear_report(
    results_file,
    links_file,
    linear_api_key,
    git_sha,
    ci_job_url,
    no_comments,
    no_labels,
    include_closed,
    dry_run,
):
    """Post a JUnit run to the Linear issues its tests verify."""
    _add_package_paths()
    from requirements.services.linear_reporter import LinearReporter, outcomes_by_requirement
    from requirements.services.results_payload import test_run_payload

    run = test_run_payload(Path(results_file), Path(links_file) if links_file else None)
    run |= {
        "git_sha": git_sha,
        "ci_job_url": ci_job_url,
        "reported_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    }

    outcomes = outcomes_by_requirement(run["results"])
    if not outcomes:
        click.echo("No linked results to report")
        return
    if dry_run:
        for external_id, outcome in outcomes.items():
            click.echo(
                f"{external_id}: {outcome.passed} passed, {outcome.failed} failed,"
                f" {outcome.total} total"
            )
        return

    result = LinearReporter(linear_api_key).report_test_results(
        run,
        add_comments=not no_comments,
        update_labels=not no_labels,
        skip_closed=not include_closed,
    )
    click.echo(result.message)
    for error in result.errors or []:
        click.echo(f"  {error}", err=True)
    if not result.success:
        raise SystemExit(1)


@linear.command(name="check")
@click.option(
    "--linear-api-key",
    envvar="LINEAR_API_KEY",
    required=True,
    help="Linear API key [env: LINEAR_API_KEY]",
)
@click.option("--workspace", default="", help="Workspace the key should reach")
@click.option("--team", default="", help="Team the key should reach")
@_format_option
def linear_check(linear_api_key, workspace, team, format):
    """Check the Linear token's format, its identity, and its read access."""
    _add_package_paths()
    from requirements.linear import LinearClient
    from requirements.linear_checks import (
        check_authentication,
        check_configuration,
        check_permissions,
    )

    client = LinearClient(linear_api_key)
    checks = [
        check_configuration(linear_api_key, workspace, team),
        check_authentication(client),
        check_permissions(client),
    ]

    if format == "json":
        click.echo(json.dumps([asdict(check) for check in checks], indent=2))
    else:
        for check in checks:
            mark = "ok" if check.passed else "FAILED"
            click.echo(f"{mark}: {check.name}")
            if check.error_message:
                click.echo(f"  {check.error_message}")
    if not all(check.passed for check in checks):
        raise SystemExit(1)


@flows.command(name="run")
@click.argument("flow")
@click.option("--context", default="{}", help="JSON execution context")
@click.option("--step-timeout", type=int, default=60, show_default=True)
@click.option("--flow-timeout", type=int, default=300, show_default=True)
@click.option("--push/--no-push", default=True, help="Record the run on the Worker")
@_remote_options(required=False)
def flows_run(flow, context, step_timeout, flow_timeout, push, url, api_key):
    """Run a verification flow from a YAML file and record what happened."""
    _add_package_paths()
    from requirements.services.flow_run_records import flow_run_payload
    from spectrace_flows import FlowSource, InMemoryStorage, SequentialFlowEngine, YAMLFlowParser

    definition = YAMLFlowParser().parse_file(Path(flow))
    if definition is None:
        raise click.ClickException(f"No flow parsed from {flow}")

    run = SequentialFlowEngine(storage=InMemoryStorage()).execute(
        flow=definition,
        context=json.loads(context),
        source=FlowSource.CLI,
        step_timeout=step_timeout,
        flow_timeout=flow_timeout,
    )

    click.echo(f"Flow: {definition.display_name} ({definition.name})")
    click.echo(f"Status: {run.status.value}")
    for step in run.steps:
        click.echo(f"  {'PASS' if step.passed else 'FAIL'} {step.name}")
        if step.error_message:
            click.echo(f"       {step.error_message}")

    if push:
        _require_remote(url, api_key)
        receipt = _send(
            lambda: _client(url, api_key).push_flow_run(flow_run_payload(definition.name, run))
        )
        click.echo(f"Recorded run {receipt['run_id']} with {receipt['steps']} steps")

    if run.status.value != "passed":
        raise SystemExit(1)


def main():
    cli()

"""GitHub webhook handler for processing workflow_run events."""
import json
import logging
from typing import TYPE_CHECKING

from django.utils import timezone
from junitparser import JUnitXml, Failure, Error, Skipped

from ..models import TestRun, TestResult, Requirement, TestRequirementLink

if TYPE_CHECKING:
    from ..models import WebhookEvent
    from .github_app import GitHubWorkflowRun

logger = logging.getLogger(__name__)


class WorkflowProcessingError(Exception):
    """Error during workflow run processing."""

    pass


def process_workflow_run(
    workflow_run: "GitHubWorkflowRun",
    installation_id: int,
    webhook_event: "WebhookEvent",
) -> TestRun | None:
    """Process a workflow_run.completed webhook event.

    Downloads test artifacts and imports results into the database.

    Args:
        workflow_run: Parsed workflow run data.
        installation_id: GitHub App installation ID for API access.
        webhook_event: WebhookEvent record for audit trail.

    Returns:
        TestRun if results were imported, None if no artifacts found.

    Raises:
        WorkflowProcessingError: If processing fails.
    """
    from .github_app import GitHubClient, GitHubArtifactError

    logger.info(
        "Processing workflow run %d (%s) for %s",
        workflow_run.id,
        workflow_run.name,
        workflow_run.repository_full_name,
    )

    # Skip failed workflow runs - no point importing if tests didn't complete
    if workflow_run.conclusion not in ("success", "failure"):
        logger.info(
            "Skipping workflow with conclusion '%s' (run %d)",
            workflow_run.conclusion,
            workflow_run.id,
        )
        return None

    # Parse repository owner/name
    parts = workflow_run.repository_full_name.split("/")
    if len(parts) != 2:
        raise WorkflowProcessingError(
            f"Invalid repository name: {workflow_run.repository_full_name}"
        )
    owner, repo = parts

    # Initialize GitHub client and fetch artifacts
    client = GitHubClient()

    try:
        files = client.fetch_test_artifacts(
            owner=owner,
            repo=repo,
            run_id=workflow_run.id,
            installation_id=installation_id,
        )
    except GitHubArtifactError as e:
        # Artifact not found is not an error - workflow may not produce test results
        if "not found" in str(e).lower():
            logger.info("No test-results artifact found for run %d", workflow_run.id)
            return None
        raise WorkflowProcessingError(f"Failed to fetch artifacts: {e}") from e

    # Must have JUnit XML at minimum
    junit_content = files.get("junit.xml")
    if not junit_content:
        logger.warning("No junit.xml found in artifact for run %d", workflow_run.id)
        return None

    # Import the test results
    test_run = import_junit_from_bytes(
        junit_content=junit_content,
        source_name=f"github:{workflow_run.repository_full_name}:{workflow_run.id}",
        git_sha=workflow_run.head_sha,
        git_branch=workflow_run.head_branch,
        workflow_name=workflow_run.name,
        workflow_run_id=workflow_run.id,
        workflow_run_url=workflow_run.html_url,
        repository=workflow_run.repository_full_name,
    )

    logger.info(
        "Imported %d test results from workflow run %d",
        test_run.total_tests,
        workflow_run.id,
    )

    # Link results to requirements if links.json exists
    links_content = files.get("links.json")
    if links_content:
        try:
            link_summary = link_results_from_bytes(test_run, links_content)
            logger.info(
                "Linked %d tests to requirements (%d unlinked)",
                link_summary["linked_count"],
                len(link_summary["unlinked_tests"]),
            )
        except Exception as e:
            logger.warning("Failed to link results to requirements: %s", e)
            # Don't fail the import if linking fails
    else:
        logger.info("No links.json found in artifact, skipping requirement linking")

    # Update verification statuses
    status_summary = update_verification_statuses(test_run)
    if status_summary["status_changes"]:
        logger.info(
            "Updated %d requirement links with %d status changes",
            status_summary["updated_count"],
            len(status_summary["status_changes"]),
        )

    return test_run


def import_junit_from_bytes(
    junit_content: bytes,
    source_name: str,
    git_sha: str = "",
    git_branch: str = "",
    workflow_name: str = "",
    workflow_run_id: int | None = None,
    workflow_run_url: str = "",
    repository: str = "",
) -> TestRun:
    """Import JUnit XML content from bytes into database.

    Similar to importer.import_junit_xml but works with byte content
    instead of a file path.

    Args:
        junit_content: JUnit XML file content as bytes.
        source_name: Identifier for the source (e.g., "github:owner/repo:run_id").
        git_sha: Git commit SHA for this test run.
        git_branch: Git branch for this test run.
        workflow_name: GitHub Actions workflow name.
        workflow_run_id: GitHub Actions workflow run ID.
        workflow_run_url: URL to the workflow run.
        repository: Repository full name (owner/repo).

    Returns:
        TestRun instance with all test results.
    """
    xml = JUnitXml.fromstring(junit_content)

    test_run = TestRun.objects.create(
        source_file=source_name,
        git_sha=git_sha,
        git_branch=git_branch,
        ci_job_url=workflow_run_url,
        workflow_name=workflow_name,
        workflow_run_id=workflow_run_id,
        repository=repository,
        started_at=timezone.now(),
    )

    for suite in xml:
        for case in suite:
            # Determine status from result list
            status = "passed"
            message = ""

            if case.result:
                for result in case.result:
                    if isinstance(result, Failure):
                        status = "failed"
                        message = result.message or ""
                        break
                    elif isinstance(result, Error):
                        status = "error"
                        message = result.message or ""
                        break
                    elif isinstance(result, Skipped):
                        status = "skipped"
                        message = result.message or ""

            # Build nodeid from classname and name
            nodeid = f"{case.classname}::{case.name}" if case.classname else case.name

            TestResult.objects.create(
                test_run=test_run,
                test_nodeid=nodeid,
                classname=case.classname or "",
                name=case.name,
                time=case.time or 0.0,
                status=status,
                message=message,
            )

    # Mark test run as finished
    test_run.finished_at = timezone.now()
    test_run.save()

    return test_run


def _normalize_nodeid(nodeid: str) -> str:
    """Normalize a test nodeid to a canonical format.

    JUnit XML uses dotted class paths while pytest uses file paths.
    This normalizes to the file path format.
    """
    if "::" in nodeid:
        path_part, test_part = nodeid.split("::", 1)
    else:
        path_part = nodeid
        test_part = ""

    if "." in path_part and "/" not in path_part and not path_part.endswith(".py"):
        path_part = path_part.replace(".", "/") + ".py"

    if test_part:
        return f"{path_part}::{test_part}"
    return path_part


def link_results_from_bytes(test_run: TestRun, links_content: bytes) -> dict:
    """Link test results to requirements from links.json bytes.

    Similar to importer.link_results_to_requirements but works with
    byte content instead of a file path.

    Args:
        test_run: TestRun instance whose results should be linked.
        links_content: links.json content as bytes.

    Returns:
        Summary dict with linked_count and unlinked_tests.
    """
    data = json.loads(links_content.decode("utf-8"))

    # Build normalized nodeid -> requirement_ids lookup
    nodeid_to_reqs: dict[str, list[str]] = {}
    for link in data.get("links", []):
        nodeid = _normalize_nodeid(link["test_nodeid"])
        req_id = link["requirement_id"]
        if nodeid not in nodeid_to_reqs:
            nodeid_to_reqs[nodeid] = []
        nodeid_to_reqs[nodeid].append(req_id)

    linked_count = 0
    unlinked_tests = []

    for result in test_run.results.all():
        normalized_nodeid = _normalize_nodeid(result.test_nodeid)
        req_ids = nodeid_to_reqs.get(normalized_nodeid, [])
        if req_ids:
            requirements = Requirement.objects.filter(external_id__in=req_ids)
            result.requirements.set(requirements)
            linked_count += 1
        else:
            unlinked_tests.append(result.test_nodeid)

    return {"linked_count": linked_count, "unlinked_tests": unlinked_tests}


def update_verification_statuses(test_run: TestRun) -> dict:
    """Update TestRequirementLink records based on test results.

    Updates last_status and last_run_at for all links whose tests
    were included in this test run.

    Args:
        test_run: TestRun instance to process.

    Returns:
        Summary dict with updated_count and status_changes.
    """
    updated_count = 0
    status_changes = []

    # Build mapping of normalized nodeids to test results
    nodeid_to_result = {}
    for result in test_run.results.all():
        normalized = _normalize_nodeid(result.test_nodeid)
        nodeid_to_result[normalized] = result

    # Update all matching TestRequirementLinks
    for link in TestRequirementLink.objects.all():
        normalized = _normalize_nodeid(link.test_nodeid)
        result = nodeid_to_result.get(normalized)

        if result:
            old_status = link.last_status
            new_status = result.status

            link.last_status = new_status
            link.last_run_at = test_run.imported_at

            # Flag for review if status changed to failing
            if old_status == "passed" and new_status in ("failed", "error"):
                link.needs_review = True
                link.review_reason = f"status changed: {old_status} → {new_status}"
                status_changes.append((link.test_nodeid, old_status, new_status))

            link.save()
            updated_count += 1

    return {
        "updated_count": updated_count,
        "status_changes": status_changes,
    }

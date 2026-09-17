"""Linear reporter service for posting test results to Linear issues.

This service posts test status updates as comments on Linear issues,
following the pattern established in the observability/services/datadog_linear.py
from the Canary project.
"""

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


PASSING_STATUS = "passed"
FAILING_STATUSES = ("failed", "error")


@dataclass
class RequirementOutcome:
    """How one requirement's linked tests came out in a run."""

    passed: int = 0
    failed: int = 0
    total: int = 0


def outcomes_by_requirement(results: list[dict]) -> dict[str, RequirementOutcome]:
    """Tally each requirement's linked cases from a `test_run_payload` result list."""
    outcomes: dict[str, RequirementOutcome] = {}
    for result in results:
        for requirement_id in result.get("requirement_ids", []):
            outcome = outcomes.setdefault(requirement_id, RequirementOutcome())
            outcome.total += 1
            if result.get("status") == PASSING_STATUS:
                outcome.passed += 1
            elif result.get("status") in FAILING_STATUSES:
                outcome.failed += 1
    return outcomes


@dataclass
class LinearReportResult:
    """Result of a Linear reporting operation."""

    success: bool
    message: str
    issues_updated: int = 0
    issues_skipped: int = 0
    errors: list[str] | None = None


class LinearReporter:
    """Reports test results to Linear issues via comments and labels.

    Capabilities:
    1. Post test results summary as comments on Linear issues
    2. Update labels (tests:passing, tests:failing, tests:linked)
    3. Skip closed issues to avoid spam
    """

    API_URL = "https://api.linear.app/graphql"

    # Labels to manage
    LABEL_LINKED = "tests:linked"
    LABEL_PASSING = "tests:passing"
    LABEL_FAILING = "tests:failing"

    def __init__(self, api_key: str):
        """Initialize reporter with Linear API key.

        Args:
            api_key: Linear API key (starts with 'lin_api_')
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": api_key,
                "Content-Type": "application/json",
            }
        )
        # Cache for label IDs
        self._label_ids: dict[str, str] = {}
        self._team_id: str | None = None

    def _execute_query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query against Linear API."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self.session.post(self.API_URL, json=payload)
        response.raise_for_status()

        result = response.json()
        if "errors" in result:
            raise ValueError(f"GraphQL errors: {result['errors']}")

        return result.get("data", {})

    def _get_issue_by_identifier(self, identifier: str) -> dict | None:
        """Get issue details by identifier (e.g., CAN-1234)."""
        query = """
        query GetIssue($identifier: String!) {
            issue(id: $identifier) {
                id
                identifier
                title
                state {
                    type
                }
                team {
                    id
                }
                labels {
                    nodes {
                        id
                        name
                    }
                }
            }
        }
        """
        try:
            data = self._execute_query(query, {"identifier": identifier})
            return data.get("issue")
        except (requests.RequestException, ValueError) as e:
            logger.warning("Failed to get issue %s: %s", identifier, e)
            return None

    def _get_or_create_label(self, team_id: str, name: str, color: str = "#888888") -> str:
        """Get existing label ID or create it."""
        cache_key = f"{team_id}:{name}"
        if cache_key in self._label_ids:
            return self._label_ids[cache_key]

        # Search for existing label
        query = """
        query GetLabels($teamId: String!) {
            team(id: $teamId) {
                labels {
                    nodes {
                        id
                        name
                    }
                }
            }
        }
        """
        data = self._execute_query(query, {"teamId": team_id})
        labels = data.get("team", {}).get("labels", {}).get("nodes", [])

        for label in labels:
            if label["name"] == name:
                self._label_ids[cache_key] = label["id"]
                return label["id"]

        # Create label if not found
        mutation = """
        mutation CreateLabel($teamId: String!, $name: String!, $color: String!) {
            issueLabelCreate(input: {teamId: $teamId, name: $name, color: $color}) {
                issueLabel {
                    id
                }
                success
            }
        }
        """
        data = self._execute_query(
            mutation,
            {
                "teamId": team_id,
                "name": name,
                "color": color,
            },
        )
        label_id = data.get("issueLabelCreate", {}).get("issueLabel", {}).get("id")
        if label_id:
            self._label_ids[cache_key] = label_id
        return label_id

    def _add_comment(self, issue_id: str, body: str) -> bool:
        """Add a comment to an issue."""
        mutation = """
        mutation AddComment($issueId: String!, $body: String!) {
            commentCreate(input: {issueId: $issueId, body: $body}) {
                success
            }
        }
        """
        try:
            data = self._execute_query(
                mutation,
                {
                    "issueId": issue_id,
                    "body": body,
                },
            )
            return data.get("commentCreate", {}).get("success", False)
        except (requests.RequestException, ValueError) as e:
            logger.warning("Failed to add comment to issue %s: %s", issue_id, e)
            return False

    def _update_labels(self, issue_id: str, label_ids: list[str]) -> bool:
        """Update labels on an issue."""
        mutation = """
        mutation UpdateIssue($issueId: String!, $labelIds: [String!]!) {
            issueUpdate(id: $issueId, input: {labelIds: $labelIds}) {
                success
            }
        }
        """
        try:
            data = self._execute_query(
                mutation,
                {
                    "issueId": issue_id,
                    "labelIds": label_ids,
                },
            )
            return data.get("issueUpdate", {}).get("success", False)
        except (requests.RequestException, ValueError) as e:
            logger.warning("Failed to update labels on issue %s: %s", issue_id, e)
            return False

    def report_test_results(
        self,
        run: dict,
        add_comments: bool = True,
        update_labels: bool = True,
        skip_closed: bool = True,
    ) -> LinearReportResult:
        """Report a test run to every Linear issue its results name.

        Args:
            run: `test_run_payload` output, optionally carrying `git_sha`,
                `ci_job_url`, and `reported_at` for the comment body.
            add_comments: Whether to add comments to issues.
            update_labels: Whether to update labels on issues.
            skip_closed: Whether to skip closed/completed/canceled issues.

        Returns:
            LinearReportResult with summary.
        """
        errors = []
        issues_updated = 0
        issues_skipped = 0

        for external_id, outcome in outcomes_by_requirement(run.get("results", [])).items():
            try:
                reported = self._report_to_requirement(
                    external_id, outcome, run, add_comments, update_labels, skip_closed
                )
                if reported:
                    issues_updated += 1
                else:
                    issues_skipped += 1
            except Exception as e:
                errors.append(f"{external_id}: {str(e)}")

        return LinearReportResult(
            success=len(errors) == 0,
            message=f"Updated {issues_updated} issues, skipped {issues_skipped}",
            issues_updated=issues_updated,
            issues_skipped=issues_skipped,
            errors=errors if errors else None,
        )

    def _report_to_requirement(
        self,
        external_id: str,
        outcome: RequirementOutcome,
        run: dict,
        add_comments: bool,
        update_labels: bool,
        skip_closed: bool,
    ) -> bool:
        """Report one requirement's outcome to its Linear issue.

        Returns True if updated, False if skipped.
        """
        if outcome.total == 0:
            return False

        issue = self._get_issue_by_identifier(external_id)
        if not issue:
            return False

        state_type = issue.get("state", {}).get("type", "")
        if skip_closed and state_type in ("completed", "canceled"):
            return False

        team_id = issue.get("team", {}).get("id")
        issue_id = issue.get("id")

        if add_comments:
            self._add_comment(issue_id, self._comment_body(outcome, run))

        if update_labels and team_id:
            current_labels = [
                lbl["id"]
                for lbl in issue.get("labels", {}).get("nodes", [])
                if lbl["name"] not in [self.LABEL_LINKED, self.LABEL_PASSING, self.LABEL_FAILING]
            ]

            linked_label_id = self._get_or_create_label(team_id, self.LABEL_LINKED, "#888888")
            if linked_label_id:
                current_labels.append(linked_label_id)

            if outcome.failed == 0:
                passing_label_id = self._get_or_create_label(team_id, self.LABEL_PASSING, "#22c55e")
                if passing_label_id:
                    current_labels.append(passing_label_id)
            else:
                failing_label_id = self._get_or_create_label(team_id, self.LABEL_FAILING, "#ef4444")
                if failing_label_id:
                    current_labels.append(failing_label_id)

            self._update_labels(issue_id, current_labels)

        return True

    def _comment_body(self, outcome: RequirementOutcome, run: dict) -> str:
        status_emoji = "\u2705" if outcome.failed == 0 else "\u274c"
        body = f"""{status_emoji} **Test Results Updated**

| Status | Count |
|--------|-------|
| Passed | {outcome.passed} |
| Failed | {outcome.failed} |
| Total | {outcome.total} |
"""
        reported_at = run.get("reported_at")
        if reported_at:
            body += f"\n*From test run at {reported_at}*\n"
        git_sha = run.get("git_sha")
        if git_sha:
            body += f"\nCommit: `{git_sha[:8]}`"
        ci_job_url = run.get("ci_job_url")
        if ci_job_url:
            body += f"\n[View CI Job]({ci_job_url})"
        return body

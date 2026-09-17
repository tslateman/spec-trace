"""Client for submitting validation results to SpecTrace API."""

import logging
import os

import requests

from .models import ValidationResult, ValidationStatus

logger = logging.getLogger(__name__)


class ValidationClient:
    """Client for submitting validation results to SpecTrace API.

    Reads configuration from environment variables or Django settings:
    - SPECTRACE_URL / settings.SPECTRACE['API_URL']
    - SPECTRACE_API_KEY / settings.SPECTRACE['API_KEY']
    - SPECTRACE_ENABLED / settings.SPECTRACE['ENABLED']

    Best-effort submission: Logs warnings on failure but doesn't raise exceptions.
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        enabled: bool = True,
        timeout: int = 10,
    ):
        """Initialize validation client.

        Args:
            api_url: SpecTrace API base URL
            api_key: Optional API key for authentication
            enabled: Whether to actually submit validations
            timeout: Request timeout in seconds
        """
        self.api_url = (api_url or self._get_default_url()).rstrip("/")
        self.api_key = api_key
        self.enabled = enabled
        self.timeout = timeout
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({"X-API-Key": self.api_key})

    @classmethod
    def from_settings(cls) -> "ValidationClient":
        """Create client from Django settings and environment variables.

        Environment variables take precedence over Django settings.
        """
        # Check environment variables first
        api_url = os.environ.get("SPECTRACE_URL")
        api_key = os.environ.get("SPECTRACE_API_KEY")
        enabled_str = os.environ.get("SPECTRACE_ENABLED", "true").lower()
        enabled = enabled_str in ("true", "1", "yes", "on")

        from django.conf import settings

        # Override with Django settings if present
        if hasattr(settings, "SPECTRACE"):
            config = settings.SPECTRACE
            api_url = config.get("API_URL", api_url)
            api_key = config.get("API_KEY", api_key)
            enabled = config.get("ENABLED", enabled)

        return cls(
            api_url=api_url,
            api_key=api_key,
            enabled=enabled,
        )

    def _get_default_url(self) -> str:
        """Get default API URL from environment or fallback."""
        return os.environ.get("SPECTRACE_URL", "http://localhost:8000")

    def submit_validation(self, result: ValidationResult) -> bool:
        """Submit validation result to SpecTrace.

        Best-effort submission: logs error but doesn't raise on failure.

        Args:
            result: ValidationResult to submit

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug(
                "SpecTrace client disabled, skipping validation submission for %s",
                result.requirement_id,
            )
            return True

        try:
            url = f"{self.api_url}/api/v1/results/enforcement/"
            payload = {
                "source": "spectrace-client",
                "validations": [result.to_dict()],
            }

            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            logger.info(
                "Submitted validation for %s: %s",
                result.requirement_id,
                result.overall_status.value,
            )
            return True

        except requests.RequestException as e:
            # Log warning but don't fail the validation
            logger.warning(
                "Failed to submit validation to SpecTrace for %s: %s",
                result.requirement_id,
                e,
                exc_info=True,
            )
            return False

    def submit_validation_dict(
        self,
        requirement_id: str,
        name: str,
        status: str,
        message: str = "",
        context: dict | None = None,
    ) -> bool:
        """Submit simple validation without steps (convenience method).

        Args:
            requirement_id: Requirement ID (e.g., "REQ-PMS-OPERA-001")
            name: Human-readable validation name
            status: Status string ("success", "failure", "degraded", "error")
            message: Optional status message
            context: Optional context dict (hotel_id, vendor, etc.)

        Returns:
            True if successful, False otherwise
        """
        result = ValidationResult(
            requirement_id=requirement_id,
            name=name,
            status=ValidationStatus(status),
            message=message,
            context=context or {},
        )
        return self.submit_validation(result)

    def push_specs(
        self,
        project: str,
        requirements: list[dict],
        links: list[dict],
        flows: list[dict],
        replace: bool = False,
    ) -> dict:
        """Upsert one project's requirement tree, test links, and flows.

        PUT /api/v1/specs/. With `replace`, rows of the project absent from the
        payload are deleted, so the store ends up matching it. Raises
        requests.HTTPError on a non-2xx response.

        Args:
            project: Project name
            requirements: Flat list of requirements as SpecParser.parse_directory yields them
            links: Entries of .spectrace/links.json ({test_nodeid, requirement_id})
            flows: Flow definitions as YAMLFlowParser reads them
            replace: Delete the project's stored rows the payload omits

        Returns:
            Counts of created, updated, and deleted rows per kind, plus unresolved references
        """
        return self._send(
            "PUT",
            "/api/v1/specs/",
            {
                "project": project,
                "replace": replace,
                "requirements": requirements,
                "links": links,
                "flows": flows,
            },
        )

    def push_slos(self, slos: list[dict]) -> dict:
        """Upsert SLO definitions by name and relink them to requirements.

        PUT /api/v1/slos/. Leaves each SLO's status, current value, and error
        budget alone, since observability platforms own those through
        POST /api/v1/integrations/slo/status/. Raises requests.HTTPError on a
        non-2xx response.

        Args:
            slos: SLO definitions as OpenSLOParser.parse_directory yields them

        Returns:
            Counts of created and updated SLOs, plus requirement ids that matched nothing
        """
        return self._send("PUT", "/api/v1/slos/", {"slos": slos})

    def push_corpus(self, entries: list[dict]) -> dict:
        """Upsert corpus entries and record any version the store lacks.

        PUT /api/v1/corpus/entries/. Entry versions are immutable: re-pushing a
        version whose content hash differs from the stored one is refused rather
        than overwritten, and a version that drops a check id the previous
        version defined is refused unless the document declares `renamed_from`
        or `retired_checks`. Raises requests.HTTPError on a non-2xx response.

        Args:
            entries: Parsed entries as parse_corpus_directory yields them

        Returns:
            Counts of entries created, versions created, and versions already stored
        """
        return self._send("PUT", "/api/v1/corpus/entries/", {"entries": entries})

    def push_flow_run(self, record: dict) -> dict:
        """Record one flow execution against its stored flow definition.

        POST /api/v1/flows/runs/. The flow must already be stored, which
        `spectrace push --flows` does, since a run without its definition names
        nothing. Raises requests.HTTPError on a non-2xx response.

        Args:
            record: A run as push_payloads.flow_run_payload builds it

        Returns:
            The stored run's id, its flow, its status, and how many steps landed
        """
        return self._send("POST", "/api/v1/flows/runs/", record)

    def push_results(
        self, source: str, validations: list[dict], update_verification_status: bool = False
    ) -> dict:
        """Submit a batch of validation results.

        POST /api/v1/results/enforcement/. Raises requests.HTTPError on a non-2xx response.

        Args:
            source: Where the results came from (a file path or app name)
            validations: ValidationItem dicts (requirement_id, name, status, ...)
            update_verification_status: Recompute every requirement's verification status
                from the stored results, so coverage reflects this push

        Returns:
            ValidationResultResponse: success, imported, skipped, created_validations,
            successful, failed
        """
        response = self.session.post(
            f"{self.api_url}/api/v1/results/enforcement/",
            json={
                "source": source,
                "validations": validations,
                "update_verification_status": update_verification_status,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def push_test_run(self, payload: dict, update_verification_status: bool = False) -> dict:
        """Submit a JUnit test run and the requirements each case verifies.

        POST /api/v1/results/test-runs/. Raises requests.HTTPError on a non-2xx response.

        Args:
            payload: source_file plus a results list of test_nodeid, status, and requirement_ids
            update_verification_status: Recompute every requirement's verification status
                from the stored results, so coverage reflects this run

        Returns:
            run_id, imported, linked, and the passed/failed/errors/skipped tally
        """
        response = self.session.post(
            f"{self.api_url}/api/v1/results/test-runs/",
            json={**payload, "update_verification_status": update_verification_status},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def push_impact(self, report: dict) -> dict:
        """Store an impact report; GET /api/v1/specs/impact/ serves it.

        POST /api/v1/results/impact/. Raises requests.HTTPError on a non-2xx response.

        Args:
            report: ImpactReport body: project, base, head, generated_at, the ImpactAnalyzer result

        Returns:
            Receipt with project, generated_at, and stored_at
        """
        return self._send("POST", "/api/v1/results/impact/", report)

    def push_drift(self, report: dict) -> dict:
        """Store a drift report; GET /api/v1/specs/drift/ serves it.

        POST /api/v1/results/drift/. Raises requests.HTTPError on a non-2xx response.

        Args:
            report: DriftReport body (project, generated_at, and the detect_all_drift result)

        Returns:
            Receipt with project, generated_at, and stored_at
        """
        return self._send("POST", "/api/v1/results/drift/", report)

    def push_coverage(self, snapshot: dict) -> dict:
        """Append a coverage snapshot; GET /api/v1/specs/coverage/trend serves the series.

        POST /api/v1/results/coverage/. Raises requests.HTTPError on a non-2xx response.

        Args:
            snapshot: CoverageSnapshotPush body: project, commit_sha, git_branch,
                generated_at, the three rates, and the total, non_draft, and passing counts

        Returns:
            Receipt with project, generated_at, stored_at, and `previous` — the snapshot
            stored before this one, or None on the project's first run
        """
        return self._send("POST", "/api/v1/results/coverage/", snapshot)

    def task_outcomes(self, since: str | None = None, limit: int = 50) -> dict:
        """Read a page of the Lore outbox.

        GET /api/v1/tasks/outcomes. Raises requests.HTTPError on a non-2xx response.

        Args:
            since: Cursor of the last outcome processed; omit to start after the last ack
            limit: Page size, at most 100

        Returns:
            {"data": [TaskOutcome, ...], "meta": {"limit": int, "next_cursor": str | None}}
        """
        params = {"limit": limit}
        if since is not None:
            params["since"] = since
        response = self.session.get(
            f"{self.api_url}/api/v1/tasks/outcomes",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def ack_task_outcomes(self, cursor: str) -> dict:
        """Mark outcomes up to and including cursor drained.

        POST /api/v1/tasks/outcomes/ack. Raises requests.HTTPError on a non-2xx response.

        Returns:
            {"cursor": str, "drained": int}
        """
        return self._send("POST", "/api/v1/tasks/outcomes/ack", {"cursor": cursor})

    def list_tasks(
        self,
        status: str | None = None,
        page: int = 1,
        per_page: int | None = None,
        sort: str | None = None,
    ) -> dict:
        """Read a page of agent tasks.

        GET /api/v1/tasks/. Raises requests.HTTPError on a non-2xx response.

        Args:
            status: Keep only tasks in this status
            page: 1-based page number
            per_page: Page size; omit for the Worker's default
            sort: Comma-separated AgentTask fields, `-` prefix for descending

        Returns:
            {"data": [TaskSummary, ...], "meta": PagePosition}
        """
        params = {"page": page}
        if status is not None:
            params["status"] = status
        if per_page is not None:
            params["per_page"] = per_page
        if sort is not None:
            params["sort"] = sort
        response = self.session.get(
            f"{self.api_url}/api/v1/tasks/",
            params=params,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def task_context(self, task_id: str) -> dict:
        """Read the context bundle an agent needs before it works a task.

        GET /api/v1/tasks/{task_id}/context. Raises requests.HTTPError on a non-2xx
        response; a 404 means the ledger holds no such task.

        Returns:
            TaskContext: the task with its done_when and scope, every linked
            requirement with its FRET fields, tree placement, and test results, and
            drift over the whole database
        """
        return self._send("GET", f"/api/v1/tasks/{task_id}/context", None)

    def register_agent(self, agent_id: str, role: str, config: dict | None = None) -> dict:
        """Create an agent, or update its role and mark it active.

        POST /api/v1/tasks/agents/register/. Raises requests.HTTPError on a non-2xx response.

        Args:
            agent_id: Agent name, at most 100 characters
            role: planner, coder, or reviewer
            config: Free-form agent configuration

        Returns:
            Agent: agent_id, role, is_active
        """
        return self._send(
            "POST",
            "/api/v1/tasks/agents/register/",
            {"agent_id": agent_id, "role": role, "config": config or {}},
        )

    def create_task(self, draft: dict) -> dict:
        """Record a task in draft; only a planner agent may create one.

        POST /api/v1/tasks/. Raises requests.HTTPError on a non-2xx response.

        Args:
            draft: CreateTaskRequest body: agent_id, task_id, title, and the optional
                description, requirements, done_when, scope_in, scope_out, spec_ref,
                max_attempts

        Returns:
            TaskDraft: the stored task with status draft
        """
        return self._send("POST", "/api/v1/tasks/", draft)

    def approve_spec(self, task_id: str, reviewer_id: str, feedback: str = "") -> dict:
        """Pass the spec-review gate, moving the task from draft to unclaimed.

        POST /api/v1/tasks/{task_id}/approve-spec. Raises requests.HTTPError on a
        non-2xx response; a 409 carries SPEC_INCOMPLETE or NOT_DRAFT as details.reason.

        Returns:
            TransitionResult plus reviewer_id
        """
        return self._send(
            "POST",
            f"/api/v1/tasks/{task_id}/approve-spec",
            {"reviewer_id": reviewer_id, "feedback": feedback},
        )

    def record_intent_validation(
        self,
        task_id: str,
        validator_id: str,
        commit_sha: str,
        strategic_score: int,
        opportunity_score: int,
        drift_score: int,
        passed: bool | None = None,
        failure_reasons: list[str] | None = None,
    ) -> dict:
        """Record the verdict of an intent evaluation of one commit on the task.

        POST /api/v1/tasks/{task_id}/intent-validations. Raises requests.HTTPError on a
        non-2xx response; a 409 carries SELF_INTENT_NOT_ALLOWED as details.reason when
        the validator is the agent holding the task's claim.

        Args:
            task_id: Task external id
            validator_id: Agent that judged the commit; any agent but the claimant
            commit_sha: Commit the evaluation covers, at most 40 characters
            strategic_score: 0 to 100
            opportunity_score: 0 to 100
            drift_score: 0 to 100
            passed: Overrides the computed verdict (every score at 70 or above)
            failure_reasons: Why the commit missed the intent

        Returns:
            IntentValidation: the stored verdict with created_at
        """
        verdict = {
            "validator_id": validator_id,
            "commit_sha": commit_sha,
            "strategic_score": strategic_score,
            "opportunity_score": opportunity_score,
            "drift_score": drift_score,
            "failure_reasons": failure_reasons or [],
        }
        if passed is not None:
            verdict["passed"] = passed
        return self._send("POST", f"/api/v1/tasks/{task_id}/intent-validations", verdict)

    def claim_task(self, task_id: str, agent_id: str, lease_minutes: int = 30) -> dict:
        """Claim an unclaimed task and take a lease.

        POST /api/v1/tasks/{task_id}/claim. Raises requests.HTTPError on a non-2xx response.

        Returns:
            TransitionResult plus lease_expires and agent_id
        """
        return self._send(
            "POST",
            f"/api/v1/tasks/{task_id}/claim",
            {"agent_id": agent_id, "lease_minutes": lease_minutes},
        )

    def start_task(self, task_id: str, agent_id: str) -> dict:
        """Move a claimed task to in_progress; only the claiming agent may start it.

        POST /api/v1/tasks/{task_id}/start. Raises requests.HTTPError on a non-2xx response.

        Returns:
            TransitionResult
        """
        return self._send("POST", f"/api/v1/tasks/{task_id}/start", {"agent_id": agent_id})

    def complete_task(self, task_id: str, agent_id: str, commit_sha: str, branch: str = "") -> dict:
        """Submit a commit for review, moving the task to ready_for_review.

        POST /api/v1/tasks/{task_id}/complete. Raises requests.HTTPError on a non-2xx
        response; a 409 carries INTENT_NOT_VALIDATED or INTENT_FAILED as details.reason
        when the commit's latest intent validation is missing or failed.

        Args:
            task_id: Task external ID
            agent_id: Agent holding the claim
            commit_sha: Commit submitted for review
            branch: Branch the commit sits on, recorded so `merge_task` merges what the
                review read; the task keeps the branch it already carries when omitted

        Returns:
            TransitionResult plus commit_sha and branch
        """
        return self._send(
            "POST",
            f"/api/v1/tasks/{task_id}/complete",
            {"agent_id": agent_id, "commit_sha": commit_sha, "branch": branch},
        )

    def review_task(
        self,
        task_id: str,
        reviewer_id: str,
        decision: str,
        feedback: str = "",
        blocking_issues: list[str] | None = None,
        suggestions: list[str] | None = None,
    ) -> dict:
        """Record a review of a submitted task.

        POST /api/v1/tasks/{task_id}/review. Raises requests.HTTPError on a non-2xx response.

        Args:
            task_id: Task external id
            reviewer_id: A reviewer agent other than the submitter
            decision: approved, changes_requested, or rejected
            feedback: Review text
            blocking_issues: What must change before approval
            suggestions: Non-blocking ideas

        Returns:
            TransitionResult
        """
        return self._send(
            "POST",
            f"/api/v1/tasks/{task_id}/review",
            {
                "reviewer_id": reviewer_id,
                "decision": decision,
                "feedback": feedback,
                "blocking_issues": blocking_issues or [],
                "suggestions": suggestions or [],
            },
        )

    def get_task(self, task_id: str) -> dict:
        """Read one task's ledger row.

        GET /api/v1/tasks/{task_id}. Raises requests.HTTPError on a non-2xx response.

        Returns:
            TaskDetail: status, claim, scope, and the git facts branch, commit_sha,
            and merge_sha
        """
        return self._send("GET", f"/api/v1/tasks/{task_id}", None)

    def merge_task(self, task_id: str, merge_sha: str, branch_head_sha: str) -> dict:
        """Record the merge of an approved task's branch into the base branch.

        POST /api/v1/tasks/{task_id}/merge. Raises requests.HTTPError on a non-2xx
        response; a 409 carries BRANCH_DRIFTED as details.reason when branch_head_sha
        differs from the commit the review read.

        Args:
            task_id: Task external ID
            merge_sha: Commit the merge produced on the base branch
            branch_head_sha: Tip of the task branch that was merged

        Returns:
            TransitionResult plus merge_sha and branch
        """
        return self._send(
            "POST",
            f"/api/v1/tasks/{task_id}/merge",
            {"merge_sha": merge_sha, "branch_head_sha": branch_head_sha},
        )

    def release_task(self, task_id: str, reason: str = "manual") -> dict:
        """Drop the claim and lease, returning the task to unclaimed.

        POST /api/v1/tasks/{task_id}/release. Raises requests.HTTPError on a non-2xx response.

        Returns:
            TransitionResult
        """
        return self._send("POST", f"/api/v1/tasks/{task_id}/release", {"reason": reason})

    def _send(self, method: str, path: str, payload: dict | None) -> dict:
        response = self.session.request(
            method,
            f"{self.api_url}{path}",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["data"]

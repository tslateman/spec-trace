"""Requirement model for storing parsed spec requirements."""
from functools import cached_property

from django.db import models
from treebeard.mp_tree import MP_Node


class VerificationStatus(models.TextChoices):
    """Verification status for requirements based on linked test results."""
    PASSING = 'passing', 'Passing'
    FAILING = 'failing', 'Failing'
    UNTESTED = 'untested', 'Untested'


class VerificationMethod(models.TextChoices):
    """How a requirement should be verified."""
    TEST = 'test', 'Test Automation'
    INAPP = 'inapp', 'In-App Validation'
    BOTH = 'both', 'Both Methods'
    UNSPECIFIED = 'unspecified', 'Unspecified'


class SLOStatus(models.TextChoices):
    """Status of SLO compliance for a requirement."""
    MET = 'met', 'Met'
    AT_RISK = 'at_risk', 'At Risk'
    BREACHED = 'breached', 'Breached'
    NOT_LINKED = 'not_linked', 'Not Linked'

    @classmethod
    def from_string(cls, value: str) -> 'SLOStatus':
        """Convert lowercase string to SLOStatus.

        Args:
            value: Status string (met, at_risk, breached)

        Returns:
            Corresponding SLOStatus, or NOT_LINKED for unknown values.
        """
        mapping = {
            'met': cls.MET,
            'at_risk': cls.AT_RISK,
            'breached': cls.BREACHED,
        }
        return mapping.get(value.lower(), cls.NOT_LINKED)


class AgentTaskStatus(models.TextChoices):
    """Task lifecycle states for agent coordination."""
    DRAFT = 'draft', 'Draft'
    UNCLAIMED = 'unclaimed', 'Unclaimed'
    CLAIMED = 'claimed', 'Claimed'
    IN_PROGRESS = 'in_progress', 'In Progress'
    READY_FOR_REVIEW = 'ready_for_review', 'Ready for Review'
    CHANGES_REQUESTED = 'changes_requested', 'Changes Requested'
    APPROVED = 'approved', 'Approved'
    MERGED = 'merged', 'Merged'
    BLOCKED = 'blocked', 'Blocked'
    ABANDONED = 'abandoned', 'Abandoned'


class AgentRole(models.TextChoices):
    """Agent specializations for blackboard coordination."""
    PLANNER = 'planner', 'Planner'
    CODER = 'coder', 'Coder'
    REVIEWER = 'reviewer', 'Code Reviewer'


class ReviewDecision(models.TextChoices):
    """Review outcomes for agent task reviews."""
    APPROVED = 'approved', 'Approved'
    CHANGES_REQUESTED = 'changes_requested', 'Changes Requested'
    REJECTED = 'rejected', 'Rejected'


class Requirement(MP_Node):
    """A requirement parsed from a spec markdown file.

    Uses django-treebeard's materialized path implementation for
    efficient hierarchical queries (ancestors, descendants, siblings).
    """

    # Identity
    external_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique ID from spec file (e.g., REQ-AUTH-001)"
    )
    title = models.CharField(
        max_length=200,
        help_text="Short descriptive title"
    )

    # Content
    description = models.TextField(
        blank=True,
        help_text="Markdown body from spec file"
    )

    # Metadata from frontmatter
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Category tags for filtering"
    )
    priority = models.CharField(
        max_length=20,
        blank=True,
        help_text="Priority level (high, medium, low)"
    )
    status = models.CharField(
        max_length=20,
        default='draft',
        help_text="Requirement status (draft, active, deprecated)"
    )

    # Verification method (how this requirement should be verified)
    verification_method = models.CharField(
        max_length=20,
        choices=VerificationMethod.choices,
        default=VerificationMethod.UNSPECIFIED,
        db_index=True,
        help_text="How this requirement should be verified"
    )

    # Verification status (computed from test results)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNTESTED,
        db_index=True,
        help_text="Verification status based on linked test results"
    )

    # SLO status (computed from linked SLOs)
    slo_status = models.CharField(
        max_length=20,
        choices=SLOStatus.choices,
        default=SLOStatus.NOT_LINKED,
        db_index=True,
        help_text="SLO compliance status for this requirement"
    )

    # Structured fields (FRET-inspired, all optional)
    scope = models.TextField(
        blank=True,
        default="",
        help_text="When does this requirement apply? (e.g., 'when in active_session')"
    )
    condition = models.TextField(
        blank=True,
        default="",
        help_text="What triggers the behavior? (e.g., 'battery_level < 10')"
    )
    component = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="What system owns this? (e.g., 'warning_system')"
    )
    timing = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Performance constraint? (e.g., 'within 2 seconds')"
    )
    response = models.TextField(
        blank=True,
        default="",
        help_text="What must happen? (e.g., 'display battery_warning')"
    )

    # Computed metadata for structured fields
    structure_completeness = models.FloatField(
        default=0.0,
        help_text="Percentage of structured fields populated (0.0-1.0)"
    )

    # Source tracking
    source_file = models.CharField(
        max_length=500,
        help_text="Relative path to source spec file"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Dependencies (separate from parent-child hierarchy)
    depends_on = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='depended_by',
        help_text="Requirements that must be satisfied before this one"
    )

    # treebeard settings - ordering for siblings
    node_order_by = ['external_id']

    class Meta:
        verbose_name = "Requirement"
        verbose_name_plural = "Requirements"

    def __str__(self):
        return f"{self.external_id}: {self.title}"

    def calculate_structure_completeness(self) -> float:
        """Calculate the percentage of structured fields that are populated.

        Returns:
            Float between 0.0 and 1.0 representing completeness.
        """
        fields = [self.scope, self.condition, self.component, self.timing, self.response]
        populated = sum(1 for f in fields if f and f.strip())
        return populated / len(fields)

    def save(self, *args, **kwargs):
        """Update structure_completeness before saving."""
        self.structure_completeness = self.calculate_structure_completeness()
        super().save(*args, **kwargs)


class TestRun(models.Model):
    """A single pytest run that generated JUnit XML."""
    imported_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the test results were imported"
    )
    source_file = models.CharField(
        max_length=500,
        help_text="Path to JUnit XML file"
    )
    # CI metadata
    git_sha = models.CharField(
        max_length=40,
        blank=True,
        help_text="Git commit SHA for this test run"
    )
    git_branch = models.CharField(
        max_length=200,
        blank=True,
        help_text="Git branch for this test run"
    )
    ci_job_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="URL to CI job that produced this test run"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the test run started"
    )
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the test run finished"
    )

    class Meta:
        ordering = ['-imported_at']
        verbose_name = "Test Run"
        verbose_name_plural = "Test Runs"

    def __str__(self):
        return f"TestRun {self.id} ({self.source_file}) - {self.imported_at}"

    @property
    def total_tests(self) -> int:
        """Total number of test results in this run."""
        return self.results.count()

    @property
    def passed(self) -> int:
        """Number of passed tests."""
        return self.results.filter(status='passed').count()

    @property
    def failed(self) -> int:
        """Number of failed tests."""
        return self.results.filter(status='failed').count()

    @property
    def errors(self) -> int:
        """Number of tests with errors."""
        return self.results.filter(status='error').count()

    @property
    def skipped(self) -> int:
        """Number of skipped tests."""
        return self.results.filter(status='skipped').count()


class TestResult(models.Model):
    """Individual test case result from a pytest run."""

    class Status(models.TextChoices):
        PASSED = 'passed', 'Passed'
        FAILED = 'failed', 'Failed'
        ERROR = 'error', 'Error'
        SKIPPED = 'skipped', 'Skipped'

    test_run = models.ForeignKey(
        TestRun,
        on_delete=models.CASCADE,
        related_name='results'
    )
    test_nodeid = models.CharField(
        max_length=500,
        db_index=True,
        help_text="pytest nodeid (e.g., tests/test_auth.py::test_login)"
    )
    classname = models.CharField(
        max_length=300,
        blank=True,
        help_text="Test class name from JUnit XML"
    )
    name = models.CharField(
        max_length=200,
        help_text="Test function/method name"
    )
    time = models.FloatField(
        default=0.0,
        help_text="Test execution time in seconds"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        help_text="Test result status"
    )
    message = models.TextField(
        blank=True,
        help_text="Failure/error message"
    )

    # Link to requirements (populated from extract_links JSON)
    requirements = models.ManyToManyField(
        'Requirement',
        related_name='test_results',
        blank=True
    )

    class Meta:
        ordering = ['test_nodeid']
        verbose_name = "Test Result"
        verbose_name_plural = "Test Results"

    def __str__(self):
        return f"{self.test_nodeid} ({self.status})"


class InAppValidationStatus(models.TextChoices):
    """Status of an in-app validation check."""
    SUCCESS = 'success', 'Success'
    FAILURE = 'failure', 'Failure'
    UNKNOWN = 'unknown', 'Unknown'
    NOT_RUN = 'not_run', 'Not Run'


class InAppValidation(models.Model):
    """An in-app validation point that verifies a requirement.

    Represents a validation button or endpoint in the product UI that
    can be triggered to verify a requirement is working correctly.
    """
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='inapp_validations',
        help_text="The requirement this validation verifies"
    )
    name = models.CharField(
        max_length=200,
        help_text="Human-readable validation name (e.g., 'Verify Mobile Key Connection')"
    )
    endpoint = models.CharField(
        max_length=500,
        blank=True,
        help_text="API endpoint or identifier for this validation (e.g., '/api/mobile-key/verify')"
    )
    vendor = models.CharField(
        max_length=100,
        blank=True,
        help_text="Integration vendor (e.g., 'Opera', 'Mews', 'Ambiance', 'OpenKey')"
    )
    feature_flags = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feature flags active during validation (e.g., {'use_new_auth': True})"
    )

    class Meta:
        verbose_name = "In-App Validation"
        verbose_name_plural = "In-App Validations"
        ordering = ['requirement', 'name']

    def __str__(self):
        return f"{self.name} ({self.status})"

    @cached_property
    def latest_result(self):
        """Get the most recent validation result (cached per instance)."""
        return self.results.order_by('-checked_at').first()

    @property
    def status(self) -> str:
        """Current validation status from latest result."""
        result = self.latest_result
        return result.status if result else InAppValidationStatus.NOT_RUN

    @property
    def last_checked(self):
        """When this validation was last run."""
        result = self.latest_result
        return result.checked_at if result else None

    @property
    def message(self) -> str:
        """Status message from last validation run."""
        result = self.latest_result
        return result.message if result else ''
    
    def detect_regression(self) -> dict:
        """Detect if validation regressed from passing to failing.
        
        Returns:
            {
                'is_regression': bool,
                'previous_status': str,
                'current_status': str,
                'regressed_at': datetime,
            }
        """
        # Get last 2 results
        results = list(self.results.order_by('-checked_at')[:2])
        if len(results) < 2:
            return {'is_regression': False}
        
        current, previous = results[0], results[1]
        
        # Regression = was SUCCESS, now FAILURE
        is_regression = (
            previous.status == InAppValidationStatus.SUCCESS and
            current.status == InAppValidationStatus.FAILURE
        )
        
        return {
            'is_regression': is_regression,
            'previous_status': previous.status,
            'current_status': current.status,
            'regressed_at': current.checked_at if is_regression else None,
        }


def detect_validation_regressions():
    """Find all validations that recently regressed.
    
    Returns:
        List of InAppValidation objects with regression info
    """
    regressions = []
    for validation in InAppValidation.objects.all():
        regression = validation.detect_regression()
        if regression['is_regression']:
            validation._regression_info = regression  # type: ignore[attr-defined]
            regressions.append(validation)
    return regressions


class InAppValidationRun(models.Model):
    """A batch import of in-app validation results."""
    imported_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the validation results were imported"
    )
    source = models.CharField(
        max_length=500,
        help_text="Source file or system that provided the results"
    )

    class Meta:
        ordering = ['-imported_at']
        verbose_name = "In-App Validation Run"
        verbose_name_plural = "In-App Validation Runs"

    def __str__(self):
        return f"ValidationRun {self.id} ({self.source}) - {self.imported_at}"

    @property
    def total_validations(self) -> int:
        """Total number of validation results in this run."""
        return self.results.count()

    @property
    def successful(self) -> int:
        """Number of successful validations."""
        return self.results.filter(status=InAppValidationStatus.SUCCESS).count()

    @property
    def failed(self) -> int:
        """Number of failed validations."""
        return self.results.filter(status=InAppValidationStatus.FAILURE).count()

    @property
    def pass_rate(self) -> float:
        """Pass rate as a percentage (0-100)."""
        total = self.total_validations
        if total == 0:
            return 0.0
        return round((self.successful / total) * 100, 1)

    def get_results_by_vendor(self) -> dict:
        """Get validation results grouped by vendor.

        Returns:
            Dict mapping vendor names to lists of InAppValidationResult objects.
        """
        from collections import defaultdict
        results_by_vendor = defaultdict(list)

        results = self.results.select_related('validation', 'validation__requirement').order_by(
            'validation__vendor', 'validation__name'
        )

        for result in results:
            vendor = result.validation.vendor or 'Unassigned'
            results_by_vendor[vendor].append(result)

        return dict(sorted(results_by_vendor.items()))


class InAppValidationResult(models.Model):
    """Individual result from an in-app validation run."""
    validation_run = models.ForeignKey(
        InAppValidationRun,
        on_delete=models.CASCADE,
        related_name='results'
    )
    validation = models.ForeignKey(
        InAppValidation,
        on_delete=models.CASCADE,
        related_name='results'
    )
    status = models.CharField(
        max_length=20,
        choices=InAppValidationStatus.choices,
        help_text="Result status"
    )
    message = models.TextField(
        blank=True,
        help_text="Status message or error details"
    )
    checked_at = models.DateTimeField(
        help_text="When this validation was executed"
    )
    steps = models.JSONField(
        default=list,
        blank=True,
        help_text="List of validation steps with pass/fail/details"
    )
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Debugging context (hotel_id, vendor, config version, etc.)"
    )

    class Meta:
        ordering = ['-checked_at']
        verbose_name = "In-App Validation Result"
        verbose_name_plural = "In-App Validation Results"

    def __str__(self):
        return f"{self.validation.name} ({self.status}) at {self.checked_at}"

    @property
    def steps_passed(self) -> int:
        """Number of steps that passed."""
        if not self.steps:
            return 0
        return sum(1 for s in self.steps if s.get('passed', False))

    @property
    def steps_failed(self) -> int:
        """Number of steps that failed."""
        if not self.steps:
            return 0
        return sum(1 for s in self.steps if not s.get('passed', False))

    @property
    def first_failed_step(self) -> dict | None:
        """Get the first step that failed, or None if all passed."""
        if not self.steps:
            return None
        for step in self.steps:
            if not step.get('passed', False):
                return step
        return None


class VerificationFlowStatus(models.TextChoices):
    """Status of a verification flow run."""
    RUNNING = 'running', 'Running'
    PASSED = 'passed', 'Passed'
    FAILED = 'failed', 'Failed'


class VerificationFlowSource(models.TextChoices):
    """Source that triggered a verification flow run."""
    API = 'api', 'API'
    MANUAL = 'manual', 'Manual'
    SCHEDULED = 'scheduled', 'Scheduled'


class VerificationFlow(models.Model):
    """A verification flow definition synced from code.

    Flows are defined in Python code and synced to the database on startup
    for visibility. Each flow contains ordered steps that execute sequentially.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique identifier (e.g., 'linear-connection')"
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Human-readable name"
    )
    description = models.TextField(
        blank=True,
        help_text="Flow description"
    )
    steps = models.JSONField(
        default=list,
        help_text="Ordered list of step definitions"
    )
    version = models.PositiveIntegerField(
        default=1,
        help_text="Flow version number"
    )
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When last synced from code"
    )

    class Meta:
        verbose_name = "Verification Flow"
        verbose_name_plural = "Verification Flows"
        ordering = ['name']

    def __str__(self):
        return f"{self.display_name} (v{self.version})"


class VerificationFlowRun(models.Model):
    """A single execution of a verification flow.

    Tracks the overall status and context of a flow execution,
    with individual steps stored as VerificationFlowStep records.
    """
    flow = models.ForeignKey(
        VerificationFlow,
        on_delete=models.CASCADE,
        related_name='runs',
        help_text="The flow that was executed"
    )
    status = models.CharField(
        max_length=20,
        choices=VerificationFlowStatus.choices,
        default=VerificationFlowStatus.RUNNING,
        db_index=True,
        help_text="Current execution status"
    )
    context = models.JSONField(
        default=dict,
        help_text="Execution context and state"
    )
    source = models.CharField(
        max_length=20,
        choices=VerificationFlowSource.choices,
        default=VerificationFlowSource.API,
        help_text="What triggered this run"
    )
    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When execution started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When execution completed"
    )

    class Meta:
        verbose_name = "Verification Flow Run"
        verbose_name_plural = "Verification Flow Runs"
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.flow.name} run {self.id} ({self.status})"

    @property
    def duration_ms(self) -> int | None:
        """Duration of the run in milliseconds."""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None


class VerificationFlowStep(models.Model):
    """Individual step result from a flow run.

    Stores the outcome of each verification check within a flow,
    including timing, status, and debug information.
    """
    flow_run = models.ForeignKey(
        VerificationFlowRun,
        on_delete=models.CASCADE,
        related_name='steps',
        help_text="The flow run this step belongs to"
    )
    step_order = models.PositiveIntegerField(
        help_text="Order of execution (0-indexed)"
    )
    name = models.CharField(
        max_length=100,
        help_text="Step name from flow definition"
    )
    passed = models.BooleanField(
        help_text="Whether the step passed"
    )
    details = models.TextField(
        blank=True,
        help_text="Human-readable success details"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error description when step fails"
    )
    response_status = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code if applicable"
    )
    response_body = models.TextField(
        blank=True,
        help_text="Sanitized response content for debugging"
    )
    started_at = models.DateTimeField(
        help_text="When step execution started"
    )
    completed_at = models.DateTimeField(
        help_text="When step execution completed"
    )

    class Meta:
        verbose_name = "Verification Flow Step"
        verbose_name_plural = "Verification Flow Steps"
        ordering = ['flow_run', 'step_order']
        unique_together = [['flow_run', 'step_order']]

    def __str__(self):
        status = "✓" if self.passed else "✗"
        return f"{status} {self.name} (step {self.step_order})"

    @property
    def duration_ms(self) -> int | None:
        """Duration of the step in milliseconds."""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None


class TestRequirementLink(models.Model):
    """Links a test nodeid to a Requirement for traceability.

    This explicit link model tracks metadata about the test-requirement relationship,
    including the last test status, when it was last run, and whether it needs review.

    Unlike the TestResult.requirements M2M which tracks actual test runs, this tracks
    the declared link from pytest markers (e.g., @pytest.mark.linear("CAN-1234")).
    """
    test_nodeid = models.CharField(
        max_length=500,
        db_index=True,
        help_text="pytest nodeid (e.g., tests/test_auth.py::test_login)"
    )
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='test_links',
        help_text="The requirement this test verifies"
    )
    last_status = models.CharField(
        max_length=20,
        default='unknown',
        help_text="Status from last test run (passed, failed, error, skipped, unknown)"
    )
    last_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this test was last run"
    )
    needs_review = models.BooleanField(
        default=False,
        help_text="Flag for manual review needed"
    )
    review_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Reason for review (e.g., 'flaky', 'new link', 'status changed')"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Test-Requirement Link"
        verbose_name_plural = "Test-Requirement Links"
        unique_together = [('test_nodeid', 'requirement')]
        ordering = ['requirement__external_id', 'test_nodeid']

    def __str__(self):
        return f"{self.test_nodeid} → {self.requirement.external_id}"


class ConflictPattern(models.TextChoices):
    """Types of conflicts detected between requirements."""
    MUTUAL_EXCLUSION = 'mutual_exclusion', 'Mutual Exclusion'
    CODE_OVERLAP = 'code_overlap', 'Code Overlap'
    INVERSE_CORRELATION = 'inverse_correlation', 'Inverse Correlation'
    # Structured field-based conflicts
    CONDITION_OVERLAP = 'condition_overlap', 'Condition Overlap'
    TIMING_CONFLICT = 'timing_conflict', 'Timing Conflict'
    RESPONSE_CONTRADICTION = 'response_contradiction', 'Response Contradiction'


class ConflictConfidence(models.TextChoices):
    """Confidence level of detected conflicts."""
    HIGH = 'high', 'High'
    MEDIUM = 'medium', 'Medium'
    LOW = 'low', 'Low'


class ConflictLog(models.Model):
    """Logged conflicts between requirements for review.

    Stores detected patterns where requirements may be in conflict,
    such as mutual exclusion (tests for both never pass together).
    """
    requirement_a = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='conflicts_as_a',
        help_text="First requirement in the conflict"
    )
    requirement_b = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='conflicts_as_b',
        help_text="Second requirement in the conflict"
    )
    pattern = models.CharField(
        max_length=50,
        choices=ConflictPattern.choices,
        help_text="Type of conflict pattern detected"
    )
    confidence = models.CharField(
        max_length=20,
        choices=ConflictConfidence.choices,
        help_text="Confidence level of the detection"
    )
    details = models.JSONField(
        default=dict,
        help_text="Additional details about the conflict (runs analyzed, test results, etc.)"
    )
    resolved = models.BooleanField(
        default=False,
        help_text="Whether this conflict has been reviewed and resolved"
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the conflict was marked as resolved"
    )
    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes on how the conflict was resolved"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conflict Log"
        verbose_name_plural = "Conflict Logs"
        ordering = ['-created_at']

    def __str__(self):
        status = "✓ Resolved" if self.resolved else "⚠ Active"
        return f"{self.requirement_a.external_id} ↔ {self.requirement_b.external_id} ({self.pattern}) {status}"


class SLO(models.Model):
    """Service Level Objective linked to requirements.

    Imported from OpenSLO YAML files. Tracks SLO status from
    observability platforms.
    """
    # Identity
    name = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text="OpenSLO metadata.name (unique identifier)"
    )
    display_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Human-readable display name"
    )
    description = models.TextField(
        blank=True,
        help_text="SLO description"
    )

    # Link to requirements
    requirements = models.ManyToManyField(
        Requirement,
        related_name='slos',
        blank=True,
        help_text="Requirements this SLO helps verify"
    )

    # OpenSLO spec fields
    service = models.CharField(
        max_length=200,
        blank=True,
        help_text="Service name from OpenSLO spec"
    )
    target = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Target SLO percentage (e.g., 0.999 for 99.9%)"
    )
    time_window = models.CharField(
        max_length=50,
        blank=True,
        help_text="Time window for SLO (e.g., '30d', '7d')"
    )
    budgeting_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="Budgeting method (occurrences, timeslices)"
    )

    # Status from observability platform
    status = models.CharField(
        max_length=20,
        choices=SLOStatus.choices,
        default=SLOStatus.NOT_LINKED,
        db_index=True,
        help_text="Current SLO compliance status"
    )
    current_value = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Current SLO value from observability platform"
    )
    error_budget_remaining = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Remaining error budget as decimal (e.g., 0.5 = 50%)"
    )
    last_updated = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When status was last updated from observability platform"
    )

    # Source tracking
    source_file = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to OpenSLO YAML source file"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SLO"
        verbose_name_plural = "SLOs"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.status})"


# =============================================================================
# Agent Coordination Models (Blackboard Architecture)
# =============================================================================


class AgentSprint(models.Model):
    """A batch of related tasks for agent coordination.

    Similar to InAppValidationRun, this groups tasks into a sprint
    with a goal and tracks overall progress.
    """

    name = models.CharField(
        max_length=200,
        help_text="Sprint name (e.g., 'Auth Flow v2')"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional additional description"
    )
    goal_description = models.TextField(
        help_text="What this sprint should accomplish"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether new tasks can be added to this sprint"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the sprint was marked complete"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agent Sprint"
        verbose_name_plural = "Agent Sprints"
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def task_count(self) -> int:
        """Total number of tasks in this sprint."""
        return self.tasks.count()

    @property
    def progress(self) -> dict:
        """Get sprint progress stats."""
        tasks = self.tasks.all()
        total = tasks.count()
        if total == 0:
            return {
                'total': 0,
                'merged': 0,
                'in_progress': 0,
                'pending': 0,
                'percent_complete': 0.0,
            }

        merged = tasks.filter(status=AgentTaskStatus.MERGED).count()
        in_progress = tasks.filter(
            status__in=[
                AgentTaskStatus.CLAIMED,
                AgentTaskStatus.IN_PROGRESS,
                AgentTaskStatus.READY_FOR_REVIEW,
            ]
        ).count()
        return {
            'total': total,
            'merged': merged,
            'in_progress': in_progress,
            'pending': total - merged - in_progress,
            'percent_complete': round((merged / total) * 100, 1),
        }


class Agent(models.Model):
    """A registered agent that can interact with the blackboard.

    Agents have roles (Planner, Coder, Reviewer) that determine
    which actions they can perform.
    """

    agent_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique agent identifier (e.g., 'coder-1', 'reviewer-opus')"
    )
    role = models.CharField(
        max_length=20,
        choices=AgentRole.choices,
        db_index=True,
        help_text="Agent specialization determining allowed actions"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether agent is active and can claim tasks"
    )
    last_heartbeat = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When agent last reported being alive"
    )

    # Configuration
    config = models.JSONField(
        default=dict,
        help_text="Agent-specific configuration (model, temperature, etc.)"
    )

    # Timestamps
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agents"

    def __str__(self):
        return f"{self.agent_id} ({self.role})"

    def can_claim_tasks(self) -> bool:
        """Only coders can claim tasks."""
        return self.role == AgentRole.CODER

    def can_review_tasks(self) -> bool:
        """Only reviewers can approve/reject."""
        return self.role == AgentRole.REVIEWER

    def can_create_tasks(self) -> bool:
        """Only planners can create tasks."""
        return self.role == AgentRole.PLANNER

    @property
    def current_task(self):
        """Get the agent's currently claimed task, if any."""
        return self.claimed_tasks.filter(
            status__in=[
                AgentTaskStatus.CLAIMED,
                AgentTaskStatus.IN_PROGRESS,
            ]
        ).first()


class AgentTask(models.Model):
    """A unit of work on the blackboard.

    Tasks move through a state machine from DRAFT to MERGED.
    Each task links to requirements and has falsifiable done_when criteria.
    """

    # Identity
    external_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Task ID (e.g., 'task-auth-login-001')"
    )
    title = models.CharField(
        max_length=200,
        help_text="Short descriptive title"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed task description"
    )

    # Link to requirements
    requirements = models.ManyToManyField(
        Requirement,
        related_name='agent_tasks',
        blank=True,
        help_text="Requirements this task implements"
    )

    # State machine
    status = models.CharField(
        max_length=20,
        choices=AgentTaskStatus.choices,
        default=AgentTaskStatus.DRAFT,
        db_index=True,
        help_text="Current task state"
    )

    # Claiming
    claimed_by = models.ForeignKey(
        Agent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='claimed_tasks',
        help_text="Agent that claimed this task"
    )
    claimed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the task was claimed"
    )
    lease_expires = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Task returns to UNCLAIMED if lease expires"
    )

    # Falsifiable completion criteria
    done_when = models.JSONField(
        default=list,
        help_text="List of falsifiable criteria (e.g., 'pytest tests/test_auth.py exits 0')"
    )

    # Scope boundaries
    scope_in = models.JSONField(
        default=list,
        help_text="What IS in scope for this task"
    )
    scope_out = models.JSONField(
        default=list,
        help_text="What is NOT in scope (explicit exclusions)"
    )

    # Spec reference
    spec_ref = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to spec file (e.g., 'specs/auth.md')"
    )

    # Git integration
    worktree_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path to git worktree (e.g., '.worktrees/task-auth-001')"
    )
    branch_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Git branch for this task"
    )
    commit_sha = models.CharField(
        max_length=40,
        blank=True,
        help_text="Latest commit SHA submitted for review"
    )

    # Dependencies
    depends_on = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='blocks',
        help_text="Tasks that must complete before this one"
    )

    # Sprint grouping
    sprint = models.ForeignKey(
        AgentSprint,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='tasks',
        help_text="Sprint this task belongs to"
    )

    # Retry tracking (hypothesis exhaustion)
    attempt_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this task has been attempted"
    )
    max_attempts = models.PositiveIntegerField(
        default=2,
        help_text="After this many failures by different coders, task is presumed wrong"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Agent Task"
        verbose_name_plural = "Agent Tasks"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.external_id}: {self.title}"

    def is_claimable(self) -> bool:
        """Check if task can be claimed."""
        if self.status != AgentTaskStatus.UNCLAIMED:
            return False
        # Check dependencies
        for dep in self.depends_on.all():
            if dep.status != AgentTaskStatus.MERGED:
                return False
        return True

    def can_transition_to(self, new_status: str) -> bool:
        """Validate state transition."""
        allowed = AGENT_TASK_STATE_TRANSITIONS.get(self.status, [])
        return new_status in allowed


# State machine transitions for AgentTask
AGENT_TASK_STATE_TRANSITIONS = {
    AgentTaskStatus.DRAFT: [AgentTaskStatus.UNCLAIMED, AgentTaskStatus.ABANDONED],
    AgentTaskStatus.UNCLAIMED: [AgentTaskStatus.CLAIMED, AgentTaskStatus.BLOCKED],
    AgentTaskStatus.CLAIMED: [AgentTaskStatus.IN_PROGRESS, AgentTaskStatus.UNCLAIMED],
    AgentTaskStatus.IN_PROGRESS: [AgentTaskStatus.READY_FOR_REVIEW, AgentTaskStatus.BLOCKED],
    AgentTaskStatus.READY_FOR_REVIEW: [AgentTaskStatus.APPROVED, AgentTaskStatus.CHANGES_REQUESTED],
    AgentTaskStatus.CHANGES_REQUESTED: [AgentTaskStatus.READY_FOR_REVIEW, AgentTaskStatus.ABANDONED],
    AgentTaskStatus.APPROVED: [AgentTaskStatus.MERGED],
    AgentTaskStatus.BLOCKED: [AgentTaskStatus.UNCLAIMED, AgentTaskStatus.ABANDONED],
    AgentTaskStatus.MERGED: [],  # Terminal
    AgentTaskStatus.ABANDONED: [],  # Terminal
}


class AgentTaskHistory(models.Model):
    """Audit trail for task state changes.

    Every action on a task is logged with the agent, action,
    state transition, and additional details.
    """

    task = models.ForeignKey(
        AgentTask,
        on_delete=models.CASCADE,
        related_name='history',
        help_text="The task this history entry belongs to"
    )
    agent = models.ForeignKey(
        Agent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_history',
        help_text="Agent that performed the action (null for system actions)"
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this action occurred"
    )

    # What happened
    action = models.CharField(
        max_length=50,
        help_text="Action taken (e.g., 'CLAIMED', 'SUBMITTED_FOR_REVIEW', 'APPROVED')"
    )
    from_status = models.CharField(
        max_length=20,
        blank=True,
        help_text="Status before transition"
    )
    to_status = models.CharField(
        max_length=20,
        blank=True,
        help_text="Status after transition"
    )

    # Additional context
    details = models.JSONField(
        default=dict,
        help_text="Additional context (commit SHA, review feedback, etc.)"
    )

    class Meta:
        verbose_name = "Agent Task History"
        verbose_name_plural = "Agent Task History"
        ordering = ['-timestamp']

    def __str__(self):
        agent_str = self.agent.agent_id if self.agent else 'system'
        return f"{self.task.external_id}: {self.action} by {agent_str}"


class AgentTaskReview(models.Model):
    """A review of submitted work.

    Captures the reviewer's decision, done_when verification results,
    and structured feedback.
    """

    task = models.ForeignKey(
        AgentTask,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="The task being reviewed"
    )
    reviewer = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reviews_given',
        help_text="Agent that performed the review"
    )

    # Review details
    decision = models.CharField(
        max_length=20,
        choices=ReviewDecision.choices,
        help_text="Review outcome"
    )
    commit_sha = models.CharField(
        max_length=40,
        help_text="The commit SHA that was reviewed"
    )

    # Criteria verification
    done_when_results = models.JSONField(
        default=list,
        help_text="Pass/fail for each done_when criterion"
    )

    # Feedback
    feedback = models.TextField(
        blank=True,
        help_text="Detailed review feedback"
    )
    blocking_issues = models.JSONField(
        default=list,
        help_text="Issues that must be fixed"
    )
    suggestions = models.JSONField(
        default=list,
        help_text="Non-blocking suggestions"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agent Task Review"
        verbose_name_plural = "Agent Task Reviews"
        ordering = ['-created_at']

    def __str__(self):
        return f"Review of {self.task.external_id}: {self.decision}"

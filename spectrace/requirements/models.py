"""Requirement model for storing parsed spec requirements."""
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

    # Source tracking
    source_file = models.CharField(
        max_length=500,
        help_text="Relative path to source spec file"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # treebeard settings - ordering for siblings
    node_order_by = ['external_id']

    class Meta:
        verbose_name = "Requirement"
        verbose_name_plural = "Requirements"

    def __str__(self):
        return f"{self.external_id}: {self.title}"


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

    class Meta:
        verbose_name = "In-App Validation"
        verbose_name_plural = "In-App Validations"
        ordering = ['requirement', 'name']

    def __str__(self):
        return f"{self.name} ({self.status})"

    @property
    def latest_result(self):
        """Get the most recent validation result."""
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

    class Meta:
        ordering = ['-checked_at']
        verbose_name = "In-App Validation Result"
        verbose_name_plural = "In-App Validation Results"

    def __str__(self):
        return f"{self.validation.name} ({self.status}) at {self.checked_at}"


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

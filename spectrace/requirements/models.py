"""Requirement model for storing parsed spec requirements."""
from django.db import models
from treebeard.mp_tree import MP_Node


class VerificationStatus(models.TextChoices):
    """Verification status for requirements based on linked test results."""
    PASSING = 'passing', 'Passing'
    FAILING = 'failing', 'Failing'
    UNTESTED = 'untested', 'Untested'


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

    # Verification status (computed from test results)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNTESTED,
        db_index=True,
        help_text="Verification status based on linked test results"
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
    total_tests = models.IntegerField(default=0)
    passed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)

    class Meta:
        ordering = ['-imported_at']
        verbose_name = "Test Run"
        verbose_name_plural = "Test Runs"

    def __str__(self):
        return f"TestRun {self.id} ({self.source_file}) - {self.imported_at}"


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

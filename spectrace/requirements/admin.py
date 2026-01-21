"""Admin configuration for Requirement, TestRun, and TestResult models."""
from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Requirement, TestRun, TestResult


@admin.register(Requirement)
class RequirementAdmin(ModelAdmin):
    """Admin interface for Requirement with unfold styling."""

    list_display = ['external_id', 'title', 'verification_status', 'priority', 'status', 'updated_at']
    list_filter = ['verification_status', 'status', 'priority']
    search_fields = ['external_id', 'title', 'description']
    readonly_fields = ['verification_status', 'created_at', 'updated_at']


@admin.register(TestRun)
class TestRunAdmin(ModelAdmin):
    """Admin interface for TestRun."""

    list_display = ['source_file', 'imported_at', 'total_tests', 'passed', 'failed', 'errors', 'skipped']
    readonly_fields = ['imported_at']
    ordering = ['-imported_at']


@admin.register(TestResult)
class TestResultAdmin(ModelAdmin):
    """Admin interface for TestResult."""

    list_display = ['test_nodeid', 'status', 'test_run', 'time']
    list_filter = ['status', 'test_run']
    search_fields = ['test_nodeid', 'name', 'classname']

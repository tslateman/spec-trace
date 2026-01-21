"""Admin configuration for Requirement, TestRun, and TestResult models."""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import Requirement, TestRun, TestResult


STATUS_BADGE_COLORS = {
    'passed': '#22c55e',
    'failed': '#ef4444',
    'error': '#f97316',
    'skipped': '#6b7280',
    'passing': '#22c55e',
    'failing': '#ef4444',
    'untested': '#6b7280',
}


@admin.register(Requirement)
class RequirementAdmin(ModelAdmin):
    """Admin interface for Requirement with unfold styling."""

    list_display = ['external_id', 'title', 'verification_status', 'priority', 'status', 'updated_at']
    list_filter = ['verification_status', 'status', 'priority']
    search_fields = ['external_id', 'title', 'description']
    readonly_fields = ['verification_status', 'created_at', 'updated_at', 'linked_tests']

    def linked_tests(self, obj):
        """Display linked test results with status badges and clickable links."""
        tests = obj.test_results.select_related('test_run').order_by('-test_run__imported_at')
        if not tests.exists():
            return format_html('<span style="color: #6b7280;">No linked tests</span>')

        links = []
        for test in tests:
            url = reverse('admin:requirements_testresult_change', args=[test.pk])
            color = STATUS_BADGE_COLORS.get(test.status, '#6b7280')
            links.append(format_html(
                '<div style="margin-bottom: 4px;">'
                '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
                'font-size: 11px; font-weight: 500; color: white; background-color: {}; '
                'margin-right: 8px;">{}</span>'
                '<a href="{}">{}</a>'
                '</div>',
                color, test.status.upper(), url, test.test_nodeid
            ))
        return format_html(''.join(str(link) for link in links))

    linked_tests.short_description = "Linked Tests"


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
    readonly_fields = ['linked_requirements']

    def linked_requirements(self, obj):
        """Display linked requirements with verification status badges and clickable links."""
        requirements = obj.requirements.all().order_by('external_id')
        if not requirements.exists():
            return format_html('<span style="color: #6b7280;">No linked requirements</span>')

        links = []
        for req in requirements:
            url = reverse('admin:requirements_requirement_change', args=[req.pk])
            color = STATUS_BADGE_COLORS.get(req.verification_status, '#6b7280')
            links.append(format_html(
                '<div style="margin-bottom: 4px;">'
                '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
                'font-size: 11px; font-weight: 500; color: white; background-color: {}; '
                'margin-right: 8px;">{}</span>'
                '<a href="{}">{}: {}</a>'
                '</div>',
                color, req.verification_status.upper(), url, req.external_id, req.title
            ))
        return format_html(''.join(str(link) for link in links))

    linked_requirements.short_description = "Linked Requirements"

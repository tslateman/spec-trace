"""Admin configuration for Requirement, TestRun, and TestResult models."""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import (
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    Requirement,
    SLO,
    TestResult,
    TestRun,
)


STATUS_BADGE_COLORS = {
    'passed': '#22c55e',
    'failed': '#ef4444',
    'error': '#f97316',
    'skipped': '#6b7280',
    'passing': '#22c55e',
    'failing': '#ef4444',
    'untested': '#6b7280',
}


SLO_STATUS_BADGE_COLORS = {
    'met': '#22c55e',
    'at_risk': '#f97316',
    'breached': '#ef4444',
    'not_linked': '#6b7280',
}


@admin.register(Requirement)
class RequirementAdmin(ModelAdmin):
    """Admin interface for Requirement with unfold styling."""

    list_display = [
        'external_id', 'title', 'verification_method', 'verification_status',
        'slo_status', 'priority', 'status', 'updated_at'
    ]
    list_filter = ['verification_status', 'verification_method', 'slo_status', 'status', 'priority']
    search_fields = ['external_id', 'title', 'description']
    readonly_fields = [
        'verification_status', 'slo_status', 'created_at', 'updated_at',
        'linked_tests', 'linked_slos', 'linked_inapp_validations'
    ]

    fieldsets = (
        (None, {
            'fields': ('external_id', 'title', 'description')
        }),
        ('Metadata', {
            'fields': ('tags', 'priority', 'status', 'verification_method', 'source_file')
        }),
        ('Verification Status', {
            'fields': ('verification_status', 'slo_status', 'linked_tests', 'linked_inapp_validations', 'linked_slos')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

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

    def linked_slos(self, obj):
        """Display linked SLOs with status badges and clickable links."""
        slos = obj.slos.all().order_by('name')
        if not slos.exists():
            return format_html('<span style="color: #6b7280;">No linked SLOs</span>')

        links = []
        for slo in slos:
            url = reverse('admin:requirements_slo_change', args=[slo.pk])
            color = SLO_STATUS_BADGE_COLORS.get(slo.status, '#6b7280')
            target_str = f"{float(slo.target) * 100:.2f}%" if slo.target else 'N/A'
            links.append(format_html(
                '<div style="margin-bottom: 4px;">'
                '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
                'font-size: 11px; font-weight: 500; color: white; background-color: {}; '
                'margin-right: 8px;">{}</span>'
                '<a href="{}">{}</a> (target: {})'
                '</div>',
                color, slo.status.upper(), url, slo.display_name or slo.name, target_str
            ))
        return format_html(''.join(str(link) for link in links))

    linked_slos.short_description = "Linked SLOs"

    def linked_inapp_validations(self, obj):
        """Display linked in-app validations with status badges."""
        validations = obj.inapp_validations.all().order_by('name')
        if not validations.exists():
            return format_html('<span style="color: #6b7280;">No in-app validations</span>')

        links = []
        for val in validations:
            url = reverse('admin:requirements_inappvalidation_change', args=[val.pk])
            color = INAPP_STATUS_COLORS.get(val.status, '#6b7280')
            links.append(format_html(
                '<div style="margin-bottom: 4px;">'
                '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
                'font-size: 11px; font-weight: 500; color: white; background-color: {}; '
                'margin-right: 8px;">{}</span>'
                '<a href="{}">{}</a>'
                '</div>',
                color, val.status.upper(), url, val.name
            ))
        return format_html(''.join(str(link) for link in links))

    linked_inapp_validations.short_description = "In-App Validations"


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


# In-App Validation Admin

INAPP_STATUS_COLORS = {
    'success': '#22c55e',
    'failure': '#ef4444',
    'unknown': '#6b7280',
    'not_run': '#6b7280',
}


@admin.register(InAppValidation)
class InAppValidationAdmin(ModelAdmin):
    """Admin interface for InAppValidation."""

    list_display = ['name', 'requirement', 'status', 'endpoint', 'last_checked']
    list_filter = ['status']
    search_fields = ['name', 'endpoint', 'requirement__external_id']
    readonly_fields = ['last_checked']


@admin.register(InAppValidationRun)
class InAppValidationRunAdmin(ModelAdmin):
    """Admin interface for InAppValidationRun."""

    list_display = ['source', 'imported_at', 'total_validations', 'successful', 'failed']
    readonly_fields = ['imported_at']
    ordering = ['-imported_at']


@admin.register(InAppValidationResult)
class InAppValidationResultAdmin(ModelAdmin):
    """Admin interface for InAppValidationResult."""

    list_display = ['validation', 'status', 'validation_run', 'checked_at']
    list_filter = ['status', 'validation_run']
    search_fields = ['validation__name', 'message']


# SLO Admin

SLO_STATUS_COLORS = {
    'met': '#22c55e',
    'at_risk': '#f97316',
    'breached': '#ef4444',
    'not_linked': '#6b7280',
}


@admin.register(SLO)
class SLOAdmin(ModelAdmin):
    """Admin interface for SLO."""

    list_display = ['name', 'display_name', 'status', 'target', 'current_value', 'error_budget_remaining', 'service']
    list_filter = ['status', 'service']
    search_fields = ['name', 'display_name', 'description', 'service']
    readonly_fields = ['last_updated', 'created_at', 'updated_at', 'linked_requirements_display']
    filter_horizontal = ['requirements']

    fieldsets = (
        (None, {
            'fields': ('name', 'display_name', 'description')
        }),
        ('Specification', {
            'fields': ('service', 'target', 'time_window', 'budgeting_method')
        }),
        ('Status', {
            'fields': ('status', 'current_value', 'error_budget_remaining', 'last_updated')
        }),
        ('Requirements', {
            'fields': ('requirements', 'linked_requirements_display')
        }),
        ('Source', {
            'fields': ('source_file', 'raw_yaml'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def linked_requirements_display(self, obj):
        """Display linked requirements with verification status badges."""
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

    linked_requirements_display.short_description = "Linked Requirements (Current Status)"

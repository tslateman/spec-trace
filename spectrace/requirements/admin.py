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


# Color dictionaries for status badges
STATUS_BADGE_COLORS = {
    'passed': '#22c55e',
    'failed': '#ef4444',
    'error': '#f97316',
    'skipped': '#6b7280',
    'passing': '#22c55e',
    'failing': '#ef4444',
    'untested': '#6b7280',
}

SLO_STATUS_COLORS = {
    'met': '#22c55e',
    'at_risk': '#f97316',
    'breached': '#ef4444',
    'not_linked': '#6b7280',
}

INAPP_STATUS_COLORS = {
    'success': '#22c55e',
    'failure': '#ef4444',
    'unknown': '#6b7280',
    'not_run': '#6b7280',
}


def _render_badge_link(color: str, status: str, url: str, label: str, suffix: str = '') -> str:
    """Render a single badge with link for admin displays."""
    return format_html(
        '<div style="margin-bottom: 4px;">'
        '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
        'font-size: 11px; font-weight: 500; color: white; background-color: {}; '
        'margin-right: 8px;">{}</span>'
        '<a href="{}">{}</a>{}'
        '</div>',
        color, status.upper(), url, label, suffix
    )


def _render_badge_list(items, color_dict, get_status, get_url, get_label, empty_message, get_suffix=None):
    """Render a list of items as badge links."""
    if not items.exists():
        return format_html('<span style="color: #6b7280;">{}</span>', empty_message)

    links = []
    for item in items:
        status = get_status(item)
        color = color_dict.get(status, '#6b7280')
        url = get_url(item)
        label = get_label(item)
        suffix = get_suffix(item) if get_suffix else ''
        links.append(_render_badge_link(color, status, url, label, suffix))
    return format_html(''.join(str(link) for link in links))


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
        return _render_badge_list(
            tests, STATUS_BADGE_COLORS,
            get_status=lambda t: t.status,
            get_url=lambda t: reverse('admin:requirements_testresult_change', args=[t.pk]),
            get_label=lambda t: t.test_nodeid,
            empty_message='No linked tests'
        )

    linked_tests.short_description = "Linked Tests"

    def linked_slos(self, obj):
        """Display linked SLOs with status badges and clickable links."""
        slos = obj.slos.all().order_by('name')
        return _render_badge_list(
            slos, SLO_STATUS_COLORS,
            get_status=lambda s: s.status,
            get_url=lambda s: reverse('admin:requirements_slo_change', args=[s.pk]),
            get_label=lambda s: s.display_name or s.name,
            empty_message='No linked SLOs',
            get_suffix=lambda s: f" (target: {float(s.target) * 100:.2f}%)" if s.target else " (target: N/A)"
        )

    linked_slos.short_description = "Linked SLOs"

    def linked_inapp_validations(self, obj):
        """Display linked in-app validations with status badges."""
        validations = obj.inapp_validations.all().order_by('name')
        return _render_badge_list(
            validations, INAPP_STATUS_COLORS,
            get_status=lambda v: v.status,
            get_url=lambda v: reverse('admin:requirements_inappvalidation_change', args=[v.pk]),
            get_label=lambda v: v.name,
            empty_message='No in-app validations'
        )

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
        return _render_badge_list(
            requirements, STATUS_BADGE_COLORS,
            get_status=lambda r: r.verification_status,
            get_url=lambda r: reverse('admin:requirements_requirement_change', args=[r.pk]),
            get_label=lambda r: f"{r.external_id}: {r.title}",
            empty_message='No linked requirements'
        )

    linked_requirements.short_description = "Linked Requirements"


@admin.register(InAppValidation)
class InAppValidationAdmin(ModelAdmin):
    """Admin interface for InAppValidation."""

    list_display = ['name', 'requirement', 'vendor', 'status', 'endpoint', 'last_checked']
    list_filter = ['vendor', 'requirement']
    search_fields = ['name', 'endpoint', 'vendor', 'requirement__external_id']
    readonly_fields = ['status', 'last_checked', 'message']


@admin.register(InAppValidationRun)
class InAppValidationRunAdmin(ModelAdmin):
    """Admin interface for InAppValidationRun."""

    list_display = ['source', 'imported_at', 'total_validations', 'successful', 'failed']
    readonly_fields = ['imported_at']
    ordering = ['-imported_at']


@admin.register(InAppValidationResult)
class InAppValidationResultAdmin(ModelAdmin):
    """Admin interface for InAppValidationResult."""

    list_display = ['validation', 'status', 'validation_run', 'checked_at', 'step_summary']
    list_filter = ['status', 'validation_run']
    search_fields = ['validation__name', 'message']
    readonly_fields = ['steps_display', 'context_display']
    
    def step_summary(self, obj):
        """Show step pass/fail counts."""
        if not obj.steps:
            return "—"
        passed = sum(1 for s in obj.steps if s.get('passed'))
        total = len(obj.steps)
        return f"{passed}/{total} passed"
    step_summary.short_description = 'Steps'  # type: ignore[attr-defined]
    
    def steps_display(self, obj):
        """Pretty-print steps JSON."""
        import json
        if not obj.steps:
            return "No steps"
        return format_html('<pre style="max-width: 600px; overflow-x: auto;">{}</pre>', 
                          json.dumps(obj.steps, indent=2))
    steps_display.short_description = 'Steps Detail'  # type: ignore[attr-defined]
    
    def context_display(self, obj):
        """Pretty-print context JSON."""
        import json
        if not obj.context:
            return "No context"
        return format_html('<pre style="max-width: 600px; overflow-x: auto;">{}</pre>', 
                          json.dumps(obj.context, indent=2))
    context_display.short_description = 'Context Detail'  # type: ignore[attr-defined]


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
            'fields': ('source_file',),
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
        return _render_badge_list(
            requirements, STATUS_BADGE_COLORS,
            get_status=lambda r: r.verification_status,
            get_url=lambda r: reverse('admin:requirements_requirement_change', args=[r.pk]),
            get_label=lambda r: f"{r.external_id}: {r.title}",
            empty_message='No linked requirements'
        )

    linked_requirements_display.short_description = "Linked Requirements (Current Status)"

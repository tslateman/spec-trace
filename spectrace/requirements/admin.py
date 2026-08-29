"""Admin configuration for Requirement, TestRun, and TestResult models."""

import json

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    SLO,
    Agent,
    AgentSprint,
    AgentTask,
    AgentTaskHistory,
    AgentTaskReview,
    ConflictLog,
    CorpusEntry,
    CorpusEntryVersion,
    CorpusSnapshot,
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    Requirement,
    ReviewCoverage,
    ReviewFinding,
    SpecReview,
    TestRequirementLink,
    TestResult,
    TestRun,
    VerificationFlow,
)

# Color dictionaries for status badges
STATUS_BADGE_COLORS = {
    "passed": "#22c55e",
    "failed": "#ef4444",
    "error": "#f97316",
    "skipped": "#6b7280",
    "passing": "#22c55e",
    "failing": "#ef4444",
    "untested": "#6b7280",
}

SLO_STATUS_COLORS = {
    "met": "#22c55e",
    "at_risk": "#f97316",
    "breached": "#ef4444",
    "not_linked": "#6b7280",
}

INAPP_STATUS_COLORS = {
    "success": "#22c55e",
    "failure": "#ef4444",
    "unknown": "#6b7280",
    "not_run": "#6b7280",
}

# Completeness score colors (gradient from red to green)
COMPLETENESS_COLORS = {
    "none": "#ef4444",  # 0%
    "low": "#f97316",  # 1-40%
    "medium": "#eab308",  # 41-80%
    "high": "#22c55e",  # 81-100%
}


class StructureCompletenessFilter(admin.SimpleListFilter):
    """Filter requirements by structure completeness level."""

    title = "structure completeness"
    parameter_name = "completeness"

    def lookups(self, request, model_admin):
        return [
            ("none", "None (0%)"),
            ("low", "Low (1-40%)"),
            ("medium", "Medium (41-80%)"),
            ("high", "High (81-100%)"),
            ("needs_structure", "Needs Structure (<80%)"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "none":
            return queryset.filter(structure_completeness=0)
        elif self.value() == "low":
            return queryset.filter(structure_completeness__gt=0, structure_completeness__lte=0.4)
        elif self.value() == "medium":
            return queryset.filter(structure_completeness__gt=0.4, structure_completeness__lte=0.8)
        elif self.value() == "high":
            return queryset.filter(structure_completeness__gt=0.8)
        elif self.value() == "needs_structure":
            return queryset.filter(structure_completeness__lt=0.8)
        return queryset


def _render_badge_link(color: str, status: str, url: str, label: str, suffix: str = "") -> str:
    """Render a single badge with link for admin displays."""
    return format_html(
        '<div style="margin-bottom: 4px;">'
        '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
        "font-size: 11px; font-weight: 500; color: white; background-color: {}; "
        'margin-right: 8px;">{}</span>'
        '<a href="{}">{}</a>{}'
        "</div>",
        color,
        status.upper(),
        url,
        label,
        suffix,
    )


def _render_badge_list(
    items, color_dict, get_status, get_url, get_label, empty_message, get_suffix=None
):
    """Render a list of items as badge links."""
    if not items.exists():
        return format_html('<span style="color: #6b7280;">{}</span>', empty_message)

    links = []
    for item in items:
        status = get_status(item)
        color = color_dict.get(status, "#6b7280")
        url = get_url(item)
        label = get_label(item)
        suffix = get_suffix(item) if get_suffix else ""
        links.append(_render_badge_link(color, status, url, label, suffix))
    return format_html("".join(str(link) for link in links))


@admin.register(Requirement)
class RequirementAdmin(ModelAdmin):
    """Admin interface for Requirement with unfold styling."""

    list_display = [
        "external_id",
        "title",
        "verification_method",
        "verification_status",
        "slo_status",
        "priority",
        "status",
        "completeness_badge",
        "component",
        "updated_at",
    ]
    list_filter = [
        "verification_status",
        "verification_method",
        "slo_status",
        "status",
        "priority",
        "component",
        StructureCompletenessFilter,
    ]
    search_fields = [
        "external_id",
        "title",
        "description",
        "component",
        "condition",
        "response",
    ]
    readonly_fields = [
        "verification_status",
        "slo_status",
        "created_at",
        "updated_at",
        "linked_tests",
        "linked_slos",
        "linked_inapp_validations",
        "linked_flows",
        "structure_completeness",
        "completeness_badge",
        "linked_dependencies",
        "linked_depended_by",
    ]
    filter_horizontal = ["depends_on"]

    fieldsets = (
        (None, {"fields": ("external_id", "title", "description")}),
        (
            "Metadata",
            {
                "fields": (
                    "tags",
                    "priority",
                    "status",
                    "verification_method",
                    "source_file",
                )
            },
        ),
        (
            "Structured Fields (FRET-inspired)",
            {
                "fields": (
                    "scope",
                    "condition",
                    "component",
                    "timing",
                    "response",
                    "structure_completeness",
                ),
                "description": "Optional structured fields for formal requirement specification. "
                "Scope: when does this apply? Condition: what triggers it? "
                "Component: what system owns it? Timing: performance constraint? "
                "Response: what must happen?",
            },
        ),
        (
            "Verification Status",
            {
                "fields": (
                    "verification_status",
                    "slo_status",
                    "linked_tests",
                    "linked_inapp_validations",
                    "linked_slos",
                    "linked_flows",
                )
            },
        ),
        (
            "Dependencies",
            {
                "fields": ("depends_on", "linked_dependencies", "linked_depended_by"),
                "description": "Requirements that must be satisfied before this one (depends_on) "
                "and requirements that depend on this one (depended_by).",
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def completeness_badge(self, obj):
        """Display structure completeness as a colored badge."""
        score = obj.structure_completeness
        pct = int(score * 100)

        if score == 0:
            color = COMPLETENESS_COLORS["none"]
            label = "None"
        elif score <= 0.4:
            color = COMPLETENESS_COLORS["low"]
            label = f"{pct}%"
        elif score <= 0.8:
            color = COMPLETENESS_COLORS["medium"]
            label = f"{pct}%"
        else:
            color = COMPLETENESS_COLORS["high"]
            label = f"{pct}%"

        return format_html(
            '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
            'font-size: 11px; font-weight: 500; color: white; background-color: {};">{}</span>',
            color,
            label,
        )

    completeness_badge.short_description = "Structure"

    def linked_tests(self, obj):
        """Display linked test results with status badges and clickable links."""
        tests = obj.test_results.select_related("test_run").order_by("-test_run__imported_at")
        return _render_badge_list(
            tests,
            STATUS_BADGE_COLORS,
            get_status=lambda t: t.status,
            get_url=lambda t: reverse("admin:requirements_testresult_change", args=[t.pk]),
            get_label=lambda t: t.test_nodeid,
            empty_message="No linked tests",
        )

    linked_tests.short_description = "Linked Tests"

    def linked_slos(self, obj):
        """Display linked SLOs with status badges and clickable links."""
        slos = obj.slos.all().order_by("name")
        return _render_badge_list(
            slos,
            SLO_STATUS_COLORS,
            get_status=lambda s: s.status,
            get_url=lambda s: reverse("admin:requirements_slo_change", args=[s.pk]),
            get_label=lambda s: s.display_name or s.name,
            empty_message="No linked SLOs",
            get_suffix=lambda s: (
                f" (target: {float(s.target) * 100:.2f}%)" if s.target else " (target: N/A)"
            ),
        )

    linked_slos.short_description = "Linked SLOs"

    def linked_inapp_validations(self, obj):
        """Display linked in-app validations with status badges."""
        validations = obj.inapp_validations.all().order_by("name")
        return _render_badge_list(
            validations,
            INAPP_STATUS_COLORS,
            get_status=lambda v: v.status,
            get_url=lambda v: reverse("admin:requirements_inappvalidation_change", args=[v.pk]),
            get_label=lambda v: v.name,
            empty_message="No in-app validations",
        )

    linked_inapp_validations.short_description = "In-App Validations"

    def linked_dependencies(self, obj):
        """Display requirements this one depends on with verification status badges."""
        dependencies = obj.depends_on.all().order_by("external_id")
        return _render_badge_list(
            dependencies,
            STATUS_BADGE_COLORS,
            get_status=lambda r: r.verification_status,
            get_url=lambda r: reverse("admin:requirements_requirement_change", args=[r.pk]),
            get_label=lambda r: f"{r.external_id}: {r.title}",
            empty_message="No dependencies",
        )

    linked_dependencies.short_description = "Depends On (Display)"

    def linked_depended_by(self, obj):
        """Display requirements that depend on this one with verification status badges."""
        dependents = obj.depended_by.all().order_by("external_id")
        return _render_badge_list(
            dependents,
            STATUS_BADGE_COLORS,
            get_status=lambda r: r.verification_status,
            get_url=lambda r: reverse("admin:requirements_requirement_change", args=[r.pk]),
            get_label=lambda r: f"{r.external_id}: {r.title}",
            empty_message="No dependents",
        )

    linked_depended_by.short_description = "Depended By (Display)"

    def linked_flows(self, obj):
        """Display linked verification flows."""
        flows = obj.verification_flows.all().order_by("name")
        return _render_badge_list(
            flows,
            FLOW_STATUS_COLORS,
            get_status=lambda f: "unknown",  # No run status on flow model
            get_url=lambda f: reverse("admin:requirements_verificationflow_change", args=[f.pk]),
            get_label=lambda f: f.display_name,
            empty_message="No linked flows",
        )

    linked_flows.short_description = "Linked Flows"


@admin.register(TestRun)
class TestRunAdmin(ModelAdmin):
    """Admin interface for TestRun."""

    change_list_template = "admin/requirements/testrun/change_list.html"
    list_display = [
        "source_file",
        "imported_at",
        "git_sha_short",
        "git_branch",
        "total_tests",
        "passed",
        "failed",
        "errors",
        "skipped",
    ]
    readonly_fields = ["imported_at", "started_at", "finished_at"]
    ordering = ["-imported_at"]
    search_fields = ["source_file", "git_sha", "git_branch"]
    list_filter = ["git_branch"]

    fieldsets = (
        (None, {"fields": ("source_file",)}),
        ("CI Metadata", {"fields": ("git_sha", "git_branch", "ci_job_url")}),
        (
            "Timestamps",
            {
                "fields": ("imported_at", "started_at", "finished_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def git_sha_short(self, obj):
        """Display shortened git SHA."""
        if obj.git_sha:
            return obj.git_sha[:8]
        return "—"

    git_sha_short.short_description = "Commit"  # type: ignore[attr-defined]


@admin.register(TestResult)
class TestResultAdmin(ModelAdmin):
    """Admin interface for TestResult."""

    list_display = ["test_nodeid", "status", "test_run", "time"]
    list_filter = ["status", "test_run"]
    search_fields = ["test_nodeid", "name", "classname"]
    readonly_fields = ["linked_requirements"]

    def linked_requirements(self, obj):
        """Display linked requirements with verification status badges and clickable links."""
        requirements = obj.requirements.all().order_by("external_id")
        return _render_badge_list(
            requirements,
            STATUS_BADGE_COLORS,
            get_status=lambda r: r.verification_status,
            get_url=lambda r: reverse("admin:requirements_requirement_change", args=[r.pk]),
            get_label=lambda r: f"{r.external_id}: {r.title}",
            empty_message="No linked requirements",
        )

    linked_requirements.short_description = "Linked Requirements"


@admin.register(InAppValidation)
class InAppValidationAdmin(ModelAdmin):
    """Admin interface for InAppValidation."""

    list_display = [
        "name",
        "requirement",
        "vendor",
        "status",
        "endpoint",
        "last_checked",
    ]
    list_filter = ["vendor", "requirement"]
    search_fields = ["name", "endpoint", "vendor", "requirement__external_id"]
    readonly_fields = ["status", "last_checked", "message"]


@admin.register(InAppValidationRun)
class InAppValidationRunAdmin(ModelAdmin):
    """Admin interface for InAppValidationRun."""

    list_display = [
        "source",
        "imported_at",
        "total_validations",
        "successful",
        "failed",
    ]
    readonly_fields = ["imported_at"]
    ordering = ["-imported_at"]


@admin.register(InAppValidationResult)
class InAppValidationResultAdmin(ModelAdmin):
    """Admin interface for InAppValidationResult."""

    list_display = [
        "validation",
        "status",
        "validation_run",
        "checked_at",
        "step_summary",
    ]
    list_filter = ["status", "validation_run"]
    search_fields = ["validation__name", "message"]
    readonly_fields = ["steps_display", "context_display"]

    def step_summary(self, obj):
        """Show step pass/fail counts."""
        if not obj.steps:
            return "—"
        passed = sum(1 for s in obj.steps if s.get("passed"))
        total = len(obj.steps)
        return f"{passed}/{total} passed"

    step_summary.short_description = "Steps"  # type: ignore[attr-defined]

    def steps_display(self, obj):
        """Pretty-print steps JSON."""
        import json

        if not obj.steps:
            return "No steps"
        return format_html(
            '<pre style="max-width: 600px; overflow-x: auto;">{}</pre>',
            json.dumps(obj.steps, indent=2),
        )

    steps_display.short_description = "Steps Detail"  # type: ignore[attr-defined]

    def context_display(self, obj):
        """Pretty-print context JSON."""
        import json

        if not obj.context:
            return "No context"
        return format_html(
            '<pre style="max-width: 600px; overflow-x: auto;">{}</pre>',
            json.dumps(obj.context, indent=2),
        )

    context_display.short_description = "Context Detail"  # type: ignore[attr-defined]


@admin.register(SLO)
class SLOAdmin(ModelAdmin):
    """Admin interface for SLO."""

    list_display = [
        "name",
        "display_name",
        "status",
        "target",
        "current_value",
        "error_budget_remaining",
        "service",
    ]
    list_filter = ["status", "service"]
    search_fields = ["name", "display_name", "description", "service"]
    readonly_fields = [
        "last_updated",
        "created_at",
        "updated_at",
        "linked_requirements_display",
    ]
    filter_horizontal = ["requirements"]

    fieldsets = (
        (None, {"fields": ("name", "display_name", "description")}),
        (
            "Specification",
            {"fields": ("service", "target", "time_window", "budgeting_method")},
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "current_value",
                    "error_budget_remaining",
                    "last_updated",
                )
            },
        ),
        ("Requirements", {"fields": ("requirements", "linked_requirements_display")}),
        ("Source", {"fields": ("source_file",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def linked_requirements_display(self, obj):
        """Display linked requirements with verification status badges."""
        requirements = obj.requirements.all().order_by("external_id")
        return _render_badge_list(
            requirements,
            STATUS_BADGE_COLORS,
            get_status=lambda r: r.verification_status,
            get_url=lambda r: reverse("admin:requirements_requirement_change", args=[r.pk]),
            get_label=lambda r: f"{r.external_id}: {r.title}",
            empty_message="No linked requirements",
        )

    linked_requirements_display.short_description = "Linked Requirements (Current Status)"


# Status badge colors for test-requirement links
LINK_STATUS_COLORS = {
    "passed": "#22c55e",
    "failed": "#ef4444",
    "error": "#f97316",
    "skipped": "#6b7280",
    "unknown": "#6b7280",
}

# Conflict confidence colors
CONFLICT_CONFIDENCE_COLORS = {
    "high": "#ef4444",
    "medium": "#f97316",
    "low": "#6b7280",
}

# Agent task status colors
AGENT_TASK_STATUS_COLORS = {
    "draft": "#6b7280",  # gray
    "unclaimed": "#3b82f6",  # blue
    "claimed": "#8b5cf6",  # purple
    "in_progress": "#f59e0b",  # amber
    "ready_for_review": "#eab308",  # yellow
    "changes_requested": "#f97316",  # orange
    "approved": "#22c55e",  # green
    "merged": "#10b981",  # emerald
    "blocked": "#ef4444",  # red
    "abandoned": "#374151",  # dark gray
}

# Review decision colors
REVIEW_DECISION_COLORS = {
    "approved": "#22c55e",
    "changes_requested": "#f97316",
    "rejected": "#ef4444",
}


@admin.register(TestRequirementLink)
class TestRequirementLinkAdmin(ModelAdmin):
    """Admin interface for TestRequirementLink."""

    list_display = [
        "test_nodeid",
        "requirement_link",
        "last_status_badge",
        "last_run_at",
        "needs_review",
        "review_reason",
    ]
    list_filter = ["last_status", "needs_review", "requirement"]
    search_fields = ["test_nodeid", "requirement__external_id", "review_reason"]
    readonly_fields = ["created_at", "updated_at", "last_run_at"]
    raw_id_fields = ["requirement"]

    fieldsets = (
        (None, {"fields": ("test_nodeid", "requirement")}),
        ("Status", {"fields": ("last_status", "last_run_at")}),
        ("Review", {"fields": ("needs_review", "review_reason")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def requirement_link(self, obj):
        """Display requirement as a clickable link."""
        url = reverse("admin:requirements_requirement_change", args=[obj.requirement.pk])
        return format_html('<a href="{}">{}</a>', url, obj.requirement.external_id)

    requirement_link.short_description = "Requirement"  # type: ignore[attr-defined]

    def last_status_badge(self, obj):
        """Display last_status as a colored badge."""
        color = LINK_STATUS_COLORS.get(obj.last_status, "#6b7280")
        return format_html(
            '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
            'font-size: 11px; font-weight: 500; color: white; background-color: {};">{}</span>',
            color,
            obj.last_status.upper(),
        )

    last_status_badge.short_description = "Status"  # type: ignore[attr-defined]


@admin.register(ConflictLog)
class ConflictLogAdmin(ModelAdmin):
    """Admin interface for ConflictLog."""

    list_display = [
        "conflict_display",
        "pattern",
        "confidence_badge",
        "resolved",
        "created_at",
    ]
    list_filter = ["pattern", "confidence", "resolved"]
    search_fields = [
        "requirement_a__external_id",
        "requirement_b__external_id",
        "resolution_notes",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "requirement_a_link",
        "requirement_b_link",
        "details_display",
    ]
    raw_id_fields = ["requirement_a", "requirement_b"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "requirement_a",
                    "requirement_b",
                    "requirement_a_link",
                    "requirement_b_link",
                )
            },
        ),
        ("Conflict Details", {"fields": ("pattern", "confidence", "details_display")}),
        ("Resolution", {"fields": ("resolved", "resolved_at", "resolution_notes")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def conflict_display(self, obj):
        """Display conflict as A ↔ B."""
        return f"{obj.requirement_a.external_id} ↔ {obj.requirement_b.external_id}"

    conflict_display.short_description = "Conflict"  # type: ignore[attr-defined]

    def confidence_badge(self, obj):
        """Display confidence as a colored badge."""
        color = CONFLICT_CONFIDENCE_COLORS.get(obj.confidence, "#6b7280")
        return format_html(
            '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
            'font-size: 11px; font-weight: 500; color: white; background-color: {};">{}</span>',
            color,
            obj.confidence.upper(),
        )

    confidence_badge.short_description = "Confidence"  # type: ignore[attr-defined]

    def requirement_a_link(self, obj):
        """Display requirement A as a clickable link."""
        url = reverse("admin:requirements_requirement_change", args=[obj.requirement_a.pk])
        return format_html(
            '<a href="{}">{}: {}</a>',
            url,
            obj.requirement_a.external_id,
            obj.requirement_a.title,
        )

    requirement_a_link.short_description = "Requirement A"  # type: ignore[attr-defined]

    def requirement_b_link(self, obj):
        """Display requirement B as a clickable link."""
        url = reverse("admin:requirements_requirement_change", args=[obj.requirement_b.pk])
        return format_html(
            '<a href="{}">{}: {}</a>',
            url,
            obj.requirement_b.external_id,
            obj.requirement_b.title,
        )

    requirement_b_link.short_description = "Requirement B"  # type: ignore[attr-defined]

    def details_display(self, obj):
        """Pretty-print details JSON."""
        if not obj.details:
            return "No details"
        return format_html(
            '<pre style="max-width: 600px; overflow-x: auto;">{}</pre>',
            json.dumps(obj.details, indent=2),
        )

    details_display.short_description = "Details"  # type: ignore[attr-defined]


# =============================================================================
# Verification Flow Admin Classes
# =============================================================================

FLOW_STATUS_COLORS = {
    "passed": "#22c55e",
    "failed": "#ef4444",
    "running": "#f59e0b",
    "unknown": "#6b7280",
}


@admin.register(VerificationFlow)
class VerificationFlowAdmin(ModelAdmin):
    """Admin interface for VerificationFlow."""

    list_display = [
        "name",
        "display_name",
        "version",
        "synced_at",
        "requirements_count",
    ]
    list_filter = ["version"]
    search_fields = ["name", "display_name", "description"]
    readonly_fields = ["synced_at", "linked_requirements_display"]
    filter_horizontal = ["requirements"]

    fieldsets = (
        (None, {"fields": ("name", "display_name", "description")}),
        ("Definition", {"fields": ("steps", "version", "synced_at")}),
        ("Requirements", {"fields": ("requirements", "linked_requirements_display")}),
    )

    def get_queryset(self, request):
        """Prefetch requirements to avoid N+1 queries."""
        return super().get_queryset(request).prefetch_related("requirements")

    def requirements_count(self, obj):
        """Display count of linked requirements."""
        count = obj.requirements.count()
        return count if count > 0 else "-"

    requirements_count.short_description = "Requirements"  # type: ignore[attr-defined]

    def linked_requirements_display(self, obj):
        """Display linked requirements with verification status badges."""
        requirements = obj.requirements.all().order_by("external_id")
        return _render_badge_list(
            requirements,
            STATUS_BADGE_COLORS,
            get_status=lambda r: r.verification_status,
            get_url=lambda r: reverse("admin:requirements_requirement_change", args=[r.pk]),
            get_label=lambda r: f"{r.external_id}: {r.title}",
            empty_message="No linked requirements",
        )

    linked_requirements_display.short_description = "Linked Requirements"  # type: ignore[attr-defined]


# =============================================================================
# Agent Coordination Admin Classes
# =============================================================================


@admin.register(AgentSprint)
class AgentSprintAdmin(ModelAdmin):
    """Admin interface for AgentSprint."""

    list_display = ["name", "is_active", "task_count", "progress_badge", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "description", "goal_description"]
    readonly_fields = ["created_at", "completed_at", "task_count", "progress_badge"]

    fieldsets = (
        (None, {"fields": ("name", "description", "goal_description")}),
        ("Status", {"fields": ("is_active", "completed_at")}),
        (
            "Progress",
            {
                "fields": ("task_count", "progress_badge"),
                "description": "Read-only progress metrics",
            },
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def task_count(self, obj):
        """Display task count."""
        return obj.task_count

    task_count.short_description = "Tasks"  # type: ignore[attr-defined]

    def progress_badge(self, obj):
        """Display progress as a colored badge with percentage."""
        progress = obj.progress
        pct = progress["percent_complete"]
        merged = progress["merged"]
        total = progress["total"]

        if total == 0:
            color = "#6b7280"
            label = "No tasks"
        elif pct == 100:
            color = "#22c55e"
            label = "Complete"
        elif pct >= 50:
            color = "#f59e0b"
            label = f"{pct:.0f}%"
        else:
            color = "#3b82f6"
            label = f"{pct:.0f}%"

        return format_html(
            '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
            'font-size: 11px; font-weight: 500; color: white; background-color: {};">'
            '{}</span> <span style="color: #6b7280;">({}/{})</span>',
            color,
            label,
            merged,
            total,
        )

    progress_badge.short_description = "Progress"  # type: ignore[attr-defined]


@admin.register(Agent)
class AgentAdmin(ModelAdmin):
    """Admin interface for Agent."""

    list_display = [
        "agent_id",
        "role",
        "is_active",
        "last_heartbeat",
        "current_task_display",
    ]
    list_filter = ["role", "is_active"]
    search_fields = ["agent_id"]
    readonly_fields = [
        "registered_at",
        "last_heartbeat",
        "current_task_display",
        "config_display",
    ]

    fieldsets = (
        (None, {"fields": ("agent_id", "role")}),
        ("Status", {"fields": ("is_active", "last_heartbeat", "current_task_display")}),
        (
            "Configuration",
            {"fields": ("config", "config_display"), "classes": ("collapse",)},
        ),
        ("Timestamps", {"fields": ("registered_at",), "classes": ("collapse",)}),
    )

    def current_task_display(self, obj):
        """Display current task as a clickable link."""
        task = obj.current_task
        if not task:
            return format_html('<span style="color: #6b7280;">None</span>')
        url = reverse("admin:requirements_agenttask_change", args=[task.pk])
        color = AGENT_TASK_STATUS_COLORS.get(task.status, "#6b7280")
        return format_html(
            '<a href="{}">{}</a> '
            '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
            'font-size: 11px; font-weight: 500; color: white; background-color: {};">{}</span>',
            url,
            task.external_id,
            color,
            task.status.upper(),
        )

    current_task_display.short_description = "Current Task"  # type: ignore[attr-defined]

    def config_display(self, obj):
        """Pretty-print config JSON."""
        if not obj.config:
            return "No config"
        return format_html(
            '<pre style="max-width: 600px; overflow-x: auto;">{}</pre>',
            json.dumps(obj.config, indent=2),
        )

    config_display.short_description = "Config Detail"  # type: ignore[attr-defined]


@admin.register(AgentTask)
class AgentTaskAdmin(ModelAdmin):
    """Admin interface for AgentTask."""

    list_display = [
        "external_id",
        "title",
        "status_badge",
        "claimed_by",
        "sprint",
        "attempt_count",
        "updated_at",
    ]
    list_filter = ["status", "sprint", "claimed_by"]
    search_fields = ["external_id", "title", "description"]
    filter_horizontal = ["requirements", "depends_on"]
    readonly_fields = [
        "attempt_count",
        "created_at",
        "updated_at",
        "status_badge",
        "done_when_display",
        "scope_in_display",
        "scope_out_display",
        "linked_requirements_display",
    ]
    raw_id_fields = ["claimed_by", "sprint"]

    fieldsets = (
        (None, {"fields": ("external_id", "title", "description")}),
        (
            "Requirements",
            {"fields": ("requirements", "linked_requirements_display", "spec_ref")},
        ),
        (
            "State",
            {
                "fields": (
                    "status",
                    "status_badge",
                    "claimed_by",
                    "claimed_at",
                    "lease_expires",
                )
            },
        ),
        (
            "Completion Criteria",
            {
                "fields": (
                    "done_when",
                    "done_when_display",
                    "scope_in",
                    "scope_in_display",
                    "scope_out",
                    "scope_out_display",
                ),
                "description": "Falsifiable criteria and scope boundaries",
            },
        ),
        (
            "Git",
            {
                "fields": ("worktree_path", "branch_name", "commit_sha"),
                "classes": ("collapse",),
            },
        ),
        ("Dependencies", {"fields": ("depends_on", "sprint")}),
        (
            "Retries",
            {
                "fields": ("attempt_count", "max_attempts"),
                "description": "Hypothesis exhaustion tracking",
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def status_badge(self, obj):
        """Display status as a colored badge."""
        color = AGENT_TASK_STATUS_COLORS.get(obj.status, "#6b7280")
        return format_html(
            '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
            'font-size: 11px; font-weight: 500; color: white; background-color: {};">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"  # type: ignore[attr-defined]

    def done_when_display(self, obj):
        """Pretty-print done_when as a checklist."""
        if not obj.done_when:
            return format_html('<span style="color: #6b7280;">No criteria defined</span>')
        items = "".join(f"<li>{criterion}</li>" for criterion in obj.done_when)
        return format_html('<ul style="margin: 0; padding-left: 20px;">{}</ul>', format_html(items))

    done_when_display.short_description = "Done When (Display)"  # type: ignore[attr-defined]

    def scope_in_display(self, obj):
        """Pretty-print scope_in as a list."""
        if not obj.scope_in:
            return format_html('<span style="color: #6b7280;">Not specified</span>')
        items = "".join(f"<li>{item}</li>" for item in obj.scope_in)
        return format_html('<ul style="margin: 0; padding-left: 20px;">{}</ul>', format_html(items))

    scope_in_display.short_description = "In Scope (Display)"  # type: ignore[attr-defined]

    def scope_out_display(self, obj):
        """Pretty-print scope_out as a list."""
        if not obj.scope_out:
            return format_html('<span style="color: #6b7280;">Not specified</span>')
        items = "".join(f"<li>{item}</li>" for item in obj.scope_out)
        return format_html('<ul style="margin: 0; padding-left: 20px;">{}</ul>', format_html(items))

    scope_out_display.short_description = "Out of Scope (Display)"  # type: ignore[attr-defined]

    def linked_requirements_display(self, obj):
        """Display linked requirements with verification status badges."""
        requirements = obj.requirements.all().order_by("external_id")
        return _render_badge_list(
            requirements,
            STATUS_BADGE_COLORS,
            get_status=lambda r: r.verification_status,
            get_url=lambda r: reverse("admin:requirements_requirement_change", args=[r.pk]),
            get_label=lambda r: f"{r.external_id}: {r.title}",
            empty_message="No linked requirements",
        )

    linked_requirements_display.short_description = "Linked Requirements"  # type: ignore[attr-defined]


@admin.register(AgentTaskHistory)
class AgentTaskHistoryAdmin(ModelAdmin):
    """Admin interface for AgentTaskHistory."""

    list_display = [
        "task_link",
        "action",
        "agent",
        "from_status",
        "to_status",
        "timestamp",
    ]
    list_filter = ["action", "agent"]
    search_fields = ["task__external_id", "action"]
    readonly_fields = [
        "task",
        "task_link",
        "agent",
        "timestamp",
        "action",
        "from_status",
        "to_status",
        "details_display",
    ]

    fieldsets = (
        (None, {"fields": ("task", "task_link", "agent")}),
        ("Action", {"fields": ("action", "from_status", "to_status", "timestamp")}),
        ("Details", {"fields": ("details_display",)}),
    )

    def task_link(self, obj):
        """Display task as a clickable link."""
        url = reverse("admin:requirements_agenttask_change", args=[obj.task.pk])
        return format_html('<a href="{}">{}</a>', url, obj.task.external_id)

    task_link.short_description = "Task"  # type: ignore[attr-defined]

    def details_display(self, obj):
        """Pretty-print details JSON."""
        if not obj.details:
            return "No details"
        return format_html(
            '<pre style="max-width: 600px; overflow-x: auto;">{}</pre>',
            json.dumps(obj.details, indent=2),
        )

    details_display.short_description = "Details"  # type: ignore[attr-defined]


@admin.register(AgentTaskReview)
class AgentTaskReviewAdmin(ModelAdmin):
    """Admin interface for AgentTaskReview."""

    list_display = [
        "task_link",
        "reviewer",
        "decision_badge",
        "commit_sha_short",
        "created_at",
    ]
    list_filter = ["decision", "reviewer"]
    search_fields = ["task__external_id", "feedback"]
    readonly_fields = [
        "task",
        "task_link",
        "reviewer",
        "created_at",
        "done_when_results_display",
        "blocking_issues_display",
        "suggestions_display",
    ]

    fieldsets = (
        (None, {"fields": ("task", "task_link", "reviewer")}),
        ("Decision", {"fields": ("decision", "commit_sha")}),
        (
            "Criteria Verification",
            {"fields": ("done_when_results", "done_when_results_display")},
        ),
        (
            "Feedback",
            {
                "fields": (
                    "feedback",
                    "blocking_issues",
                    "blocking_issues_display",
                    "suggestions",
                    "suggestions_display",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def task_link(self, obj):
        """Display task as a clickable link."""
        url = reverse("admin:requirements_agenttask_change", args=[obj.task.pk])
        return format_html('<a href="{}">{}</a>', url, obj.task.external_id)

    task_link.short_description = "Task"  # type: ignore[attr-defined]

    def decision_badge(self, obj):
        """Display decision as a colored badge."""
        color = REVIEW_DECISION_COLORS.get(obj.decision, "#6b7280")
        return format_html(
            '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
            'font-size: 11px; font-weight: 500; color: white; background-color: {};">{}</span>',
            color,
            obj.get_decision_display(),
        )

    decision_badge.short_description = "Decision"  # type: ignore[attr-defined]

    def commit_sha_short(self, obj):
        """Display shortened commit SHA."""
        if obj.commit_sha:
            return obj.commit_sha[:8]
        return "—"

    commit_sha_short.short_description = "Commit"  # type: ignore[attr-defined]

    def done_when_results_display(self, obj):
        """Pretty-print done_when_results as a checklist."""
        if not obj.done_when_results:
            return format_html('<span style="color: #6b7280;">No results</span>')
        items = []
        for result in obj.done_when_results:
            criterion = result.get("criterion", "Unknown")
            passed = result.get("passed", False)
            icon = "✓" if passed else "✗"
            color = "#22c55e" if passed else "#ef4444"
            items.append(f'<li><span style="color: {color};">{icon}</span> {criterion}</li>')
        return format_html(
            '<ul style="margin: 0; padding-left: 20px;">{}</ul>',
            format_html("".join(items)),
        )

    done_when_results_display.short_description = "Criteria Results"  # type: ignore[attr-defined]

    def blocking_issues_display(self, obj):
        """Pretty-print blocking_issues as a list."""
        if not obj.blocking_issues:
            return format_html('<span style="color: #6b7280;">None</span>')
        items = "".join(
            f'<li style="color: #ef4444;">{issue}</li>' for issue in obj.blocking_issues
        )
        return format_html('<ul style="margin: 0; padding-left: 20px;">{}</ul>', format_html(items))

    blocking_issues_display.short_description = "Blocking Issues"  # type: ignore[attr-defined]

    def suggestions_display(self, obj):
        """Pretty-print suggestions as a list."""
        if not obj.suggestions:
            return format_html('<span style="color: #6b7280;">None</span>')
        items = "".join(f"<li>{suggestion}</li>" for suggestion in obj.suggestions)
        return format_html('<ul style="margin: 0; padding-left: 20px;">{}</ul>', format_html(items))

    suggestions_display.short_description = "Suggestions"  # type: ignore[attr-defined]


# ============================================================================
# Corpus review admin
# ============================================================================


class CorpusEntryVersionInline(TabularInline):
    """Versions of one corpus entry, newest first. Versions are immutable."""

    model = CorpusEntryVersion
    extra = 0
    can_delete = False
    fields = ["version", "effective_date", "content_hash", "supersedes", "source_file"]
    readonly_fields = fields
    ordering = ["-version"]

    def has_add_permission(self, request, obj):
        return False


class ReviewCoverageInline(TabularInline):
    """Every entry version the review surfaced, finding or not."""

    model = ReviewCoverage
    extra = 0
    can_delete = False
    fields = ["entry_version", "cited", "matched_by_display"]
    readonly_fields = fields

    def has_add_permission(self, request, obj):
        return False

    def matched_by_display(self, obj):
        """Render the persisted match reasons as scope_key=value pairs."""
        if not obj.matched_by:
            return format_html('<span style="color: #6b7280;">None</span>')
        items = format_html_join(
            "",
            "<li>{}={} ({})</li>",
            (
                (
                    reason["scope_key"],
                    reason["matched_value"],
                    reason["matched_requirement_id"],
                )
                for reason in obj.matched_by
            ),
        )
        return format_html('<ul style="margin: 0; padding-left: 20px;">{}</ul>', items)

    matched_by_display.short_description = "Matched By"  # type: ignore[attr-defined]


class ReviewFindingInline(TabularInline):
    """Findings the review produced, each naming an entry version."""

    model = ReviewFinding
    extra = 0
    can_delete = False
    fields = ["finding_type", "entry_version", "check_id", "detail"]
    readonly_fields = fields

    def has_add_permission(self, request, obj):
        return False


@admin.register(CorpusEntry)
class CorpusEntryAdmin(ModelAdmin):
    """Admin interface for corpus entries with their versions inline."""

    list_display = ["external_id", "title", "kind", "status", "owner", "source_file", "updated_at"]
    list_filter = ["kind", "status", "owner"]
    search_fields = ["external_id", "title", "owner", "source_file"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [CorpusEntryVersionInline]


@admin.register(CorpusEntryVersion)
class CorpusEntryVersionAdmin(ModelAdmin):
    """Admin interface for immutable corpus entry versions."""

    list_display = ["__str__", "entry", "version", "effective_date", "source_file", "created_at"]
    list_filter = ["entry__kind", "entry__status", "effective_date"]
    search_fields = ["entry__external_id", "entry__title", "content_hash", "body"]
    readonly_fields = [
        "entry",
        "version",
        "body",
        "content_hash",
        "applies_to",
        "checks",
        "effective_date",
        "supersedes",
        "source_file",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False


@admin.register(CorpusSnapshot)
class CorpusSnapshotAdmin(ModelAdmin):
    """Admin interface for pinned corpus snapshots."""

    list_display = ["snapshot_hash", "version_count", "created_at"]
    search_fields = ["snapshot_hash"]
    readonly_fields = ["snapshot_hash", "entry_version_hashes", "created_at"]
    filter_horizontal = ["entry_versions"]

    def version_count(self, obj):
        """Number of entry versions the snapshot pins."""
        return len(obj.entry_version_hashes)

    version_count.short_description = "Versions"  # type: ignore[attr-defined]


@admin.register(SpecReview)
class SpecReviewAdmin(ModelAdmin):
    """Admin interface for spec reviews with coverage and findings inline."""

    list_display = [
        "requirement",
        "outcome_badge",
        "coverage_count",
        "finding_count",
        "spec_file",
        "reviewer",
        "created_at",
    ]
    list_filter = ["outcome", "reviewer", "created_at"]
    search_fields = ["requirement__external_id", "spec_file", "reviewer"]
    readonly_fields = ["requirement", "snapshot", "spec_file", "reviewer", "outcome", "created_at"]
    inlines = [ReviewCoverageInline, ReviewFindingInline]

    def outcome_badge(self, obj):
        """Display the review outcome as a colored badge."""
        color = "#ef4444" if obj.outcome == "findings" else "#22c55e"
        return format_html(
            '<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; '
            'font-size: 11px; font-weight: 500; color: white; background-color: {};">{}</span>',
            color,
            obj.get_outcome_display(),
        )

    outcome_badge.short_description = "Outcome"  # type: ignore[attr-defined]

    def coverage_count(self, obj):
        """How many entry versions this review surfaced."""
        return obj.coverage.count()

    coverage_count.short_description = "Entries Surfaced"  # type: ignore[attr-defined]

    def finding_count(self, obj):
        """How many findings this review produced."""
        return obj.findings.count()

    finding_count.short_description = "Findings"  # type: ignore[attr-defined]

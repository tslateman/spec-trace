"""URL patterns for the requirements app.

Include in your project's urls.py:
    path("", include("requirements.urls"))
"""

from django.urls import path
from django.views.generic import TemplateView

from requirements import api, api_v1
from requirements.openapi.views import openapi_spec, swagger_ui
from requirements.views import (
    about_view,
    demo_agent_pipeline,
    demo_hub,
    flow_editor_list_view,
    flow_editor_view,
    flow_live_status_view,
    flow_load_demo_view,
    flow_run_detail_view,
    flow_runs_view,
    flow_status_list_view,
    flow_sync_to_db_view,
    high_risk_dashboard_view,
    impact_analysis_view,
    impact_load_demo_view,
    landing_view,
    matrix_export,
    matrix_load_demo_view,
    matrix_view,
    qa_ecosystem_view,
    requirement_detail_view,
    spec_syntax_help_view,
    spectrace_overview,
    validation_run_compare_view,
    validation_run_detail_view,
    validation_run_list_view,
    validation_run_steps_view,
    vendor_coverage_view,
    vendor_load_demo_view,
)

# Admin views (place before admin.site.urls in your urlpatterns)
admin_urlpatterns = [
    path("", landing_view, name="landing"),
    path("admin/matrix/", matrix_view, name="admin-matrix"),
    path("admin/matrix/export/", matrix_export, name="admin-matrix-export"),
    path("admin/matrix/load-demo/", matrix_load_demo_view, name="admin-matrix-load-demo"),
    path("admin/vendor-coverage/", vendor_coverage_view, name="admin-vendor-coverage"),
    path(
        "admin/vendor-coverage/load-demo/",
        vendor_load_demo_view,
        name="admin-vendor-load-demo",
    ),
    path("admin/impact-analysis/", impact_analysis_view, name="admin-impact-analysis"),
    path(
        "admin/impact-analysis/load-demo/",
        impact_load_demo_view,
        name="admin-impact-load-demo",
    ),
    path("admin/high-risk/", high_risk_dashboard_view, name="admin-high-risk"),
    path(
        "admin/requirement/<str:external_id>/",
        requirement_detail_view,
        name="admin-requirement-detail",
    ),
    path("admin/about/", about_view, name="admin-about"),
    path("admin/spec-syntax/", spec_syntax_help_view, name="admin-spec-syntax"),
    path(
        "getting-started/",
        TemplateView.as_view(template_name="admin/requirements/getting_started.html"),
        name="getting-started",
    ),
    # Validation runs
    path("admin/validation-runs/", validation_run_list_view, name="admin-validation-runs"),
    path(
        "admin/validation-runs/<int:run_id>/",
        validation_run_detail_view,
        name="admin-validation-run-detail",
    ),
    path(
        "admin/validation-runs/<int:run_id>/steps/",
        validation_run_steps_view,
        name="admin-validation-run-steps",
    ),
    path(
        "admin/validation-runs/compare/",
        validation_run_compare_view,
        name="admin-validation-run-compare",
    ),
    # Flow status
    path("admin/flow-status/", flow_status_list_view, name="admin-flow-status"),
    path("admin/flow-status/live/", flow_live_status_view, name="admin-flow-live"),
    path("admin/flow-status/load-demo/", flow_load_demo_view, name="admin-flow-load-demo"),
    path(
        "admin/flow-status/run/<int:run_id>/",
        flow_run_detail_view,
        name="admin-flow-run-detail",
    ),
    path("admin/flow-status/<str:flow_name>/", flow_runs_view, name="admin-flow-runs"),
    # Flow editor
    path("admin/flow-editor/", flow_editor_list_view, name="admin-flow-editor"),
    path(
        "admin/flow-editor/<path:file_path>/",
        flow_editor_view,
        name="admin-flow-editor-edit",
    ),
    path(
        "admin/flow-editor/<path:file_path>/sync/",
        flow_sync_to_db_view,
        name="admin-flow-editor-sync",
    ),
    # Demo
    path("demo/", demo_hub, name="demo_hub"),
    path("demo/agent-pipeline/", demo_agent_pipeline, name="demo_agent_pipeline"),
    path("demo/spectrace-overview/", spectrace_overview, name="spectrace_overview"),
    path("demo/qa-ecosystem/", qa_ecosystem_view, name="qa_ecosystem"),
]


def _get_webhook_urlpatterns():
    """Return webhook URLs only if GitHub dependencies are available and configured."""
    try:
        import jwt  # noqa: F401
    except ImportError:
        return []

    from django.conf import settings

    if not getattr(settings, "GITHUB_WEBHOOK_SECRET", ""):
        return []

    from requirements import webhooks

    return [
        path("api/webhooks/github/", webhooks.github_webhook, name="api-github-webhook"),
    ]


# Webhook endpoints (conditionally registered)
webhook_urlpatterns = _get_webhook_urlpatterns()

# REST API endpoints
api_urlpatterns = [
    # API v1 (New Structure)
    path("api/v1/tasks/", api_v1.list_tasks, name="api-v1-tasks-list"),
    path("api/v1/tasks/<str:task_id>/claim", api_v1.claim_task_view, name="api-v1-tasks-claim"),
    path(
        "api/v1/tasks/<str:task_id>/complete",
        api_v1.complete_task_view,
        name="api-v1-tasks-complete",
    ),
    path("api/v1/specs/coverage/", api_v1.specs_coverage_view, name="api-v1-specs-coverage"),
    path("api/v1/specs/drift/", api_v1.specs_drift_view, name="api-v1-specs-drift"),
    path(
        "api/v1/specs/<str:external_id>/context",
        api_v1.spec_context_view,
        name="api-v1-specs-context",
    ),
    path("api/v1/specs/impact/", api_v1.specs_impact_view, name="api-v1-specs-impact"),
    path("api/v1/results/conflicts/", api_v1.list_conflicts_view, name="api-v1-results-conflicts"),
    path("api/v1/results/conflicts/detect", api_v1.detect_conflicts_view, name="api-v1-results-conflicts-detect"),
    path("api/v1/results/conflicts/<int:conflict_id>", api_v1.get_conflict_view, name="api-v1-results-conflict-detail"),
    path("api/v1/results/conflicts/<int:conflict_id>/resolve", api_v1.resolve_conflict_view, name="api-v1-results-conflict-resolve"),

    # External system integration
    path("api/slo/status/", api.update_slo_status, name="api-slo-status"),
    path(
        "api/validation/result/",
        api.submit_validation_result,
        name="api-validation-result",
    ),
    path(
        "api/requirement/<str:external_id>/status/",
        api.get_requirement_status,
        name="api-requirement-status",
    ),
    # Health checks
    path(
        "api/integrations/linear/test-connection/",
        api.test_linear_connection,
        name="api-linear-test-connection",
    ),
    path(
        "api/integrations/linear/health/",
        api.get_linear_health,
        name="api-linear-health",
    ),
    # Validation runs
    path("api/validation-runs/", api.list_validation_runs, name="api-validation-runs"),
    path(
        "api/validation-runs/<int:run_id>/",
        api.get_validation_run,
        name="api-validation-run-detail",
    ),
    path(
        "api/validation-runs/<int:run_id>/steps/",
        api.get_validation_run_steps,
        name="api-validation-run-steps",
    ),
    # Flow runs
    path(
        "api/flow-runs/running/",
        api.get_running_flow_runs,
        name="api-flow-runs-running",
    ),
    # Test runs (CI/CD integration)
    path("api/test-runs/latest/", api.get_latest_test_run, name="api-test-runs-latest"),
    # Conflicts
    path("api/conflicts/", api.list_conflicts, name="api-conflicts"),
    path("api/conflicts/detect/", api.detect_conflicts, name="api-conflicts-detect"),
    path("api/conflicts/<int:conflict_id>/", api.get_conflict, name="api-conflict-detail"),
    path(
        "api/conflicts/<int:conflict_id>/resolve/",
        api.resolve_conflict,
        name="api-conflict-resolve",
    ),
    # OpenAPI
    path("api/openapi.json", openapi_spec, name="openapi-spec"),
    path("api/docs/", swagger_ui, name="swagger-ui"),
]

# Combined patterns for simple include
urlpatterns = admin_urlpatterns + api_urlpatterns + webhook_urlpatterns

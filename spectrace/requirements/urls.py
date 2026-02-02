"""URL patterns for the requirements app.

Include in your project's urls.py:
    path("", include("requirements.urls"))
"""

from django.urls import path

from requirements import api
from requirements.openapi.views import openapi_spec, swagger_ui
from requirements.views import (
    about_view,
    demo_agent_pipeline,
    demo_hub,
    flow_editor_list_view,
    flow_editor_view,
    flow_load_demo_view,
    flow_run_detail_view,
    flow_runs_view,
    flow_status_list_view,
    impact_analysis_view,
    matrix_export,
    matrix_load_demo_view,
    matrix_view,
    spec_syntax_help_view,
    validation_run_compare_view,
    validation_run_detail_view,
    validation_run_list_view,
    validation_run_steps_view,
    vendor_coverage_view,
)

# Admin views (place before admin.site.urls in your urlpatterns)
admin_urlpatterns = [
    path("admin/matrix/", matrix_view, name="admin-matrix"),
    path("admin/matrix/export/", matrix_export, name="admin-matrix-export"),
    path("admin/matrix/load-demo/", matrix_load_demo_view, name="admin-matrix-load-demo"),
    path("admin/vendor-coverage/", vendor_coverage_view, name="admin-vendor-coverage"),
    path("admin/impact-analysis/", impact_analysis_view, name="admin-impact-analysis"),
    path("admin/about/", about_view, name="admin-about"),
    path("admin/spec-syntax/", spec_syntax_help_view, name="admin-spec-syntax"),
    # Validation runs
    path("admin/validation-runs/", validation_run_list_view, name="admin-validation-runs"),
    path("admin/validation-runs/<int:run_id>/", validation_run_detail_view, name="admin-validation-run-detail"),
    path("admin/validation-runs/<int:run_id>/steps/", validation_run_steps_view, name="admin-validation-run-steps"),
    path("admin/validation-runs/compare/", validation_run_compare_view, name="admin-validation-run-compare"),
    # Flow status
    path("admin/flow-status/", flow_status_list_view, name="admin-flow-status"),
    path("admin/flow-status/load-demo/", flow_load_demo_view, name="admin-flow-load-demo"),
    path("admin/flow-status/run/<int:run_id>/", flow_run_detail_view, name="admin-flow-run-detail"),
    path("admin/flow-status/<str:flow_name>/", flow_runs_view, name="admin-flow-runs"),
    # Flow editor
    path("admin/flow-editor/", flow_editor_list_view, name="admin-flow-editor"),
    path("admin/flow-editor/<path:file_path>/", flow_editor_view, name="admin-flow-editor-edit"),
    # Demo
    path("demo/", demo_hub, name="demo_hub"),
    path("demo/agent-pipeline/", demo_agent_pipeline, name="demo_agent_pipeline"),
]

# REST API endpoints
api_urlpatterns = [
    # External system integration
    path("api/slo/status/", api.update_slo_status, name="api-slo-status"),
    path("api/validation/result/", api.submit_validation_result, name="api-validation-result"),
    path("api/requirement/<str:external_id>/status/", api.get_requirement_status, name="api-requirement-status"),
    # Health checks
    path("api/integrations/linear/test-connection/", api.test_linear_connection, name="api-linear-test-connection"),
    path("api/integrations/linear/health/", api.get_linear_health, name="api-linear-health"),
    # Validation runs
    path("api/validation-runs/", api.list_validation_runs, name="api-validation-runs"),
    path("api/validation-runs/<int:run_id>/", api.get_validation_run, name="api-validation-run-detail"),
    path("api/validation-runs/<int:run_id>/steps/", api.get_validation_run_steps, name="api-validation-run-steps"),
    # OpenAPI
    path("api/openapi.json", openapi_spec, name="openapi-spec"),
    path("api/docs/", swagger_ui, name="swagger-ui"),
]

# Combined patterns for simple include
urlpatterns = admin_urlpatterns + api_urlpatterns

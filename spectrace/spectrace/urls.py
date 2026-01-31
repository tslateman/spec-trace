"""
URL configuration for spectrace project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from requirements import api
from requirements.openapi.views import openapi_spec, swagger_ui
from requirements.views import (
    matrix_view,
    matrix_export,
    vendor_coverage_view,
    impact_analysis_view,
    validation_run_list_view,
    validation_run_detail_view,
    validation_run_steps_view,
    validation_run_compare_view,
    about_view,
    spec_syntax_help_view,
)

urlpatterns = [
    # Matrix views must come before admin to avoid being caught by admin prefix
    path('admin/matrix/', matrix_view, name='admin-matrix'),
    path('admin/matrix/export/', matrix_export, name='admin-matrix-export'),
    path('admin/vendor-coverage/', vendor_coverage_view, name='admin-vendor-coverage'),
    path('admin/impact-analysis/', impact_analysis_view, name='admin-impact-analysis'),
    path('admin/about/', about_view, name='admin-about'),
    path('admin/spec-syntax/', spec_syntax_help_view, name='admin-spec-syntax'),
    # Validation run views
    path('admin/validation-runs/', validation_run_list_view, name='admin-validation-runs'),
    path('admin/validation-runs/<int:run_id>/', validation_run_detail_view, name='admin-validation-run-detail'),
    path('admin/validation-runs/<int:run_id>/steps/', validation_run_steps_view, name='admin-validation-run-steps'),
    path('admin/validation-runs/compare/', validation_run_compare_view, name='admin-validation-run-compare'),
    path('admin/', admin.site.urls),

    # API endpoints for external systems
    path('api/slo/status/', api.update_slo_status, name='api-slo-status'),
    path('api/validation/result/', api.submit_validation_result, name='api-validation-result'),
    path('api/requirement/<str:external_id>/status/', api.get_requirement_status, name='api-requirement-status'),

    # Integration health check endpoints
    path('api/integrations/linear/test-connection/', api.test_linear_connection, name='api-linear-test-connection'),
    path('api/integrations/linear/health/', api.get_linear_health, name='api-linear-health'),

    # Validation run API endpoints
    path('api/validation-runs/', api.list_validation_runs, name='api-validation-runs'),
    path('api/validation-runs/<int:run_id>/', api.get_validation_run, name='api-validation-run-detail'),
    path('api/validation-runs/<int:run_id>/steps/', api.get_validation_run_steps, name='api-validation-run-steps'),

    # OpenAPI documentation endpoints
    path('api/openapi.json', openapi_spec, name='openapi-spec'),
    path('api/docs/', swagger_ui, name='swagger-ui'),
]

"""Tests for the /api/v1/ surface and the retired unversioned paths."""

import json
import sys
from types import ModuleType

import pytest
from django.urls import resolve

from requirements.api_redirects import LEGACY_API_SUNSET, legacy_alias
from requirements.models import SLOStatus
from requirements.urls import _get_webhook_urlpatterns

V1_ENDPOINTS = [
    "/api/v1/integrations/slo/status/",
    "/api/v1/integrations/linear/test-connection/",
    "/api/v1/integrations/linear/health/",
    "/api/v1/results/enforcement/",
    "/api/v1/results/enforcement-runs/",
    "/api/v1/results/enforcement-runs/7/",
    "/api/v1/results/enforcement-runs/7/steps/",
    "/api/v1/results/test-runs/latest/",
    "/api/v1/results/conflicts/",
    "/api/v1/results/conflicts/detect",
    "/api/v1/results/conflicts/7",
    "/api/v1/results/conflicts/7/resolve",
    "/api/v1/specs/REQ-TEST-001/status/",
    "/api/v1/tasks/flow-runs/running/",
]

LEGACY_REDIRECTS = [
    ("get", "/api/requirement/REQ-TEST-001/status/", "/api/v1/specs/REQ-TEST-001/status/", 301),
    ("get", "/api/integrations/linear/health/", "/api/v1/integrations/linear/health/", 301),
    ("get", "/api/validation-runs/", "/api/v1/results/enforcement-runs/", 301),
    ("get", "/api/validation-runs/7/", "/api/v1/results/enforcement-runs/7/", 301),
    ("get", "/api/validation-runs/7/steps/", "/api/v1/results/enforcement-runs/7/steps/", 301),
    ("get", "/api/flow-runs/running/", "/api/v1/tasks/flow-runs/running/", 301),
    ("get", "/api/test-runs/latest/", "/api/v1/results/test-runs/latest/", 301),
    ("get", "/api/conflicts/", "/api/v1/results/conflicts/", 301),
    ("get", "/api/conflicts/7/", "/api/v1/results/conflicts/7", 301),
    ("post", "/api/slo/status/", "/api/v1/integrations/slo/status/", 308),
    ("post", "/api/validation/result/", "/api/v1/results/enforcement/", 308),
    (
        "post",
        "/api/integrations/linear/test-connection/",
        "/api/v1/integrations/linear/test-connection/",
        308,
    ),
    ("post", "/api/conflicts/detect/", "/api/v1/results/conflicts/detect", 308),
    ("post", "/api/conflicts/7/resolve/", "/api/v1/results/conflicts/7/resolve", 308),
]


@pytest.mark.parametrize("path", V1_ENDPOINTS)
def test_contract_endpoint__is_registered_under_v1(path):
    """Every endpoint in the API contract answers under /api/v1/."""
    match = resolve(path)

    assert getattr(match.func, "is_legacy_route", False) is False


@pytest.mark.parametrize("method, legacy_path, v1_path, status", LEGACY_REDIRECTS)
def test_legacy_path__redirects_to_v1_target(client, method, legacy_path, v1_path, status):
    """Every retired unversioned path redirects to its v1 target."""
    response = getattr(client, method)(legacy_path)

    assert response.status_code == status
    assert response["Location"] == v1_path


@pytest.mark.parametrize("method, legacy_path, v1_path, status", LEGACY_REDIRECTS)
def test_legacy_path__announces_deprecation(client, method, legacy_path, v1_path, status):
    """Redirects carry the RFC 8594 deprecation headers and a JSON body."""
    response = getattr(client, method)(legacy_path)

    assert response["Deprecation"] == "true"
    assert response["Link"] == f'<{v1_path}>; rel="successor-version"'
    assert response["Sunset"] == LEGACY_API_SUNSET
    assert response.json() == {
        "message": f"This endpoint has moved to {v1_path}",
        "code": "ENDPOINT_MOVED",
    }


def test_legacy_conflicts__keeps_query_string_in_redirect(client):
    """Query parameters survive the redirect."""
    response = client.get("/api/conflicts/?confidence=high&page=2")

    assert response["Location"] == "/api/v1/results/conflicts/?confidence=high&page=2"


@pytest.mark.django_db
def test_legacy_slo_status__preserves_method_and_body_through_redirect(client, sample_slo):
    """A POST to the retired path lands on the v1 handler with its body intact."""
    response = client.post(
        "/api/slo/status/",
        data=json.dumps(
            {
                "slos": [
                    {
                        "name": "test-slo",
                        "status": "met",
                        "current_value": 0.9995,
                        "error_budget_remaining": 0.75,
                    }
                ]
            }
        ),
        content_type="application/json",
        follow=True,
    )

    assert response.redirect_chain == [("/api/v1/integrations/slo/status/", 308)]
    assert response.status_code == 200
    assert response.json()["updated"] == 1

    sample_slo.refresh_from_db()
    assert sample_slo.status == SLOStatus.MET


@pytest.mark.django_db
def test_legacy_enforcement_result__preserves_method_and_body_through_redirect(
    client, sample_requirement
):
    """Enforcement evidence posted to the retired path reaches the v1 handler."""
    response = client.post(
        "/api/validation/result/",
        data=json.dumps(
            {
                "source": "redirect-test",
                "validations": [
                    {
                        "requirement_id": sample_requirement.external_id,
                        "name": "Redirected validation",
                        "status": "success",
                        "message": "All passed",
                    }
                ],
            }
        ),
        content_type="application/json",
        follow=True,
    )

    assert response.redirect_chain == [("/api/v1/results/enforcement/", 308)]
    assert response.status_code == 200
    assert response.json()["imported"] == 1


@pytest.mark.django_db
def test_get_running_flow_runs__answers_at_v1_path(client):
    """Flow runs moved to the tasks group."""
    response = client.get("/api/v1/tasks/flow-runs/running/")

    assert response.status_code == 200
    assert response.json()["runs"] == []


@pytest.mark.django_db
def test_get_latest_test_run__answers_at_v1_path(client):
    """Test runs moved to the results group."""
    response = client.get("/api/v1/results/test-runs/latest/")

    assert response.status_code == 200
    assert response.json()["test_run"] is None


def test_openapi_spec__lists_only_the_v1_surface(client):
    """Retired paths stay out of the spec so it describes one surface."""
    response = client.get("/api/openapi.json")

    unversioned = [
        path
        for path in response.json()["paths"]
        if not path.startswith("/api/v1/") and path != "/api/docs/"
    ]
    assert unversioned == []


def test_webhook_urlpatterns__serve_v1_path_with_legacy_alias(settings, monkeypatch):
    """GitHub ignores redirects, so the retired webhook path stays live."""
    monkeypatch.setitem(sys.modules, "jwt", ModuleType("jwt"))
    settings.GITHUB_WEBHOOK_SECRET = "test-secret"

    patterns = _get_webhook_urlpatterns()

    assert [str(pattern.pattern) for pattern in patterns] == [
        "api/v1/integrations/webhooks/github/",
        "api/webhooks/github/",
    ]
    assert getattr(patterns[0].callback, "is_legacy_route", False) is False
    assert patterns[1].callback.is_legacy_route is True
    assert patterns[1].callback.csrf_exempt is True


def test_legacy_alias__delegates_to_the_wrapped_view():
    """The alias serves the same view rather than redirecting."""
    calls = []

    def view(request, **kwargs):
        calls.append(kwargs)
        return "served"

    view.csrf_exempt = True

    assert legacy_alias(view)("request", external_id="REQ-1") == "served"
    assert calls == [{"external_id": "REQ-1"}]

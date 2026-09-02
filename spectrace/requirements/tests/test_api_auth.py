"""Tests for API key enforcement across the /api/v1/ surface."""

import pytest


@pytest.fixture
def api_key(settings):
    settings.SPECTRACE_API_KEY = "test-key"
    return "test-key"


class TestReadEndpointsRequireKey:
    def test_specs_coverage__rejects_missing_key(self, client, api_key, db):
        response = client.get("/api/v1/specs/coverage/")
        assert response.status_code == 401
        assert "Authentication required" in response.json()["error"]

    def test_specs_coverage__rejects_wrong_key(self, client, api_key, db):
        response = client.get("/api/v1/specs/coverage/", headers={"X-API-Key": "wrong"})
        assert response.status_code == 401

    def test_specs_coverage__accepts_x_api_key_header(self, client, api_key, db):
        response = client.get("/api/v1/specs/coverage/", headers={"X-API-Key": api_key})
        assert response.status_code == 200

    def test_specs_coverage__accepts_bearer_header(self, client, api_key, db):
        response = client.get(
            "/api/v1/specs/coverage/", headers={"Authorization": f"Bearer {api_key}"}
        )
        assert response.status_code == 200

    def test_tasks_list__rejects_missing_key(self, client, api_key, db):
        response = client.get("/api/v1/tasks/")
        assert response.status_code == 401

    def test_validation_runs__rejects_missing_key(self, client, api_key, db):
        response = client.get("/api/v1/results/enforcement-runs/")
        assert response.status_code == 401


class TestWriteEndpointsRequireKey:
    def test_task_claim__rejects_missing_key(self, client, api_key, db):
        response = client.post("/api/v1/tasks/T-404/claim")
        assert response.status_code == 401

    def test_detect_conflicts__rejects_missing_key(self, client, api_key, db):
        response = client.post("/api/v1/results/conflicts/detect")
        assert response.status_code == 401


class TestUnconfiguredKeyBypasses:
    def test_specs_coverage__allows_request_without_configured_key(self, client, settings, db):
        settings.SPECTRACE_API_KEY = ""
        response = client.get("/api/v1/specs/coverage/")
        assert response.status_code == 200


class TestPublicSurfaceStaysOpen:
    def test_openapi_spec__needs_no_key(self, client, api_key, db):
        response = client.get("/api/openapi.json")
        assert response.status_code == 200

    def test_swagger_ui__needs_no_key(self, client, api_key, db):
        response = client.get("/api/docs/")
        assert response.status_code == 200

    def test_landing_page__needs_no_key(self, client, api_key, db):
        response = client.get("/")
        assert response.status_code == 200

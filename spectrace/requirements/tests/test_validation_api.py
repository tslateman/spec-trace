"""Tests for validation run API endpoints."""

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from requirements.models import (
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    InAppValidationStatus,
    Requirement,
)


@pytest.fixture
def api_client():
    """Return a Django test client."""
    return Client()


@pytest.fixture
def sample_validation_data(db):
    """Create sample validation run data for testing."""
    # Create requirement
    req = Requirement.add_root(
        external_id="REQ-TEST-001",
        title="Test Requirement",
        source_file="test.md",
    )

    # Create validation
    validation = InAppValidation.objects.create(
        requirement=req,
        name="Test Validation",
        endpoint="/api/test",
        vendor="test-vendor",
    )

    # Create validation run
    run = InAppValidationRun.objects.create(source="test-source")

    # Create result with steps
    result = InAppValidationResult.objects.create(
        validation_run=run,
        validation=validation,
        status=InAppValidationStatus.SUCCESS,
        message="All passed",
        checked_at=timezone.now(),
        steps=[
            {"name": "Step 1", "passed": True, "details": "OK"},
            {"name": "Step 2", "passed": True, "details": "OK"},
        ],
        context={"vendor": "test-vendor", "feature_flags": {"flag1": True}},
    )

    return {"requirement": req, "validation": validation, "run": run, "result": result}


class TestListValidationRuns:
    """Tests for list validation runs endpoint."""

    def test_list_validation_runs__returns_runs(self, api_client, sample_validation_data):
        """Returns list of validation runs."""
        response = api_client.get(reverse("api-validation-runs"))

        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert "pagination" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["source"] == "test-source"

    def test_list_validation_runs__filter_by_requirement(self, api_client, sample_validation_data):
        """Filters by requirement_id."""
        response = api_client.get(
            reverse("api-validation-runs"), {"requirement_id": "REQ-TEST-001"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 1

        # Non-existent requirement
        response = api_client.get(reverse("api-validation-runs"), {"requirement_id": "NONEXISTENT"})
        data = response.json()
        assert len(data["runs"]) == 0

    def test_list_validation_runs__filter_by_vendor(self, api_client, sample_validation_data):
        """Filters by vendor."""
        response = api_client.get(reverse("api-validation-runs"), {"vendor": "test-vendor"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 1

    def test_list_validation_runs__filter_by_status(self, api_client, sample_validation_data):
        """Filters by status."""
        response = api_client.get(reverse("api-validation-runs"), {"status": "success"})

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 1

        response = api_client.get(reverse("api-validation-runs"), {"status": "failure"})
        data = response.json()
        assert len(data["runs"]) == 0

    def test_list_validation_runs__pagination(self, api_client, db):
        """Pagination works correctly."""
        # Create multiple runs
        for i in range(5):
            InAppValidationRun.objects.create(source=f"source-{i}")

        response = api_client.get(reverse("api-validation-runs"), {"page": 1, "per_page": 2})

        data = response.json()
        assert len(data["runs"]) == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["total_pages"] == 3
        assert data["pagination"]["has_next"] is True

    def test_list_validation_runs__empty_list(self, api_client, db):
        """Returns empty list when no runs exist."""
        response = api_client.get(reverse("api-validation-runs"))

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 0
        assert data["pagination"]["total"] == 0


class TestGetValidationRun:
    """Tests for get validation run detail endpoint."""

    def test_get_validation_run__returns_detail(self, api_client, sample_validation_data):
        """Returns run detail with results."""
        run_id = sample_validation_data["run"].id
        response = api_client.get(reverse("api-validation-run-detail", kwargs={"run_id": run_id}))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == run_id
        assert data["source"] == "test-source"
        assert len(data["results"]) == 1
        assert data["results"][0]["validation_name"] == "Test Validation"
        assert data["results"][0]["step_count"] == 2
        assert data["results"][0]["steps_passed"] == 2

    def test_get_validation_run__not_found(self, api_client, db):
        """Returns 404 for non-existent run."""
        response = api_client.get(reverse("api-validation-run-detail", kwargs={"run_id": 99999}))

        assert response.status_code == 404


class TestGetValidationRunSteps:
    """Tests for get validation run steps endpoint."""

    def test_get_validation_run_steps__returns_steps(self, api_client, sample_validation_data):
        """Returns step-level detail."""
        run_id = sample_validation_data["run"].id
        response = api_client.get(reverse("api-validation-run-steps", kwargs={"run_id": run_id}))

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert len(data["results"]) == 1
        assert len(data["results"][0]["steps"]) == 2
        assert data["results"][0]["context"]["vendor"] == "test-vendor"

    def test_get_validation_run_steps__filter_by_result(self, api_client, sample_validation_data):
        """Filters to specific result."""
        run_id = sample_validation_data["run"].id
        result_id = sample_validation_data["result"].id
        response = api_client.get(
            reverse("api-validation-run-steps", kwargs={"run_id": run_id}),
            {"result_id": result_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1

    def test_get_validation_run_steps__not_found(self, api_client, db):
        """Returns 404 for non-existent run."""
        response = api_client.get(reverse("api-validation-run-steps", kwargs={"run_id": 99999}))

        assert response.status_code == 404

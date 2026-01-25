---
phase: 14
plan: 01
title: Validation Run API Endpoints
wave: 1
depends_on: []
files_modified:
  - spectrace/requirements/api.py (MODIFIED)
  - spectrace/spectrace/urls.py (MODIFIED)
  - spectrace/requirements/tests/test_validation_api.py (NEW)
autonomous: true
---

# Plan 01: Validation Run API Endpoints

## Goal

Create JSON API endpoints for querying validation run data to enable custom UI development.

## must_haves

- [ ] GET `/api/validation-runs/` — list runs with pagination
- [ ] Filtering by requirement_id, vendor, status, date range
- [ ] GET `/api/validation-runs/<id>/` — detail with results
- [ ] GET `/api/validation-runs/<id>/steps/` — step-level detail
- [ ] Proper error responses (404, 400)

## Tasks

<task id="1">
Add validation run list endpoint to `spectrace/requirements/api.py`:

```python
@require_http_methods(["GET"])
def list_validation_runs(request):
    """List validation runs with filtering and pagination.

    GET /api/validation-runs/

    Query parameters:
        page: Page number (default: 1)
        per_page: Items per page (default: 20, max: 100)
        requirement_id: Filter by requirement external_id
        vendor: Filter by vendor name
        status: Filter by status (success, failure, unknown)
        start_date: Filter runs after this date (ISO format)
        end_date: Filter runs before this date (ISO format)

    Response:
    {
        "runs": [
            {
                "id": 1,
                "source": "production-app",
                "imported_at": "2024-01-15T10:30:00Z",
                "total_validations": 10,
                "successful": 8,
                "failed": 2
            },
            ...
        ],
        "pagination": {
            "page": 1,
            "per_page": 20,
            "total": 50,
            "total_pages": 3,
            "has_next": true,
            "has_prev": false
        }
    }
    """
    # Parse pagination
    page = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 20)), 100)

    # Build queryset with filters
    queryset = InAppValidationRun.objects.prefetch_related('results__validation__requirement')

    # Filter by requirement_id
    requirement_id = request.GET.get('requirement_id')
    if requirement_id:
        queryset = queryset.filter(results__validation__requirement__external_id=requirement_id).distinct()

    # Filter by vendor
    vendor = request.GET.get('vendor')
    if vendor:
        queryset = queryset.filter(results__validation__vendor=vendor).distinct()

    # Filter by status
    status = request.GET.get('status')
    if status:
        queryset = queryset.filter(results__status=status).distinct()

    # Filter by date range
    start_date = request.GET.get('start_date')
    if start_date:
        parsed_start = parse_datetime(start_date)
        if parsed_start:
            queryset = queryset.filter(imported_at__gte=parsed_start)

    end_date = request.GET.get('end_date')
    if end_date:
        parsed_end = parse_datetime(end_date)
        if parsed_end:
            queryset = queryset.filter(imported_at__lte=parsed_end)

    # Order by newest first
    queryset = queryset.order_by('-imported_at')

    # Paginate
    total = queryset.count()
    total_pages = (total + per_page - 1) // per_page
    offset = (page - 1) * per_page
    runs = queryset[offset:offset + per_page]

    # Serialize
    runs_data = []
    for run in runs:
        runs_data.append({
            'id': run.id,
            'source': run.source,
            'imported_at': run.imported_at.isoformat(),
            'total_validations': run.total_validations,
            'successful': run.successful,
            'failed': run.failed,
        })

    return JsonResponse({
        'runs': runs_data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        },
    })
```
</task>

<task id="2">
Add validation run detail endpoint to `spectrace/requirements/api.py`:

```python
@require_http_methods(["GET"])
def get_validation_run(request, run_id):
    """Get validation run detail with all results.

    GET /api/validation-runs/<id>/

    Response:
    {
        "id": 1,
        "source": "production-app",
        "imported_at": "2024-01-15T10:30:00Z",
        "total_validations": 10,
        "successful": 8,
        "failed": 2,
        "results": [
            {
                "id": 1,
                "validation_id": 5,
                "validation_name": "Login Flow Check",
                "requirement_id": "REQ-AUTH-001",
                "vendor": "acme",
                "status": "success",
                "message": "All checks passed",
                "checked_at": "2024-01-15T10:30:00Z",
                "step_count": 3,
                "steps_passed": 3
            },
            ...
        ]
    }
    """
    try:
        run = InAppValidationRun.objects.prefetch_related(
            'results__validation__requirement'
        ).get(id=run_id)
    except InAppValidationRun.DoesNotExist:
        return JsonResponse({'error': 'Validation run not found'}, status=404)

    results_data = []
    for result in run.results.all():
        steps = result.steps or []
        results_data.append({
            'id': result.id,
            'validation_id': result.validation.id,
            'validation_name': result.validation.name,
            'requirement_id': result.validation.requirement.external_id,
            'vendor': result.validation.vendor,
            'status': result.status,
            'message': result.message,
            'checked_at': result.checked_at.isoformat(),
            'step_count': len(steps),
            'steps_passed': sum(1 for s in steps if s.get('passed')),
        })

    return JsonResponse({
        'id': run.id,
        'source': run.source,
        'imported_at': run.imported_at.isoformat(),
        'total_validations': run.total_validations,
        'successful': run.successful,
        'failed': run.failed,
        'results': results_data,
    })
```
</task>

<task id="3">
Add validation run steps endpoint to `spectrace/requirements/api.py`:

```python
@require_http_methods(["GET"])
def get_validation_run_steps(request, run_id):
    """Get step-level detail for a validation run.

    GET /api/validation-runs/<id>/steps/

    Query parameters:
        result_id: Filter to specific result (optional)

    Response:
    {
        "run_id": 1,
        "results": [
            {
                "result_id": 1,
                "validation_name": "Login Flow Check",
                "requirement_id": "REQ-AUTH-001",
                "status": "success",
                "steps": [
                    {
                        "name": "Check login form",
                        "passed": true,
                        "details": "Form rendered correctly",
                        "duration_ms": 50
                    },
                    ...
                ],
                "context": {
                    "vendor": "acme",
                    "feature_flags": {"new_ui": true},
                    "environment": "production"
                }
            },
            ...
        ]
    }
    """
    try:
        run = InAppValidationRun.objects.prefetch_related(
            'results__validation__requirement'
        ).get(id=run_id)
    except InAppValidationRun.DoesNotExist:
        return JsonResponse({'error': 'Validation run not found'}, status=404)

    # Optional filter to specific result
    result_id = request.GET.get('result_id')
    results = run.results.all()
    if result_id:
        results = results.filter(id=result_id)

    results_data = []
    for result in results:
        results_data.append({
            'result_id': result.id,
            'validation_name': result.validation.name,
            'requirement_id': result.validation.requirement.external_id,
            'status': result.status,
            'steps': result.steps or [],
            'context': result.context or {},
        })

    return JsonResponse({
        'run_id': run.id,
        'results': results_data,
    })
```
</task>

<task id="4">
Add URL routes to `spectrace/spectrace/urls.py`:

```python
# Add to imports
from requirements.api import (
    # existing imports...
    list_validation_runs,
    get_validation_run,
    get_validation_run_steps,
)

# Add to urlpatterns
path('api/validation-runs/', list_validation_runs, name='api-validation-runs'),
path('api/validation-runs/<int:run_id>/', get_validation_run, name='api-validation-run-detail'),
path('api/validation-runs/<int:run_id>/steps/', get_validation_run_steps, name='api-validation-run-steps'),
```
</task>

<task id="5">
Create tests at `spectrace/requirements/tests/test_validation_api.py`:

```python
"""Tests for validation run API endpoints."""
import json
from datetime import timedelta

from django.test import Client
from django.urls import reverse
from django.utils import timezone

import pytest

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
        response = api_client.get(
            reverse("api-validation-runs"), {"requirement_id": "NONEXISTENT"}
        )
        data = response.json()
        assert len(data["runs"]) == 0

    def test_list_validation_runs__filter_by_vendor(self, api_client, sample_validation_data):
        """Filters by vendor."""
        response = api_client.get(
            reverse("api-validation-runs"), {"vendor": "test-vendor"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 1

    def test_list_validation_runs__filter_by_status(self, api_client, sample_validation_data):
        """Filters by status."""
        response = api_client.get(
            reverse("api-validation-runs"), {"status": "success"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 1

        response = api_client.get(
            reverse("api-validation-runs"), {"status": "failure"}
        )
        data = response.json()
        assert len(data["runs"]) == 0

    def test_list_validation_runs__pagination(self, api_client, db):
        """Pagination works correctly."""
        # Create multiple runs
        for i in range(5):
            InAppValidationRun.objects.create(source=f"source-{i}")

        response = api_client.get(
            reverse("api-validation-runs"), {"page": 1, "per_page": 2}
        )

        data = response.json()
        assert len(data["runs"]) == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["total_pages"] == 3
        assert data["pagination"]["has_next"] is True


class TestGetValidationRun:
    """Tests for get validation run detail endpoint."""

    def test_get_validation_run__returns_detail(self, api_client, sample_validation_data):
        """Returns run detail with results."""
        run_id = sample_validation_data["run"].id
        response = api_client.get(
            reverse("api-validation-run-detail", kwargs={"run_id": run_id})
        )

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
        response = api_client.get(
            reverse("api-validation-run-detail", kwargs={"run_id": 99999})
        )

        assert response.status_code == 404


class TestGetValidationRunSteps:
    """Tests for get validation run steps endpoint."""

    def test_get_validation_run_steps__returns_steps(self, api_client, sample_validation_data):
        """Returns step-level detail."""
        run_id = sample_validation_data["run"].id
        response = api_client.get(
            reverse("api-validation-run-steps", kwargs={"run_id": run_id})
        )

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
        response = api_client.get(
            reverse("api-validation-run-steps", kwargs={"run_id": 99999})
        )

        assert response.status_code == 404
```
</task>

<task id="6">
Run tests to verify:

```bash
python -m pytest spectrace/requirements/tests/test_validation_api.py -v
```
</task>

## Verification

- [ ] GET `/api/validation-runs/` returns paginated list
- [ ] Filtering by requirement_id, vendor, status works
- [ ] Date range filtering works
- [ ] GET `/api/validation-runs/<id>/` returns detail with results
- [ ] GET `/api/validation-runs/<id>/steps/` returns step-level detail
- [ ] 404 returned for non-existent runs
- [ ] All tests pass

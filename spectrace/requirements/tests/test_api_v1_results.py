"""Tests for API v1 results endpoints (enforcement runs + conflicts)."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from requirements.models import (
    ConflictConfidence,
    ConflictLog,
    ConflictPattern,
    InAppValidationRun,
    Requirement,
)

# ============================================================================
# Local Fixtures
# ============================================================================


@pytest.fixture
def sample_requirement_b(db):
    """Create a second requirement for conflict pairs."""
    return Requirement.add_root(
        external_id="REQ-TEST-002",
        title="Second Test Requirement",
        status="active",
        source_file="test.md",
    )


@pytest.fixture
def validation_run(db):
    """Create an InAppValidationRun for enforcement run tests."""
    return InAppValidationRun.objects.create(source="ci-pipeline")


@pytest.fixture
def sample_conflict(db, sample_requirement, sample_requirement_b):
    """Create an unresolved conflict between two requirements."""
    return ConflictLog.objects.create(
        requirement_a=sample_requirement,
        requirement_b=sample_requirement_b,
        pattern=ConflictPattern.MUTUAL_EXCLUSION,
        confidence=ConflictConfidence.HIGH,
        details={"correlation": -0.85},
        resolved=False,
    )


@pytest.fixture
def resolved_conflict(db, sample_requirement, sample_requirement_b):
    """Create an already-resolved conflict."""
    return ConflictLog.objects.create(
        requirement_a=sample_requirement,
        requirement_b=sample_requirement_b,
        pattern=ConflictPattern.CODE_OVERLAP,
        confidence=ConflictConfidence.MEDIUM,
        details={},
        resolved=True,
        resolved_at=timezone.now(),
        resolution_notes="Resolved by refactoring shared module",
    )


# ============================================================================
# GET /api/v1/results/enforcement-runs/latest/
# ============================================================================


@pytest.mark.django_db
@patch("requirements.api_v1.get_validation_runs_data", autospec=True)
def test_latest_run__returns_latest(mock_get_runs, client):
    mock_get_runs.return_value = {
        "runs": [
            {
                "id": 1,
                "source": "ci-pipeline",
                "imported_at": datetime(2026, 1, 15, 12, 0, 0),
                "total": 10,
                "success": 8,
                "failure": 2,
                "pass_rate": 80.0,
            }
        ],
        "pagination": {},
        "summary": {},
    }

    resp = client.get("/api/v1/results/enforcement-runs/latest/")
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["run_id"] == 1
    assert data["source"] == "ci-pipeline"
    assert data["pass_rate"] == 80.0
    assert data["total"] == 10
    assert data["passed"] == 8
    assert data["failed"] == 2
    assert "imported_at" in data
    mock_get_runs.assert_called_once_with(page=1, per_page=1, filters={})


@pytest.mark.django_db
@patch("requirements.api_v1.get_validation_runs_data", autospec=True)
def test_latest_run__returns_404_when_empty(mock_get_runs, client):
    mock_get_runs.return_value = {
        "runs": [],
        "pagination": {},
        "summary": {},
    }

    resp = client.get("/api/v1/results/enforcement-runs/latest/")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"


@pytest.mark.django_db
@patch("requirements.api_v1.get_validation_runs_data", autospec=True)
def test_latest_run__filters_by_source(mock_get_runs, client):
    mock_get_runs.return_value = {
        "runs": [
            {
                "id": 5,
                "source": "staging",
                "imported_at": datetime(2026, 2, 1, 10, 0, 0),
                "total": 20,
                "success": 20,
                "failure": 0,
                "pass_rate": 100.0,
            }
        ],
        "pagination": {},
        "summary": {},
    }

    resp = client.get("/api/v1/results/enforcement-runs/latest/", {"source": "staging"})
    assert resp.status_code == 200
    mock_get_runs.assert_called_once_with(page=1, per_page=1, filters={"source": "staging"})


# ============================================================================
# GET /api/v1/results/enforcement-runs/{run_id}/diff/
# ============================================================================


@pytest.mark.django_db
@patch("requirements.api_v1.build_run_comparison", autospec=True)
@patch("requirements.api_v1.get_adjacent_runs", autospec=True)
def test_run_diff__returns_comparison(mock_adjacent, mock_comparison, client, validation_run):
    prev_run = MagicMock()
    mock_adjacent.return_value = {"previous": prev_run, "next": None}
    mock_comparison.return_value = {
        "run_a": {
            "id": 1,
            "source": "old-pipeline",
            "imported_at": datetime(2026, 1, 10, 8, 0, 0),
        },
        "run_b": {
            "id": validation_run.id,
            "source": "ci-pipeline",
            "imported_at": datetime(2026, 1, 15, 12, 0, 0),
        },
        "changes": [
            {
                "requirement_id": "REQ-001",
                "validation_name": "Check login",
                "vendor": "Acme",
                "status_a": "failure",
                "status_b": "success",
                "change_type": "improved",
            }
        ],
        "summary": {
            "improved": 1,
            "regressed": 0,
            "unchanged": 0,
            "new": 0,
            "removed": 0,
        },
    }

    resp = client.get(f"/api/v1/results/enforcement-runs/{validation_run.id}/diff/")
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["compared_to"]["id"] == 1
    assert data["compared_to"]["source"] == "old-pipeline"
    assert data["summary"]["improved"] == 1
    assert len(data["changes"]) == 1
    assert data["changes"][0]["change_type"] == "improved"
    mock_adjacent.assert_called_once_with(validation_run)
    mock_comparison.assert_called_once_with(prev_run, validation_run)


@pytest.mark.django_db
def test_run_diff__returns_404_for_unknown_run(client):
    resp = client.get("/api/v1/results/enforcement-runs/99999/diff/")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"


@pytest.mark.django_db
@patch("requirements.api_v1.get_adjacent_runs", autospec=True)
def test_run_diff__returns_409_when_no_predecessor(mock_adjacent, client, validation_run):
    mock_adjacent.return_value = {"previous": None, "next": None}

    resp = client.get(f"/api/v1/results/enforcement-runs/{validation_run.id}/diff/")
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "no_predecessor"


# ============================================================================
# GET /api/v1/results/conflicts/
# ============================================================================


@pytest.mark.django_db
def test_list_conflicts__returns_empty_list(client):
    resp = client.get("/api/v1/results/conflicts/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["meta"] == {"limit": 25, "offset": 0, "total": 0}


@pytest.mark.django_db
def test_list_conflicts__returns_conflicts_with_meta(client, sample_conflict):
    resp = client.get("/api/v1/results/conflicts/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 1
    conflict = body["data"][0]
    assert conflict["id"] == sample_conflict.id
    assert conflict["requirement_a"] == "REQ-TEST-001"
    assert conflict["requirement_b"] == "REQ-TEST-002"
    assert conflict["pattern"] == ConflictPattern.MUTUAL_EXCLUSION
    assert conflict["confidence"] == ConflictConfidence.HIGH
    assert conflict["resolved"] is False
    assert "created_at" in conflict


@pytest.mark.django_db
def test_list_conflicts__filters_by_confidence(client, sample_conflict):
    resp = client.get("/api/v1/results/conflicts/", {"confidence": "high"})
    body = resp.json()
    assert body["meta"]["total"] == 1

    resp2 = client.get("/api/v1/results/conflicts/", {"confidence": "low"})
    body2 = resp2.json()
    assert body2["meta"]["total"] == 0


@pytest.mark.django_db
def test_list_conflicts__filters_by_pattern(client, sample_conflict):
    resp = client.get("/api/v1/results/conflicts/", {"pattern": "mutual_exclusion"})
    body = resp.json()
    assert body["meta"]["total"] == 1

    resp2 = client.get("/api/v1/results/conflicts/", {"pattern": "code_overlap"})
    body2 = resp2.json()
    assert body2["meta"]["total"] == 0


@pytest.mark.django_db
def test_list_conflicts__filters_by_resolved(client, sample_conflict, resolved_conflict):
    resp_unresolved = client.get("/api/v1/results/conflicts/", {"resolved": "false"})
    body_unresolved = resp_unresolved.json()
    assert body_unresolved["meta"]["total"] == 1
    assert body_unresolved["data"][0]["id"] == sample_conflict.id

    resp_resolved = client.get("/api/v1/results/conflicts/", {"resolved": "true"})
    body_resolved = resp_resolved.json()
    assert body_resolved["meta"]["total"] == 1
    assert body_resolved["data"][0]["id"] == resolved_conflict.id


@pytest.mark.django_db
def test_list_conflicts__filters_by_requirement_id(client, sample_conflict):
    resp = client.get("/api/v1/results/conflicts/", {"requirement_id": "REQ-TEST-001"})
    body = resp.json()
    assert body["meta"]["total"] == 1

    resp2 = client.get("/api/v1/results/conflicts/", {"requirement_id": "REQ-NONE"})
    body2 = resp2.json()
    assert body2["meta"]["total"] == 0


@pytest.mark.django_db
def test_list_conflicts__respects_limit_and_offset(client, sample_conflict, resolved_conflict):
    resp = client.get("/api/v1/results/conflicts/", {"limit": "1", "offset": "0"})
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["meta"]["limit"] == 1
    assert body["meta"]["offset"] == 0
    assert body["meta"]["total"] == 2

    resp2 = client.get("/api/v1/results/conflicts/", {"limit": "1", "offset": "1"})
    body2 = resp2.json()
    assert len(body2["data"]) == 1
    assert body["data"][0]["id"] != body2["data"][0]["id"]


@pytest.mark.django_db
def test_list_conflicts__rejects_invalid_limit(client):
    resp = client.get("/api/v1/results/conflicts/", {"limit": "abc"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_query_param"


@pytest.mark.django_db
def test_list_conflicts__rejects_invalid_offset(client):
    resp = client.get("/api/v1/results/conflicts/", {"offset": "xyz"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_query_param"


# ============================================================================
# POST /api/v1/results/conflicts/detect
# ============================================================================


@pytest.mark.django_db
@patch("requirements.services.conflict_detector.ConflictDetector", autospec=True)
def test_detect_conflicts__returns_results(mock_detector_cls, client):
    mock_detector = mock_detector_cls.return_value
    mock_detector.detect_mutual_exclusion.return_value = ["conflict1", "conflict2"]
    mock_detector.detect_all_structured_conflicts.return_value = ["conflict3"]
    mock_detector.log_conflicts.return_value = {"created_count": 2, "skipped_count": 1}

    resp = client.post(
        "/api/v1/results/conflicts/detect",
        json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["conflicts_found"] == 3
    assert data["logged"] == 2
    assert data["skipped_existing"] == 1
    mock_detector_cls.assert_called_once_with(min_runs=10, min_overlap=5)


@pytest.mark.django_db
@patch("requirements.services.conflict_detector.ConflictDetector", autospec=True)
def test_detect_conflicts__passes_custom_params(mock_detector_cls, client):
    mock_detector = mock_detector_cls.return_value
    mock_detector.detect_mutual_exclusion.return_value = []
    mock_detector.detect_all_structured_conflicts.return_value = []
    mock_detector.log_conflicts.return_value = {"created_count": 0, "skipped_count": 0}

    resp = client.post(
        "/api/v1/results/conflicts/detect",
        json.dumps({"min_runs": 20, "min_overlap": 10, "include_structured": True}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_detector_cls.assert_called_once_with(min_runs=20, min_overlap=10)


@pytest.mark.django_db
@patch("requirements.services.conflict_detector.ConflictDetector", autospec=True)
def test_detect_conflicts__excludes_structured_when_false(mock_detector_cls, client):
    mock_detector = mock_detector_cls.return_value
    mock_detector.detect_mutual_exclusion.return_value = ["conflict1"]
    mock_detector.log_conflicts.return_value = {"created_count": 1, "skipped_count": 0}

    resp = client.post(
        "/api/v1/results/conflicts/detect",
        json.dumps({"include_structured": False}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["conflicts_found"] == 1
    mock_detector.detect_all_structured_conflicts.assert_not_called()


@pytest.mark.django_db
def test_detect_conflicts__rejects_invalid_json(client):
    resp = client.post(
        "/api/v1/results/conflicts/detect",
        "not json",
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_json"


@pytest.mark.django_db
@patch("requirements.services.conflict_detector.ConflictDetector", autospec=True)
def test_detect_conflicts__handles_empty_body(mock_detector_cls, client):
    mock_detector = mock_detector_cls.return_value
    mock_detector.detect_mutual_exclusion.return_value = []
    mock_detector.detect_all_structured_conflicts.return_value = []
    mock_detector.log_conflicts.return_value = {"created_count": 0, "skipped_count": 0}

    resp = client.post(
        "/api/v1/results/conflicts/detect",
        "",
        content_type="application/json",
    )
    assert resp.status_code == 200
    mock_detector_cls.assert_called_once_with(min_runs=10, min_overlap=5)


# ============================================================================
# GET /api/v1/results/conflicts/{conflict_id}
# ============================================================================


@pytest.mark.django_db
def test_get_conflict__returns_detail(client, sample_conflict):
    resp = client.get(f"/api/v1/results/conflicts/{sample_conflict.id}")
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["id"] == sample_conflict.id
    assert data["requirement_a"] == "REQ-TEST-001"
    assert data["requirement_b"] == "REQ-TEST-002"
    assert data["requirement_a_title"] == "Test Requirement"
    assert data["requirement_b_title"] == "Second Test Requirement"
    assert data["pattern"] == ConflictPattern.MUTUAL_EXCLUSION
    assert data["confidence"] == ConflictConfidence.HIGH
    assert data["details"] == {"correlation": -0.85}
    assert data["resolved"] is False
    assert data["resolved_at"] is None
    assert data["resolution_notes"] == ""
    assert "created_at" in data


@pytest.mark.django_db
def test_get_conflict__returns_404_for_unknown(client):
    resp = client.get("/api/v1/results/conflicts/99999")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"


# ============================================================================
# POST /api/v1/results/conflicts/{conflict_id}/resolve
# ============================================================================


@pytest.mark.django_db
def test_resolve_conflict__marks_resolved(client, sample_conflict):
    resp = client.post(
        f"/api/v1/results/conflicts/{sample_conflict.id}/resolve",
        json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert data["conflict_id"] == sample_conflict.id
    assert "resolved_at" in data

    sample_conflict.refresh_from_db()
    assert sample_conflict.resolved is True


@pytest.mark.django_db
def test_resolve_conflict__saves_resolution_notes(client, sample_conflict):
    resp = client.post(
        f"/api/v1/results/conflicts/{sample_conflict.id}/resolve",
        json.dumps({"resolution_notes": "Duplicate requirement removed"}),
        content_type="application/json",
    )
    assert resp.status_code == 200

    sample_conflict.refresh_from_db()
    assert sample_conflict.resolved is True
    assert sample_conflict.resolution_notes == "Duplicate requirement removed"


@pytest.mark.django_db
def test_resolve_conflict__returns_404_for_unknown(client):
    resp = client.post(
        "/api/v1/results/conflicts/99999/resolve",
        json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_resolve_conflict__rejects_already_resolved(client, resolved_conflict):
    resp = client.post(
        f"/api/v1/results/conflicts/{resolved_conflict.id}/resolve",
        json.dumps({}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_state"


@pytest.mark.django_db
def test_resolve_conflict__rejects_invalid_json(client, sample_conflict):
    resp = client.post(
        f"/api/v1/results/conflicts/{sample_conflict.id}/resolve",
        "not json",
        content_type="application/json",
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_json"


@pytest.mark.django_db
def test_resolve_conflict__handles_empty_body(client, sample_conflict):
    resp = client.post(
        f"/api/v1/results/conflicts/{sample_conflict.id}/resolve",
        "",
        content_type="application/json",
    )
    assert resp.status_code == 200

    sample_conflict.refresh_from_db()
    assert sample_conflict.resolved is True
    assert sample_conflict.resolution_notes == ""

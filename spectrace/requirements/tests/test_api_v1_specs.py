"""Tests for API v1 spec endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from requirements.models import (
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    InAppValidationStatus,
    Requirement,
    TestRequirementLink,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def requirement_with_fret(db):
    """Requirement with all FRET fields populated."""
    return Requirement.add_root(
        external_id="REQ-FRET-001",
        title="FRET Requirement",
        status="active",
        source_file="fret.md",
        scope="When the system is online",
        condition="If the user is authenticated",
        component="AuthService",
        timing="Within 500ms",
        response="shall return a valid token",
    )


@pytest.fixture
def requirement_with_test_links(db, sample_requirement):
    """Requirement with associated TestRequirementLink records."""
    TestRequirementLink.objects.create(
        test_nodeid="tests/test_auth.py::test_login",
        requirement=sample_requirement,
        last_status="passed",
    )
    TestRequirementLink.objects.create(
        test_nodeid="tests/test_auth.py::test_logout",
        requirement=sample_requirement,
        last_status="failed",
    )
    return sample_requirement


@pytest.fixture
def requirement_with_validation(db, sample_requirement):
    """Requirement with InAppValidation and results (regression scenario)."""
    validation = InAppValidation.objects.create(
        requirement=sample_requirement,
        name="Verify Login Flow",
        endpoint="/api/login/verify",
        vendor="Opera",
    )
    run = InAppValidationRun.objects.create(source="test-import")
    checked = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Previous result: success
    InAppValidationResult.objects.create(
        validation_run=run,
        validation=validation,
        status=InAppValidationStatus.SUCCESS,
        message="All checks passed",
        checked_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
        steps=[{"name": "step1", "passed": True}],
    )
    # Current result: failure (regression)
    InAppValidationResult.objects.create(
        validation_run=run,
        validation=validation,
        status=InAppValidationStatus.FAILURE,
        message="Login timeout",
        checked_at=checked,
        steps=[
            {"name": "step1", "passed": True},
            {"name": "step2", "passed": False},
        ],
    )
    return sample_requirement, validation


# ============================================================================
# TestSpecContextV1
# ============================================================================


@pytest.mark.django_db
def test_spec_context__returns_requirement_details(client, sample_requirement):
    resp = client.get("/api/v1/specs/REQ-TEST-001/context")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["external_id"] == "REQ-TEST-001"
    assert data["title"] == "Test Requirement"
    assert data["status"] == "active"
    assert data["test_results"] == []
    assert data["depends_on"] == []
    assert data["depended_by"] == []


@pytest.mark.django_db
def test_spec_context__includes_test_results(client, requirement_with_test_links):
    resp = client.get("/api/v1/specs/REQ-TEST-001/context")
    assert resp.status_code == 200

    results = resp.json()["data"]["test_results"]
    assert len(results) == 2
    nodeids = [r["test_nodeid"] for r in results]
    assert "tests/test_auth.py::test_login" in nodeids
    assert "tests/test_auth.py::test_logout" in nodeids


@pytest.mark.django_db
def test_spec_context__includes_dependencies(client, db):
    parent = Requirement.add_root(
        external_id="REQ-PARENT",
        title="Parent",
        status="active",
        source_file="test.md",
    )
    child = Requirement.add_root(
        external_id="REQ-CHILD",
        title="Child",
        status="active",
        source_file="test.md",
    )
    child.depends_on.add(parent)

    resp = client.get("/api/v1/specs/REQ-CHILD/context")
    data = resp.json()["data"]
    assert data["depends_on"] == ["REQ-PARENT"]
    assert data["depended_by"] == []

    resp = client.get("/api/v1/specs/REQ-PARENT/context")
    data = resp.json()["data"]
    assert data["depends_on"] == []
    assert data["depended_by"] == ["REQ-CHILD"]


@pytest.mark.django_db
def test_spec_context__includes_fret_fields(client, requirement_with_fret):
    resp = client.get("/api/v1/specs/REQ-FRET-001/context")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert "fret" in data
    fret = data["fret"]
    assert fret["scope"] == "When the system is online"
    assert fret["condition"] == "If the user is authenticated"
    assert fret["component"] == "AuthService"
    assert fret["timing"] == "Within 500ms"
    assert fret["response"] == "shall return a valid token"


@pytest.mark.django_db
def test_spec_context__omits_fret_when_empty(client, sample_requirement):
    resp = client.get("/api/v1/specs/REQ-TEST-001/context")
    assert resp.status_code == 200
    assert "fret" not in resp.json()["data"]


@pytest.mark.django_db
def test_spec_context__returns_404_for_unknown(client, db):
    resp = client.get("/api/v1/specs/REQ-NOPE/context")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


# ============================================================================
# TestSpecsCoverageV1
# ============================================================================


@pytest.mark.django_db
@patch("requirements.api_v1.detect_spec_drift", autospec=True)
@patch("requirements.api_v1.detect_stale_links", autospec=True)
def test_specs_coverage__returns_metrics(mock_stale, mock_drift, client, sample_requirement):
    mock_stale.return_value = MagicMock(errors=[])
    mock_drift.return_value = MagicMock(warnings=[])

    resp = client.get("/api/v1/specs/coverage/")
    assert resp.status_code == 200

    metrics = resp.json()["data"]["metrics"]
    assert metrics["total"] == 1
    assert metrics["stale"] == 0


@pytest.mark.django_db
@patch("requirements.api_v1.detect_spec_drift", autospec=True)
@patch("requirements.api_v1.detect_stale_links", autospec=True)
def test_specs_coverage__includes_stale_requirements(
    mock_stale, mock_drift, client, sample_requirement
):
    stale_error = MagicMock()
    stale_error.type = "stale_link"
    stale_error.details = {"requirement_id": "REQ-TEST-001"}
    mock_stale.return_value = MagicMock(errors=[stale_error])

    drift_warning = MagicMock()
    drift_warning.type = "spec_drift"
    drift_warning.details = {"affected_requirements": ["REQ-TEST-001"]}
    mock_drift.return_value = MagicMock(warnings=[drift_warning])

    resp = client.get("/api/v1/specs/coverage/")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["metrics"]["stale"] == 1
    assert "REQ-TEST-001" in data["stale_requirements"]


# ============================================================================
# TestSpecsDriftV1
# ============================================================================


@pytest.mark.django_db
@patch("requirements.api_v1.detect_all_drift", autospec=True)
def test_specs_drift__returns_drift_data(mock_drift, client):
    mock_drift.return_value = MagicMock(
        to_dict=MagicMock(return_value={"errors": [], "warnings": []})
    )
    resp = client.get("/api/v1/specs/drift/")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"errors": [], "warnings": []}


@pytest.mark.django_db
@patch("requirements.api_v1.detect_all_drift", autospec=True)
def test_specs_drift__accepts_custom_dirs(mock_drift, client, tmp_path):
    specs = tmp_path / "specs"
    tests = tmp_path / "tests"
    specs.mkdir()
    tests.mkdir()

    mock_drift.return_value = MagicMock(to_dict=MagicMock(return_value={"custom": True}))

    resp = client.get(f"/api/v1/specs/drift/?specs_dir={specs}&tests_dir={tests}")
    assert resp.status_code == 200

    call_kwargs = mock_drift.call_args.kwargs
    assert call_kwargs["test_directory"] == tests
    assert call_kwargs["specs_directory"] == specs


@pytest.mark.django_db
@patch("requirements.api_v1.detect_all_drift", autospec=True)
def test_specs_drift__uses_defaults_when_no_params(mock_drift, client):
    mock_drift.return_value = MagicMock(to_dict=MagicMock(return_value={}))
    resp = client.get("/api/v1/specs/drift/")
    assert resp.status_code == 200
    mock_drift.assert_called_once()


# ============================================================================
# TestSpecsImpactV1
# ============================================================================


@pytest.mark.django_db
@patch("requirements.services.impact_analyzer.ImpactAnalyzer")
def test_specs_impact__returns_impact_for_spec_id(mock_analyzer_cls, client):
    analyzer = mock_analyzer_cls.return_value
    analyzer.get_affected_tests.return_value = (
        ["tests/test_a.py::test_one"],
        {},
        {"REQ-001": ["REQ-002"]},
    )
    analyzer.compute_risk.return_value = (0.3, "low")

    resp = client.get("/api/v1/specs/impact/?spec_id=REQ-001")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["changed_requirements"] == ["REQ-001"]
    assert data["affected_tests"] == ["tests/test_a.py::test_one"]
    assert data["risk_score"] == 0.3
    assert data["risk_level"] == "low"


@pytest.mark.django_db
@patch("requirements.services.impact_analyzer.ImpactAnalyzer")
def test_specs_impact__returns_impact_for_file_path(mock_analyzer_cls, client):
    analyzer = mock_analyzer_cls.return_value
    analyzer.extract_requirement_ids.return_value = ["REQ-001"]
    analyzer.get_affected_tests.return_value = (["tests/test_b.py::test_two"], {}, {})
    analyzer.compute_risk.return_value = (0.7, "high")

    resp = client.get("/api/v1/specs/impact/?file_path=specs/auth.md")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["changed_requirements"] == ["REQ-001"]
    assert data["risk_level"] == "high"
    analyzer.extract_requirement_ids.assert_called_once_with(["specs/auth.md"], "HEAD")


@pytest.mark.django_db
def test_specs_impact__rejects_missing_params(client):
    resp = client.get("/api/v1/specs/impact/")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_query_param"


@pytest.mark.django_db
@patch("requirements.services.impact_analyzer.ImpactAnalyzer")
def test_specs_impact__returns_404_when_no_reqs_found(mock_analyzer_cls, client):
    analyzer = mock_analyzer_cls.return_value
    analyzer.extract_requirement_ids.return_value = []

    resp = client.get("/api/v1/specs/impact/?file_path=specs/empty.md")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


# ============================================================================
# TestSpecStatusV1
# ============================================================================


@pytest.mark.django_db
def test_spec_status__returns_basic_status(client, sample_requirement):
    resp = client.get("/api/v1/specs/REQ-TEST-001/status/")
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["external_id"] == "REQ-TEST-001"
    assert data["title"] == "Test Requirement"
    assert data["latest_result"] is None
    assert data["last_checked"] is None
    assert data["regression"] == {"is_regression": False}


@pytest.mark.django_db
def test_spec_status__includes_latest_result(client, requirement_with_validation):
    req, validation = requirement_with_validation

    resp = client.get("/api/v1/specs/REQ-TEST-001/status/")
    assert resp.status_code == 200

    data = resp.json()["data"]
    result = data["latest_result"]
    assert result is not None
    assert result["status"] == "failure"
    assert result["message"] == "Login timeout"
    assert result["steps_passed"] == 1
    assert result["steps_failed"] == 1


@pytest.mark.django_db
def test_spec_status__detects_regression(client, requirement_with_validation):
    req, validation = requirement_with_validation

    resp = client.get("/api/v1/specs/REQ-TEST-001/status/")
    assert resp.status_code == 200

    regression = resp.json()["data"]["regression"]
    assert regression["is_regression"] is True
    assert regression["previous_status"] == "success"
    assert regression["regressed_at"] is not None


@pytest.mark.django_db
def test_spec_status__returns_404_for_unknown(client, db):
    resp = client.get("/api/v1/specs/REQ-NOPE/status/")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"

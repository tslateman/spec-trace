"""Tests for API endpoints."""
import json

import pytest
from django.test import Client

from requirements.models import (
    InAppValidation,
    InAppValidationRun,
    Requirement,
    SLO,
    SLOStatus,
)


@pytest.fixture
def client():
    """Django test client."""
    return Client()


@pytest.fixture
def sample_requirement(db):
    """Create a sample requirement."""
    return Requirement.add_root(
        external_id="REQ-TEST-001",
        title="Test Requirement",
        status="active",
        source_file="test.md",
    )


@pytest.fixture
def sample_slo(db):
    """Create a sample SLO."""
    return SLO.objects.create(
        name="test-slo",
        display_name="Test SLO",
        status=SLOStatus.NOT_LINKED,
    )


class TestUpdateSLOStatusAPI:
    """Tests for POST /api/slo/status/"""

    @pytest.mark.django_db
    def test_update_slo_status_met(self, client, sample_slo):
        """Update SLO status to 'met'."""
        response = client.post(
            '/api/slo/status/',
            data=json.dumps({
                'slos': [
                    {
                        'name': 'test-slo',
                        'status': 'met',
                        'current_value': 0.9995,
                        'error_budget_remaining': 0.75,
                    }
                ]
            }),
            content_type='application/json',
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['updated'] == 1
        assert data['not_found'] == 0

        sample_slo.refresh_from_db()
        assert sample_slo.status == SLOStatus.MET

    @pytest.mark.django_db
    def test_update_slo_status_unknown_slo(self, client, db):
        """Unknown SLO name returns not_found count."""
        response = client.post(
            '/api/slo/status/',
            data=json.dumps({
                'slos': [
                    {'name': 'unknown-slo', 'status': 'met'}
                ]
            }),
            content_type='application/json',
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['updated'] == 0
        assert data['not_found'] == 1

    @pytest.mark.django_db
    def test_update_slo_status_invalid_json(self, client):
        """Invalid JSON returns 400."""
        response = client.post(
            '/api/slo/status/',
            data='not valid json',
            content_type='application/json',
        )

        assert response.status_code == 400
        assert response.json()['success'] is False

    @pytest.mark.django_db
    def test_update_slo_status_empty_slos(self, client, db):
        """Empty SLOs array returns 400."""
        response = client.post(
            '/api/slo/status/',
            data=json.dumps({'slos': []}),
            content_type='application/json',
        )

        assert response.status_code == 400
        assert response.json()['success'] is False


class TestSubmitValidationResultAPI:
    """Tests for POST /api/validation/result/"""

    @pytest.mark.django_db
    def test_submit_validation_success(self, client, sample_requirement):
        """Submit a successful validation."""
        response = client.post(
            '/api/validation/result/',
            data=json.dumps({
                'source': 'test-app',
                'validations': [
                    {
                        'requirement_id': 'REQ-TEST-001',
                        'name': 'Test Validation',
                        'status': 'success',
                        'message': 'All checks passed',
                    }
                ]
            }),
            content_type='application/json',
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['imported'] == 1
        assert data['skipped'] == 0
        assert data['created_validations'] == 1
        assert data['successful'] == 1

        # Check validation was created
        assert InAppValidation.objects.count() == 1
        assert InAppValidationRun.objects.count() == 1

    @pytest.mark.django_db
    def test_submit_validation_unknown_requirement(self, client, db):
        """Unknown requirement is skipped."""
        response = client.post(
            '/api/validation/result/',
            data=json.dumps({
                'source': 'test-app',
                'validations': [
                    {
                        'requirement_id': 'REQ-UNKNOWN',
                        'name': 'Test Validation',
                        'status': 'success',
                    }
                ]
            }),
            content_type='application/json',
        )

        assert response.status_code == 200
        data = response.json()
        assert data['imported'] == 0
        assert data['skipped'] == 1

    @pytest.mark.django_db
    def test_submit_validation_empty_list(self, client, db):
        """Empty validations array returns 400."""
        response = client.post(
            '/api/validation/result/',
            data=json.dumps({'source': 'test', 'validations': []}),
            content_type='application/json',
        )

        assert response.status_code == 400
        assert response.json()['success'] is False


class TestGetRequirementStatusAPI:
    """Tests for GET /api/requirement/{external_id}/status/"""

    @pytest.mark.django_db
    def test_get_requirement_status(self, client, sample_requirement):
        """Get status for existing requirement."""
        response = client.get('/api/requirement/REQ-TEST-001/status/')

        assert response.status_code == 200
        data = response.json()
        assert data['external_id'] == 'REQ-TEST-001'
        assert data['title'] == 'Test Requirement'
        assert 'verification_status' in data
        assert 'slo_status' in data
        assert 'linked_tests' in data

    @pytest.mark.django_db
    def test_get_requirement_status_not_found(self, client, db):
        """Unknown requirement returns 404."""
        response = client.get('/api/requirement/REQ-UNKNOWN/status/')

        assert response.status_code == 404
        assert response.json()['success'] is False

    @pytest.mark.django_db
    def test_get_requirement_with_linked_items(self, client, sample_requirement, sample_slo):
        """Requirement with linked SLO shows correct counts."""
        sample_slo.requirements.add(sample_requirement)

        response = client.get('/api/requirement/REQ-TEST-001/status/')

        data = response.json()
        assert data['linked_slos'] == 1

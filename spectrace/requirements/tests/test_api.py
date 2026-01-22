"""Tests for API endpoints."""
import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import Client

from requirements.health import TestConnectionResult, VerificationCheck
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


class TestLinearTestConnectionAPI:
    """Tests for POST /api/integrations/linear/test-connection/"""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before each test."""
        cache.clear()
        yield
        cache.clear()

    @pytest.mark.django_db
    def test_test_connection_all_checks_pass(self, client):
        """Successful connection test returns healthy status."""
        mock_result = TestConnectionResult(
            success=True,
            message="All checks passed",
            checks=[
                VerificationCheck(name="Configuration", passed=True, details="Config OK"),
                VerificationCheck(name="Authentication", passed=True, details="Auth OK"),
                VerificationCheck(name="Permissions", passed=True, details="Perms OK"),
            ]
        )

        with patch('requirements.api.verify_linear_connection', return_value=mock_result):
            response = client.post('/api/integrations/linear/test-connection/')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['status'] == 'healthy'
        assert data['cached'] is False
        assert len(data['checks']) == 3
        assert all(c['passed'] for c in data['checks'])

    @pytest.mark.django_db
    def test_test_connection_auth_fails(self, client):
        """Failed auth returns degraded status with partial checks."""
        mock_result = TestConnectionResult(
            success=False,
            message="Authentication failed",
            checks=[
                VerificationCheck(name="Configuration", passed=True, details="Config OK"),
                VerificationCheck(
                    name="Authentication",
                    passed=False,
                    error_message="HTTP 401: Authentication failed",
                    response_status=401
                ),
            ]
        )

        with patch('requirements.api.verify_linear_connection', return_value=mock_result):
            response = client.post('/api/integrations/linear/test-connection/')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert data['status'] == 'degraded'
        assert len(data['checks']) == 2
        assert data['checks'][0]['passed'] is True
        assert data['checks'][1]['passed'] is False

    @pytest.mark.django_db
    def test_test_connection_config_fails(self, client):
        """All checks fail returns unhealthy status."""
        mock_result = TestConnectionResult(
            success=False,
            message="Configuration invalid",
            checks=[
                VerificationCheck(
                    name="Configuration",
                    passed=False,
                    error_message="LINEAR_API_KEY not configured"
                ),
            ]
        )

        with patch('requirements.api.verify_linear_connection', return_value=mock_result):
            response = client.post('/api/integrations/linear/test-connection/')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert data['status'] == 'unhealthy'
        assert data['checks'][0]['error_message'] == "LINEAR_API_KEY not configured"

    @pytest.mark.django_db
    def test_test_connection_invalid_json(self, client):
        """Invalid JSON body returns 400."""
        response = client.post(
            '/api/integrations/linear/test-connection/',
            data='not valid json',
            content_type='application/json',
        )

        assert response.status_code == 400
        assert response.json()['success'] is False
        assert 'Invalid JSON' in response.json()['error']

    @pytest.mark.django_db
    def test_test_connection_uses_request_body_overrides(self, client):
        """Request body can override settings."""
        mock_result = TestConnectionResult(
            success=True,
            message="All checks passed",
            checks=[]
        )

        with patch('requirements.api.verify_linear_connection', return_value=mock_result) as mock_verify:
            response = client.post(
                '/api/integrations/linear/test-connection/',
                data=json.dumps({
                    'api_key': 'lin_api_custom',
                    'workspace': 'custom-workspace',
                    'team': 'custom-team'
                }),
                content_type='application/json',
            )

        assert response.status_code == 200
        mock_verify.assert_called_once_with('lin_api_custom', 'custom-workspace', 'custom-team')

    @pytest.mark.django_db
    def test_test_connection_caches_result(self, client):
        """Test connection result is cached."""
        mock_result = TestConnectionResult(
            success=True,
            message="All checks passed",
            checks=[]
        )

        with patch('requirements.api.verify_linear_connection', return_value=mock_result):
            client.post('/api/integrations/linear/test-connection/')

        # Check cache was populated
        from requirements.api import LINEAR_HEALTH_CACHE_KEY
        cached = cache.get(LINEAR_HEALTH_CACHE_KEY)
        assert cached is not None
        assert cached['success'] is True
        assert cached['status'] == 'healthy'


class TestLinearHealthAPI:
    """Tests for GET /api/integrations/linear/health/"""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before each test."""
        cache.clear()
        yield
        cache.clear()

    @pytest.mark.django_db
    def test_health_no_cached_result(self, client):
        """No cached result returns unknown status."""
        response = client.get('/api/integrations/linear/health/')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert data['status'] == 'unknown'
        assert data['message'] == 'No cached health check available'
        assert data['cached'] is False

    @pytest.mark.django_db
    def test_health_returns_cached_result(self, client):
        """Cached result is returned."""
        from requirements.api import LINEAR_HEALTH_CACHE_KEY

        # Manually populate cache
        cached_data = {
            'success': True,
            'message': 'All checks passed',
            'status': 'healthy',
            'checks': [{'name': 'Test', 'passed': True}],
            'error_details': None,
        }
        cache.set(LINEAR_HEALTH_CACHE_KEY, cached_data, 60)

        response = client.get('/api/integrations/linear/health/')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['status'] == 'healthy'
        assert data['cached'] is True
        assert len(data['checks']) == 1

    @pytest.mark.django_db
    def test_health_after_test_connection(self, client):
        """Health endpoint returns result from test-connection."""
        mock_result = TestConnectionResult(
            success=True,
            message="All checks passed",
            checks=[
                VerificationCheck(name="Configuration", passed=True, details="Config OK"),
            ]
        )

        with patch('requirements.api.verify_linear_connection', return_value=mock_result):
            client.post('/api/integrations/linear/test-connection/')

        # Now health should return cached result
        response = client.get('/api/integrations/linear/health/')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['status'] == 'healthy'
        assert data['cached'] is True

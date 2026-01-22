"""Tests for matrix view."""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from requirements.models import Requirement, TestResult, TestRun


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        username='admin',
        email='admin@test.com',
        password='adminpass'
    )


@pytest.fixture
def admin_client(admin_user):
    """Create an authenticated admin client."""
    client = Client()
    client.login(username='admin', password='adminpass')
    return client


@pytest.fixture
def sample_data(db):
    """Create sample requirements and test results."""
    # Create requirements
    req1 = Requirement.add_root(
        external_id="REQ-001",
        title="Login Feature",
        status="active",
        source_file="test.md",
        tags=["auth"],
        verification_status="passing",
    )
    req2 = Requirement.add_root(
        external_id="REQ-002",
        title="Dashboard Feature",
        status="active",
        source_file="test.md",
        tags=["ui"],
        verification_status="failing",
    )

    # Create test run and results
    test_run = TestRun.objects.create(
        source_file="results.xml",
        total_tests=2,
        passed=1,
        failed=1,
    )

    result1 = TestResult.objects.create(
        test_run=test_run,
        test_nodeid="tests/test_auth.py::test_login",
        name="test_login",
        classname="tests.test_auth",
        status="passed",
    )
    result1.requirements.add(req1)

    result2 = TestResult.objects.create(
        test_run=test_run,
        test_nodeid="tests/test_dashboard.py::test_view",
        name="test_view",
        classname="tests.test_dashboard",
        status="failed",
    )
    result2.requirements.add(req2)

    return {'requirements': [req1, req2], 'results': [result1, result2]}


class TestMatrixViewAccess:
    """Tests for matrix view access control."""

    def test_requires_login(self, client):
        """Unauthenticated users are redirected to login."""
        response = client.get('/admin/matrix/')
        assert response.status_code == 302
        assert '/admin/login/' in response.url or '/accounts/login/' in response.url

    @pytest.mark.django_db
    def test_staff_can_access(self, admin_client):
        """Staff users can access the matrix view."""
        response = admin_client.get('/admin/matrix/')
        assert response.status_code == 200

    @pytest.mark.django_db
    def test_renders_template(self, admin_client):
        """View renders the correct template."""
        response = admin_client.get('/admin/matrix/')
        assert 'Traceability Matrix' in response.content.decode()


class TestMatrixViewContent:
    """Tests for matrix view content."""

    @pytest.mark.django_db
    def test_shows_requirements(self, admin_client, sample_data):
        """Matrix shows requirements."""
        response = admin_client.get('/admin/matrix/')
        content = response.content.decode()

        assert 'REQ-001' in content
        assert 'REQ-002' in content

    @pytest.mark.django_db
    def test_shows_tests(self, admin_client, sample_data):
        """Matrix shows test names."""
        response = admin_client.get('/admin/matrix/')
        content = response.content.decode()

        assert 'test_login' in content
        assert 'test_view' in content

    @pytest.mark.django_db
    def test_shows_empty_state(self, admin_client):
        """Matrix shows empty state when no data."""
        response = admin_client.get('/admin/matrix/')
        content = response.content.decode()

        assert 'No requirements found' in content


class TestMatrixViewFilters:
    """Tests for matrix view filtering."""

    @pytest.mark.django_db
    def test_filter_by_status(self, admin_client, sample_data):
        """Can filter by requirement status."""
        response = admin_client.get('/admin/matrix/?status=passing')
        content = response.content.decode()

        assert 'REQ-001' in content
        assert 'REQ-002' not in content

    @pytest.mark.django_db
    def test_filter_by_tags(self, admin_client, sample_data):
        """Can filter by tags."""
        response = admin_client.get('/admin/matrix/?tags=ui')
        content = response.content.decode()

        assert 'REQ-002' in content
        assert 'REQ-001' not in content


class TestMatrixViewPagination:
    """Tests for matrix view pagination."""

    @pytest.mark.django_db
    def test_pagination_info(self, admin_client, sample_data):
        """Pagination info is displayed."""
        response = admin_client.get('/admin/matrix/')
        content = response.content.decode()

        assert 'Page 1' in content

    @pytest.mark.django_db
    def test_per_page_parameter(self, admin_client, sample_data):
        """Per page parameter is respected."""
        response = admin_client.get('/admin/matrix/?per_page=1')
        content = response.content.decode()

        # Should show pagination since we have 2 items
        assert 'Page 1 of 2' in content

    @pytest.mark.django_db
    def test_page_parameter(self, admin_client, sample_data):
        """Page parameter navigates correctly."""
        response = admin_client.get('/admin/matrix/?per_page=1&page=2')
        content = response.content.decode()

        assert 'Page 2 of 2' in content

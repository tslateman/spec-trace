"""Tests for detect_drift management command."""

import json

import pytest
from django.core.management import call_command
from io import StringIO

from requirements.models import (
    Requirement,
    TestRequirementLink,
    TestResult,
    TestRun,
)


@pytest.fixture
def requirement(db):
    """Create a basic requirement."""
    return Requirement.add_root(
        external_id='REQ-001',
        title='Test Requirement',
        status='active',
        source_file='test.md',
    )


@pytest.fixture
def test_run(db):
    """Create a test run."""
    return TestRun.objects.create(source_file='results.xml')


class TestDetectDriftCommand:
    """Tests for the detect_drift management command."""

    @pytest.mark.django_db
    def test_command__runs_all_checks(self, requirement, test_run):
        """Command runs and returns output."""
        out = StringIO()
        try:
            call_command('detect_drift', stdout=out)
        except SystemExit:
            pass  # Expected if issues found

        output = out.getvalue()
        assert 'all drift checks' in output

    @pytest.mark.django_db
    def test_command__json_format(self, requirement, test_run):
        """Command outputs valid JSON when --format json."""
        out = StringIO()
        try:
            call_command('detect_drift', '--format', 'json', stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        data = json.loads(output)
        assert 'errors' in data
        assert 'warnings' in data
        assert 'summary' in data

    @pytest.mark.django_db
    def test_command__stale_check(self, requirement, test_run):
        """Command can run specific check type."""
        # Create stale link
        TestRequirementLink.objects.create(
            test_nodeid='old_test.py::test_deleted',
            requirement=requirement,
        )
        TestResult.objects.create(
            test_run=test_run,
            test_nodeid='new_test.py::test_current',
            name='test_current',
            status='passed',
        )

        out = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command('detect_drift', '--check', 'stale', stdout=out)

        output = out.getvalue()
        # Should find stale link and exit with error
        assert exc_info.value.code == 1

    @pytest.mark.django_db
    def test_command__orphan_check(self, requirement):
        """Command detects orphan requirements."""
        out = StringIO()
        try:
            call_command('detect_drift', '--check', 'orphan', stdout=out)
        except SystemExit:
            pass

        output = out.getvalue()
        # Should find orphan requirement (active with no tests)
        assert 'orphan' in output.lower() or 'ORPHAN' in output

    @pytest.mark.django_db
    def test_command__unmarked_check_requires_path(self):
        """Unmarked check requires --tests path."""
        err = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command('detect_drift', '--check', 'unmarked', stderr=err)

        assert exc_info.value.code == 2

    @pytest.mark.django_db
    def test_command__drift_check_requires_path(self):
        """Drift check requires --specs path."""
        err = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command('detect_drift', '--check', 'drift', stderr=err)

        assert exc_info.value.code == 2

    @pytest.mark.django_db
    def test_command__with_test_directory(self, requirement, test_run, tmp_path):
        """Command runs with test directory specified."""
        test_dir = tmp_path / 'tests'
        test_dir.mkdir()

        out = StringIO()
        try:
            call_command(
                'detect_drift',
                '--check', 'unmarked',
                '--tests', str(test_dir),
                stdout=out,
            )
        except SystemExit:
            pass

        output = out.getvalue()
        assert 'unmarked' in output.lower()

    @pytest.mark.django_db
    def test_command__strict_mode(self, requirement):
        """Strict mode exits 1 on warnings."""
        # Orphan requirement will generate warning
        out = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command(
                'detect_drift',
                '--check', 'orphan',
                '--strict',
                stdout=out,
            )

        # Should exit with 1 due to warning
        assert exc_info.value.code == 1

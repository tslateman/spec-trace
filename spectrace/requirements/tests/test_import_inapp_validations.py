"""Tests for import_inapp_validations management command."""

import json
import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from requirements.models import (
    InAppValidation,
    InAppValidationResult,
    InAppValidationRun,
    InAppValidationStatus,
    Requirement,
)


@pytest.fixture
def sample_requirement(db):
    """Create a single requirement."""
    return Requirement.add_root(
        external_id="REQ-TEST-001",
        title="Test Requirement",
        status="active",
        source_file="test.md",
    )


@pytest.fixture
def valid_validations_json(sample_requirement):
    """Create a temporary JSON file with valid validation data."""
    data = {
        "source": "test-app",
        "validations": [
            {
                "requirement_id": "REQ-TEST-001",
                "name": "Verify Test Flow",
                "endpoint": "/api/test/verify",
                "status": "success",
                "message": "All checks passed",
                "checked_at": "2024-01-15T10:30:00Z",
            }
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


@pytest.fixture
def failed_validation_json(sample_requirement):
    """Create a temporary JSON file with a failed validation."""
    data = {
        "source": "test-app",
        "validations": [
            {
                "requirement_id": "REQ-TEST-001",
                "name": "Verify Failed Flow",
                "endpoint": "/api/test/verify",
                "status": "failure",
                "message": "Validation failed",
                "checked_at": "2024-01-15T10:30:00Z",
            }
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


@pytest.fixture
def unknown_requirement_json(db):
    """Create a JSON file referencing unknown requirement."""
    data = {
        "source": "test-app",
        "validations": [
            {
                "requirement_id": "REQ-UNKNOWN",
                "name": "Unknown Validation",
                "status": "success",
            }
        ],
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


@pytest.fixture
def empty_validations_json():
    """Create a JSON file with no validations."""
    data = {"source": "test-app", "validations": []}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


class TestImportInAppValidations:
    """Tests for the import_inapp_validations command."""

    @pytest.mark.django_db
    def test_import_successful_validation(self, valid_validations_json, capsys):
        """Successful validation is imported correctly."""
        call_command("import_inapp_validations", str(valid_validations_json))

        # Check run was created
        assert InAppValidationRun.objects.count() == 1
        run = InAppValidationRun.objects.first()
        assert run.source == "test-app"
        assert run.total_validations == 1
        assert run.successful == 1
        assert run.failed == 0

        # Check validation was created
        assert InAppValidation.objects.count() == 1
        validation = InAppValidation.objects.first()
        assert validation.name == "Verify Test Flow"
        assert validation.endpoint == "/api/test/verify"
        assert validation.status == InAppValidationStatus.SUCCESS

        # Check result was created
        assert InAppValidationResult.objects.count() == 1
        result = InAppValidationResult.objects.first()
        assert result.status == InAppValidationStatus.SUCCESS
        assert result.message == "All checks passed"

    @pytest.mark.django_db
    def test_import_failed_validation(self, failed_validation_json, capsys):
        """Failed validation is imported correctly."""
        call_command("import_inapp_validations", str(failed_validation_json))

        run = InAppValidationRun.objects.first()
        assert run.successful == 0
        assert run.failed == 1

        validation = InAppValidation.objects.first()
        assert validation.status == InAppValidationStatus.FAILURE

    @pytest.mark.django_db
    def test_unknown_requirement_skipped(self, unknown_requirement_json, capsys):
        """Unknown requirements are skipped with warning."""
        call_command("import_inapp_validations", str(unknown_requirement_json))

        captured = capsys.readouterr()
        assert "Requirement not found: REQ-UNKNOWN" in captured.out

        # No validation created for unknown requirement
        assert InAppValidation.objects.count() == 0

    @pytest.mark.django_db
    def test_empty_validations_warning(self, empty_validations_json, capsys):
        """Empty validations array shows warning."""
        call_command("import_inapp_validations", str(empty_validations_json))

        captured = capsys.readouterr()
        assert "No validations found" in captured.out

    def test_missing_file_error(self):
        """Non-existent file raises CommandError."""
        with pytest.raises(CommandError) as exc_info:
            call_command("import_inapp_validations", "/nonexistent/file.json")

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.django_db
    def test_multiple_validations(self, sample_requirement):
        """Multiple validations for same requirement are imported."""
        # Create second requirement
        Requirement.add_root(
            external_id="REQ-TEST-002",
            title="Second Requirement",
            status="active",
            source_file="test.md",
        )

        data = {
            "source": "test-app",
            "validations": [
                {
                    "requirement_id": "REQ-TEST-001",
                    "name": "Validation 1",
                    "status": "success",
                },
                {
                    "requirement_id": "REQ-TEST-002",
                    "name": "Validation 2",
                    "status": "failure",
                },
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            json_path = Path(f.name)

        call_command("import_inapp_validations", str(json_path))

        assert InAppValidation.objects.count() == 2
        assert InAppValidationResult.objects.count() == 2

        run = InAppValidationRun.objects.first()
        assert run.successful == 1
        assert run.failed == 1

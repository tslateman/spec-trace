"""Integration tests for SDK Phase 2 enhancements."""

from datetime import datetime

import pytest
from django.test import Client

from requirements.models import InAppValidation, InAppValidationStatus, Requirement
from spectrace_client.models import ValidationResult, ValidationStatus, ValidationStep


@pytest.mark.django_db
class TestSDKPhase2Integration:
    """Test SDK with vendor, feature_flags, steps, and context fields."""

    def test_api_accepts_extended_fields(self):
        """Test that API accepts and stores vendor, steps, and context."""
        # Create a requirement using add_root (required for treebeard)
        req = Requirement.add_root(
            external_id="REQ-TEST-001", title="Test Requirement", description="Test"
        )

        # Create validation result with extended fields
        result = ValidationResult(
            requirement_id="REQ-TEST-001",
            name="Test PMS Connection",
            status=ValidationStatus.DEGRADED,
            message="2 passed, 1 failed",
            steps=[
                ValidationStep(
                    name="config",
                    passed=True,
                    details="Config OK",
                    timestamp=datetime.fromisoformat("2024-01-01T10:00:00Z"),
                ),
                ValidationStep(
                    name="auth",
                    passed=True,
                    details="Auth OK",
                    timestamp=datetime.fromisoformat("2024-01-01T10:00:01Z"),
                ),
                ValidationStep(
                    name="connect",
                    passed=False,
                    error_message="Timeout",
                    timestamp=datetime.fromisoformat("2024-01-01T10:00:02Z"),
                ),
            ],
            context={
                "vendor": "Stripe",
                "hotel_id": 123,
                "feature_flags": {"new_auth": True, "legacy_mode": False},
            },
        )

        # Submit via API
        client = Client()
        response = client.post(
            "/api/v1/results/enforcement/",
            data={"source": "spectrace-client", "validations": [result.to_dict()]},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["imported"] == 1

        # Verify in database
        validation = InAppValidation.objects.get(requirement=req)
        assert validation.vendor == "Stripe"
        assert validation.feature_flags == {"new_auth": True, "legacy_mode": False}

        latest_result = validation.latest_result
        assert latest_result is not None
        assert len(latest_result.steps) == 3
        assert latest_result.steps[0]["name"] == "config"
        assert latest_result.steps[0]["passed"] is True
        assert latest_result.context["vendor"] == "Stripe"
        assert latest_result.context["hotel_id"] == 123

    def test_regression_detection(self):
        """Test regression detection when validation goes from success to failure."""
        req = Requirement.add_root(external_id="REQ-TEST-002", title="Test Requirement 2")

        validation = InAppValidation.objects.create(
            requirement=req, name="Test Validation", vendor="Twilio"
        )

        from django.utils import timezone

        from requirements.models import InAppValidationResult, InAppValidationRun

        run1 = InAppValidationRun.objects.create(source="test")
        run2 = InAppValidationRun.objects.create(source="test")

        # First result: SUCCESS
        InAppValidationResult.objects.create(
            validation_run=run1,
            validation=validation,
            status=InAppValidationStatus.SUCCESS,
            message="All good",
            checked_at=timezone.now(),
        )

        # Second result: FAILURE (regression!)
        InAppValidationResult.objects.create(
            validation_run=run2,
            validation=validation,
            status=InAppValidationStatus.FAILURE,
            message="Connection failed",
            checked_at=timezone.now(),
        )

        # Detect regression
        regression = validation.detect_regression()
        assert regression["is_regression"] is True
        assert regression["previous_status"] == InAppValidationStatus.SUCCESS
        assert regression["current_status"] == InAppValidationStatus.FAILURE
        assert regression["regressed_at"] is not None

    def test_vendor_coverage_view(self):
        """Test vendor coverage dashboard view."""
        # Create validations for multiple vendors
        req1 = Requirement.add_root(external_id="REQ-V1", title="Req 1")
        req2 = Requirement.add_root(external_id="REQ-V2", title="Req 2")

        InAppValidation.objects.create(requirement=req1, name="Stripe Validation", vendor="Stripe")

        InAppValidation.objects.create(requirement=req2, name="Twilio Validation", vendor="Twilio")

        # Access vendor coverage view
        from django.contrib.auth.models import User

        user = User.objects.create_superuser("admin", "admin@test.com", "password")

        client = Client()
        client.force_login(user)
        response = client.get("/admin/vendor-coverage/")

        assert response.status_code == 200
        assert "Stripe" in response.content.decode() or "Twilio" in response.content.decode()

    def test_backward_compatibility(self):
        """Test that old API calls without new fields still work."""
        req = Requirement.add_root(external_id="REQ-OLD-001", title="Old Requirement")

        # Old-style validation (no vendor, steps, context)
        client = Client()
        response = client.post(
            "/api/v1/results/enforcement/",
            data={
                "source": "legacy-client",
                "validations": [
                    {
                        "requirement_id": "REQ-OLD-001",
                        "name": "Legacy Validation",
                        "status": "success",
                        "message": "All good",
                        "checked_at": "2024-01-01T10:00:00Z",
                    }
                ],
            },
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify empty defaults
        validation = InAppValidation.objects.get(requirement=req)
        assert validation.vendor == ""
        assert validation.feature_flags == {}

        latest_result = validation.latest_result
        assert latest_result.steps == []
        assert latest_result.context == {}

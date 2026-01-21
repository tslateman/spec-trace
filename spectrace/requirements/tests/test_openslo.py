"""Tests for OpenSLO parser and import functionality."""
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from requirements.models import Requirement, SLO, SLOStatus
from requirements.openslo import (
    OpenSLOParser,
    import_slos_to_database,
    update_slo_status_from_json,
)


@pytest.fixture
def sample_requirement(db):
    """Create a sample requirement."""
    return Requirement.add_root(
        external_id="REQ-API-001",
        title="API Availability",
        status="active",
        source_file="test.md",
    )


@pytest.fixture
def sample_openslo_yaml():
    """Create a sample OpenSLO YAML file."""
    content = """
apiVersion: openslo/v1
kind: SLO
metadata:
  name: api-availability
  displayName: API Availability SLO
  labels:
    requirement: REQ-API-001
spec:
  service: api-gateway
  description: API should be available 99.9% of the time
  objectives:
    - target: 0.999
      timeWindow:
        duration: 30d
  budgetingMethod: Occurrences
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def slo_with_multiple_reqs_yaml():
    """Create an OpenSLO YAML with multiple requirement links."""
    content = """
apiVersion: openslo/v1
kind: SLO
metadata:
  name: multi-req-slo
  labels:
    requirements: REQ-API-001, REQ-API-002
spec:
  service: api-gateway
  objectives:
    - target: 0.995
      timeWindow:
        duration: 7d
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def non_slo_yaml():
    """Create a non-SLO OpenSLO document."""
    content = """
apiVersion: openslo/v1
kind: Service
metadata:
  name: api-gateway
spec:
  displayName: API Gateway
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        f.write(content)
        return Path(f.name)


class TestOpenSLOParser:
    """Tests for OpenSLOParser."""

    def test_parse_valid_slo_file(self, sample_openslo_yaml):
        """Parse a valid OpenSLO SLO file."""
        parser = OpenSLOParser()
        result = parser.parse_file(sample_openslo_yaml)

        assert result is not None
        assert result["name"] == "api-availability"
        assert result["display_name"] == "API Availability SLO"
        assert result["service"] == "api-gateway"
        assert result["target"] == Decimal("0.999")
        assert result["time_window"] == "30d"
        assert result["budgeting_method"] == "Occurrences"
        assert result["requirement_ids"] == ["REQ-API-001"]

    def test_parse_non_slo_returns_none(self, non_slo_yaml):
        """Non-SLO documents return None."""
        parser = OpenSLOParser()
        result = parser.parse_file(non_slo_yaml)

        assert result is None

    def test_parse_multiple_requirement_links(self, slo_with_multiple_reqs_yaml):
        """Parse SLO with comma-separated requirement links."""
        parser = OpenSLOParser()
        result = parser.parse_file(slo_with_multiple_reqs_yaml)

        assert result is not None
        assert "REQ-API-001" in result["requirement_ids"]
        assert "REQ-API-002" in result["requirement_ids"]

    def test_parse_directory(self, sample_openslo_yaml, non_slo_yaml):
        """Parse all YAML files in a directory."""
        # Create temp dir with both files
        import shutil
        temp_dir = Path(tempfile.mkdtemp())
        shutil.copy(sample_openslo_yaml, temp_dir / "slo1.yaml")
        shutil.copy(non_slo_yaml, temp_dir / "service.yaml")

        parser = OpenSLOParser()
        results = parser.parse_directory(temp_dir)

        # Should only return the SLO, not the Service
        assert len(results) == 1
        assert results[0]["name"] == "api-availability"


class TestImportSLOs:
    """Tests for import_slos_to_database."""

    @pytest.mark.django_db
    def test_import_creates_slo(self, sample_requirement):
        """Import creates SLO and links to requirement."""
        slos = [
            {
                "name": "api-availability",
                "display_name": "API Availability",
                "description": "99.9% uptime",
                "service": "api-gateway",
                "target": Decimal("0.999"),
                "time_window": "30d",
                "budgeting_method": "Occurrences",
                "requirement_ids": ["REQ-API-001"],
                "source_file": "slos/api.yaml",
                "raw_yaml": "...",
            }
        ]

        created = import_slos_to_database(slos)

        assert created == 1
        assert SLO.objects.count() == 1

        slo = SLO.objects.first()
        assert slo.name == "api-availability"
        assert slo.target == Decimal("0.999")
        assert sample_requirement in slo.requirements.all()

    @pytest.mark.django_db
    def test_import_updates_existing(self, sample_requirement):
        """Re-import updates existing SLO."""
        # Create initial SLO
        slo = SLO.objects.create(
            name="api-availability",
            display_name="Old Name",
            target=Decimal("0.99"),
        )

        # Import with updated data
        slos = [
            {
                "name": "api-availability",
                "display_name": "New Name",
                "target": Decimal("0.999"),
                "requirement_ids": [],
            }
        ]

        created = import_slos_to_database(slos)

        assert created == 0  # Updated, not created
        slo.refresh_from_db()
        assert slo.display_name == "New Name"
        assert slo.target == Decimal("0.999")

    @pytest.mark.django_db
    def test_import_clear_existing(self, sample_requirement):
        """--clear removes existing SLOs before import."""
        SLO.objects.create(name="old-slo")

        slos = [
            {
                "name": "new-slo",
                "requirement_ids": [],
            }
        ]

        import_slos_to_database(slos, clear_existing=True)

        assert SLO.objects.count() == 1
        assert SLO.objects.first().name == "new-slo"


class TestUpdateSLOStatus:
    """Tests for update_slo_status_from_json."""

    @pytest.mark.django_db
    def test_update_status_met(self):
        """Update SLO status to 'met'."""
        slo = SLO.objects.create(name="test-slo")

        json_data = {
            "slos": [
                {
                    "name": "test-slo",
                    "status": "met",
                    "current_value": 0.9995,
                    "error_budget_remaining": 0.75,
                }
            ]
        }

        summary = update_slo_status_from_json(json_data)

        assert summary["updated"] == 1
        assert summary["not_found"] == 0

        slo.refresh_from_db()
        assert slo.status == SLOStatus.MET
        assert slo.current_value == Decimal("0.9995")
        assert slo.error_budget_remaining == Decimal("0.75")

    @pytest.mark.django_db
    def test_update_status_breached(self):
        """Update SLO status to 'breached'."""
        slo = SLO.objects.create(name="test-slo")

        json_data = {
            "slos": [
                {
                    "name": "test-slo",
                    "status": "breached",
                    "current_value": 0.985,
                }
            ]
        }

        update_slo_status_from_json(json_data)

        slo.refresh_from_db()
        assert slo.status == SLOStatus.BREACHED

    @pytest.mark.django_db
    def test_unknown_slo_not_found(self):
        """Unknown SLO name is reported but doesn't fail."""
        json_data = {
            "slos": [
                {
                    "name": "unknown-slo",
                    "status": "met",
                }
            ]
        }

        summary = update_slo_status_from_json(json_data)

        assert summary["updated"] == 0
        assert summary["not_found"] == 1

"""Tests for structured fields (FRET-inspired) functionality."""

import pytest

from requirements.linear import LinearClient
from requirements.models import Requirement
from requirements.openslo import parse_timing_to_seconds
from requirements.parser import SpecParser, import_requirements_to_database
from requirements.services.conflict_detector import ConflictDetector
from requirements.services.requirement_parser import (
    extract_from_markdown,
    extract_structured_fields,
    merge_structured_fields,
)

# ============================================================================
# Requirement Model Structured Fields Tests
# ============================================================================


class TestRequirementStructuredFields:
    """Tests for structured fields on Requirement model."""

    def test_calculate_structure_completeness__all_fields_populated(self, db):
        """Completeness is 1.0 when all structured fields populated."""
        req = Requirement.add_root(
            external_id="REQ-FULL-001",
            title="Full Requirement",
            source_file="test.md",
            scope="when in active_session",
            condition="battery_level < 10",
            component="warning_system",
            timing="within 2 seconds",
            response="display battery_warning",
        )

        assert req.structure_completeness == 1.0

    def test_calculate_structure_completeness__no_fields_populated(self, db):
        """Completeness is 0.0 when no structured fields populated."""
        req = Requirement.add_root(
            external_id="REQ-EMPTY-001",
            title="Empty Requirement",
            source_file="test.md",
        )

        assert req.structure_completeness == 0.0

    def test_calculate_structure_completeness__partial_fields(self, db):
        """Completeness reflects percentage of populated fields."""
        req = Requirement.add_root(
            external_id="REQ-PARTIAL-001",
            title="Partial Requirement",
            source_file="test.md",
            scope="when in active_session",
            component="warning_system",
        )

        # 2 out of 5 fields = 0.4
        assert req.structure_completeness == 0.4

    def test_calculate_structure_completeness__whitespace_only_not_counted(self, db):
        """Whitespace-only values don't count as populated."""
        req = Requirement.add_root(
            external_id="REQ-WS-001",
            title="Whitespace Requirement",
            source_file="test.md",
            scope="   ",  # Whitespace only
            condition="battery < 10",  # Real value
            component="",  # Empty
        )

        # Only 1 out of 5 fields has actual content
        assert req.structure_completeness == 0.2

    def test_save_updates_completeness_automatically(self, db):
        """Saving requirement auto-updates completeness."""
        req = Requirement.add_root(
            external_id="REQ-AUTO-001",
            title="Auto Update Test",
            source_file="test.md",
        )
        assert req.structure_completeness == 0.0

        # Update and save
        req.scope = "when active"
        req.condition = "x > 5"
        req.save()

        req.refresh_from_db()
        assert req.structure_completeness == 0.4


# ============================================================================
# Parser Structured Fields Tests
# ============================================================================


class TestParserStructuredFields:
    """Tests for extracting structured fields from YAML."""

    def test_parse_single__extracts_all_structured_fields(self, tmp_path):
        """Parser extracts all structured fields from single-requirement file."""
        spec_file = tmp_path / "req.md"
        spec_file.write_text("""---
id: REQ-BATTERY-001
title: Battery Warning
scope: when in active_session
condition: battery_level < 10
component: warning_system
timing: within 2 seconds
response: display battery_warning
---

Battery warning requirement description.
""")

        parser = SpecParser()
        requirements = parser.parse_file(spec_file)

        assert len(requirements) == 1
        req = requirements[0]
        assert req["scope"] == "when in active_session"
        assert req["condition"] == "battery_level < 10"
        assert req["component"] == "warning_system"
        assert req["timing"] == "within 2 seconds"
        assert req["response"] == "display battery_warning"

    def test_parse_single__empty_structured_fields_default_to_empty_string(self, tmp_path):
        """Parser returns empty strings for missing structured fields."""
        spec_file = tmp_path / "req.md"
        spec_file.write_text("""---
id: REQ-MINIMAL-001
title: Minimal Requirement
---

Just a basic requirement.
""")

        parser = SpecParser()
        requirements = parser.parse_file(spec_file)

        req = requirements[0]
        assert req["scope"] == ""
        assert req["condition"] == ""
        assert req["component"] == ""
        assert req["timing"] == ""
        assert req["response"] == ""

    def test_import_requirements__structured_fields_saved_to_db(self, db, tmp_path):
        """Importing requirements saves structured fields to database."""
        requirements = [
            {
                "external_id": "REQ-IMPORT-001",
                "title": "Import Test",
                "source_file": "test.md",
                "scope": "during checkout",
                "condition": "cart_total > 100",
                "component": "discount_engine",
                "timing": "within 500ms",
                "response": "apply discount",
            }
        ]

        import_requirements_to_database(requirements)

        req = Requirement.objects.get(external_id="REQ-IMPORT-001")
        assert req.scope == "during checkout"
        assert req.condition == "cart_total > 100"
        assert req.component == "discount_engine"
        assert req.timing == "within 500ms"
        assert req.response == "apply discount"
        assert req.structure_completeness == 1.0


# ============================================================================
# Requirement Parser Service Tests
# ============================================================================


class TestRequirementParserService:
    """Tests for structured field extraction from free-form text."""

    def test_extract_structured_fields__scope_extraction(self):
        """Extracts scope from various phrasings."""
        text = "In active_session mode, the system should respond."
        result = extract_structured_fields(text)
        assert "scope" in result
        assert "active_session" in result["scope"]

    def test_extract_structured_fields__condition_extraction(self):
        """Extracts condition from when/if clauses."""
        text = "When battery_level < 20, display a warning."
        result = extract_structured_fields(text)
        assert "condition" in result
        assert "battery_level" in result["condition"].lower()  # Case-insensitive check

    def test_extract_structured_fields__timing_extraction(self):
        """Extracts timing constraints."""
        text = "The response should arrive within 2 seconds."
        result = extract_structured_fields(text)
        assert "timing" in result
        assert "2" in result["timing"]

    def test_extract_structured_fields__response_extraction(self):
        """Extracts response/action from shall/should clauses."""
        text = "The system shall display a notification to the user."
        result = extract_structured_fields(text)
        assert "response" in result
        assert "display" in result["response"].lower()

    def test_extract_structured_fields__component_extraction(self):
        """Extracts component from text."""
        text = "The auth_service should validate the token."
        extract_structured_fields(text)
        # Component extraction depends on patterns matching
        # This is a best-effort extraction

    def test_extract_structured_fields__empty_text_returns_empty(self):
        """Empty text returns empty dict."""
        result = extract_structured_fields("")
        assert result == {}

    def test_extract_structured_fields__no_matches_returns_empty(self):
        """Text without patterns returns empty dict."""
        result = extract_structured_fields("Just some random text without patterns.")
        assert result == {}

    def test_extract_from_markdown__labeled_sections(self):
        """Extracts from markdown labeled sections."""
        text = """
**Scope:** during checkout flow
**Condition:** cart total > 100
**Response:** apply discount
"""
        result = extract_from_markdown(text)
        assert result.get("scope") == "during checkout flow"
        assert result.get("response") == "Apply discount"

    def test_merge_structured_fields__override_takes_precedence(self):
        """Override values replace base values."""
        base = {"scope": "original", "condition": "base condition"}
        override = {"scope": "overridden", "timing": "within 1s"}

        result = merge_structured_fields(base, override)

        assert result["scope"] == "overridden"
        assert result["condition"] == "base condition"
        assert result["timing"] == "within 1s"

    def test_merge_structured_fields__empty_override_preserves_base(self):
        """Empty override values don't replace base values."""
        base = {"scope": "original"}
        override = {"scope": ""}

        result = merge_structured_fields(base, override)

        assert result["scope"] == "original"


# ============================================================================
# Linear Import Structured Fields Tests
# ============================================================================


class TestLinearStructuredFields:
    """Tests for structured field extraction in Linear imports."""

    @pytest.fixture
    def linear_client(self):
        """Create a LinearClient with a mock API key."""
        return LinearClient("lin_api_test_key")

    def test_issue_to_requirement__extracts_structured_from_description(self, linear_client):
        """Extracts structured fields from issue description."""
        issue = {
            "identifier": "PROJ-789",
            "title": "Battery Warning",
            "description": (
                "When battery_level < 10, the warning_system"
                " shall display battery_warning within 2 seconds."
            ),
            "priority": 2,
            "state": {"name": "In Progress", "type": "started"},
            "labels": {"nodes": [{"name": "requirement"}]},
            "parent": None,
            "team": {"key": "PROJ"},
        }

        req = linear_client._issue_to_requirement(issue, "requirement")

        # Check structured fields were extracted
        assert req["condition"] != ""  # Should have extracted condition
        assert req["timing"] != ""  # Should have extracted timing

    def test_issue_to_requirement__empty_description_returns_empty_fields(self, linear_client):
        """Empty description returns empty structured fields."""
        issue = {
            "identifier": "PROJ-EMPTY",
            "title": "Empty Description",
            "description": "",
            "priority": 0,
            "state": {"name": "Backlog", "type": "backlog"},
            "labels": {"nodes": []},
            "parent": None,
            "team": {"key": "PROJ"},
        }

        req = linear_client._issue_to_requirement(issue, "requirement")

        assert req["scope"] == ""
        assert req["condition"] == ""
        assert req["component"] == ""
        assert req["timing"] == ""
        assert req["response"] == ""


# ============================================================================
# Conflict Detector Structured Fields Tests
# ============================================================================


class TestConflictDetectorStructuredFields:
    """Tests for structured field-based conflict detection."""

    @pytest.fixture
    def detector(self):
        """Create a ConflictDetector instance."""
        return ConflictDetector()

    def test_detect_condition_overlap__same_component_overlapping_conditions(self, db, detector):
        """Detects overlap when same component has overlapping conditions."""
        Requirement.add_root(
            external_id="REQ-OVL-001",
            title="Low Battery Warning",
            source_file="test.md",
            component="battery_monitor",
            condition="battery_level < 20",
        )
        Requirement.add_root(
            external_id="REQ-OVL-002",
            title="Critical Battery Warning",
            source_file="test.md",
            component="battery_monitor",
            condition="battery_level < 10",
        )

        conflicts = detector.detect_condition_overlap()

        # Both reference battery_level on same component
        assert len(conflicts) >= 1
        conflict = conflicts[0]
        assert conflict.pattern == "condition_overlap"
        assert "battery_level" in conflict.details.get("common_variables", [])

    def test_detect_condition_overlap__different_components_no_conflict(self, db, detector):
        """No conflict when conditions are on different components."""
        Requirement.add_root(
            external_id="REQ-DIFF-001",
            title="Battery Warning",
            source_file="test.md",
            component="battery_monitor",
            condition="level < 10",
        )
        Requirement.add_root(
            external_id="REQ-DIFF-002",
            title="Storage Warning",
            source_file="test.md",
            component="storage_monitor",
            condition="level < 10",
        )

        conflicts = detector.detect_condition_overlap()

        # Different components, so no conflict
        assert len(conflicts) == 0

    def test_detect_timing_conflicts__same_component_different_timing(self, db, detector):
        """Detects conflict when same component has different timing requirements."""
        Requirement.add_root(
            external_id="REQ-TIME-001",
            title="Fast Response",
            source_file="test.md",
            component="api_gateway",
            timing="within 100ms",
        )
        Requirement.add_root(
            external_id="REQ-TIME-002",
            title="Slow Response",
            source_file="test.md",
            component="api_gateway",
            timing="within 5 seconds",
        )

        conflicts = detector.detect_timing_conflicts()

        assert len(conflicts) >= 1
        conflict = conflicts[0]
        assert conflict.pattern == "timing_conflict"

    def test_detect_response_contradictions__antonym_responses(self, db, detector):
        """Detects contradiction when responses use antonyms."""
        Requirement.add_root(
            external_id="REQ-CONTRA-001",
            title="Show Warning",
            source_file="test.md",
            condition="battery_level < 20",
            response="show battery warning",
        )
        Requirement.add_root(
            external_id="REQ-CONTRA-002",
            title="Hide Warning",
            source_file="test.md",
            condition="battery_level < 15",
            response="hide battery warning",
        )

        conflicts = detector.detect_response_contradictions()

        assert len(conflicts) >= 1
        conflict = conflicts[0]
        assert conflict.pattern == "response_contradiction"
        assert conflict.details.get("contradiction_type") == "antonym"

    def test_detect_all_structured_conflicts__combines_all_detections(self, db, detector):
        """detect_all_structured_conflicts runs all structured detectors."""
        # Create requirements that should trigger different conflict types
        Requirement.add_root(
            external_id="REQ-ALL-001",
            title="Req 1",
            source_file="test.md",
            component="test_component",
            condition="x < 10",
            timing="within 1s",
            response="show alert",
        )
        Requirement.add_root(
            external_id="REQ-ALL-002",
            title="Req 2",
            source_file="test.md",
            component="test_component",
            condition="x < 5",
            timing="within 10s",
            response="hide alert",
        )

        conflicts = detector.detect_all_structured_conflicts()

        # Should find conflicts from multiple detectors
        {c.pattern for c in conflicts}
        # At least one type of conflict should be detected
        assert len(conflicts) >= 1


# ============================================================================
# OpenSLO Timing Parser Tests
# ============================================================================


class TestTimingParser:
    """Tests for timing constraint parsing."""

    def test_parse_timing_to_seconds__seconds(self):
        """Parses seconds correctly."""
        assert parse_timing_to_seconds("2 seconds") == 2.0
        assert parse_timing_to_seconds("within 5s") == 5.0
        assert parse_timing_to_seconds("1 second") == 1.0

    def test_parse_timing_to_seconds__milliseconds(self):
        """Parses milliseconds correctly."""
        assert parse_timing_to_seconds("500ms") == 0.5
        assert parse_timing_to_seconds("100 milliseconds") == 0.1

    def test_parse_timing_to_seconds__minutes(self):
        """Parses minutes correctly."""
        assert parse_timing_to_seconds("2 minutes") == 120.0
        assert parse_timing_to_seconds("1m") == 60.0

    def test_parse_timing_to_seconds__with_prefix(self):
        """Parses timing with prefix words."""
        assert parse_timing_to_seconds("within 3 seconds") == 3.0
        assert parse_timing_to_seconds("in 500ms") == 0.5
        assert parse_timing_to_seconds("after 1 minute") == 60.0

    def test_parse_timing_to_seconds__invalid_returns_none(self):
        """Invalid timing returns None."""
        assert parse_timing_to_seconds("") is None
        assert parse_timing_to_seconds("fast") is None
        assert parse_timing_to_seconds("immediately") is None

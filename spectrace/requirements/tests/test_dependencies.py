"""Tests for requirement dependency features."""
import tempfile
from pathlib import Path

import pytest

from requirements.models import Requirement, TestRequirementLink
from requirements.parser import SpecParser, import_requirements_to_database
from requirements.services.dependency_validator import (
    CircularDependency,
    DependencyChain,
    DependencyValidator,
)
from requirements.services.impact_analyzer import ImpactAnalyzer


class TestRequirementDependsOnField:
    """Tests for the depends_on M2M field on Requirement model."""

    def test_depends_on__can_set_dependencies(self, db):
        """A requirement can depend on other requirements."""
        req_a = Requirement.add_root(
            external_id="REQ-A",
            title="Requirement A",
            source_file="test.md",
        )
        req_b = Requirement.add_root(
            external_id="REQ-B",
            title="Requirement B",
            source_file="test.md",
        )
        req_c = Requirement.add_root(
            external_id="REQ-C",
            title="Requirement C",
            source_file="test.md",
        )

        req_c.depends_on.add(req_a, req_b)

        assert set(req_c.depends_on.values_list("external_id", flat=True)) == {
            "REQ-A",
            "REQ-B",
        }

    def test_depended_by__reverse_relation_works(self, db):
        """The depended_by reverse relation shows what depends on a requirement."""
        req_a = Requirement.add_root(
            external_id="REQ-DEP-A",
            title="Base Requirement",
            source_file="test.md",
        )
        req_b = Requirement.add_root(
            external_id="REQ-DEP-B",
            title="Dependent 1",
            source_file="test.md",
        )
        req_c = Requirement.add_root(
            external_id="REQ-DEP-C",
            title="Dependent 2",
            source_file="test.md",
        )

        req_b.depends_on.add(req_a)
        req_c.depends_on.add(req_a)

        assert set(req_a.depended_by.values_list("external_id", flat=True)) == {
            "REQ-DEP-B",
            "REQ-DEP-C",
        }

    def test_depends_on__asymmetric_relationship(self, db):
        """Dependency relationship is not symmetric."""
        req_a = Requirement.add_root(
            external_id="REQ-ASYM-A",
            title="Requirement A",
            source_file="test.md",
        )
        req_b = Requirement.add_root(
            external_id="REQ-ASYM-B",
            title="Requirement B",
            source_file="test.md",
        )

        req_b.depends_on.add(req_a)

        assert req_a in req_b.depends_on.all()
        assert req_b not in req_a.depends_on.all()


class TestParserDependsOn:
    """Tests for parsing depends_on from spec files."""

    def test_parse_single__parses_depends_on_list(self):
        """Parses depends_on as a list of requirement IDs."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """---
id: REQ-TEST
title: Test Requirement
depends_on: [REQ-A, REQ-B]
---
Test description.
"""
            )
            f.flush()
            parser = SpecParser()
            result = parser.parse_file(Path(f.name))

        assert len(result) == 1
        assert result[0]["depends_on"] == ["REQ-A", "REQ-B"]

    def test_parse_single__parses_depends_on_string(self):
        """Parses depends_on as a single string (converted to list)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """---
id: REQ-SINGLE-DEP
title: Single Dependency
depends_on: REQ-ONLY-ONE
---
Test description.
"""
            )
            f.flush()
            parser = SpecParser()
            result = parser.parse_file(Path(f.name))

        assert result[0]["depends_on"] == ["REQ-ONLY-ONE"]

    def test_parse_single__no_depends_on_returns_empty_list(self):
        """Missing depends_on returns empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(
                """---
id: REQ-NO-DEPS
title: No Dependencies
---
Test description.
"""
            )
            f.flush()
            parser = SpecParser()
            result = parser.parse_file(Path(f.name))

        assert result[0]["depends_on"] == []


class TestImportDependencies:
    """Tests for importing dependencies to database."""

    def test_import__creates_dependency_relationships(self, db):
        """Import establishes M2M relationships for depends_on."""
        requirements = [
            {"external_id": "REQ-BASE", "title": "Base", "source_file": "test.md"},
            {
                "external_id": "REQ-DEPENDENT",
                "title": "Dependent",
                "source_file": "test.md",
                "depends_on": ["REQ-BASE"],
            },
        ]

        import_requirements_to_database(requirements, clear_existing=True)

        dependent = Requirement.objects.get(external_id="REQ-DEPENDENT")
        assert list(dependent.depends_on.values_list("external_id", flat=True)) == [
            "REQ-BASE"
        ]

    def test_import__warns_on_missing_dependency(self, db, capsys):
        """Prints warning when dependency target doesn't exist."""
        requirements = [
            {
                "external_id": "REQ-ORPHAN",
                "title": "Orphan",
                "source_file": "test.md",
                "depends_on": ["REQ-NONEXISTENT"],
            },
        ]

        import_requirements_to_database(requirements, clear_existing=True)

        captured = capsys.readouterr()
        assert "REQ-ORPHAN depends on REQ-NONEXISTENT" in captured.out
        assert "not found" in captured.out

    def test_import__multiple_dependencies(self, db):
        """Import handles multiple dependencies correctly."""
        requirements = [
            {"external_id": "REQ-A1", "title": "A1", "source_file": "test.md"},
            {"external_id": "REQ-B1", "title": "B1", "source_file": "test.md"},
            {"external_id": "REQ-C1", "title": "C1", "source_file": "test.md"},
            {
                "external_id": "REQ-MULTI",
                "title": "Multi-dep",
                "source_file": "test.md",
                "depends_on": ["REQ-A1", "REQ-B1", "REQ-C1"],
            },
        ]

        import_requirements_to_database(requirements, clear_existing=True)

        multi = Requirement.objects.get(external_id="REQ-MULTI")
        deps = set(multi.depends_on.values_list("external_id", flat=True))
        assert deps == {"REQ-A1", "REQ-B1", "REQ-C1"}


class TestDependencyValidator:
    """Tests for DependencyValidator service."""

    def test_detect_circular__no_cycles(self, db):
        """Returns empty list when no circular dependencies exist."""
        req_a = Requirement.add_root(
            external_id="REQ-NC-A",
            title="A",
            source_file="test.md",
        )
        req_b = Requirement.add_root(
            external_id="REQ-NC-B",
            title="B",
            source_file="test.md",
        )
        req_c = Requirement.add_root(
            external_id="REQ-NC-C",
            title="C",
            source_file="test.md",
        )

        # Linear chain: A <- B <- C
        req_b.depends_on.add(req_a)
        req_c.depends_on.add(req_b)

        validator = DependencyValidator()
        cycles = validator.detect_circular_dependencies()

        assert cycles == []

    def test_detect_circular__simple_cycle(self, db):
        """Detects a simple circular dependency."""
        req_a = Requirement.add_root(
            external_id="REQ-CYCLE-A",
            title="A",
            source_file="test.md",
        )
        req_b = Requirement.add_root(
            external_id="REQ-CYCLE-B",
            title="B",
            source_file="test.md",
        )

        # A <- B and B <- A (cycle)
        req_a.depends_on.add(req_b)
        req_b.depends_on.add(req_a)

        validator = DependencyValidator()
        cycles = validator.detect_circular_dependencies()

        assert len(cycles) >= 1
        cycle_ids = set()
        for cycle in cycles:
            cycle_ids.update(cycle.cycle)
        assert "REQ-CYCLE-A" in cycle_ids
        assert "REQ-CYCLE-B" in cycle_ids

    def test_get_dependency_chain__returns_transitive_deps(self, db):
        """Returns all transitive dependencies."""
        req_a = Requirement.add_root(
            external_id="REQ-CHAIN-A",
            title="A",
            source_file="test.md",
        )
        req_b = Requirement.add_root(
            external_id="REQ-CHAIN-B",
            title="B",
            source_file="test.md",
        )
        req_c = Requirement.add_root(
            external_id="REQ-CHAIN-C",
            title="C",
            source_file="test.md",
        )

        # C depends on B depends on A
        req_b.depends_on.add(req_a)
        req_c.depends_on.add(req_b)

        validator = DependencyValidator()
        chain = validator.get_dependency_chain("REQ-CHAIN-C")

        assert chain.root_id == "REQ-CHAIN-C"
        assert "REQ-CHAIN-B" in chain.direct
        assert "REQ-CHAIN-A" in chain.transitive
        assert "REQ-CHAIN-B" in chain.transitive

    def test_get_dependents__returns_all_dependents(self, db):
        """Returns all requirements that depend on a given requirement."""
        req_base = Requirement.add_root(
            external_id="REQ-DEPTEST-BASE",
            title="Base",
            source_file="test.md",
        )
        req_mid = Requirement.add_root(
            external_id="REQ-DEPTEST-MID",
            title="Mid",
            source_file="test.md",
        )
        req_top = Requirement.add_root(
            external_id="REQ-DEPTEST-TOP",
            title="Top",
            source_file="test.md",
        )

        # TOP depends on MID depends on BASE
        req_mid.depends_on.add(req_base)
        req_top.depends_on.add(req_mid)

        validator = DependencyValidator()
        dependents = validator.get_dependents("REQ-DEPTEST-BASE")

        # Both MID and TOP (transitively) depend on BASE
        assert "REQ-DEPTEST-MID" in dependents
        assert "REQ-DEPTEST-TOP" in dependents


class TestImpactAnalyzerDependencyExpansion:
    """Tests for impact analyzer with dependency expansion."""

    def test_get_affected_tests__includes_dependents(self, db):
        """Includes tests for requirements that depend on changed requirements."""
        req_base = Requirement.add_root(
            external_id="REQ-IMPACT-BASE",
            title="Base",
            source_file="test.md",
        )
        req_dep = Requirement.add_root(
            external_id="REQ-IMPACT-DEP",
            title="Dependent",
            source_file="test.md",
        )
        req_dep.depends_on.add(req_base)

        TestRequirementLink.objects.create(
            test_nodeid="tests/test_dependent.py::test_dep_feature",
            requirement=req_dep,
        )

        analyzer = ImpactAnalyzer()
        tests, hierarchy, deps = analyzer.get_affected_tests(
            ["REQ-IMPACT-BASE"], include_hierarchy=False, include_dependents=True
        )

        assert "tests/test_dependent.py::test_dep_feature" in tests
        assert deps == {"REQ-IMPACT-BASE": ["REQ-IMPACT-DEP"]}

    def test_get_affected_tests__skips_dependents_when_disabled(self, db):
        """Does not include dependent tests when include_dependents=False."""
        req_base = Requirement.add_root(
            external_id="REQ-NODEP-BASE",
            title="Base",
            source_file="test.md",
        )
        req_dep = Requirement.add_root(
            external_id="REQ-NODEP-DEP",
            title="Dependent",
            source_file="test.md",
        )
        req_dep.depends_on.add(req_base)

        TestRequirementLink.objects.create(
            test_nodeid="tests/test_nodep.py::test_feature",
            requirement=req_dep,
        )

        analyzer = ImpactAnalyzer()
        tests, hierarchy, deps = analyzer.get_affected_tests(
            ["REQ-NODEP-BASE"], include_hierarchy=False, include_dependents=False
        )

        assert tests == []
        assert deps == {}

    def test_analyze__includes_dependency_expansion(self, db, tmp_path):
        """Full analysis includes dependency expansion in result."""
        from unittest.mock import patch

        req_base = Requirement.add_root(
            external_id="REQ-ANALYZE-BASE",
            title="Base",
            source_file="specs/base.md",
        )
        req_dep = Requirement.add_root(
            external_id="REQ-ANALYZE-DEP",
            title="Dependent",
            source_file="specs/dep.md",
        )
        req_dep.depends_on.add(req_base)

        TestRequirementLink.objects.create(
            test_nodeid="tests/test_analyze_dep.py::test_it",
            requirement=req_dep,
        )

        analyzer = ImpactAnalyzer(repo_path=tmp_path, spec_dir="specs")

        with patch.object(analyzer, "get_changed_files", return_value=["specs/base.md"]):
            with patch.object(
                analyzer, "extract_requirement_ids", return_value=["REQ-ANALYZE-BASE"]
            ):
                result = analyzer.analyze("main", "feature", include_dependents=True)

        assert "REQ-ANALYZE-BASE" in result.changed_requirements
        assert "tests/test_analyze_dep.py::test_it" in result.affected_tests
        assert "REQ-ANALYZE-BASE" in result.dependency_expansion
        assert "REQ-ANALYZE-DEP" in result.dependency_expansion["REQ-ANALYZE-BASE"]

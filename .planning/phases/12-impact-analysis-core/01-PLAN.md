---
phase: 12
plan: 01
title: Impact Analysis Service
wave: 1
depends_on: []
files_modified:
  - spectrace/requirements/services/impact_analyzer.py (NEW)
  - spectrace/requirements/tests/test_impact_analyzer.py (NEW)
autonomous: true
---

# Plan 01: Impact Analysis Service

## Goal

Create the `ImpactAnalyzer` service that detects changed requirements between git refs and returns affected tests.

## must_haves

- [ ] Service accepts two git refs (base, head) and returns changed requirement IDs
- [ ] Service returns linked tests for any requirement ID
- [ ] Hierarchy propagation: parent change includes child requirement tests
- [ ] Graceful error handling for invalid refs

## Tasks

<task id="1">
Create ImpactAnalyzer service class at `spectrace/requirements/services/impact_analyzer.py`:

```python
"""Impact analysis service for detecting spec changes and affected tests."""
from dataclasses import dataclass
import subprocess
from pathlib import Path
from typing import Optional

from requirements.models import Requirement, TestRequirementLink


@dataclass
class ImpactResult:
    """Result of impact analysis."""
    changed_requirements: list[str]  # External IDs of changed requirements
    affected_tests: list[str]  # Test nodeids affected by changes
    hierarchy_expansion: dict[str, list[str]]  # Parent ID -> child IDs included


class ImpactAnalyzer:
    """Analyzes impact of spec file changes on tests."""

    def __init__(self, repo_path: Optional[Path] = None, spec_dir: str = "specs"):
        """Initialize analyzer.

        Args:
            repo_path: Path to git repository root. Defaults to current directory.
            spec_dir: Directory containing spec files relative to repo root.
        """
        self.repo_path = repo_path or Path.cwd()
        self.spec_dir = spec_dir

    def get_changed_files(self, base_ref: str, head_ref: str) -> list[str]:
        """Get list of changed spec files between two refs.

        Args:
            base_ref: Base git ref (commit, branch, tag)
            head_ref: Head git ref to compare against base

        Returns:
            List of changed file paths relative to repo root.

        Raises:
            ValueError: If refs are invalid or git command fails.
        """
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", base_ref, head_ref, "--", f"{self.spec_dir}/"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return [f for f in result.stdout.strip().split('\n') if f and f.endswith('.md')]
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Git diff failed: {e.stderr}") from e
        except subprocess.TimeoutExpired:
            raise ValueError("Git diff timed out")

    def extract_requirement_ids(self, file_paths: list[str], ref: str) -> list[str]:
        """Extract requirement IDs from spec files at a given ref.

        Args:
            file_paths: List of spec file paths
            ref: Git ref to read files from

        Returns:
            List of requirement external IDs found in files.
        """
        ids = []
        for path in file_paths:
            try:
                result = subprocess.run(
                    ["git", "show", f"{ref}:{path}"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
                # Extract ID from YAML frontmatter
                content = result.stdout
                for line in content.split('\n'):
                    if line.startswith('id:'):
                        req_id = line.split(':', 1)[1].strip().strip('"\'')
                        if req_id:
                            ids.append(req_id)
                        break
            except subprocess.CalledProcessError:
                # File doesn't exist at this ref (new or deleted)
                continue
        return ids

    def get_affected_tests(self, requirement_ids: list[str], include_hierarchy: bool = True) -> tuple[list[str], dict[str, list[str]]]:
        """Get tests affected by changes to given requirements.

        Args:
            requirement_ids: List of requirement external IDs
            include_hierarchy: If True, include tests for child requirements

        Returns:
            Tuple of (test nodeids, hierarchy expansion dict)
        """
        all_ids = set(requirement_ids)
        hierarchy_expansion = {}

        if include_hierarchy:
            for req_id in requirement_ids:
                try:
                    req = Requirement.objects.get(external_id=req_id)
                    descendants = req.get_descendants()
                    child_ids = [d.external_id for d in descendants]
                    if child_ids:
                        hierarchy_expansion[req_id] = child_ids
                        all_ids.update(child_ids)
                except Requirement.DoesNotExist:
                    continue

        # Get all linked tests
        links = TestRequirementLink.objects.filter(
            requirement__external_id__in=all_ids
        ).select_related('requirement')

        tests = list(set(link.test_nodeid for link in links))
        return tests, hierarchy_expansion

    def analyze(self, base_ref: str, head_ref: str, include_hierarchy: bool = True) -> ImpactResult:
        """Perform full impact analysis between two git refs.

        Args:
            base_ref: Base git ref
            head_ref: Head git ref
            include_hierarchy: Include child requirements' tests

        Returns:
            ImpactResult with changed requirements and affected tests.
        """
        # Get changed spec files
        changed_files = self.get_changed_files(base_ref, head_ref)

        if not changed_files:
            return ImpactResult(
                changed_requirements=[],
                affected_tests=[],
                hierarchy_expansion={},
            )

        # Extract IDs from changed files (union of base and head)
        base_ids = set(self.extract_requirement_ids(changed_files, base_ref))
        head_ids = set(self.extract_requirement_ids(changed_files, head_ref))
        changed_ids = list(base_ids | head_ids)  # Any file that was added, modified, or deleted

        # Get affected tests
        tests, hierarchy = self.get_affected_tests(changed_ids, include_hierarchy)

        return ImpactResult(
            changed_requirements=changed_ids,
            affected_tests=tests,
            hierarchy_expansion=hierarchy,
        )
```
</task>

<task id="2">
Create tests at `spectrace/requirements/tests/test_impact_analyzer.py`:

```python
"""Tests for ImpactAnalyzer service."""
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from requirements.models import Requirement, TestRequirementLink
from requirements.services.impact_analyzer import ImpactAnalyzer, ImpactResult


class TestImpactAnalyzerGetChangedFiles:
    """Tests for get_changed_files method."""

    def test_get_changed_files__returns_markdown_files(self, tmp_path):
        """Returns only .md files from git diff."""
        analyzer = ImpactAnalyzer(repo_path=tmp_path, spec_dir="specs")

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout="specs/auth.md\nspecs/billing.md\nspecs/README.txt\n",
                returncode=0,
            )

            files = analyzer.get_changed_files("main", "feature-branch")

            assert files == ["specs/auth.md", "specs/billing.md"]
            mock_run.assert_called_once()

    def test_get_changed_files__handles_empty_diff(self, tmp_path):
        """Returns empty list when no files changed."""
        analyzer = ImpactAnalyzer(repo_path=tmp_path)

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)

            files = analyzer.get_changed_files("main", "main")

            assert files == []

    def test_get_changed_files__raises_on_invalid_ref(self, tmp_path):
        """Raises ValueError for invalid git refs."""
        analyzer = ImpactAnalyzer(repo_path=tmp_path)

        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                128, "git", stderr="fatal: bad revision 'invalid-ref'"
            )

            with pytest.raises(ValueError, match="Git diff failed"):
                analyzer.get_changed_files("invalid-ref", "main")


class TestImpactAnalyzerGetAffectedTests:
    """Tests for get_affected_tests method."""

    def test_get_affected_tests__returns_linked_tests(self, db):
        """Returns tests linked to given requirements."""
        req = Requirement.add_root(
            external_id="REQ-001",
            title="Test Requirement",
            source_file="test.md",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_auth.py::test_login",
            requirement=req,
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_auth.py::test_logout",
            requirement=req,
        )

        analyzer = ImpactAnalyzer()
        tests, hierarchy = analyzer.get_affected_tests(["REQ-001"])

        assert set(tests) == {
            "tests/test_auth.py::test_login",
            "tests/test_auth.py::test_logout",
        }
        assert hierarchy == {}

    def test_get_affected_tests__includes_hierarchy(self, db):
        """Includes tests from child requirements when hierarchy enabled."""
        parent = Requirement.add_root(
            external_id="REQ-PARENT",
            title="Parent",
            source_file="test.md",
        )
        child = parent.add_child(
            external_id="REQ-CHILD",
            title="Child",
            source_file="test.md",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_child.py::test_feature",
            requirement=child,
        )

        analyzer = ImpactAnalyzer()
        tests, hierarchy = analyzer.get_affected_tests(["REQ-PARENT"], include_hierarchy=True)

        assert "tests/test_child.py::test_feature" in tests
        assert hierarchy == {"REQ-PARENT": ["REQ-CHILD"]}

    def test_get_affected_tests__skips_hierarchy_when_disabled(self, db):
        """Does not include child tests when hierarchy disabled."""
        parent = Requirement.add_root(
            external_id="REQ-P2",
            title="Parent",
            source_file="test.md",
        )
        child = parent.add_child(
            external_id="REQ-C2",
            title="Child",
            source_file="test.md",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_child.py::test_x",
            requirement=child,
        )

        analyzer = ImpactAnalyzer()
        tests, hierarchy = analyzer.get_affected_tests(["REQ-P2"], include_hierarchy=False)

        assert tests == []
        assert hierarchy == {}


class TestImpactAnalyzerAnalyze:
    """Tests for full analyze method."""

    def test_analyze__full_flow(self, db, tmp_path):
        """Full analysis returns changed requirements and affected tests."""
        req = Requirement.add_root(
            external_id="REQ-ANALYZE",
            title="Analyze Test",
            source_file="specs/test.md",
        )
        TestRequirementLink.objects.create(
            test_nodeid="tests/test_main.py::test_it",
            requirement=req,
        )

        analyzer = ImpactAnalyzer(repo_path=tmp_path, spec_dir="specs")

        with patch.object(analyzer, 'get_changed_files', return_value=["specs/test.md"]):
            with patch.object(analyzer, 'extract_requirement_ids', return_value=["REQ-ANALYZE"]):
                result = analyzer.analyze("main", "feature")

        assert result.changed_requirements == ["REQ-ANALYZE"]
        assert "tests/test_main.py::test_it" in result.affected_tests

    def test_analyze__no_changes(self, tmp_path):
        """Returns empty result when no spec files changed."""
        analyzer = ImpactAnalyzer(repo_path=tmp_path)

        with patch.object(analyzer, 'get_changed_files', return_value=[]):
            result = analyzer.analyze("main", "main")

        assert result.changed_requirements == []
        assert result.affected_tests == []
        assert result.hierarchy_expansion == {}
```
</task>

<task id="3">
Run tests to verify:

```bash
python -m pytest spectrace/requirements/tests/test_impact_analyzer.py -v
```
</task>

## Verification

- [ ] `ImpactAnalyzer` class exists with `analyze()`, `get_changed_files()`, `get_affected_tests()` methods
- [ ] Tests pass for git diff detection
- [ ] Tests pass for test lookup via TestRequirementLink
- [ ] Tests pass for hierarchy propagation
- [ ] Error handling tested for invalid refs

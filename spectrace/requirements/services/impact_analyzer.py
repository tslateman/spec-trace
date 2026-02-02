"""Impact analysis service for detecting spec changes and affected tests."""
from dataclasses import dataclass
import logging
import re
import subprocess
from pathlib import Path
from typing import Optional

from requirements.models import Requirement, TestRequirementLink

logger = logging.getLogger(__name__)

# Valid git ref pattern: alphanumeric, dots, slashes, hyphens, underscores, colons
# Also allows HEAD, HEAD~N, HEAD^N, @{upstream}, etc.
GIT_REF_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._/:\-~^@{}]*$')


def validate_git_ref(ref: str) -> None:
    """Validate a git ref is safe to use in commands.

    Args:
        ref: Git reference string (commit, branch, tag)

    Raises:
        ValueError: If ref is empty, too long, or contains invalid characters.
    """
    if not ref:
        raise ValueError("Git ref cannot be empty")
    if len(ref) > 256:
        raise ValueError("Git ref too long (max 256 characters)")
    if not GIT_REF_PATTERN.match(ref):
        raise ValueError(
            "Invalid git ref format. Use alphanumeric characters, dots, "
            "slashes, hyphens, underscores, or standard git ref syntax."
        )
    # Block refs that look like command-line flags
    if ref.startswith('-'):
        raise ValueError("Git ref cannot start with a hyphen")


@dataclass
class ImpactResult:
    """Result of impact analysis."""

    changed_requirements: list[str]  # External IDs of changed requirements
    affected_tests: list[str]  # Test nodeids affected by changes
    hierarchy_expansion: dict[str, list[str]]  # Parent ID -> child IDs included
    dependency_expansion: dict[str, list[str]]  # Req ID -> dependent IDs included


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
        # Validate refs before using in subprocess
        validate_git_ref(base_ref)
        validate_git_ref(head_ref)

        try:
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    "--name-only",
                    base_ref,
                    head_ref,
                    "--",
                    f"{self.spec_dir}/",
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            return [f for f in result.stdout.strip().split("\n") if f and f.endswith(".md")]
        except subprocess.CalledProcessError as e:
            # Log full error for debugging, return sanitized message to user
            logger.error("Git diff failed: %s", e.stderr)
            raise ValueError(
                "Git diff failed. Please check that the refs exist and are valid."
            ) from e
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
        # Ref should already be validated by get_changed_files, but validate again
        validate_git_ref(ref)

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
                for line in content.split("\n"):
                    if line.startswith("id:"):
                        req_id = line.split(":", 1)[1].strip().strip("\"'")
                        if req_id:
                            ids.append(req_id)
                        break
            except subprocess.CalledProcessError:
                # File doesn't exist at this ref (new or deleted)
                continue
        return ids

    def get_affected_tests(
        self,
        requirement_ids: list[str],
        include_hierarchy: bool = True,
        include_dependents: bool = True,
    ) -> tuple[list[str], dict[str, list[str]], dict[str, list[str]]]:
        """Get tests affected by changes to given requirements.

        Args:
            requirement_ids: List of requirement external IDs
            include_hierarchy: If True, include tests for child requirements
            include_dependents: If True, include tests for requirements that depend on changed ones

        Returns:
            Tuple of (test nodeids, hierarchy expansion dict, dependency expansion dict)
        """
        all_ids = set(requirement_ids)
        hierarchy_expansion: dict[str, list[str]] = {}
        dependency_expansion: dict[str, list[str]] = {}

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

        if include_dependents:
            for req_id in requirement_ids:
                try:
                    req = Requirement.objects.get(external_id=req_id)
                    # Get requirements that depend on this one (depended_by is the reverse relation)
                    dependents = req.depended_by.all()
                    dependent_ids = [d.external_id for d in dependents]
                    if dependent_ids:
                        dependency_expansion[req_id] = dependent_ids
                        all_ids.update(dependent_ids)
                except Requirement.DoesNotExist:
                    continue

        # Get all linked tests
        links = TestRequirementLink.objects.filter(
            requirement__external_id__in=all_ids
        ).select_related("requirement")

        tests = list(set(link.test_nodeid for link in links))
        return tests, hierarchy_expansion, dependency_expansion

    def analyze(
        self,
        base_ref: str,
        head_ref: str,
        include_hierarchy: bool = True,
        include_dependents: bool = True,
    ) -> ImpactResult:
        """Perform full impact analysis between two git refs.

        Args:
            base_ref: Base git ref
            head_ref: Head git ref
            include_hierarchy: Include child requirements' tests
            include_dependents: Include tests for requirements that depend on changed ones

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
                dependency_expansion={},
            )

        # Extract IDs from changed files (union of base and head)
        base_ids = set(self.extract_requirement_ids(changed_files, base_ref))
        head_ids = set(self.extract_requirement_ids(changed_files, head_ref))
        changed_ids = list(base_ids | head_ids)  # Any file that was added, modified, or deleted

        # Get affected tests
        tests, hierarchy, dependencies = self.get_affected_tests(
            changed_ids, include_hierarchy, include_dependents
        )

        return ImpactResult(
            changed_requirements=changed_ids,
            affected_tests=tests,
            hierarchy_expansion=hierarchy,
            dependency_expansion=dependencies,
        )

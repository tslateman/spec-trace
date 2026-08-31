"""Spec file parser for importing markdown requirements into the database."""

import re
from pathlib import Path
from typing import Any, TypedDict

import frontmatter

from requirements.models import Requirement, RiskLevel, VerificationMethod
from requirements.projects import default_project
from requirements.services.map_reader import project_for_path


class InvalidRiskLevelError(ValueError):
    """A spec declared a `risk_level` outside the RiskLevel choices."""


class RequirementData(TypedDict, total=False):
    """Type definition for requirement data dictionaries.

    Used by SpecParser and importers like LinearClient.
    """

    external_id: str  # required
    title: str
    description: str
    tags: list[str]
    priority: str
    status: str
    risk_level: str
    parent_id: str | None
    source_file: str
    verification_method: str
    # Structured fields (FRET-inspired)
    scope: str
    condition: str
    component: str
    timing: str
    response: str
    # Dependencies (separate from parent-child hierarchy)
    depends_on: list[str]


def normalize_verification_method(value: str | None) -> str:
    """Normalize verification method to valid enum value.

    Args:
        value: Raw verification method value from input

    Returns:
        Valid VerificationMethod value, defaulting to UNSPECIFIED
    """
    if value is None or value not in VerificationMethod.values:
        return VerificationMethod.UNSPECIFIED
    return value


def resolve_risk_level(value: Any, source_file: str) -> str:
    """Validate an authored risk level against the RiskLevel choices.

    Args:
        value: Raw `risk_level` value from frontmatter, or None when unstated
        source_file: Spec file the value came from, named in the error

    Returns:
        A RiskLevel value; UNCLASSIFIED when the spec states none

    Raises:
        InvalidRiskLevelError: The value is outside the RiskLevel choices
    """
    if value is None:
        return RiskLevel.UNCLASSIFIED
    if value not in RiskLevel.values:
        allowed = ", ".join(RiskLevel.values)
        raise InvalidRiskLevelError(
            f"{source_file or 'requirement data'}: risk_level '{value}' is not a "
            f"RiskLevel. Use one of: {allowed}"
        )
    return value


def _extract_requirement_fields(req_data: dict[str, Any]) -> dict[str, Any]:
    """Extract database fields from requirement data dict.

    Args:
        req_data: Raw requirement data dictionary

    Returns:
        Dictionary of fields ready for Requirement model
    """
    return {
        "title": req_data.get("title", ""),
        "description": req_data.get("description", ""),
        "tags": req_data.get("tags", []),
        "priority": req_data.get("priority", ""),
        "status": req_data.get("status", "draft"),
        "risk_level": resolve_risk_level(
            req_data.get("risk_level"), req_data.get("source_file", "")
        ),
        "source_file": req_data.get("source_file", ""),
        "verification_method": normalize_verification_method(req_data.get("verification_method")),
        # Structured fields (FRET-inspired)
        "scope": req_data.get("scope", ""),
        "condition": req_data.get("condition", ""),
        "component": req_data.get("component", ""),
        "timing": req_data.get("timing", ""),
        "response": req_data.get("response", ""),
    }


def import_requirements_to_database(
    requirements: list[dict[str, Any]],
    clear_existing: bool = False,
    source_prefix: str | None = None,
    project: str | None = None,
) -> int:
    """Import requirement dicts to database.

    Used by SpecParser and external importers (e.g., LinearClient).
    Uses treebeard's add_root and add_child methods for proper hierarchy.

    Args:
        requirements: List of requirement dicts with keys:
            - external_id (required)
            - title, description, tags, priority, status, source_file
            - parent_id (optional, references external_id of parent)
        clear_existing: If True, delete this project's requirements before import.
            If source_prefix is set, only deletes requirements with matching source_file.
        source_prefix: If set, only clear requirements whose source_file starts with this.
            Useful for clearing only Linear-sourced requirements.
        project: Project that owns these requirements. Defaults to the project
            this installation owns, so another project's specs never land here
            unnamed.

    Returns:
        Number of requirements created (not updated)
    """
    project = project or default_project()

    owned = Requirement.objects.filter(project=project)
    if clear_existing:
        if source_prefix:
            owned.filter(source_file__startswith=source_prefix).delete()
        else:
            owned.delete()

    # Build lookup of existing requirements by external_id
    existing = {req.external_id: req for req in owned}

    # Separate root requirements (no parent) and children
    roots = [r for r in requirements if r.get("parent_id") is None]
    children = [r for r in requirements if r.get("parent_id") is not None]

    created_count = 0

    # First pass: create all root requirements
    for req_data in roots:
        external_id = req_data["external_id"]
        fields = _extract_requirement_fields(req_data)
        fields["project"] = project

        if external_id in existing:
            # Update existing
            req = existing[external_id]
            for field, value in fields.items():
                setattr(req, field, value)
            req.save()
        else:
            # Create new root
            req = Requirement.add_root(external_id=external_id, **fields)
            existing[external_id] = req
            created_count += 1

    # Second pass: create children with parent references
    for req_data in children:
        external_id = req_data["external_id"]
        parent_id = req_data["parent_id"]
        fields = _extract_requirement_fields(req_data)
        fields["project"] = project

        if external_id in existing:
            # Update existing
            req = existing[external_id]
            for field, value in fields.items():
                setattr(req, field, value)
            req.save()
        else:
            # Find parent. Reload it: treebeard derives a child's path from the
            # parent's stored path and numchild, which a cached instance loses
            # as soon as a sibling is added.
            parent = (
                Requirement.objects.filter(external_id=parent_id).first()
                if parent_id in existing
                else None
            )
            if parent is None:
                # Parent not found, create as root with warning
                print(f"Warning: Parent {parent_id} not found for {external_id}, creating as root")
                req = Requirement.add_root(external_id=external_id, **fields)
            else:
                # Create as child of parent
                req = parent.add_child(external_id=external_id, **fields)
            existing[external_id] = req
            created_count += 1

    # Third pass: establish dependency relationships
    for req_data in requirements:
        depends_on_ids = req_data.get("depends_on", [])
        if not depends_on_ids:
            continue

        req = existing.get(req_data["external_id"])
        if not req:
            continue

        valid_deps = []
        for dep_id in depends_on_ids:
            dep_req = existing.get(dep_id)
            if dep_req:
                valid_deps.append(dep_req)
            else:
                print(
                    f"Warning: {req_data['external_id']} depends on"
                    f" {dep_id}, but {dep_id} not found"
                )

        req.depends_on.set(valid_deps)

    return created_count


class SpecParser:
    """Parses markdown spec files with YAML frontmatter into Requirement objects.

    Supports two formats:
    1. Single-requirement files: One `id` in frontmatter = one Requirement
    2. Multi-requirement files: Multiple `## REQ-XXX: Title` headings = multiple Requirements

    Example single-requirement format:
        ---
        id: REQ-XXX
        title: Requirement Title
        tags: [auth, security]
        priority: high
        status: active
        risk_level: critical  # optional, one of the RiskLevel choices
        parent: REQ-YYY  # optional, for explicit hierarchy
        ---

        Requirement description in markdown...
    """

    # Pattern to match requirement headings in multi-requirement files
    REQ_HEADING_PATTERN = re.compile(r"^##\s+(REQ-[\w-]+):\s*(.+)$", re.MULTILINE)

    def parse_file(self, file_path: Path) -> list[dict[str, Any]]:
        """Parse a single spec file, return list of requirement dicts.

        Args:
            file_path: Path to the markdown spec file

        Returns:
            List of requirement dictionaries ready for database import
        """
        post = frontmatter.load(file_path)

        # Check if single-requirement or multi-requirement file
        if "id" in post.metadata:
            # Single requirement file
            return [self._parse_single(post, file_path)]
        else:
            # Multi-requirement file (parse headings)
            return self._parse_multi(post, file_path)

    def _parse_single(self, post: frontmatter.Post, file_path: Path) -> dict[str, Any]:
        """Parse single-requirement file.

        Args:
            post: Parsed frontmatter post object
            file_path: Path to source file for tracking

        Returns:
            Requirement dictionary
        """
        # Handle depends_on as string or list
        depends_on_raw = post.metadata.get("depends_on", [])
        if isinstance(depends_on_raw, str):
            depends_on_raw = [depends_on_raw]

        return {
            "external_id": post.metadata["id"],
            "title": post.metadata.get("title", ""),
            "description": post.content,
            "tags": post.metadata.get("tags", []),
            "priority": post.metadata.get("priority", ""),
            "status": post.metadata.get("status", "draft"),
            "risk_level": post.metadata.get("risk_level"),
            "parent_id": post.metadata.get("parent"),
            "source_file": str(file_path),
            "verification_method": post.metadata.get(
                "verification_method", VerificationMethod.UNSPECIFIED
            ),
            # Structured fields (FRET-inspired)
            "scope": post.metadata.get("scope", ""),
            "condition": post.metadata.get("condition", ""),
            "component": post.metadata.get("component", ""),
            "timing": post.metadata.get("timing", ""),
            "response": post.metadata.get("response", ""),
            # Dependencies
            "depends_on": depends_on_raw,
        }

    def _parse_multi(self, post: frontmatter.Post, file_path: Path) -> list[dict[str, Any]]:
        """Parse multi-requirement file with ## REQ-XXX: Title headings.

        The first requirement becomes root, nested requirements become children
        based on explicit `parent` references or heading structure.

        Args:
            post: Parsed frontmatter post object
            file_path: Path to source file for tracking

        Returns:
            List of requirement dictionaries
        """
        requirements = []
        content = post.content

        # Find all requirement headings
        matches = list(self.REQ_HEADING_PATTERN.finditer(content))

        if not matches:
            # No requirement headings found, skip file
            return []

        # Get shared metadata from frontmatter (tags, priority, etc.)
        shared_tags = post.metadata.get("tags", [])
        shared_priority = post.metadata.get("priority", "")
        shared_status = post.metadata.get("status", "draft")
        shared_risk_level = post.metadata.get("risk_level")
        shared_verification_method = post.metadata.get(
            "verification_method", VerificationMethod.UNSPECIFIED
        )
        # Structured fields (FRET-inspired) - shared across all requirements in file
        shared_scope = post.metadata.get("scope", "")
        shared_condition = post.metadata.get("condition", "")
        shared_component = post.metadata.get("component", "")
        shared_timing = post.metadata.get("timing", "")
        shared_response = post.metadata.get("response", "")
        # Dependencies - shared across all requirements in file
        shared_depends_on_raw = post.metadata.get("depends_on", [])
        if isinstance(shared_depends_on_raw, str):
            shared_depends_on_raw = [shared_depends_on_raw]
        shared_depends_on = shared_depends_on_raw

        # Track the first requirement as root for implicit hierarchy
        first_req_id = None

        for i, match in enumerate(matches):
            req_id = match.group(1)
            title = match.group(2).strip()

            # Get description (content between this heading and next)
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            description = content[start:end].strip()

            # Determine parent (first req has no parent, others use first as parent)
            if first_req_id is None:
                first_req_id = req_id
                parent_id = None
            else:
                # Default children to first requirement unless otherwise specified
                parent_id = first_req_id

            requirements.append(
                {
                    "external_id": req_id,
                    "title": title,
                    "description": description,
                    "tags": shared_tags,
                    "priority": shared_priority,
                    "status": shared_status,
                    "risk_level": shared_risk_level,
                    "parent_id": parent_id,
                    "source_file": str(file_path),
                    "verification_method": shared_verification_method,
                    # Structured fields (FRET-inspired)
                    "scope": shared_scope,
                    "condition": shared_condition,
                    "component": shared_component,
                    "timing": shared_timing,
                    "response": shared_response,
                    # Dependencies (shared from frontmatter for multi-req files)
                    "depends_on": shared_depends_on,
                }
            )

        return requirements

    def parse_directory(self, specs_dir: Path) -> list[dict[str, Any]]:
        """Parse all .md files in directory recursively.

        Args:
            specs_dir: Path to specs directory

        Returns:
            List of all requirement dictionaries from all files
        """
        requirements = []
        for md_file in sorted(specs_dir.glob("**/*.md")):
            try:
                file_requirements = self.parse_file(md_file)
                requirements.extend(file_requirements)
            except Exception as e:
                # Log warning but continue parsing other files
                print(f"Warning: Failed to parse {md_file}: {e}")
        return requirements

    def import_to_database(
        self, specs_dir: Path, clear_existing: bool = False, project: str | None = None
    ) -> int:
        """Parse specs and create/update Requirement objects in database.

        Uses treebeard's add_root and add_child methods for proper hierarchy.

        Args:
            specs_dir: Path to specs directory
            clear_existing: If True, delete this project's requirements first
            project: Project that owns these specs. Defaults to the project the
                nearest spectrace-map.yaml above the specs directory declares,
                and to this installation's own project when no map declares one.

        Returns:
            Number of requirements created
        """
        requirements = self.parse_directory(specs_dir)
        return import_requirements_to_database(
            requirements,
            clear_existing=clear_existing,
            project=project or project_for_path(specs_dir),
        )

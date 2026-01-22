"""Spec file parser for importing markdown requirements into the database."""
import re
from pathlib import Path
from typing import Any, TypedDict

import frontmatter

from requirements.models import Requirement, VerificationMethod


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
    parent_id: str | None
    source_file: str
    verification_method: str


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


def _extract_requirement_fields(req_data: dict[str, Any]) -> dict[str, Any]:
    """Extract database fields from requirement data dict.

    Args:
        req_data: Raw requirement data dictionary

    Returns:
        Dictionary of fields ready for Requirement model
    """
    return {
        'title': req_data.get('title', ''),
        'description': req_data.get('description', ''),
        'tags': req_data.get('tags', []),
        'priority': req_data.get('priority', ''),
        'status': req_data.get('status', 'draft'),
        'source_file': req_data.get('source_file', ''),
        'verification_method': normalize_verification_method(req_data.get('verification_method')),
    }


def import_requirements_to_database(
    requirements: list[dict[str, Any]],
    clear_existing: bool = False,
    source_prefix: str | None = None
) -> int:
    """Import requirement dicts to database.

    Used by SpecParser and external importers (e.g., LinearClient).
    Uses treebeard's add_root and add_child methods for proper hierarchy.

    Args:
        requirements: List of requirement dicts with keys:
            - external_id (required)
            - title, description, tags, priority, status, source_file
            - parent_id (optional, references external_id of parent)
        clear_existing: If True, delete requirements before import.
            If source_prefix is set, only deletes requirements with matching source_file.
        source_prefix: If set, only clear requirements whose source_file starts with this.
            Useful for clearing only Linear-sourced requirements.

    Returns:
        Number of requirements created (not updated)
    """
    if clear_existing:
        if source_prefix:
            Requirement.objects.filter(source_file__startswith=source_prefix).delete()
        else:
            Requirement.objects.all().delete()

    # Build lookup of existing requirements by external_id
    existing = {req.external_id: req for req in Requirement.objects.all()}

    # Separate root requirements (no parent) and children
    roots = [r for r in requirements if r.get('parent_id') is None]
    children = [r for r in requirements if r.get('parent_id') is not None]

    created_count = 0

    # First pass: create all root requirements
    for req_data in roots:
        external_id = req_data['external_id']
        fields = _extract_requirement_fields(req_data)

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
        external_id = req_data['external_id']
        parent_id = req_data['parent_id']
        fields = _extract_requirement_fields(req_data)

        if external_id in existing:
            # Update existing
            req = existing[external_id]
            for field, value in fields.items():
                setattr(req, field, value)
            req.save()
        else:
            # Find parent
            parent = existing.get(parent_id)
            if parent is None:
                # Parent not found, create as root with warning
                print(f"Warning: Parent {parent_id} not found for {external_id}, creating as root")
                req = Requirement.add_root(external_id=external_id, **fields)
            else:
                # Create as child of parent
                req = parent.add_child(external_id=external_id, **fields)
            existing[external_id] = req
            created_count += 1

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
        parent: REQ-YYY  # optional, for explicit hierarchy
        ---

        Requirement description in markdown...
    """

    # Pattern to match requirement headings in multi-requirement files
    REQ_HEADING_PATTERN = re.compile(r'^##\s+(REQ-[\w-]+):\s*(.+)$', re.MULTILINE)

    def parse_file(self, file_path: Path) -> list[dict[str, Any]]:
        """Parse a single spec file, return list of requirement dicts.

        Args:
            file_path: Path to the markdown spec file

        Returns:
            List of requirement dictionaries ready for database import
        """
        post = frontmatter.load(file_path)

        # Check if single-requirement or multi-requirement file
        if 'id' in post.metadata:
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
        return {
            'external_id': post.metadata['id'],
            'title': post.metadata.get('title', ''),
            'description': post.content,
            'tags': post.metadata.get('tags', []),
            'priority': post.metadata.get('priority', ''),
            'status': post.metadata.get('status', 'draft'),
            'parent_id': post.metadata.get('parent'),
            'source_file': str(file_path),
            'verification_method': post.metadata.get('verification_method', VerificationMethod.UNSPECIFIED),
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
        shared_tags = post.metadata.get('tags', [])
        shared_priority = post.metadata.get('priority', '')
        shared_status = post.metadata.get('status', 'draft')
        shared_verification_method = post.metadata.get('verification_method', VerificationMethod.UNSPECIFIED)

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

            requirements.append({
                'external_id': req_id,
                'title': title,
                'description': description,
                'tags': shared_tags,
                'priority': shared_priority,
                'status': shared_status,
                'parent_id': parent_id,
                'source_file': str(file_path),
                'verification_method': shared_verification_method,
            })

        return requirements

    def parse_directory(self, specs_dir: Path) -> list[dict[str, Any]]:
        """Parse all .md files in directory recursively.

        Args:
            specs_dir: Path to specs directory

        Returns:
            List of all requirement dictionaries from all files
        """
        requirements = []
        for md_file in sorted(specs_dir.glob('**/*.md')):
            try:
                file_requirements = self.parse_file(md_file)
                requirements.extend(file_requirements)
            except Exception as e:
                # Log warning but continue parsing other files
                print(f"Warning: Failed to parse {md_file}: {e}")
        return requirements

    def import_to_database(self, specs_dir: Path, clear_existing: bool = False) -> int:
        """Parse specs and create/update Requirement objects in database.

        Uses treebeard's add_root and add_child methods for proper hierarchy.

        Args:
            specs_dir: Path to specs directory
            clear_existing: If True, delete all existing requirements first

        Returns:
            Number of requirements created
        """
        requirements = self.parse_directory(specs_dir)
        return import_requirements_to_database(requirements, clear_existing=clear_existing)

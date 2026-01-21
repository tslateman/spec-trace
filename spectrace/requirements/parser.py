"""Spec file parser for importing markdown requirements into the database."""
import re
from pathlib import Path
from typing import Any

import frontmatter

from requirements.models import Requirement


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
        if clear_existing:
            Requirement.objects.all().delete()

        requirements = self.parse_directory(specs_dir)

        # Build lookup of existing requirements by external_id
        existing = {req.external_id: req for req in Requirement.objects.all()}

        # Separate root requirements (no parent) and children
        roots = [r for r in requirements if r['parent_id'] is None]
        children = [r for r in requirements if r['parent_id'] is not None]

        created_count = 0

        # First pass: create all root requirements
        for req_data in roots:
            external_id = req_data['external_id']
            if external_id in existing:
                # Update existing
                req = existing[external_id]
                for field in ['title', 'description', 'tags', 'priority', 'status', 'source_file']:
                    setattr(req, field, req_data[field])
                req.save()
            else:
                # Create new root
                req = Requirement.add_root(
                    external_id=external_id,
                    title=req_data['title'],
                    description=req_data['description'],
                    tags=req_data['tags'],
                    priority=req_data['priority'],
                    status=req_data['status'],
                    source_file=req_data['source_file'],
                )
                existing[external_id] = req
                created_count += 1

        # Second pass: create children with parent references
        for req_data in children:
            external_id = req_data['external_id']
            parent_id = req_data['parent_id']

            if external_id in existing:
                # Update existing
                req = existing[external_id]
                for field in ['title', 'description', 'tags', 'priority', 'status', 'source_file']:
                    setattr(req, field, req_data[field])
                req.save()
            else:
                # Find parent
                parent = existing.get(parent_id)
                if parent is None:
                    # Parent not found, create as root with warning
                    print(f"Warning: Parent {parent_id} not found for {external_id}, creating as root")
                    req = Requirement.add_root(
                        external_id=external_id,
                        title=req_data['title'],
                        description=req_data['description'],
                        tags=req_data['tags'],
                        priority=req_data['priority'],
                        status=req_data['status'],
                        source_file=req_data['source_file'],
                    )
                else:
                    # Create as child of parent
                    req = parent.add_child(
                        external_id=external_id,
                        title=req_data['title'],
                        description=req_data['description'],
                        tags=req_data['tags'],
                        priority=req_data['priority'],
                        status=req_data['status'],
                        source_file=req_data['source_file'],
                    )
                existing[external_id] = req
                created_count += 1

        return created_count

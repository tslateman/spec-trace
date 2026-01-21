"""Requirement model for storing parsed spec requirements."""
from django.db import models
from treebeard.mp_tree import MP_Node


class Requirement(MP_Node):
    """A requirement parsed from a spec markdown file.

    Uses django-treebeard's materialized path implementation for
    efficient hierarchical queries (ancestors, descendants, siblings).
    """

    # Identity
    external_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique ID from spec file (e.g., REQ-AUTH-001)"
    )
    title = models.CharField(
        max_length=200,
        help_text="Short descriptive title"
    )

    # Content
    description = models.TextField(
        blank=True,
        help_text="Markdown body from spec file"
    )

    # Metadata from frontmatter
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Category tags for filtering"
    )
    priority = models.CharField(
        max_length=20,
        blank=True,
        help_text="Priority level (high, medium, low)"
    )
    status = models.CharField(
        max_length=20,
        default='draft',
        help_text="Requirement status (draft, active, deprecated)"
    )

    # Source tracking
    source_file = models.CharField(
        max_length=500,
        help_text="Relative path to source spec file"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # treebeard settings - ordering for siblings
    node_order_by = ['external_id']

    class Meta:
        verbose_name = "Requirement"
        verbose_name_plural = "Requirements"

    def __str__(self):
        return f"{self.external_id}: {self.title}"

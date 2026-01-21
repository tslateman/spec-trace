"""Admin configuration for Requirement model."""
from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from .models import Requirement


@admin.register(Requirement)
class RequirementAdmin(TreeAdmin):
    """Admin interface for Requirement with tree support."""

    form = movenodeform_factory(Requirement)
    list_display = ['external_id', 'title', 'status', 'priority', 'source_file']
    list_filter = ['status', 'priority']
    search_fields = ['external_id', 'title', 'description']
    readonly_fields = ['created_at', 'updated_at']

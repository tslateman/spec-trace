"""Filter utilities for views.

Consolidates repeated filter building logic across views.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.http import HttpRequest


@dataclass
class FilterSpec:
    """Specification for a single filter field."""

    name: str
    type: str = "string"  # string, int, date, tags
    default: Any = None


@dataclass
class FilterBuilder:
    """Builds filter dicts from request query parameters.

    Example usage:
        builder = FilterBuilder([
            FilterSpec("status"),
            FilterSpec("date_from", type="date"),
            FilterSpec("date_to", type="date"),
            FilterSpec("tags", type="tags"),
        ])
        filters = builder.build(request)
        current = builder.get_current_filters(request)
    """

    specs: list[FilterSpec] = field(default_factory=list)

    def build(self, request: HttpRequest) -> dict[str, Any]:
        """Build filter dict from request query parameters.

        Returns dict with only non-empty filter values, suitable for
        passing to data layer functions.
        """
        filters = {}

        for spec in self.specs:
            value = request.GET.get(spec.name)
            if not value:
                continue

            if spec.type == "date":
                try:
                    filters[spec.name] = datetime.strptime(value, "%Y-%m-%d")
                except ValueError:
                    pass  # Skip invalid dates
            elif spec.type == "tags":
                filters[spec.name] = [t.strip() for t in value.split(",") if t.strip()]
            elif spec.type == "int":
                try:
                    filters[spec.name] = int(value)
                except ValueError:
                    pass  # Skip invalid ints
            else:
                filters[spec.name] = value

        return filters

    def get_current_filters(self, request: HttpRequest, per_page: int = 25) -> dict[str, Any]:
        """Get current filter values for template context.

        Returns dict with all filter names as keys, preserving empty
        string values for template form binding.
        """
        current = {"per_page": per_page}

        for spec in self.specs:
            value = request.GET.get(spec.name, "")
            current[spec.name] = value

        return current


# Pre-built filter builders for common views
MATRIX_FILTERS = FilterBuilder(
    [
        FilterSpec("status"),
        FilterSpec("tags", type="tags"),
        FilterSpec("parent_id"),
    ]
)

VALIDATION_RUN_FILTERS = FilterBuilder(
    [
        FilterSpec("source"),
        FilterSpec("vendor"),
        FilterSpec("requirement"),
        FilterSpec("date_from", type="date"),
        FilterSpec("date_to", type="date"),
    ]
)

FLOW_RUN_FILTERS = FilterBuilder(
    [
        FilterSpec("status"),
        FilterSpec("date_from", type="date"),
        FilterSpec("date_to", type="date"),
    ]
)


def parse_pagination(request: HttpRequest, default_per_page: int = 25) -> tuple[int, int]:
    """Parse page and per_page from request with bounds validation.

    Returns (page, per_page) tuple.
    """
    try:
        page = max(1, min(int(request.GET.get("page", 1)), 10000))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = max(1, min(int(request.GET.get("per_page", default_per_page)), 100))
    except (ValueError, TypeError):
        per_page = default_per_page

    return page, per_page

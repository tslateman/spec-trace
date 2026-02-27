"""Template tags for matrix view."""

from django import template

register = template.Library()


@register.filter
def get_cell(cells, key_tuple):
    """Get a cell from the cells dictionary using a tuple key.

    Usage: {{ cells|get_cell:key_tuple }}
    """
    return cells.get(key_tuple, {"status": "unlinked", "linked": False})


@register.simple_tag
def matrix_cell(cells, req_external_id, test_nodeid):
    """Get a cell from the cells dictionary.

    Usage: {% matrix_cell cells req.external_id test.nodeid as cell %}
    """
    key = (req_external_id, test_nodeid)
    return cells.get(key, {"status": "unlinked", "linked": False, "test_result_id": None})

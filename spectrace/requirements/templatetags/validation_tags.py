"""Template tags for validation run views."""
import json

from django import template

register = template.Library()


@register.filter
def steps_passed(steps):
    """Count the number of passed steps.

    Usage: {{ result.steps|steps_passed }}
    """
    if not steps:
        return 0
    return sum(1 for s in steps if s.get('passed', False))


@register.filter
def steps_failed(steps):
    """Count the number of failed steps.

    Usage: {{ result.steps|steps_failed }}
    """
    if not steps:
        return 0
    return sum(1 for s in steps if not s.get('passed', False))


@register.filter
def multiply(value, arg):
    """Multiply the value by the argument.

    Usage: {{ value|multiply:100 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """Divide the value by the argument.

    Usage: {{ value|divide:100 }}
    """
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def pprint(value):
    """Pretty print JSON data.

    Usage: {{ context|pprint }}
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return str(value)


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key.

    Usage: {{ mydict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def subtract(value, arg):
    """Subtract the argument from the value.

    Usage: {{ value|subtract:10 }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def change_indicator(change_type):
    """Return the indicator emoji/icon for a change type.

    Usage: {% change_indicator change_type %}
    """
    indicators = {
        'improved': '<span class="text-green-500" title="Improved">&#x2714;</span>',
        'regressed': '<span class="text-red-500" title="Regressed">&#x2716;</span>',
        'unchanged': '<span class="text-gray-400" title="Unchanged">&#x25CB;</span>',
        'new': '<span class="text-blue-500" title="New">&#x2605;</span>',
        'removed': '<span class="text-gray-500" title="Removed">&#x2212;</span>',
    }
    return indicators.get(change_type, '')


@register.filter
def status_class(status):
    """Return CSS class for a validation status.

    Usage: {{ result.status|status_class }}
    """
    classes = {
        'success': 'text-green-600 bg-green-100 dark:text-green-400 dark:bg-green-900/30',
        'failure': 'text-red-600 bg-red-100 dark:text-red-400 dark:bg-red-900/30',
        'unknown': 'text-yellow-600 bg-yellow-100 dark:text-yellow-400 dark:bg-yellow-900/30',
        'not_run': 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-700',
    }
    return classes.get(status, classes['unknown'])


@register.filter
def change_class(change_type):
    """Return CSS class for a change type.

    Usage: {{ change.change_type|change_class }}
    """
    classes = {
        'improved': 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/20',
        'regressed': 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/20',
        'unchanged': 'text-gray-600 bg-gray-50 dark:text-gray-400 dark:bg-gray-800',
        'new': 'text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-900/20',
        'removed': 'text-gray-500 bg-gray-100 dark:text-gray-500 dark:bg-gray-800',
    }
    return classes.get(change_type, classes['unchanged'])

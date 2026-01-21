"""Dashboard callback for SpecTrace metrics and tree data."""
from django.db.models import Count, Q
from .models import Requirement


def dashboard_callback(request, context):
    """Provide dashboard metrics for the admin index page.

    Returns context with:
    - total_requirements, passing_count, failing_count, untested_count
    - passing_pct, failing_pct, untested_pct
    - requirements_tree (annotated list for hierarchical display)
    """
    total = Requirement.objects.count()

    if total > 0:
        metrics = Requirement.objects.aggregate(
            passing=Count('id', filter=Q(verification_status='passing')),
            failing=Count('id', filter=Q(verification_status='failing')),
            untested=Count('id', filter=Q(verification_status='untested')),
        )

        context.update({
            'total_requirements': total,
            'passing_count': metrics['passing'],
            'failing_count': metrics['failing'],
            'untested_count': metrics['untested'],
            'passing_pct': round(metrics['passing'] * 100 / total, 1),
            'failing_pct': round(metrics['failing'] * 100 / total, 1),
            'untested_pct': round(metrics['untested'] * 100 / total, 1),
        })
    else:
        context.update({
            'total_requirements': 0,
            'passing_count': 0,
            'failing_count': 0,
            'untested_count': 0,
            'passing_pct': 0,
            'failing_pct': 0,
            'untested_pct': 0,
        })

    # Get requirements tree for hierarchical display
    # get_annotated_list returns [(node, info), ...] where info has 'open', 'close', 'level'
    context['requirements_tree'] = Requirement.get_annotated_list()

    return context

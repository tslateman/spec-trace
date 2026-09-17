"""Coverage rates and counts for one project, read from the requirement tree."""

from django.db.models import Avg, Count, Q

from requirements.models import Requirement


def coverage_metrics(project: str) -> dict:
    """Measure specification, structure, and verification coverage for one project.

    Returns:
        project, the three rates as fractions of 1, and the total, non_draft, and
        passing counts behind them. An empty project reports zero rates.
    """
    counts = Requirement.objects.filter(project=project).aggregate(
        total=Count("id"),
        non_draft=Count("id", filter=~Q(status="draft")),
        passing=Count("id", filter=Q(verification_status="passing")),
        avg_structure=Avg("structure_completeness"),
    )
    total = counts["total"]

    return {
        "project": project,
        "specification_rate": counts["non_draft"] / total if total else 0.0,
        "structure_rate": counts["avg_structure"] or 0.0,
        "verification_rate": counts["passing"] / total if total else 0.0,
        "total": total,
        "non_draft": counts["non_draft"],
        "passing": counts["passing"],
    }

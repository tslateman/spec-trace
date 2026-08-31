"""Dashboard callback for SpecTrace metrics and tree data."""

from django.db.models import Avg, Count, Q

from .models import SLO, InAppValidation, Requirement, VerificationMethod
from .projects import AmbiguousProjectError, resolve_project


def dashboard_callback(request, context):
    """Provide dashboard metrics for the admin index page.

    Returns context with:
    - total_requirements, passing_count, failing_count, untested_count
    - passing_pct, failing_pct, untested_pct
    - verification_method_* metrics
    - slo_* metrics
    - inapp_* metrics
    - requirements_tree (annotated list for hierarchical display)

    Requirement metrics cover one project: the one named in `?project=`, else
    the project this installation owns, else the only project stored.
    """
    stored_projects = Requirement.project_names()
    try:
        project = resolve_project(request.GET.get("project"), stored_projects)
    except AmbiguousProjectError:
        project = stored_projects[0]
    owned = Requirement.objects.filter(project=project)
    context["current_project"] = project
    context["available_projects"] = stored_projects

    total = owned.count()

    if total > 0:
        # Verification status metrics
        status_metrics = owned.aggregate(
            passing=Count("id", filter=Q(verification_status="passing")),
            failing=Count("id", filter=Q(verification_status="failing")),
            untested=Count("id", filter=Q(verification_status="untested")),
        )

        # Verification method breakdown
        method_metrics = owned.aggregate(
            method_test=Count("id", filter=Q(verification_method=VerificationMethod.TEST)),
            method_inapp=Count("id", filter=Q(verification_method=VerificationMethod.INAPP)),
            method_both=Count("id", filter=Q(verification_method=VerificationMethod.BOTH)),
            method_unspecified=Count(
                "id", filter=Q(verification_method=VerificationMethod.UNSPECIFIED)
            ),
        )

        # SLO status breakdown
        slo_metrics = owned.aggregate(
            slo_met=Count("id", filter=Q(slo_status="met")),
            slo_at_risk=Count("id", filter=Q(slo_status="at_risk")),
            slo_breached=Count("id", filter=Q(slo_status="breached")),
            slo_not_linked=Count("id", filter=Q(slo_status="not_linked")),
        )

        # Requirements with SLO links
        reqs_with_slos = owned.filter(slos__isnull=False).distinct().count()

        # Spec coverage metrics
        coverage_metrics = owned.aggregate(
            non_draft=Count("id", filter=~Q(status="draft")),
            avg_structure=Avg("structure_completeness"),
        )
        non_draft = coverage_metrics["non_draft"]
        avg_structure = coverage_metrics["avg_structure"] or 0.0

        context.update(
            {
                # Basic verification status
                "total_requirements": total,
                "passing_count": status_metrics["passing"],
                "failing_count": status_metrics["failing"],
                "untested_count": status_metrics["untested"],
                "passing_pct": round(status_metrics["passing"] * 100 / total, 1),
                "failing_pct": round(status_metrics["failing"] * 100 / total, 1),
                "untested_pct": round(status_metrics["untested"] * 100 / total, 1),
                # Spec coverage rates
                "spec_rate": round(non_draft * 100 / total, 1),
                "struct_rate": round(avg_structure * 100, 1),
                "verif_rate": round(status_metrics["passing"] * 100 / total, 1),
                # Verification method breakdown
                "method_test_count": method_metrics["method_test"],
                "method_inapp_count": method_metrics["method_inapp"],
                "method_both_count": method_metrics["method_both"],
                "method_unspecified_count": method_metrics["method_unspecified"],
                # SLO status
                "slo_met_count": slo_metrics["slo_met"],
                "slo_at_risk_count": slo_metrics["slo_at_risk"],
                "slo_breached_count": slo_metrics["slo_breached"],
                "slo_not_linked_count": slo_metrics["slo_not_linked"],
                "reqs_with_slos": reqs_with_slos,
            }
        )
    else:
        context.update(
            {
                "total_requirements": 0,
                "passing_count": 0,
                "failing_count": 0,
                "untested_count": 0,
                "passing_pct": 0,
                "failing_pct": 0,
                "untested_pct": 0,
                "spec_rate": 0,
                "struct_rate": 0,
                "verif_rate": 0,
                "method_test_count": 0,
                "method_inapp_count": 0,
                "method_both_count": 0,
                "method_unspecified_count": 0,
                "slo_met_count": 0,
                "slo_at_risk_count": 0,
                "slo_breached_count": 0,
                "slo_not_linked_count": 0,
                "reqs_with_slos": 0,
            }
        )

    # In-App Validation metrics
    # Note: status is a computed property (from latest result), so we must count manually
    total_validations = InAppValidation.objects.count()
    if total_validations > 0:
        success_count = 0
        failure_count = 0
        not_run_count = 0
        for validation in InAppValidation.objects.prefetch_related("results"):
            status = validation.status
            if status == "success":
                success_count += 1
            elif status == "failure":
                failure_count += 1
            else:  # not_run or unknown
                not_run_count += 1
        context.update(
            {
                "total_inapp_validations": total_validations,
                "inapp_success_count": success_count,
                "inapp_failure_count": failure_count,
                "inapp_not_run_count": not_run_count,
            }
        )
    else:
        context.update(
            {
                "total_inapp_validations": 0,
                "inapp_success_count": 0,
                "inapp_failure_count": 0,
                "inapp_not_run_count": 0,
            }
        )

    # SLO metrics
    total_slos = SLO.objects.count()
    if total_slos > 0:
        slo_obj_metrics = SLO.objects.aggregate(
            met=Count("id", filter=Q(status="met")),
            at_risk=Count("id", filter=Q(status="at_risk")),
            breached=Count("id", filter=Q(status="breached")),
        )
        context.update(
            {
                "total_slos": total_slos,
                "slos_met": slo_obj_metrics["met"],
                "slos_at_risk": slo_obj_metrics["at_risk"],
                "slos_breached": slo_obj_metrics["breached"],
            }
        )
    else:
        context.update(
            {
                "total_slos": 0,
                "slos_met": 0,
                "slos_at_risk": 0,
                "slos_breached": 0,
            }
        )

    # Get requirements tree for hierarchical display
    # get_annotated_list returns [(node, info), ...] where info has 'open', 'close', 'level'
    context["requirements_tree"] = Requirement.get_annotated_list()

    return context

"""Data layer for flow status dashboard views."""
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    VerificationFlow,
    VerificationFlowRun,
    VerificationFlowStep,
    VerificationFlowSource,
    VerificationFlowStatus,
)
from .flows.definitions import REGISTERED_FLOWS, get_flow_by_name


def get_flows_overview() -> dict:
    """Get overview of all registered flows with latest run status and stats.

    Returns:
        {
            'flows': [
                {
                    'name': str,
                    'display_name': str,
                    'description': str,
                    'steps': list,
                    'version': int,
                    'latest_run': VerificationFlowRun | None,
                    'total_runs': int,
                    'passed_runs': int,
                    'failed_runs': int,
                },
                ...
            ],
            'summary': {
                'total_flows': int,
                'healthy': int,  # Flows with latest run passed
                'failing': int,  # Flows with latest run failed
                'running': int,  # Flows with latest run running
                'not_run': int,  # Flows with no runs
            }
        }
    """
    flows_data = []
    summary = {
        'total_flows': len(REGISTERED_FLOWS),
        'healthy': 0,
        'failing': 0,
        'running': 0,
        'not_run': 0,
    }

    for flow_def in REGISTERED_FLOWS:
        # Get flow from DB (may not exist if not synced)
        flow = VerificationFlow.objects.filter(name=flow_def.name).first()

        if flow:
            # Get stats for this flow
            runs = flow.runs.all()
            total_runs = runs.count()
            passed_runs = runs.filter(status=VerificationFlowStatus.PASSED).count()
            failed_runs = runs.filter(status=VerificationFlowStatus.FAILED).count()
            latest_run = runs.order_by('-started_at').first()

            # Update summary based on latest run status
            if latest_run:
                if latest_run.status == VerificationFlowStatus.PASSED:
                    summary['healthy'] += 1
                elif latest_run.status == VerificationFlowStatus.FAILED:
                    summary['failing'] += 1
                elif latest_run.status == VerificationFlowStatus.RUNNING:
                    summary['running'] += 1
            else:
                summary['not_run'] += 1
        else:
            total_runs = 0
            passed_runs = 0
            failed_runs = 0
            latest_run = None
            summary['not_run'] += 1

        flows_data.append({
            'name': flow_def.name,
            'display_name': flow_def.display_name,
            'description': flow_def.description,
            'steps': flow_def.steps,
            'version': flow_def.version,
            'latest_run': latest_run,
            'total_runs': total_runs,
            'passed_runs': passed_runs,
            'failed_runs': failed_runs,
        })

    return {
        'flows': flows_data,
        'summary': summary,
    }


def get_flow_runs_data(
    flow_name: str, page: int = 1, per_page: int = 25, filters: dict | None = None
) -> dict:
    """Get paginated runs for a specific flow.

    Args:
        flow_name: The flow name to get runs for
        page: Page number (1-indexed)
        per_page: Items per page
        filters: Optional dict with keys:
            - status: Filter by run status (passed, failed, running)
            - date_from: Filter runs started on or after this date
            - date_to: Filter runs started on or before this date

    Returns:
        {
            'flow_def': FlowDef | None,
            'flow': VerificationFlow | None,
            'runs': [
                {
                    'id': int,
                    'status': str,
                    'source': str,
                    'started_at': datetime,
                    'completed_at': datetime | None,
                    'duration_ms': int | None,
                    'steps_passed': int,
                    'steps_failed': int,
                    'total_steps': int,
                },
                ...
            ],
            'pagination': {
                'current_page': int,
                'total_pages': int,
                'total_items': int,
                'has_previous': bool,
                'has_next': bool,
                'previous_page': int | None,
                'next_page': int | None,
            },
            'summary': {
                'total_runs': int,
                'passed': int,
                'failed': int,
                'pass_rate': float,
            }
        }
    """
    # Get flow definition from code
    flow_def = get_flow_by_name(flow_name)

    # Get flow from DB
    flow = VerificationFlow.objects.filter(name=flow_name).first()

    if not flow:
        return {
            'flow_def': flow_def,
            'flow': None,
            'runs': [],
            'pagination': {
                'current_page': 1,
                'total_pages': 0,
                'total_items': 0,
                'has_previous': False,
                'has_next': False,
                'previous_page': None,
                'next_page': None,
            },
            'summary': {
                'total_runs': 0,
                'passed': 0,
                'failed': 0,
                'pass_rate': 0.0,
            }
        }

    # Query runs with step counts
    queryset = flow.runs.annotate(
        total_steps_count=Count('steps'),
        steps_passed_count=Count('steps', filter=Q(steps__passed=True)),
        steps_failed_count=Count('steps', filter=Q(steps__passed=False)),
    )

    # Apply filters
    if filters:
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        if filters.get('date_from'):
            queryset = queryset.filter(started_at__date__gte=filters['date_from'])
        if filters.get('date_to'):
            queryset = queryset.filter(started_at__date__lte=filters['date_to'])

    queryset = queryset.order_by('-started_at')

    # Calculate summary stats
    total_runs = queryset.count()
    passed = queryset.filter(status=VerificationFlowStatus.PASSED).count()
    failed = queryset.filter(status=VerificationFlowStatus.FAILED).count()
    pass_rate = round((passed / total_runs * 100), 1) if total_runs > 0 else 0.0

    # Paginate
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page)

    # Build run data
    runs = []
    for run in page_obj:
        runs.append({
            'id': run.id,
            'status': run.status,
            'source': run.source,
            'started_at': run.started_at,
            'completed_at': run.completed_at,
            'duration_ms': run.duration_ms,
            'steps_passed': run.steps_passed_count,
            'steps_failed': run.steps_failed_count,
            'total_steps': run.total_steps_count,
        })

    return {
        'flow_def': flow_def,
        'flow': flow,
        'runs': runs,
        'pagination': {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        },
        'summary': {
            'total_runs': total_runs,
            'passed': passed,
            'failed': failed,
            'pass_rate': pass_rate,
        }
    }


def get_run_detail(run_id: int) -> dict:
    """Get detailed information for a specific flow run.

    Args:
        run_id: The run ID to get details for

    Returns:
        {
            'run': VerificationFlowRun | None,
            'flow_def': FlowDef | None,
            'steps': [
                {
                    'step_order': int,
                    'name': str,
                    'display_name': str,
                    'passed': bool,
                    'details': str,
                    'error_message': str,
                    'response_status': int | None,
                    'response_body': str,
                    'started_at': datetime,
                    'completed_at': datetime,
                    'duration_ms': int | None,
                },
                ...
            ],
            'previous_run': VerificationFlowRun | None,
            'next_run': VerificationFlowRun | None,
            'summary': {
                'total_steps': int,
                'passed': int,
                'failed': int,
            }
        }
    """
    try:
        run = VerificationFlowRun.objects.select_related('flow').get(id=run_id)
    except VerificationFlowRun.DoesNotExist:
        return {
            'run': None,
            'flow_def': None,
            'steps': [],
            'previous_run': None,
            'next_run': None,
            'summary': {
                'total_steps': 0,
                'passed': 0,
                'failed': 0,
            }
        }

    # Get flow definition
    flow_def = get_flow_by_name(run.flow.name)

    # Build step display name lookup from flow definition
    step_display_names = {}
    if flow_def:
        for step in flow_def.steps:
            step_display_names[step.name] = step.display_name

    # Get steps
    db_steps = run.steps.order_by('step_order')
    steps = []
    passed_count = 0
    failed_count = 0

    for step in db_steps:
        if step.passed:
            passed_count += 1
        else:
            failed_count += 1

        steps.append({
            'step_order': step.step_order,
            'name': step.name,
            'display_name': step_display_names.get(step.name, step.name),
            'passed': step.passed,
            'details': step.details,
            'error_message': step.error_message,
            'response_status': step.response_status,
            'response_body': step.response_body,
            'started_at': step.started_at,
            'completed_at': step.completed_at,
            'duration_ms': step.duration_ms,
        })

    # Get adjacent runs (for same flow)
    previous_run = VerificationFlowRun.objects.filter(
        flow=run.flow,
        started_at__lt=run.started_at
    ).order_by('-started_at').first()

    next_run = VerificationFlowRun.objects.filter(
        flow=run.flow,
        started_at__gt=run.started_at
    ).order_by('started_at').first()

    return {
        'run': run,
        'flow_def': flow_def,
        'steps': steps,
        'previous_run': previous_run,
        'next_run': next_run,
        'summary': {
            'total_steps': len(steps),
            'passed': passed_count,
            'failed': failed_count,
        }
    }


def setup_demo_data(clear: bool = True) -> dict:
    """Set up demo data for flow status dashboard.

    Args:
        clear: Whether to clear existing runs first

    Returns:
        {
            'flows_synced': int,
            'runs_created': list of run IDs,
            'runs_cleared': int,
        }
    """
    result = {
        'flows_synced': 0,
        'runs_created': [],
        'runs_cleared': 0,
    }

    # Sync all registered flows to DB
    for flow_def in REGISTERED_FLOWS:
        VerificationFlow.objects.update_or_create(
            name=flow_def.name,
            defaults={
                'display_name': flow_def.display_name,
                'description': flow_def.description,
                'steps': [
                    {
                        'name': s.name,
                        'handler': s.handler,
                        'display_name': s.display_name,
                    }
                    for s in flow_def.steps
                ],
                'version': flow_def.version,
                'synced_at': timezone.now(),
            }
        )
        result['flows_synced'] += 1

    # Create demo runs for all registered flows
    for flow_def in REGISTERED_FLOWS:
        flow = VerificationFlow.objects.get(name=flow_def.name)

        # Clear existing runs if requested
        if clear:
            deleted, _ = flow.runs.all().delete()
            result['runs_cleared'] += deleted

        # Create demo runs
        runs = [
            _create_passed_run_linear(flow),
            _create_failed_run_auth(flow),
            _create_failed_run_config(flow),
        ]
        result['runs_created'].extend([r.id for r in runs])

    return result


def _create_passed_run_linear(flow):
    """Create a fully passing run - successful Linear connection check."""
    import json

    context = {
        'triggered_by': 'manual_health_check',
        'integration': 'linear',
    }

    run = VerificationFlowRun.objects.create(
        flow=flow,
        status=VerificationFlowStatus.PASSED,
        source=VerificationFlowSource.MANUAL,
        context=context,
        started_at=timezone.now() - timedelta(hours=1),
        completed_at=timezone.now() - timedelta(hours=1) + timedelta(seconds=3),
    )

    steps = [
        (
            'config', True,
            'LINEAR_API_KEY present, format valid (lin_api_...)',
            '',
            None,
            '',
        ),
        (
            'auth', True,
            'Authenticated as: team@example.com (Acme Corp)',
            '',
            200,
            json.dumps({
                'viewer': {
                    'id': 'user_abc123',
                    'email': 'team@example.com',
                    'name': 'Acme Corp',
                },
            }, indent=2),
        ),
        (
            'permissions', True,
            'Read access to issues confirmed, 42 issues accessible',
            '',
            200,
            json.dumps({
                'issues': {'totalCount': 42},
                'teams': {'totalCount': 3},
            }, indent=2),
        ),
    ]
    _create_steps(run, steps)
    return run


def _create_failed_run_auth(flow):
    """Create a run that fails at auth step - invalid API key."""
    import json

    context = {
        'triggered_by': 'scheduled_health_check',
        'integration': 'linear',
    }

    run = VerificationFlowRun.objects.create(
        flow=flow,
        status=VerificationFlowStatus.FAILED,
        source=VerificationFlowSource.SCHEDULED,
        context=context,
        started_at=timezone.now() - timedelta(hours=2),
        completed_at=timezone.now() - timedelta(hours=2) + timedelta(seconds=2),
    )

    steps = [
        (
            'config', True,
            'LINEAR_API_KEY present, format valid',
            '',
            None,
            '',
        ),
        (
            'auth', False,
            '',
            'Authentication failed: API key rejected by Linear. '
            'The key may have been revoked or expired.',
            401,
            json.dumps({
                'error': 'Unauthorized',
                'message': 'Invalid API key',
            }, indent=2),
        ),
    ]
    _create_steps(run, steps)
    return run


def _create_failed_run_config(flow):
    """Create a run that fails at config step - missing API key."""
    import json

    context = {
        'triggered_by': 'startup_check',
        'integration': 'linear',
    }

    run = VerificationFlowRun.objects.create(
        flow=flow,
        status=VerificationFlowStatus.FAILED,
        source=VerificationFlowSource.API,
        context=context,
        started_at=timezone.now() - timedelta(minutes=30),
        completed_at=timezone.now() - timedelta(minutes=30) + timedelta(seconds=1),
    )

    steps = [
        (
            'config', False,
            '',
            'Configuration error: LINEAR_API_KEY environment variable not set. '
            'Set this in your .env file or environment.',
            None,
            json.dumps({
                'missing_config': ['LINEAR_API_KEY'],
                'setup_guide': 'https://docs.spectrace.dev/integrations/linear',
            }, indent=2),
        ),
    ]
    _create_steps(run, steps)
    return run


def _create_steps(run, steps):
    """Create step records for a run."""
    base_time = run.started_at
    for i, (name, passed, details, error, status_code, response_body) in enumerate(steps):
        VerificationFlowStep.objects.create(
            flow_run=run,
            step_order=i,
            name=name,
            passed=passed,
            details=details,
            error_message=error,
            response_status=status_code,
            response_body=response_body,
            started_at=base_time + timedelta(seconds=i * 2),
            completed_at=base_time + timedelta(seconds=i * 2 + 1),
        )

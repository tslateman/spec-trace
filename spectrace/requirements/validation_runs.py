"""Data layer for validation runs views."""
from collections import defaultdict
from django.core.paginator import Paginator
from django.db.models import Count, Q

from .models import (
    InAppValidationRun,
    InAppValidationResult,
    InAppValidationStatus,
)


def get_validation_runs_data(page: int = 1, per_page: int = 25, filters: dict | None = None) -> dict:
    """Get paginated validation runs with stats.

    Args:
        page: Page number (1-indexed)
        per_page: Items per page
        filters: Optional filter dict with keys:
            - source: Filter by source string
            - vendor: Filter by vendor
            - date_from: Filter by start date
            - date_to: Filter by end date

    Returns:
        {
            'runs': List of run dicts with stats,
            'pagination': {
                'current_page': int,
                'total_pages': int,
                'total_items': int,
                'has_previous': bool,
                'has_next': bool,
            },
            'summary': {
                'total_runs': int,
                'avg_pass_rate': float,
                'recent_failures': int,
                'unique_vendors': int,
            }
        }
    """
    filters = filters or {}

    # Build queryset with annotations
    queryset = InAppValidationRun.objects.annotate(
        total_count=Count('results'),
        success_count=Count('results', filter=Q(results__status=InAppValidationStatus.SUCCESS)),
        failure_count=Count('results', filter=Q(results__status=InAppValidationStatus.FAILURE)),
    ).order_by('-imported_at')

    # Apply filters
    if filters.get('source'):
        queryset = queryset.filter(source__icontains=filters['source'])

    if filters.get('date_from'):
        queryset = queryset.filter(imported_at__gte=filters['date_from'])

    if filters.get('date_to'):
        queryset = queryset.filter(imported_at__lte=filters['date_to'])

    # For vendor filter, we need to filter by results
    if filters.get('vendor'):
        queryset = queryset.filter(results__validation__vendor=filters['vendor']).distinct()

    # Paginate
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page)

    # Build run data
    runs = []
    for run in page_obj:
        total = run.total_count
        success = run.success_count
        failure = run.failure_count
        pass_rate = (success / total * 100) if total > 0 else 0

        runs.append({
            'id': run.id,
            'source': run.source,
            'imported_at': run.imported_at,
            'total': total,
            'success': success,
            'failure': failure,
            'pass_rate': round(pass_rate, 1),
        })

    # Calculate summary stats
    all_runs = InAppValidationRun.objects.annotate(
        total_count=Count('results'),
        success_count=Count('results', filter=Q(results__status=InAppValidationStatus.SUCCESS)),
    )

    total_runs = all_runs.count()

    # Calculate average pass rate
    total_results = 0
    total_success = 0
    for run in all_runs:
        total_results += run.total_count
        total_success += run.success_count
    avg_pass_rate = (total_success / total_results * 100) if total_results > 0 else 0

    # Count recent failures (last 7 days)
    from django.utils import timezone
    from datetime import timedelta
    week_ago = timezone.now() - timedelta(days=7)
    recent_failures = InAppValidationResult.objects.filter(
        status=InAppValidationStatus.FAILURE,
        checked_at__gte=week_ago,
    ).count()

    # Count unique vendors
    unique_vendors = InAppValidationResult.objects.values(
        'validation__vendor'
    ).distinct().exclude(validation__vendor='').count()

    return {
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
            'avg_pass_rate': round(avg_pass_rate, 1),
            'recent_failures': recent_failures,
            'unique_vendors': unique_vendors,
        }
    }


def get_run_results_grouped(run: InAppValidationRun) -> dict:
    """Get validation results grouped by vendor.

    Args:
        run: The validation run to get results for

    Returns:
        {
            'vendor_name': [
                {
                    'id': int,
                    'validation_name': str,
                    'status': str,
                    'message': str,
                    'checked_at': datetime,
                    'steps': list,
                    'context': dict,
                    'steps_passed': int,
                    'steps_failed': int,
                    'first_failed_step': dict | None,
                },
                ...
            ],
            ...
        }
    """
    results_by_vendor = defaultdict(list)

    results = run.results.select_related('validation').order_by(
        'validation__vendor', 'validation__name'
    )

    for result in results:
        vendor = result.validation.vendor or 'Unassigned'
        steps = result.steps or []

        # Calculate step stats
        steps_passed = sum(1 for s in steps if s.get('passed', False))
        steps_failed = len(steps) - steps_passed

        # Find first failed step
        first_failed = None
        for step in steps:
            if not step.get('passed', False):
                first_failed = step
                break

        results_by_vendor[vendor].append({
            'id': result.id,
            'validation_name': result.validation.name,
            'requirement_id': result.validation.requirement.external_id,
            'requirement_title': result.validation.requirement.title,
            'status': result.status,
            'message': result.message,
            'checked_at': result.checked_at,
            'steps': steps,
            'context': result.context or {},
            'steps_passed': steps_passed,
            'steps_failed': steps_failed,
            'first_failed_step': first_failed,
        })

    # Sort vendors alphabetically
    return dict(sorted(results_by_vendor.items()))


def build_run_comparison(run_a: InAppValidationRun, run_b: InAppValidationRun) -> dict:
    """Build comparison data between two validation runs.

    Args:
        run_a: First run (typically older)
        run_b: Second run (typically newer)

    Returns:
        {
            'run_a': {'id': int, 'source': str, 'imported_at': datetime},
            'run_b': {'id': int, 'source': str, 'imported_at': datetime},
            'changes': [
                {
                    'validation_name': str,
                    'vendor': str,
                    'status_a': str | None,
                    'status_b': str | None,
                    'change_type': str,  # 'improved', 'regressed', 'unchanged', 'new', 'removed'
                },
                ...
            ],
            'summary': {
                'improved': int,
                'regressed': int,
                'unchanged': int,
                'new': int,
                'removed': int,
            }
        }
    """
    # Get results from both runs keyed by validation ID
    results_a = {
        r.validation_id: r
        for r in run_a.results.select_related('validation')
    }
    results_b = {
        r.validation_id: r
        for r in run_b.results.select_related('validation')
    }

    # Get all unique validation IDs
    all_validation_ids = set(results_a.keys()) | set(results_b.keys())

    changes = []
    summary = {'improved': 0, 'regressed': 0, 'unchanged': 0, 'new': 0, 'removed': 0}

    for val_id in all_validation_ids:
        result_a = results_a.get(val_id)
        result_b = results_b.get(val_id)

        # Determine change type
        if result_a is None:
            change_type = 'new'
            validation = result_b.validation
            status_a = None
            status_b = result_b.status
        elif result_b is None:
            change_type = 'removed'
            validation = result_a.validation
            status_a = result_a.status
            status_b = None
        else:
            validation = result_b.validation
            status_a = result_a.status
            status_b = result_b.status

            if status_a == status_b:
                change_type = 'unchanged'
            elif status_a == InAppValidationStatus.FAILURE and status_b == InAppValidationStatus.SUCCESS:
                change_type = 'improved'
            elif status_a == InAppValidationStatus.SUCCESS and status_b == InAppValidationStatus.FAILURE:
                change_type = 'regressed'
            else:
                change_type = 'unchanged'  # Other status transitions

        summary[change_type] += 1

        changes.append({
            'validation_name': validation.name,
            'vendor': validation.vendor or 'Unassigned',
            'requirement_id': validation.requirement.external_id,
            'status_a': status_a,
            'status_b': status_b,
            'change_type': change_type,
        })

    # Sort changes: regressions first, then improved, then new, then removed, then unchanged
    change_order = {'regressed': 0, 'improved': 1, 'new': 2, 'removed': 3, 'unchanged': 4}
    changes.sort(key=lambda c: (change_order.get(c['change_type'], 5), c['vendor'], c['validation_name']))

    return {
        'run_a': {
            'id': run_a.id,
            'source': run_a.source,
            'imported_at': run_a.imported_at,
        },
        'run_b': {
            'id': run_b.id,
            'source': run_b.source,
            'imported_at': run_b.imported_at,
        },
        'changes': changes,
        'summary': summary,
    }


def get_adjacent_runs(run: InAppValidationRun) -> dict:
    """Get the previous and next runs relative to a given run.

    Args:
        run: The current run

    Returns:
        {
            'previous': InAppValidationRun | None,
            'next': InAppValidationRun | None,
        }
    """
    previous_run = InAppValidationRun.objects.filter(
        imported_at__lt=run.imported_at
    ).order_by('-imported_at').first()

    next_run = InAppValidationRun.objects.filter(
        imported_at__gt=run.imported_at
    ).order_by('imported_at').first()

    return {
        'previous': previous_run,
        'next': next_run,
    }


def get_unique_vendors() -> list:
    """Get list of unique vendors with validation results.

    Returns:
        List of vendor names, sorted alphabetically
    """
    vendors = InAppValidationResult.objects.values_list(
        'validation__vendor', flat=True
    ).distinct().exclude(validation__vendor='')

    return sorted(set(vendors))


def get_unique_sources() -> list:
    """Get list of unique sources from validation runs.

    Returns:
        List of source strings, sorted alphabetically
    """
    sources = InAppValidationRun.objects.values_list(
        'source', flat=True
    ).distinct()

    return sorted(set(sources))

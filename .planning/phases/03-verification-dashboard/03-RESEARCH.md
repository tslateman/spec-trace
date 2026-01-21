# Phase 3: Verification & Core Dashboard - Research

**Researched:** 2026-01-20
**Domain:** JUnit XML parsing, Django dashboard UI, verification status computation
**Confidence:** HIGH

## Summary

This phase implements JUnit XML test result import, verification status computation (Passing/Failing/Untested), and a core dashboard displaying requirements with status indicators. The research confirms a straightforward approach: use `junitparser` (mature Python library, 1.8M weekly downloads) for XML parsing, store test results in new Django models, compute status on import with denormalized caching, and build the dashboard using `django-unfold` (modern Tailwind-based admin theme).

The key design decision is to store verification status directly on the Requirement model (denormalized) for dashboard performance, while maintaining the source data (test results, links) for audit and refresh capability. Status computation follows the user's locked decisions: "all pass = Passing, any fail = Failing, no tests = Untested."

**Primary recommendation:** Use junitparser for XML parsing, django-unfold for dashboard UI, and compute status on import with stored results. The dashboard extends django-unfold's admin with a custom index template showing the tree view and metrics.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| junitparser | >=4.0 | Parse pytest JUnit XML output | 1.8M weekly downloads, explicit pytest support, handles multiple failures/errors |
| django-unfold | >=0.76 | Modern admin dashboard theme | Tailwind CSS based, component library, dashboard callbacks, Django 5.2 support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest (--junitxml) | >=9.0 (installed) | Generate JUnit XML | Always - built into pytest |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| junitparser | xml.etree.ElementTree | junitparser handles pytest quirks (multiple failures), type checking |
| django-unfold | django-admin-interface | unfold has modern UI, component system, better dashboard support |
| Stored status | On-demand compute | Stored is faster for dashboard, compute every pageload too slow |

**Installation:**
```bash
pip install junitparser django-unfold
```

Add to pyproject.toml:
```toml
dependencies = [
    # ... existing
    "junitparser>=4.0,<5.0",
    "django-unfold>=0.76,<1.0",
]
```

## Architecture Patterns

### Recommended Project Structure
```
spectrace/
├── requirements/
│   ├── models.py              # Requirement (exists), TestResult, TestRun (new)
│   ├── admin.py               # Updated with unfold.admin.ModelAdmin
│   ├── importer.py            # JUnit XML import logic (new)
│   ├── status.py              # Status computation logic (new)
│   ├── management/
│   │   └── commands/
│   │       ├── parse_specs.py     # (exists)
│   │       ├── extract_links.py   # (exists)
│   │       └── import_results.py  # JUnit XML import command (new)
│   └── templates/
│       └── admin/
│           └── index.html     # Custom dashboard template
├── spectrace/
│   └── settings.py            # Updated with unfold config
└── templates/
    └── admin/
        └── index.html         # Dashboard with tree view and metrics
```

### Pattern 1: Test Result Data Model
**What:** Store test results and link to requirements
**When to use:** Always - needed for status computation and audit trail

```python
# Source: Based on JUnit XML schema and RTM best practices
from django.db import models

class TestRun(models.Model):
    """A single pytest run that generated JUnit XML."""
    imported_at = models.DateTimeField(auto_now_add=True)
    source_file = models.CharField(max_length=500, help_text="Path to JUnit XML file")
    total_tests = models.IntegerField(default=0)
    passed = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)

    class Meta:
        ordering = ['-imported_at']


class TestResult(models.Model):
    """Individual test case result from a pytest run."""

    class Status(models.TextChoices):
        PASSED = 'passed', 'Passed'
        FAILED = 'failed', 'Failed'
        ERROR = 'error', 'Error'
        SKIPPED = 'skipped', 'Skipped'

    test_run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name='results')
    test_nodeid = models.CharField(max_length=500, db_index=True,
        help_text="pytest nodeid (e.g., tests/test_auth.py::test_login)")
    classname = models.CharField(max_length=300, blank=True)
    name = models.CharField(max_length=200)
    time = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=Status.choices)
    message = models.TextField(blank=True, help_text="Failure/error message")

    # Link to requirements (via extract_links JSON)
    requirements = models.ManyToManyField('Requirement', related_name='test_results', blank=True)

    class Meta:
        ordering = ['test_nodeid']
```

### Pattern 2: Status Computation Logic
**What:** Derive requirement verification status from linked test results
**When to use:** On import and on-demand refresh

```python
# Source: Based on user decisions in CONTEXT.md
from enum import Enum

class VerificationStatus(Enum):
    PASSING = 'passing'    # All linked tests pass
    FAILING = 'failing'    # Any linked test fails
    UNTESTED = 'untested'  # No linked tests
    STALE = 'stale'        # Tests not in latest run

def compute_status(requirement, latest_run=None):
    """Compute verification status for a requirement.

    Rules (from user decisions):
    - All linked tests pass -> Passing
    - Any linked test fails/errors -> Failing
    - No linked tests -> Untested
    - Tests not in latest import -> Stale (optional indicator)
    """
    linked_results = requirement.test_results.all()

    if latest_run:
        # Filter to only tests from latest run
        linked_results = linked_results.filter(test_run=latest_run)

    if not linked_results.exists():
        return VerificationStatus.UNTESTED

    statuses = linked_results.values_list('status', flat=True)

    if 'failed' in statuses or 'error' in statuses:
        return VerificationStatus.FAILING

    if all(s == 'passed' for s in statuses):
        return VerificationStatus.PASSING

    # All skipped counts as untested for verification purposes
    return VerificationStatus.UNTESTED
```

### Pattern 3: JUnit XML Import with junitparser
**What:** Parse pytest JUnit XML and create TestResult records
**When to use:** In import_results management command

```python
# Source: https://junitparser.readthedocs.io/ and https://pypi.org/project/junitparser/
from junitparser import JUnitXml, Failure, Error, Skipped

def import_junit_xml(file_path: str) -> TestRun:
    """Import pytest JUnit XML file into database."""
    xml = JUnitXml.fromfile(file_path)

    test_run = TestRun.objects.create(
        source_file=file_path,
        total_tests=0,
        passed=0,
        failed=0,
        errors=0,
        skipped=0,
    )

    for suite in xml:
        for case in suite:
            # Determine status from result list
            status = 'passed'  # Default: no result element = passed
            message = ''

            if case.result:
                for result in case.result:
                    if isinstance(result, Failure):
                        status = 'failed'
                        message = result.message or ''
                        break
                    elif isinstance(result, Error):
                        status = 'error'
                        message = result.message or ''
                        break
                    elif isinstance(result, Skipped):
                        status = 'skipped'
                        message = result.message or ''

            # Build nodeid from classname and name
            # pytest format: classname is "tests.test_module" or file path
            nodeid = f"{case.classname}::{case.name}" if case.classname else case.name

            TestResult.objects.create(
                test_run=test_run,
                test_nodeid=nodeid,
                classname=case.classname or '',
                name=case.name,
                time=case.time or 0.0,
                status=status,
                message=message,
            )

            # Update run counters
            test_run.total_tests += 1
            if status == 'passed':
                test_run.passed += 1
            elif status == 'failed':
                test_run.failed += 1
            elif status == 'error':
                test_run.errors += 1
            elif status == 'skipped':
                test_run.skipped += 1

    test_run.save()
    return test_run
```

### Pattern 4: Link Test Results to Requirements
**What:** Use extract_links JSON output to connect TestResults to Requirements
**When to use:** After importing results, before computing status

```python
# Source: Based on Phase 2 extract_links output format
import json
from requirements.models import Requirement, TestResult

def link_results_to_requirements(test_run, links_json_path):
    """Link test results to requirements using extract_links output.

    extract_links JSON format:
    {
        "links": [
            {"test_nodeid": "tests/test_auth.py::test_login", "requirement_id": "REQ-AUTH-01"},
            ...
        ]
    }
    """
    with open(links_json_path) as f:
        data = json.load(f)

    # Build lookup: nodeid -> requirement_ids
    nodeid_to_reqs = {}
    for link in data['links']:
        nodeid = link['test_nodeid']
        req_id = link['requirement_id']
        if nodeid not in nodeid_to_reqs:
            nodeid_to_reqs[nodeid] = []
        nodeid_to_reqs[nodeid].append(req_id)

    # Link results to requirements
    for result in test_run.results.all():
        req_ids = nodeid_to_reqs.get(result.test_nodeid, [])
        if req_ids:
            requirements = Requirement.objects.filter(external_id__in=req_ids)
            result.requirements.set(requirements)
```

### Pattern 5: Django-Unfold Dashboard Setup
**What:** Configure django-unfold and create custom dashboard
**When to use:** For admin interface and dashboard

```python
# Source: https://unfoldadmin.com/docs/installation/quickstart/
# settings.py

INSTALLED_APPS = [
    "unfold",  # MUST be before django.contrib.admin
    "unfold.contrib.filters",  # Optional: enhanced filters
    'django.contrib.admin',
    'django.contrib.auth',
    # ... rest of apps
    'treebeard',
    'requirements',
]

UNFOLD = {
    "SITE_TITLE": "SpecTrace",
    "SITE_HEADER": "SpecTrace Dashboard",
    "DASHBOARD_CALLBACK": "requirements.dashboard.dashboard_callback",
}

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],  # Add project templates dir
        'APP_DIRS': True,
        # ... options
    },
]
```

### Pattern 6: Dashboard Callback for Metrics
**What:** Provide metrics data to dashboard template
**When to use:** For displaying summary statistics

```python
# Source: https://unfoldadmin.com/docs/configuration/dashboard/
# requirements/dashboard.py

from django.db.models import Count, Q
from requirements.models import Requirement

def dashboard_callback(request, context):
    """Provide dashboard metrics for the admin index page."""
    total = Requirement.objects.count()

    if total > 0:
        passing = Requirement.objects.filter(verification_status='passing').count()
        failing = Requirement.objects.filter(verification_status='failing').count()
        untested = Requirement.objects.filter(verification_status='untested').count()

        context.update({
            'total_requirements': total,
            'passing_count': passing,
            'failing_count': failing,
            'untested_count': untested,
            'passing_pct': round(passing * 100 / total, 1),
            'failing_pct': round(failing * 100 / total, 1),
            'untested_pct': round(untested * 100 / total, 1),
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
    context['requirements_tree'] = Requirement.get_annotated_list()

    return context
```

### Anti-Patterns to Avoid
- **Computing status on every page load:** Too slow for dashboard. Store computed status on Requirement model.
- **Deleting old test results on import:** Mark as stale instead. Preserves history for debugging.
- **Hand-parsing JUnit XML:** Use junitparser. It handles pytest quirks like multiple failure elements.
- **Tightly coupling nodeid formats:** pytest nodeids can vary. Use flexible matching (normalize paths).

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JUnit XML parsing | xml.etree manual parsing | junitparser | Handles pytest quirks, multiple failures, type detection |
| Dashboard UI | Custom Django views + CSS | django-unfold | Tailwind styling, components, dark mode, responsive |
| Tree display in admin | Custom tree rendering | treebeard.admin.TreeAdmin | Already handles expand/collapse, drag-drop |
| Status percentage calc | Manual Python division | Django aggregate with Count, Q | Database-level computation, efficient |

**Key insight:** Both junitparser and django-unfold are mature, well-maintained libraries that handle edge cases you'd otherwise have to discover and fix yourself.

## Common Pitfalls

### Pitfall 1: pytest nodeid Mismatch
**What goes wrong:** Test results don't link to requirements because nodeids don't match
**Why it happens:** JUnit XML uses `classname::name` but extract_links uses file-based nodeids
**How to avoid:** Normalize nodeids during import. Map JUnit classname to file path format. Consider storing both formats.
**Warning signs:** Requirement shows "Untested" despite linked tests

### Pitfall 2: Unfold Must Be First in INSTALLED_APPS
**What goes wrong:** Admin doesn't use Unfold theme, looks like default Django admin
**Why it happens:** Unfold templates must override Django admin templates
**How to avoid:** Place `"unfold"` before `"django.contrib.admin"` in INSTALLED_APPS
**Warning signs:** Admin looks like default Django admin

### Pitfall 3: Multiple Failure/Error Elements
**What goes wrong:** Only first failure captured, or status detection fails
**Why it happens:** pytest JUnit XML can have multiple failure elements per test case
**How to avoid:** junitparser 4.x returns `case.result` as a list. Iterate and check all.
**Warning signs:** Test marked as passed when it actually failed

### Pitfall 4: Stale Link Data
**What goes wrong:** Test-requirement links outdated after code changes
**Why it happens:** extract_links must be re-run when tests change
**How to avoid:** Run extract_links as part of import_results workflow, or separately before import
**Warning signs:** New tests not linked, deleted tests still appear

### Pitfall 5: Dashboard Performance with Large Trees
**What goes wrong:** Dashboard loads slowly with hundreds of requirements
**Why it happens:** Loading full tree on every page load
**How to avoid:** Use treebeard's `get_annotated_list()` which is optimized. Consider pagination or lazy-loading for very large trees.
**Warning signs:** Dashboard takes >1s to load

### Pitfall 6: Orphan Tests Not Surfaced
**What goes wrong:** Tests without requirement links go unnoticed
**Why it happens:** Focus on requirements misses unlinked tests
**How to avoid:** Track and display orphan tests (tests with results but no requirement links) per Better Specs "Truth Decay" principle
**Warning signs:** Coverage gaps not visible

## Code Examples

Verified patterns from official sources:

### Parsing JUnit XML with junitparser
```python
# Source: https://pypi.org/project/junitparser/
from junitparser import JUnitXml, Failure, Error, Skipped

xml = JUnitXml.fromfile('junit.xml')
for suite in xml:
    print(f"Suite: {suite.name}, Tests: {suite.tests}, Failures: {suite.failures}")
    for case in suite:
        # Check result type
        if case.result:
            for r in case.result:
                if isinstance(r, Failure):
                    print(f"  FAILED: {case.name} - {r.message}")
                elif isinstance(r, Error):
                    print(f"  ERROR: {case.name} - {r.message}")
                elif isinstance(r, Skipped):
                    print(f"  SKIPPED: {case.name}")
        else:
            print(f"  PASSED: {case.name}")
```

### Django-Unfold ModelAdmin
```python
# Source: https://unfoldadmin.com/docs/installation/quickstart/
from django.contrib import admin
from unfold.admin import ModelAdmin
from requirements.models import Requirement, TestRun, TestResult

@admin.register(Requirement)
class RequirementAdmin(ModelAdmin):
    list_display = ['external_id', 'title', 'verification_status', 'updated_at']
    list_filter = ['verification_status', 'status', 'priority']
    search_fields = ['external_id', 'title', 'description']

@admin.register(TestRun)
class TestRunAdmin(ModelAdmin):
    list_display = ['source_file', 'imported_at', 'total_tests', 'passed', 'failed']
    readonly_fields = ['imported_at']

@admin.register(TestResult)
class TestResultAdmin(ModelAdmin):
    list_display = ['test_nodeid', 'status', 'test_run']
    list_filter = ['status', 'test_run']
```

### Django Aggregate for Status Metrics
```python
# Source: https://docs.djangoproject.com/en/5.2/topics/db/aggregation/
from django.db.models import Count, Q
from requirements.models import Requirement

metrics = Requirement.objects.aggregate(
    total=Count('id'),
    passing=Count('id', filter=Q(verification_status='passing')),
    failing=Count('id', filter=Q(verification_status='failing')),
    untested=Count('id', filter=Q(verification_status='untested')),
)
# Result: {'total': 100, 'passing': 60, 'failing': 10, 'untested': 30}
```

### Generating JUnit XML with pytest
```bash
# Source: https://docs.pytest.org/en/stable/how-to/output.html
pytest tests/ --junitxml=results.xml -o junit_family=xunit2
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| django-admin-interface | django-unfold | 2024-2025 | Modern Tailwind UI, better dashboard support |
| Manual XML parsing | junitparser 4.x | 2024 | List-based results, better pytest support |
| xunit1 family | xunit2 family (default) | pytest 6.1+ | xunit2 is now default, cleaner schema |

**Deprecated/outdated:**
- `case.result` as single item (junitparser <2.0) - now a list
- `junit_family=legacy` - removed in pytest 7.0

## Open Questions

Things that couldn't be fully resolved:

1. **Parent-child status rollup**
   - What we know: Context says it's Claude's discretion. Options are: (a) independent (each req has own status), (b) pessimistic rollup (parent fails if any child fails), (c) weighted average
   - What's unclear: User preference not explicitly stated
   - Recommendation: Start with independent status (simpler). Add rollup as optional view/filter later if needed.

2. **Staleness threshold**
   - What we know: Context says tests not in latest import are "stale"
   - What's unclear: How long before considered stale? 7 days? Or just "not in latest run"?
   - Recommendation: Use "not in latest run" initially. Add time-based threshold if needed later.

3. **Nodeid normalization**
   - What we know: JUnit XML classname format may differ from extract_links nodeid format
   - What's unclear: Exact mapping between formats across different pytest configurations
   - Recommendation: Store both original JUnit classname and normalized nodeid. Try multiple matching strategies.

## Sources

### Primary (HIGH confidence)
- [junitparser PyPI](https://pypi.org/project/junitparser/) - v4.0.2, API and usage
- [junitparser ReadTheDocs](https://junitparser.readthedocs.io/en/latest/) - Parsing patterns
- [django-unfold Quickstart](https://unfoldadmin.com/docs/installation/quickstart/) - Installation, INSTALLED_APPS
- [django-unfold Dashboard](https://unfoldadmin.com/docs/configuration/dashboard/) - Dashboard callback
- [pytest JUnit XML](https://docs.pytest.org/en/stable/how-to/output.html) - --junitxml option
- [JUnit XML Schema](https://github.com/testmoapp/junitxml) - XML structure reference

### Secondary (MEDIUM confidence)
- [django-unfold Components](https://unfoldadmin.com/docs/components/introduction/) - UI components
- [Django Aggregation](https://docs.djangoproject.com/en/5.2/topics/db/aggregation/) - Count with Q filters
- [django-treebeard Admin](https://django-treebeard.readthedocs.io/en/latest/admin.html) - TreeAdmin

### Tertiary (LOW confidence)
- WebSearch results on status rollup patterns - No authoritative source found
- WebSearch on tree view UI patterns - General patterns, not library-specific

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - junitparser and django-unfold are well-documented, version-verified
- Architecture: HIGH - Follows established Django patterns, builds on Phase 1-2 code
- Pitfalls: MEDIUM - Based on documentation and common Django patterns, some from experience

**Research date:** 2026-01-20
**Valid until:** 2026-02-20 (30 days - stable libraries, unlikely to change significantly)

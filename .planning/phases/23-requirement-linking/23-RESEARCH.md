# Phase 23: Requirement Linking - Research

**Researched:** 2026-02-02
**Domain:** Django M2M relationships, admin customization, flow-to-requirement traceability
**Confidence:** HIGH

## Summary

This phase connects verification flows to requirements for bidirectional traceability. The infrastructure is 80% complete:

- `FlowDef.requirements` field already exists and YAML parser populates it
- `sync_yaml_flows_to_db()` currently stores requirements in `_metadata` as a temporary workaround
- `Requirement` model has established patterns for M2M relationships (SLOs, TestResults, AgentTasks)

The remaining work is straightforward Django: add M2M field to `VerificationFlow`, update sync logic to create actual relationships, and add admin UI display following existing patterns.

**Primary recommendation:** Add `requirements` M2M field to `VerificationFlow` (not the reverse), matching the pattern established by `SLO.requirements` and `AgentTask.requirements`.

## Current State Analysis

### What Already Exists

| Component | Status | Location |
|-----------|--------|----------|
| `FlowDef.requirements` | Complete | `flows/definitions.py:97` |
| YAML parser reads `requirements` | Complete | `flows/parser.py:142-154` |
| Temporary `_metadata` storage | Complete | `flows/sync.py:107-114` |
| `Requirement.external_id` field | Complete | `models.py:84-89` |
| `RequirementAdmin` linked displays | Complete | `admin.py:196-260` |

### What's Missing

| Component | Description |
|-----------|-------------|
| `VerificationFlow.requirements` M2M | Field linking to Requirement model |
| Migration | Database schema change |
| Sync logic update | Replace `_metadata` with M2M `.set()` |
| Missing requirement handling | Decide: warn/skip/error |
| RequirementAdmin `linked_flows` display | Show flows on requirement detail |
| Flow list/status views | Show linked requirements |
| VerificationFlowAdmin | Admin interface for flows (doesn't exist yet) |

### Gap: No VerificationFlowAdmin

The `VerificationFlow` model has no admin registration. This phase should add one to enable:
- Viewing flows and their linked requirements
- Manual flow management

## Standard Stack

### Core (Django built-ins)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django ManyToManyField | 5.x | Bidirectional relationships | Django's native M2M implementation |
| Django migrations | 5.x | Schema changes | Django's migration system |

### Supporting (already in project)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| django-unfold | 0.43.x | Admin styling | All admin classes use `unfold.admin.ModelAdmin` |

### No New Dependencies Required

All functionality uses Django built-ins and existing project patterns.

## Architecture Patterns

### M2M Field Placement Convention

**Observation:** In this codebase, M2M fields to Requirement are placed on the "linking" model, not on Requirement itself.

| Model | Field | Related Name on Requirement |
|-------|-------|----------------------------|
| `TestResult` | `requirements` | `test_results` |
| `SLO` | `requirements` | `slos` |
| `AgentTask` | `requirements` | `agent_tasks` |

**Recommendation:** Add `requirements` field to `VerificationFlow`, not the reverse.

```python
# On VerificationFlow model
requirements = models.ManyToManyField(
    'Requirement',
    related_name='verification_flows',
    blank=True,
    help_text="Requirements this flow verifies"
)
```

This gives:
- `flow.requirements.all()` - requirements linked to a flow
- `requirement.verification_flows.all()` - flows linked to a requirement

### Sync Pattern: String ID to FK Lookup

The sync must convert string requirement IDs (from YAML) to actual `Requirement` model instances.

**Pattern from OpenSLO sync (similar problem):**

```python
def sync_flow_requirements(flow: VerificationFlow, requirement_ids: list[str]) -> dict:
    """Link flow to requirements by external_id lookup.

    Returns:
        {
            'linked': list of external_ids successfully linked,
            'missing': list of external_ids not found in database,
        }
    """
    linked = []
    missing = []

    requirements = []
    for req_id in requirement_ids:
        try:
            req = Requirement.objects.get(external_id=req_id)
            requirements.append(req)
            linked.append(req_id)
        except Requirement.DoesNotExist:
            missing.append(req_id)
            logger.warning(f"Flow '{flow.name}': requirement '{req_id}' not found")

    # Use .set() to replace all links atomically
    flow.requirements.set(requirements)

    return {'linked': linked, 'missing': missing}
```

### Missing Requirement Handling

**Recommendation:** Warn and skip (don't fail sync).

Rationale:
- Flows may reference requirements that haven't been imported yet
- Syncing should be idempotent and repeatable
- User can re-sync after importing requirements

Pattern: Log warning, continue sync, return summary of missing IDs.

### Admin Display Pattern

The `RequirementAdmin` already has helper functions for displaying linked items with badges. Use the same pattern.

```python
def linked_flows(self, obj):
    """Display linked verification flows with status badges."""
    flows = obj.verification_flows.all().order_by('name')
    return _render_badge_list(
        flows, FLOW_STATUS_COLORS,
        get_status=lambda f: f.latest_run_status,  # Need to add this property
        get_url=lambda f: reverse('admin:requirements_verificationflow_change', args=[f.pk]),
        get_label=lambda f: f.display_name,
        empty_message='No linked flows'
    )
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| M2M relationships | Custom join table | Django ManyToManyField | Django handles all the complexity |
| Bulk M2M updates | Loop with `.add()` | `.set()` method | Single transaction, handles removes |
| Admin list displays | Custom template tags | `_render_badge_list()` helper | Already exists, consistent styling |
| ID to FK lookup | Raw SQL | `Requirement.objects.get(external_id=...)` | Django ORM handles escaping |

## Common Pitfalls

### Pitfall 1: N+1 Queries in Admin Display

**What goes wrong:** Displaying linked flows/requirements triggers a query per item.
**Why it happens:** Django admin calls display method for each row without prefetching.
**How to avoid:** Use `get_queryset()` override with `prefetch_related()`.
**Warning signs:** Slow admin list pages, many similar queries in logs.

```python
def get_queryset(self, request):
    return super().get_queryset(request).prefetch_related('requirements')
```

### Pitfall 2: Forgetting to Remove `_metadata` Workaround

**What goes wrong:** Old sync stores data in `_metadata`, new sync stores in M2M, data gets out of sync.
**Why it happens:** Phased migration leaves old code path.
**How to avoid:** Remove `_metadata` handling in same PR as M2M addition.
**Warning signs:** Requirement links work for some flows but not others.

### Pitfall 3: Sync Order Dependencies

**What goes wrong:** Flows reference requirements that don't exist yet.
**Why it happens:** Requirements must be imported before flows for linking to work.
**How to avoid:** Document expected order, handle missing gracefully with warnings.
**Warning signs:** All requirement links show as missing.

### Pitfall 4: Admin Missing reverse() Name

**What goes wrong:** `reverse('admin:requirements_verificationflow_change', ...)` fails.
**Why it happens:** `VerificationFlow` isn't registered in admin.
**How to avoid:** Register `VerificationFlowAdmin` before adding links to it.
**Warning signs:** NoReverseMatch exception in admin.

## Code Examples

### M2M Field Definition

```python
# In models.py, add to VerificationFlow class

class VerificationFlow(models.Model):
    # ... existing fields ...

    # Link to requirements (Phase 23)
    requirements = models.ManyToManyField(
        'Requirement',
        related_name='verification_flows',
        blank=True,
        help_text="Requirements this flow verifies"
    )
```

### Migration

```python
# Generated migration
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('requirements', '0010_requirement_depends_on'),
    ]

    operations = [
        migrations.AddField(
            model_name='verificationflow',
            name='requirements',
            field=models.ManyToManyField(
                blank=True,
                help_text='Requirements this flow verifies',
                related_name='verification_flows',
                to='requirements.requirement'
            ),
        ),
    ]
```

### Updated Sync Function

```python
# In flows/sync.py

def sync_yaml_flows_to_db(
    flows: list[FlowDef],
    clear_existing: bool = False,
) -> dict[str, str]:
    """Sync YAML-defined flows to database.

    Creates or updates VerificationFlow records from FlowDef objects.
    Now properly links to Requirement models via M2M relationship.
    """
    results = {}
    link_summary = {'total_linked': 0, 'total_missing': 0, 'missing_ids': []}

    for flow_def in flows:
        steps_data = [asdict(step) for step in flow_def.steps]

        # Store source_file in steps (requirements now use M2M)
        if flow_def.source_file:
            metadata = {'_metadata': {'source_file': flow_def.source_file}}
            steps_with_metadata = [metadata] + steps_data
        else:
            steps_with_metadata = steps_data

        flow, created = VerificationFlow.objects.update_or_create(
            name=flow_def.name,
            defaults={
                'display_name': flow_def.display_name,
                'description': flow_def.description,
                'steps': steps_with_metadata,
                'version': flow_def.version,
                'synced_at': timezone.now(),
            }
        )

        # Link requirements via M2M
        if flow_def.requirements:
            link_result = _sync_flow_requirements(flow, flow_def.requirements)
            link_summary['total_linked'] += len(link_result['linked'])
            link_summary['total_missing'] += len(link_result['missing'])
            link_summary['missing_ids'].extend(link_result['missing'])

        action = 'created' if created else 'updated'
        results[flow_def.name] = action
        logger.info(f"Flow '{flow_def.name}' {action} (v{flow_def.version})")

    if link_summary['missing_ids']:
        logger.warning(
            f"Missing requirements during flow sync: {link_summary['missing_ids']}"
        )

    return results


def _sync_flow_requirements(flow: VerificationFlow, requirement_ids: list[str]) -> dict:
    """Link flow to requirements by external_id."""
    linked = []
    missing = []

    requirements = []
    for req_id in requirement_ids:
        try:
            req = Requirement.objects.get(external_id=req_id)
            requirements.append(req)
            linked.append(req_id)
        except Requirement.DoesNotExist:
            missing.append(req_id)
            logger.warning(f"Flow '{flow.name}': requirement '{req_id}' not found")

    flow.requirements.set(requirements)
    return {'linked': linked, 'missing': missing}
```

### Admin Registration for VerificationFlow

```python
# In admin.py

FLOW_STATUS_COLORS = {
    'passed': '#22c55e',
    'failed': '#ef4444',
    'running': '#f59e0b',
    'unknown': '#6b7280',
}


@admin.register(VerificationFlow)
class VerificationFlowAdmin(ModelAdmin):
    """Admin interface for VerificationFlow."""

    list_display = ['name', 'display_name', 'version', 'synced_at', 'requirements_count']
    list_filter = ['version']
    search_fields = ['name', 'display_name', 'description']
    readonly_fields = ['synced_at', 'linked_requirements_display']
    filter_horizontal = ['requirements']

    fieldsets = (
        (None, {
            'fields': ('name', 'display_name', 'description')
        }),
        ('Definition', {
            'fields': ('steps', 'version', 'synced_at')
        }),
        ('Requirements', {
            'fields': ('requirements', 'linked_requirements_display')
        }),
    )

    def requirements_count(self, obj):
        """Display count of linked requirements."""
        count = obj.requirements.count()
        return count if count > 0 else '—'
    requirements_count.short_description = 'Requirements'

    def linked_requirements_display(self, obj):
        """Display linked requirements with verification status badges."""
        requirements = obj.requirements.all().order_by('external_id')
        return _render_badge_list(
            requirements, STATUS_BADGE_COLORS,
            get_status=lambda r: r.verification_status,
            get_url=lambda r: reverse('admin:requirements_requirement_change', args=[r.pk]),
            get_label=lambda r: f"{r.external_id}: {r.title}",
            empty_message='No linked requirements'
        )
    linked_requirements_display.short_description = 'Linked Requirements'
```

### RequirementAdmin Addition

```python
# Add to RequirementAdmin readonly_fields
readonly_fields = [
    'verification_status', 'slo_status', 'created_at', 'updated_at',
    'linked_tests', 'linked_slos', 'linked_inapp_validations',
    'structure_completeness', 'completeness_badge',
    'linked_dependencies', 'linked_depended_by',
    'linked_flows',  # NEW
]

# Add to fieldsets under Verification Status
('Verification Status', {
    'fields': (
        'verification_status', 'slo_status',
        'linked_tests', 'linked_inapp_validations', 'linked_slos',
        'linked_flows',  # NEW
    )
}),

# Add method
def linked_flows(self, obj):
    """Display linked verification flows."""
    flows = obj.verification_flows.all().order_by('name')
    return _render_badge_list(
        flows, FLOW_STATUS_COLORS,
        get_status=lambda f: 'unknown',  # TODO: Add latest run status
        get_url=lambda f: reverse('admin:requirements_verificationflow_change', args=[f.pk]),
        get_label=lambda f: f.display_name,
        empty_message='No linked flows'
    )
linked_flows.short_description = "Linked Flows"
```

## Implementation Sequence

Recommended task order:

1. **Add M2M field + migration** (models.py) - Foundation
2. **Register VerificationFlowAdmin** (admin.py) - Needed before reverse links work
3. **Update sync logic** (flows/sync.py) - Remove `_metadata`, use M2M
4. **Add `linked_flows` to RequirementAdmin** (admin.py) - Bidirectional display
5. **Update flow status views** (flow_status.py) - Show requirements in dashboard
6. **Add tests** - Verify sync, admin display

## Open Questions

1. **Should flow dashboard show requirements?**
   - Current `get_flows_overview()` doesn't return requirements
   - Recommendation: Yes, add to flow cards and detail views
   - Impact: Minor template and data layer changes

2. **What about code-defined flows?**
   - `LINEAR_CONNECTION_FLOW` in definitions.py has empty `requirements: []`
   - Recommendation: Keep empty for now; code flows don't typically need traceability
   - Can be added later if needed

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `/Users/tslater/dev/spec-trace/spectrace/requirements/models.py`
- Codebase analysis: `/Users/tslater/dev/spec-trace/spectrace/requirements/admin.py`
- Codebase analysis: `/Users/tslater/dev/spec-trace/spectrace/requirements/flows/sync.py`
- Django documentation (training data, verified current)

### Secondary (MEDIUM confidence)
- Django M2M patterns from training data (stable API)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using Django built-ins with established codebase patterns
- Architecture: HIGH - Following existing M2M patterns in this codebase
- Pitfalls: HIGH - Based on direct code analysis

**Research date:** 2026-02-02
**Valid until:** Indefinite (Django patterns are stable)

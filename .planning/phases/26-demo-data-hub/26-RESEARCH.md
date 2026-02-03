# Phase 26: Demo Data & Hub - Research

**Researched:** 2026-02-03
**Domain:** Demo data generation and YAML configuration
**Confidence:** HIGH

## Summary

Phase 26 cleans up demo infrastructure and enriches sample data to showcase SpecTrace capabilities realistically. The codebase has a mature demo system with `demos.yaml` catalog, programmatic demo data generation (`vendor_demo.py`, `flow_status.py`), and sample specs in `specs/` and `examples/document-pipeline/`.

**Current state:**
- `demos.yaml` has one unused field: `options` (line 95, only in `document-pipeline` entry)
- `talking_points` field was already removed in commit 0787fd9
- Sample specs exist but have shallow hierarchy (max 2 levels: parent → child)
- Vendor demo data uses 4 vendors (Opera, Mews, Ambiance, OpenKey) with varied pass rates
- Verification status computation is mature (passing/failing/untested based on test results)

**Primary recommendation:** This is a refinement phase, not a greenfield build. Remove vestigial `options` field, enhance existing specs with deeper hierarchy, and ensure vendor demo scenarios show regression patterns.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | (project dep) | Parse/write demos.yaml | Standard Python YAML library |
| Django ORM | 4.x | Query/create demo data | Already used throughout |
| Faker | (optional) | Generate realistic names/data | Standard for test data generation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| freezegun | (in test deps) | Deterministic timestamps | Consistent demo runs |

### Alternatives Considered
None - this phase uses existing infrastructure, no new libraries needed.

**Installation:**
```bash
# No new dependencies required
# All needed libraries already in pyproject.toml
```

## Architecture Patterns

### Demo Data Generation Pattern (Existing)
Current codebase uses **programmatic setup functions** in services layer:

```
spectrace/requirements/services/
├── vendor_demo.py          # setup_vendor_demo()
├── flow_status.py          # setup_demo_data()
└── (future) matrix_demo.py # For matrix-specific scenarios
```

**Why this pattern works:**
- Idempotent (can be run multiple times)
- Returns metadata about what was created
- Clears old demo data before creating new
- Used by management commands (`setup_flow_demo`) and views (`vendor_load_demo_view`)

**Example from vendor_demo.py:**
```python
def setup_vendor_demo(clear: bool = True) -> dict:
    """Set up demo data for vendor coverage.

    Returns:
        {
            'vendors_created': int,
            'validations_created': int,
            'results_created': int,
        }
    """
    # Clear old demo data
    if clear:
        InAppValidationRun.objects.filter(
            source__startswith=DEMO_SOURCE_PREFIX
        ).delete()

    # Create new demo data
    # ...

    return result
```

### Spec File Organization (Existing)
Current hierarchy pattern:
```
specs/
├── auth/
│   ├── login.md          # REQ-AUTH-001 (depth=1, root)
│   ├── register.md       # REQ-AUTH-002 (depth=2, parent: REQ-AUTH-001)
│   └── password_reset.md # REQ-AUTH-003 (depth=2, parent: REQ-AUTH-001)
├── dashboard/
└── data/

examples/document-pipeline/specs/
└── pipeline/
    ├── DOC-001-overview.md       # Root (depth=1)
    ├── ingest/
    │   └── DOC-ING-001.md        # Child (depth=2, parent: DOC-001)
    ├── storage/
    │   └── DOC-STR-001.md        # Child (depth=2, parent: DOC-001)
    └── transform/
        └── DOC-TRF-001.md        # Child (depth=2, parent: DOC-001)
```

**Need:** Add 3+ level hierarchy (epic → feature → story pattern)

**Proposed structure:**
```
specs/sample/
├── SAMPLE-001-platform.md        # Epic (depth=1)
├── feature-auth/
│   ├── SAMPLE-AUTH-001.md        # Feature (depth=2, parent: SAMPLE-001)
│   └── stories/
│       ├── SAMPLE-AUTH-001-001.md  # Story (depth=3, parent: SAMPLE-AUTH-001)
│       └── SAMPLE-AUTH-001-002.md  # Story (depth=3, parent: SAMPLE-AUTH-001)
└── feature-api/
    ├── SAMPLE-API-001.md         # Feature (depth=2, parent: SAMPLE-001)
    └── stories/
        └── SAMPLE-API-001-001.md   # Story (depth=3, parent: SAMPLE-API-001)
```

### Requirement Verification Status (Existing)
Status computed in `spectrace/requirements/status.py`:

```python
def compute_verification_status(requirement: Requirement, latest_run=None) -> str:
    """
    Rules:
    - All linked tests pass -> 'passing'
    - Any linked test fails/errors -> 'failing'
    - No linked tests -> 'untested'
    - All skipped counts as 'untested'
    """
```

**To create mixed dashboard:**
1. Link tests to requirements via `@pytest.mark.requirement("REQ-ID")`
2. Some tests pass (`assert True`)
3. Some tests fail (`assert False`)
4. Some requirements have no linked tests
5. Run `python manage.py import_results` to compute status

### Anti-Patterns to Avoid
- **Hardcoding demo data in migrations** - use idempotent setup functions instead
- **Creating requirements without source files** - always create spec markdown files first
- **Mixing demo and real data** - use `DEMO_SOURCE_PREFIX` pattern to tag demo data

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Realistic fake data | Random strings | Faker library | Professional names, emails, addresses |
| Deterministic timestamps | Relative dates | freezegun in tests | Reproducible demo runs |
| YAML validation | String parsing | yaml.safe_load() | Catches syntax errors, secure |
| Requirement hierarchy | Manual depth tracking | django-treebeard (existing) | Efficient ancestor/descendant queries |

**Key insight:** The codebase already has robust infrastructure. This phase is cleanup and enrichment, not building new systems.

## Common Pitfalls

### Pitfall 1: Breaking Existing Demos When Cleaning YAML
**What goes wrong:** Removing fields that are actually used breaks `list_demos.py` or `demo_hub` view
**Why it happens:** Fields like `options` and `talking_points` appear unused but may have conditional logic
**How to avoid:** Grep codebase for field usage before removal:
```bash
grep -r "talking_points\|options" spectrace/ scripts/
```
**Warning signs:**
- Test failures in `test_demo_hub.py` (if exists)
- Demo hub page shows empty cards
- `scripts/list_demos.py --show <demo-id>` errors

**Verification (from research):**
- `talking_points` removed in commit 0787fd9 - **safe to keep removed**
- `options` only used in `scripts/list_demos.py` lines 71-74 - **must remove usage when removing field**

### Pitfall 2: Creating Requirements Without Markdown Sources
**What goes wrong:** Requirements exist in DB but have no corresponding spec file
**Why it happens:** Calling `Requirement.objects.create()` directly instead of using `parse_specs`
**How to avoid:** Always create markdown spec files, then run `python manage.py parse_specs specs/`
**Warning signs:**
- `source_file` field is empty
- Requirement appears in matrix but can't be edited
- Git has no spec file for the requirement ID

### Pitfall 3: Demo Data Persists Across Runs
**What goes wrong:** Running setup again doubles demo data instead of resetting
**Why it happens:** Not clearing old demo data before creating new
**How to avoid:** Use `clear=True` pattern in setup functions:
```python
if clear:
    InAppValidationRun.objects.filter(
        source__startswith=DEMO_SOURCE_PREFIX
    ).delete()
```
**Warning signs:**
- Vendor count doubles each run
- Demo dashboard shows duplicate entries
- Pass rates change unexpectedly

### Pitfall 4: Shallow Hierarchy Doesn't Show Tree UI
**What goes wrong:** 3+ level requirement hierarchy doesn't render correctly
**Why it happens:** Django-treebeard `parent` field must reference external_id, not database ID
**How to avoid:** In spec frontmatter, use `parent: PARENT-EXTERNAL-ID`, not `parent_id: 123`
**Warning signs:**
- Requirements show as siblings instead of children
- `depth` field is wrong
- Tree view in admin is flat

## Code Examples

Verified patterns from official sources:

### Creating Demo Data with Clearing
```python
# Source: spectrace/requirements/services/vendor_demo.py
DEMO_SOURCE_PREFIX = "demo://vendor"

def setup_vendor_demo(clear: bool = True) -> dict:
    result = {
        "vendors_created": 0,
        "validations_created": 0,
        "results_created": 0,
        "runs_cleared": 0,
    }

    if clear:
        old_runs = InAppValidationRun.objects.filter(
            source__startswith=DEMO_SOURCE_PREFIX
        )
        result["runs_cleared"] = old_runs.count()
        old_runs.delete()

        InAppValidation.objects.filter(
            endpoint__startswith=DEMO_SOURCE_PREFIX
        ).delete()

    # Create fresh demo data
    # ...
    return result
```

### Creating 3-Level Requirement Hierarchy
```markdown
# File: specs/sample/SAMPLE-001-platform.md
---
id: SAMPLE-001
title: Platform Services
tags: [epic, platform]
priority: high
status: active
verification_method: both
---

# Platform Services Epic

(content)
```

```markdown
# File: specs/sample/feature-auth/SAMPLE-AUTH-001.md
---
id: SAMPLE-AUTH-001
title: Authentication Feature
parent: SAMPLE-001
tags: [feature, auth]
priority: high
status: active
verification_method: test
---

# Authentication Feature

(content)
```

```markdown
# File: specs/sample/feature-auth/stories/SAMPLE-AUTH-001-001.md
---
id: SAMPLE-AUTH-001-001
title: User Login Story
parent: SAMPLE-AUTH-001
tags: [story, auth, login]
priority: high
status: active
verification_method: test
---

# User Login Story

(content)
```

**After parsing:**
- SAMPLE-001 has `depth=1`, `parent=None`
- SAMPLE-AUTH-001 has `depth=2`, `parent=SAMPLE-001`
- SAMPLE-AUTH-001-001 has `depth=3`, `parent=SAMPLE-AUTH-001`

### Creating Mixed Verification Status
```python
# Source: spectrace/tests/test_example.py (enhanced)

@pytest.mark.requirement("SAMPLE-AUTH-001-001")
def test_login_success():
    """Passing test."""
    assert True

@pytest.mark.requirement("SAMPLE-AUTH-001-002")
def test_logout_failure():
    """Failing test."""
    assert False, "Logout endpoint returns 500"

# SAMPLE-AUTH-001-003 has no linked tests -> untested
```

**After importing results:**
- SAMPLE-AUTH-001-001: verification_status = 'passing'
- SAMPLE-AUTH-001-002: verification_status = 'failing'
- SAMPLE-AUTH-001-003: verification_status = 'untested'

### Vendor Regression Scenario
```python
# Source: spectrace/requirements/services/vendor_demo.py (existing pattern)

# Create two validation runs (older and newer)
older_run = InAppValidationRun.objects.create(
    source=f"{DEMO_SOURCE_PREFIX}/run-1",
    imported_at=now - timedelta(days=2),
)
newer_run = InAppValidationRun.objects.create(
    source=f"{DEMO_SOURCE_PREFIX}/run-2",
)

# For OpenKey vendor, first validation: pass → fail (regression)
if has_regression and i == 0:
    # Run 1: SUCCESS
    InAppValidationResult.objects.create(
        validation_run=older_run,
        validation=validation,
        status=InAppValidationStatus.SUCCESS,
        message="Validation passed",
    )
    # Run 2: FAILURE (regression)
    InAppValidationResult.objects.create(
        validation_run=newer_run,
        validation=validation,
        status=InAppValidationStatus.FAILURE,
        message="Connection timeout - regression detected",
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `talking_points` in YAML | Removed | Commit 0787fd9 | Cleaner YAML, presenter notes in demo pages |
| Flat requirement hierarchy | Multi-level supported | Phase 1 | Can show epic → feature → story |
| Manual demo data creation | Idempotent setup functions | Phase 5 | Reproducible demos |
| Single verification method | `verification_method: both` | Phase 10 | Test + in-app validation |

**Deprecated/outdated:**
- `talking_points` field in `demos.yaml` - removed, should not be re-added
- Creating requirements without `source_file` - now enforced in parser

## Open Questions

1. **How many sample specs should we create?**
   - What we know: Examples exist with ~10 requirements (document-pipeline)
   - What's unclear: Is this enough to show hierarchy and coverage patterns?
   - Recommendation: Create 15-20 sample requirements (1 epic, 3 features, 10-15 stories) to demonstrate tree navigation and filtering

2. **Should vendor demo data include feature flags?**
   - What we know: `vendor_demo.py` already includes `feature_flags` field
   - What's unclear: Does the vendor coverage UI display feature flags prominently?
   - Recommendation: Keep feature flags in demo data (already implemented), verify UI displays them

3. **What defines "realistic vendor scenarios"?**
   - What we know: Current demo has 4 vendors with 50-100% pass rates and 1 regression
   - What's unclear: Success criterion says "multiple vendors, varied outcomes" - is 4 vendors enough?
   - Recommendation: 4 vendors is sufficient; ensure varied outcomes include: all passing (Ambiance 100%), mostly passing (Opera 80%), failing (OpenKey 50%), and regression (OpenKey)

## Sources

### Primary (HIGH confidence)
- spectrace/requirements/services/vendor_demo.py - Current vendor demo implementation
- spectrace/requirements/flow_status.py - Flow demo setup patterns
- spectrace/requirements/status.py - Verification status computation
- spectrace/requirements/models.py - Requirement model with depth/parent fields
- demos.yaml - Demo catalog structure
- spectrace/templates/admin/requirements/demo_hub.html - Hub rendering logic

### Secondary (MEDIUM confidence)
- scripts/list_demos.py - CLI tool showing `options` field usage (lines 71-74)
- specs/ directory - Current sample specs with 2-level hierarchy
- examples/document-pipeline/specs/ - Example project with 2-level hierarchy

### Tertiary (LOW confidence)
None - all findings verified with source code inspection.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries needed, using existing Django/YAML infrastructure
- Architecture: HIGH - patterns verified in vendor_demo.py and flow_status.py
- Pitfalls: HIGH - all pitfalls identified from code inspection and git history

**Research date:** 2026-02-03
**Valid until:** 60 days (stable area, infrastructure unlikely to change)

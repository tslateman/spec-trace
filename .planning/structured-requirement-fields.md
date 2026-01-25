# Plan: Structured Requirement Fields (FRET-Inspired)

**Status:** ✓ IMPLEMENTED (2026-01-24)
**Commit:** `71763a9`

## Goal

Enhance spec-trace with optional structured fields in requirements, inspired by NASA FRET's approach. This bridges the gap between unstructured Linear tickets and formal requirements without sacrificing agile speed.

## Research Context

Based on research into:
- **NASA FRET**: FRETish language with scope/condition/component/timing/response fields
- **Requirements traceability best practices**: IEEE definitions, coverage analysis, change impact
- **Backstage**: Catalog-based discovery pattern
- **Open-source tools**: doorstop (git-based), StrictDoc (docs-as-code)

Key insight: Structured fields enable automation (conflict detection, SLO linking, test hints) without requiring full formal verification.

---

## Proposed Enhancement

### New Optional YAML Fields

```yaml
---
id: REQ-BATTERY-001
title: Battery Warning
priority: high
tags: [hardware, safety]
verification_method: test

# NEW: Structured fields (all optional)
scope: "when in active_session"           # When does this apply?
condition: "battery_level < 10"           # What triggers the behavior?
component: "warning_system"               # What system owns this?
timing: "within 2 seconds"                # Performance constraint?
response: "display battery_warning"       # What must happen?
---
Free-form description still supported here for human context.
```

### Benefits

| Feature | Enabled By |
|---------|------------|
| Auto-link to SLOs | `timing` field matches SLO latency targets |
| Component ownership filtering | `component` field for team-based views |
| Enhanced conflict detection | `condition` field overlap analysis |
| Test generation hints | `condition` + `response` suggest assertions |
| Completeness scoring | Track field population rates |
| Linear import enrichment | Parse structured text into fields |

---

## Implementation Plan

### Phase 1: Model & Parsing ✓

**Status:** Implemented
**Files modified:**
- `spectrace/requirements/models.py` — Add optional fields to Requirement model
- `spectrace/requirements/management/commands/parse_specs.py` — Extract new fields from YAML

**New fields on Requirement model:**
```python
# Structured fields (FRET-inspired, all optional)
scope = models.TextField(blank=True, default="")
condition = models.TextField(blank=True, default="")
component = models.CharField(max_length=255, blank=True, default="")
timing = models.CharField(max_length=100, blank=True, default="")
response = models.TextField(blank=True, default="")

# Computed metadata
structure_completeness = models.FloatField(default=0.0)  # 0.0-1.0
```

**Completeness calculation:**
```python
def calculate_structure_completeness(self) -> float:
    fields = [self.scope, self.condition, self.component, self.timing, self.response]
    populated = sum(1 for f in fields if f.strip())
    return populated / len(fields)
```

### Phase 2: Enhanced Conflict Detection ✓

**Status:** Implemented
**Files modified:**
- `spectrace/requirements/services/conflict_detector.py` — Add condition-based analysis

**New detection patterns:**
1. **Condition overlap**: Requirements with overlapping conditions on same component
2. **Timing conflicts**: Same component, conflicting timing constraints
3. **Response contradictions**: Same trigger, different expected responses

**Example:**
```
REQ-001: condition="battery < 10", response="show warning"
REQ-002: condition="battery < 15", response="hide warning"
         ↑ overlap at battery=12 — conflict detected
```

### Phase 3: Dashboard Enhancements ✓

**Status:** Implemented
**Files modified:**
- `spectrace/requirements/admin.py` — Add completeness column, structured field display
- `spectrace/requirements/templates/` — Structured field visualization

**New views:**
- Completeness score column in requirement list
- Structured field breakdown in detail view
- Filter by component
- "Needs structure" filter (completeness < threshold)

### Phase 4: SLO Auto-Linking ✓

**Status:** Implemented
**Files modified:**
- `spectrace/requirements/management/commands/import_slos.py` — Match timing fields

**Logic:**
```python
# When importing SLOs, auto-link to requirements with matching timing
if requirement.timing and slo.target:
    timing_seconds = parse_timing(requirement.timing)  # "within 2 seconds" → 2
    if timing_seconds <= slo.target:
        slo.requirements.add(requirement)
```

### Phase 5: Linear Import Enrichment ✓

**Status:** Implemented
**Files modified:**
- `spectrace/requirements/linear.py` — Parse structured patterns from issue body
- New: `spectrace/requirements/services/requirement_parser.py` — Reusable pattern extraction

**Pattern matching (best-effort):**
```python
# Attempt to extract structured fields from Linear issue body
PATTERNS = {
    'scope': r'(?:in|during|while)\s+(\w+(?:[-_]\w+)*\s*(?:mode|state|phase)?)',
    'condition': r'(?:when|if|whenever)\s+(.+?)(?:\.|,|then|$)',
    'component': r'(?:the|in)\s+(\w+(?:[-_]\w+)*)\s+(?:should|shall|must|will)',
    'timing': r'(?:within|in|after)\s+(\d+\s*(?:seconds?|minutes?|ms|s))',
    'response': r'(?:shall|should|must|will)\s+(.+?)(?:\.|$)',
}

def extract_structured_fields(text: str) -> dict[str, str]:
    """Best-effort extraction of structured fields from free-form text."""
    result = {}
    for field, pattern in PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()
    return result
```

**Integration with import_linear:**
```python
def import_issue(issue: dict) -> Requirement:
    # Extract from issue body (best-effort)
    body = issue.get('description', '')
    structured = extract_structured_fields(body)

    # Structured fields from parsing (can be overridden by explicit YAML later)
    requirement.scope = structured.get('scope', '')
    requirement.condition = structured.get('condition', '')
    # ... etc
```

---

## Scope Decision

**Selected**: All 5 phases with full automation
- All five structured fields: scope, condition, component, timing, response
- Best-effort parsing of Linear issue body text
- SLO auto-linking based on timing fields

---

## File Changes Summary

| File | Change |
|------|--------|
| `spectrace/requirements/models.py` | Add 6 new fields (scope, condition, component, timing, response, structure_completeness) |
| `spectrace/requirements/management/commands/parse_specs.py` | Extract new fields from YAML frontmatter |
| `spectrace/requirements/services/conflict_detector.py` | Add condition-based conflict patterns |
| `spectrace/requirements/admin.py` | Add completeness column, component filter |
| `spectrace/requirements/linear.py` | Parse patterns from issue body (best-effort) |
| `spectrace/requirements/management/commands/import_slos.py` | Auto-link based on timing field |
| NEW: `spectrace/requirements/services/requirement_parser.py` | Reusable pattern extraction logic |
| New migration | Add fields to database |

---

## Backward Compatibility

- All new fields are optional with empty defaults
- Existing specs continue to work unchanged
- Existing tests unaffected
- Gradual adoption: teams add structure when valuable

---

## Verification Plan

1. **Unit tests**: New fields parse correctly from YAML
2. **Conflict detection tests**: Condition overlap detected
3. **Completeness tests**: Score calculated correctly
4. **Migration test**: Existing data migrates cleanly
5. **Manual verification**: Dashboard shows new fields and filters
6. **Run existing tests**: `pytest spectrace/requirements/tests/`

---

## Out of Scope

- Formal temporal logic (LTL/PCTL*) — not needed for typical software
- Strict grammar enforcement — would slow agile teams
- Automated test generation — future enhancement
- Model checking integration — different domain

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Teams don't adopt structured fields | Make optional, show value via completeness dashboard |
| Condition parsing too complex | Start simple, iterate based on usage |
| Performance impact from new fields | Fields are indexed, queries optimized |

---

## Success Criteria

1. Requirements can include optional structured fields
2. Completeness score visible in dashboard
3. Conflict detection uses condition fields when present
4. Existing specs continue to work
5. Component-based filtering available
6. Linear imports extract structured fields from issue body
7. SLOs auto-link to requirements with matching timing constraints

---

## Implementation Order

```
Phase 1: Model & Parsing
    └─→ Phase 2: Enhanced Conflict Detection
           └─→ Phase 3: Dashboard Enhancements
                  ├─→ Phase 4: SLO Auto-Linking
                  └─→ Phase 5: Linear Import Enrichment
```

Phases 4 and 5 can be done in parallel after Phase 3.

---

## Implementation Summary

**Completed:** 2026-01-24
**Commit:** `71763a9`
**Tests:** 30 new tests, all passing (228 total)

### Files Created
- `spectrace/requirements/services/requirement_parser.py` — Pattern extraction service
- `spectrace/requirements/migrations/0008_structured_fields.py` — Database migration
- `spectrace/requirements/tests/test_structured_fields.py` — Comprehensive tests

### Files Modified
- `spectrace/requirements/models.py` — 6 new fields + completeness calculation + 3 new ConflictPattern enums
- `spectrace/requirements/parser.py` — YAML extraction for structured fields
- `spectrace/requirements/services/conflict_detector.py` — 3 new detection methods
- `spectrace/requirements/admin.py` — Completeness badge, component filter, structured fields fieldset
- `spectrace/requirements/openslo.py` — Timing parser + SLO auto-linking
- `spectrace/requirements/linear.py` — Pattern extraction from issue descriptions

### Success Criteria Met
- [x] Requirements can include optional structured fields
- [x] Completeness score visible in dashboard
- [x] Conflict detection uses condition fields when present
- [x] Existing specs continue to work
- [x] Component-based filtering available
- [x] Linear imports extract structured fields from issue body
- [x] SLOs auto-link to requirements with matching timing constraints

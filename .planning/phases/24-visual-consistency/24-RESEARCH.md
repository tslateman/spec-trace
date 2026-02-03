# Phase 24: Visual Consistency - Research

**Researched:** 2026-02-03
**Domain:** CSS/Dark Mode styling for Django templates
**Confidence:** HIGH

## Summary

This research catalogs ALL tables in the codebase and their current styling approach. The design system already provides `.st-table` with dark mode support, but it lacks alternating row colors. Two reference templates (`qa_ecosystem.html` and `spectrace_overview.html`) have established a pattern for dark-mode-aware tables with alternating rows using custom CSS classes.

The main work involves:
1. Adding alternating row pattern to `.st-table` in the design system
2. Migrating templates with custom table classes to use enhanced `.st-table`
3. Fixing one template (`validation_run_compare.html`) that uses Tailwind instead of design system
4. Removing inline `style=` attributes where possible (most are for layout, not color)

**Primary recommendation:** Enhance `.st-table` with alternating rows and explicit dark mode text colors, then migrate all custom table classes to use it.

## Standard Stack

### Core Design System
| File | Purpose | Why Standard |
|------|---------|--------------|
| `_design_system.html` | CSS variables and base components | Already supports `html.dark` prefix pattern |

### Key CSS Variables (Light/Dark)
| Variable | Light | Dark | Used For |
|----------|-------|------|----------|
| `--st-surface` | `#ffffff` | `#1c2026` | Table row background |
| `--st-surface-sunken` | `#f8f9fa` | `#16191d` | Alternating row, headers |
| `--st-text` | `#16191d` | `#f1f3f5` | Primary text |
| `--st-text-muted` | `#495057` | `#adb5bd` | Secondary text |
| `--st-border` | `#dee2e6` | `#343a40` | Table borders |
| `--st-border-muted` | `#e9ecef` | `#252a31` | Row separators |

## Architecture Patterns

### Reference Pattern: Dark-Mode-Aware Tables

From `qa_ecosystem.html` (`.component-table` and `.summary-table`):

```css
.component-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}

.component-table th {
    text-align: left;
    padding: var(--st-space-3) var(--st-space-4);
    background: var(--st-surface-sunken);
    font-weight: 600;
    color: var(--st-text);
    border-bottom: 1px solid var(--st-border);
}

.component-table td {
    padding: var(--st-space-3) var(--st-space-4);
    border-bottom: 1px solid var(--st-border);
    vertical-align: top;
    color: var(--st-text);
}

.component-table tbody tr {
    background: var(--st-surface);
}

.component-table tbody tr:nth-child(even) {
    background: var(--st-surface-sunken);
}

/* Dark mode explicit overrides */
html.dark .component-table td {
    color: var(--st-slate-200);
}
```

### Current `.st-table` (Missing Alternating Rows)

```css
.st-table {
    width: 100%;
    border-collapse: collapse;
}

.st-table th {
    padding: var(--st-space-3) var(--st-space-4);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    text-align: left;
    color: var(--st-text-subtle);
    background: var(--st-surface-sunken);
    border-bottom: 1px solid var(--st-border);
}

.st-table td {
    padding: var(--st-space-3) var(--st-space-4);
    font-size: 0.875rem;
    color: var(--st-text-muted);
    border-bottom: 1px solid var(--st-border-muted);
}

.st-table tbody tr {
    transition: background 0.1s var(--st-ease-out);
}

.st-table tbody tr:hover {
    background: var(--st-surface-sunken);
}
```

### Recommended Enhancement to `.st-table`

```css
/* Add to .st-table section */
.st-table tbody tr {
    background: var(--st-surface);
    transition: background 0.1s var(--st-ease-out);
}

.st-table tbody tr:nth-child(even) {
    background: var(--st-surface-sunken);
}

.st-table tbody tr:hover {
    background: var(--st-surface-sunken);
}

/* Dark mode: ensure text is readable */
html.dark .st-table td {
    color: var(--st-slate-200);
}
```

## Template Inventory

### Tables Using `.st-table` (7 files, 11 tables)
All use design system but need alternating rows added to `.st-table`:

| File | Tables | Status |
|------|--------|--------|
| `validation_runs.html` | 1 | Uses `.st-table` |
| `requirement_detail.html` | 4 | Uses `.st-table` |
| `high_risk_dashboard.html` | 2 | Uses `.st-table` |
| `matrix.html` | 1 | Uses `.st-table` |
| `flow_editor_list.html` | 1 | Uses `.st-table` |
| `flow_runs.html` | 1 | Uses `.st-table` |

**Action:** These will automatically get alternating rows when `.st-table` is updated.

### Tables with Custom Dark-Mode-Aware Classes (2 files, 5 tables)
These are the REFERENCE templates with working patterns:

| File | Class | Status |
|------|-------|--------|
| `qa_ecosystem.html` | `.component-table` | Has alternating rows, dark mode |
| `qa_ecosystem.html` | `.summary-table` | Has alternating rows, dark mode |
| `qa_ecosystem.html` | `.integration-table` (4x) | Minimal table, in cards |
| `spectrace_overview.html` | `.demo-matrix-table` | Has alternating rows, dark mode |

**Action:** After `.st-table` is enhanced, migrate these to use `.st-table` and remove custom CSS.

### Tables with Custom Classes (Missing Dark Mode) (1 file, 5 tables)

| File | Class | Issue |
|------|-------|-------|
| `spec_syntax_help.html` | `.field-table` | Has correct styling, needs verification |

**Action:** Verify `.field-table` works in dark mode (it uses semantic variables).

### Tables Using Tailwind (NOT Design System) (1 file, 1 table)

| File | Current | Issue |
|------|---------|-------|
| `validation_run_compare.html` | `class="w-full"` | Uses `.dark` not `html.dark`, Tailwind colors |

**Action:** Migrate to `.st-table` or add design system include and custom class.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Table dark mode | Inline `html.dark` rules per template | Semantic CSS variables in `.st-table` | Consistency, maintenance |
| Alternating rows | `:nth-child(even)` in each template | Add to `.st-table` once | DRY |
| Dark text colors | Inline `style="color:"` | `var(--st-text)` / `var(--st-text-muted)` | Auto-switches |

## Common Pitfalls

### Pitfall 1: Using `.dark` Instead of `html.dark`
**What goes wrong:** Dark mode selector doesn't match
**Why it happens:** Tailwind uses `.dark`, design system uses `html.dark`
**How to avoid:** Always use `html.dark` prefix for dark mode rules
**Seen in:** `validation_run_compare.html` lines 9-17

### Pitfall 2: Using Slate Colors Directly Instead of Semantic Variables
**What goes wrong:** Text is hard to read in one mode
**Why it happens:** Hardcoding `--st-slate-200` vs `--st-text`
**How to avoid:** Use semantic variables that auto-flip: `--st-text`, `--st-text-muted`, `--st-surface`
**Warning signs:** Direct slate color references in table styles

### Pitfall 3: Inline Styles for Colors
**What goes wrong:** Can't respond to dark mode toggle
**Why it happens:** Quick fix mentality
**How to avoid:** Use CSS classes with variables
**Note:** Many inline styles in templates are for LAYOUT (padding, flex) not colors - these are acceptable

## Files Requiring Changes

### Design System (1 file)
- `spectrace/templates/admin/requirements/_design_system.html`
  - Add alternating row pattern to `.st-table`
  - Add `html.dark .st-table td` color override

### Needs Migration to Design System (1 file)
- `spectrace/templates/admin/requirements/validation_run_compare.html`
  - Uses Tailwind classes and `.dark` selector
  - Needs `{% include "_design_system.html" %}` or migrate table to `.st-table`

### Can Remove Custom CSS After `.st-table` Enhancement (2 files)
- `spectrace/templates/admin/requirements/qa_ecosystem.html`
  - `.component-table` and `.summary-table` can become `.st-table`
- `spectrace/templates/admin/requirements/spectrace_overview.html`
  - `.demo-matrix-table` can become `.st-table`

### Need Verification Only (1 file)
- `spectrace/templates/admin/requirements/spec_syntax_help.html`
  - `.field-table` uses semantic variables, should work

## Demo Pages Checklist

All demo pages for VIS-03 verification:

| Page | Has Tables | Dark Mode Status |
|------|------------|------------------|
| `landing.html` | No | Uses design system variables - OK |
| `demo_hub.html` | No | Uses design system variables - OK |
| `spectrace_overview.html` | Yes (1) | Has `.demo-matrix-table` with dark mode - OK |
| `qa_ecosystem.html` | Yes (3) | Has custom classes with dark mode - OK |
| `about.html` | No | Uses design system variables - OK |
| `demo_presenter.html` | No | N/A |

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Custom table class per template | Single `.st-table` with full styling | Less CSS duplication |
| `.dark` selector (Tailwind) | `html.dark` selector (design system) | Consistent dark mode |
| Inline color styles | CSS variables | Dark mode responsive |

## Open Questions

1. **Should `.integration-table` in `qa_ecosystem.html` also use `.st-table`?**
   - These are minimal tables inside cards
   - May need special styling
   - Recommendation: Leave as-is initially, they work

2. **What about tables in Django admin templates we don't control?**
   - These are Unfold templates
   - Out of scope for this phase

## Sources

### Primary (HIGH confidence)
- `/Users/tslater/dev/spec-trace/spectrace/templates/admin/requirements/_design_system.html` - Examined full CSS
- All template files - Direct inspection

### Secondary (MEDIUM confidence)
- Prior decisions from phase context about `html.dark` pattern

## Metadata

**Confidence breakdown:**
- Template inventory: HIGH - Direct file inspection
- Dark mode patterns: HIGH - Verified in working templates
- Migration approach: HIGH - Based on existing reference implementations

**Research date:** 2026-02-03
**Valid until:** Stable - CSS patterns don't change rapidly

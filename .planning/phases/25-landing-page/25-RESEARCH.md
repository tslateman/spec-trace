# Phase 25: Landing Page - Research

**Researched:** 2026-02-03
**Domain:** Landing page design and implementation
**Confidence:** HIGH

## Summary

SpecTrace already has a landing page at `spectrace/templates/admin/requirements/landing.html` that serves as the app root (`/`). The current implementation includes a logo, tagline, live stats (requirements, passing %, tests, vendors), and two navigation cards (Dashboard, Take the Tour).

The current tagline is "Requirements as code, automatically verified" which is accurate but doesn't capture the PM-centric value proposition. The landing page needs enhancement to meet LAND-01 through LAND-04:

1. **Value proposition** (LAND-01): Current tagline is developer-focused. Need a PM-focused one-liner that emphasizes visibility into verification status.
2. **Feature highlights** (LAND-02): Currently only two cards. Need 3-4 feature cards with icons explaining key capabilities.
3. **Feature navigation** (LAND-03): Need links from feature cards to relevant demos/views.
4. **Dark mode** (LAND-04): Already uses design system variables - likely works but needs verification.

**Primary recommendation:** Enhance the existing landing page rather than replacing it. Add feature highlight cards below the existing navigation cards, update tagline, and verify dark mode.

## Current State

### Existing Landing Page Structure

Located at: `spectrace/templates/admin/requirements/landing.html`
URL: `/` (root, name: `landing`)
View: `landing_view()` in `views.py`

**Current layout:**
```
┌─────────────────────────────────────────┐
│           SpecTrace (logo)              │
│  "Requirements as code, automatically   │
│           verified"                     │
├─────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │   127   │  │   92%   │  │    48   │  │ (if data exists)
│  │  Reqs   │  │ Passing │  │  Tests  │  │
│  └─────────┘  └─────────┘  └─────────┘  │
├─────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐     │
│  │  Dashboard   │  │ Take Tour    │     │
│  │  (icon)      │  │   (icon)     │     │
│  │ View matrix  │  │ Interactive  │     │
│  │ & status     │  │ walkthrough  │     │
│  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────┤
│         About SpecTrace (link)          │
└─────────────────────────────────────────┘
```

**View provides:**
- `stats.total_requirements` - Count of requirements
- `stats.total_tests` - Count of test links
- `stats.total_vendors` - Count of unique vendors
- `stats.passing` - Passing percentage

### Design System Assets Available

From `_design_system.html` (Phase 24 verified):

| CSS Class/Variable | Use For |
|-------------------|---------|
| `.landing-path` | Navigation cards with hover lift |
| `.landing-path__icon` | Icon containers (64x64, accent bg) |
| `.landing-path__title` | Card titles (1.5rem, 700 weight) |
| `.landing-path__desc` | Card descriptions |
| `.landing-stats` | Stats row container |
| `.landing-stat` | Individual stat items |
| `.st-animate-in` | Staggered fade-in animation |
| `--st-accent-500` | Indigo accent color |
| `--st-surface` | Background (auto dark mode) |
| `--st-text` | Primary text (auto dark mode) |
| `--st-text-muted` | Secondary text (auto dark mode) |

### Navigation URLs Available

Key destinations for feature cards:

| URL Name | Path | Description |
|----------|------|-------------|
| `admin-matrix` | `/admin/matrix/` | Traceability matrix grid |
| `admin-validation-runs` | `/admin/validation-runs/` | Test run history |
| `admin-vendor-coverage` | `/admin/vendor-coverage/` | Vendor pass rates |
| `admin-impact-analysis` | `/admin/impact-analysis/` | Spec change impact |
| `admin-flow-status` | `/admin/flow-status/` | Verification flows |
| `admin-flow-live` | `/admin/flow-status/live/` | Live flow execution |
| `spectrace_overview` | `/demo/spectrace-overview/` | Interactive tour |
| `demo_hub` | `/demo/` | All demos catalog |

## Value Proposition Options

Based on README and MILESTONES.md, the core value is PM visibility into verification:

### Option 1: PM-Focused (Recommended)
> **"See which requirements are verified by passing tests"**

Pros: Direct, action-oriented, explains what a PM can do
Cons: Slightly long

### Option 2: Outcome-Focused
> **"Know what's tested, what's not"**

Pros: Short, punchy
Cons: Doesn't convey the requirements connection

### Option 3: Problem-Solution
> **"Requirements traceability without spreadsheets"**

Pros: Addresses a known pain point
Cons: Less descriptive of what you actually see

### Option 4: Expanded Current
> **"Requirements verified by tests, tracked automatically"**

Pros: Close to current, emphasizes automation
Cons: Still developer-leaning

**Recommendation:** Option 1 with current tagline as subtitle.

## Recommended Features to Highlight

Based on MILESTONES.md shipped features and user stories, the most compelling 3-4 features:

### Feature 1: Traceability Matrix (Must Have)
- **Name:** Traceability Matrix
- **Icon:** Grid/matrix icon (already exists in current cards)
- **One-liner:** "See every requirement and its test coverage at a glance"
- **Link:** `{% url 'admin-matrix' %}`
- **Why:** Core differentiator, visual impact

### Feature 2: Verification Flows (Must Have)
- **Name:** Verification Flows
- **Icon:** Activity/pulse icon (from v8 milestone)
- **One-liner:** "Multi-step verification pipelines with live status"
- **Link:** `{% url 'admin-flow-status' %}`
- **Why:** Newest major feature (v8), differentiates from simple test tracking

### Feature 3: Vendor Coverage (Recommended)
- **Name:** Vendor Coverage
- **Icon:** Users/people icon
- **One-liner:** "Track pass rates across all your integrations"
- **Link:** `{% url 'admin-vendor-coverage' %}`
- **Why:** Multi-vendor tracking is unique value prop

### Feature 4: Impact Analysis (Recommended)
- **Name:** Impact Analysis
- **Icon:** Alert/warning icon
- **One-liner:** "Know which tests to run when specs change"
- **Link:** `{% url 'admin-impact-analysis' %}`
- **Why:** CI/CD integration story, developer appeal

### Alternative Feature: Regression Detection
- **Name:** Regression Alerts
- **Icon:** Bell/alert icon
- **One-liner:** "Instant alerts when verified requirements start failing"
- **Link:** Could link to validation runs with filter
- **Why:** Appeals to ops/reliability concerns

**Recommendation:** Features 1-4 give a complete picture (visualization, automation, multi-vendor, CI integration).

## Dark Mode Implementation

### Current Pattern (from landing.html)

The landing page already includes dark mode overrides:

```css
/* Dark mode: ensure text contrast */
html.dark .landing-logo {
    color: #f1f3f5;
}

html.dark .landing-tagline {
    color: #adb5bd;
}

html.dark .landing-path__title {
    color: #f1f3f5;
}

html.dark .landing-path__desc {
    color: #adb5bd;
}
```

### Design System Variables

Most styling uses variables that auto-flip:
- `--st-surface` - Card backgrounds
- `--st-border` - Card borders
- `--st-accent-500` - Accent color
- `--st-accent-bg` - Icon backgrounds

### Status

The landing page uses the design system include:
```django
{% include "admin/requirements/_design_system.html" %}
```

Combined with explicit `html.dark` overrides for text, dark mode should work. Phase 24 verified this pattern.

**Action:** Add dark mode testing to verification criteria.

## Implementation Approach

### Plan Structure

**Plan 25-01: Enhance Landing Page**
1. Update tagline to PM-focused value proposition
2. Add 3-4 feature highlight cards below navigation cards
3. Each card: icon, title, one-line description, link to feature
4. Use existing `.landing-path` styling (or create `.feature-card` variation)
5. Verify dark mode rendering
6. Update view if additional context needed (likely not)

### Layout Recommendation

```
┌─────────────────────────────────────────┐
│           SpecTrace (logo)              │
│  "See which requirements are verified   │
│         by passing tests"               │
│  (Requirements as code, automated)      │ <- current as subtitle
├─────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │ (stats if data)
│  │   127   │  │   92%   │  │    48   │  │
│  └─────────┘  └─────────┘  └─────────┘  │
├─────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐     │
│  │  Dashboard   │  │ Take Tour    │     │ (existing paths)
│  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────┤
│         Feature Highlights              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌───┐ │
│  │ Matrix │ │ Flows  │ │ Vendor │ │Imp│ │ (new cards)
│  └────────┘ └────────┘ └────────┘ └───┘ │
├─────────────────────────────────────────┤
│         About SpecTrace (link)          │
└─────────────────────────────────────────┘
```

### CSS Approach

Reuse existing `.landing-path` styles or create lighter `.feature-highlight` variant:

```css
.feature-highlights {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--st-space-4);
    max-width: 900px;
    width: 100%;
    margin-top: var(--st-space-8);
}

.feature-highlight {
    /* Smaller than landing-path, text-centered */
    text-align: center;
    padding: var(--st-space-5);
    background: var(--st-surface);
    border: 1px solid var(--st-border);
    border-radius: var(--st-radius-lg);
    /* ... */
}

@media (max-width: 640px) {
    .feature-highlights {
        grid-template-columns: repeat(2, 1fr);
    }
}
```

## Common Pitfalls

### Pitfall 1: Hardcoded Colors in Dark Mode
**What goes wrong:** Text unreadable in dark mode
**Prevention:** Use `--st-text`, `--st-text-muted` variables, add `html.dark` overrides if needed

### Pitfall 2: Too Many Feature Cards
**What goes wrong:** Overwhelming, dilutes focus
**Prevention:** Limit to 4, each with distinct value

### Pitfall 3: Feature Links to Missing Data
**What goes wrong:** User clicks, sees empty state
**Prevention:** Consider conditional display or "try demo" variant for empty installations

## Files to Modify

| File | Change |
|------|--------|
| `spectrace/templates/admin/requirements/landing.html` | Add value prop, feature cards |
| `spectrace/requirements/views.py` | None expected (stats already provided) |

## Code Examples

### Icon Patterns (from demo_hub.html)

Matrix icon:
```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <rect x="3" y="3" width="7" height="7"></rect>
    <rect x="14" y="3" width="7" height="7"></rect>
    <rect x="14" y="14" width="7" height="7"></rect>
    <rect x="3" y="14" width="7" height="7"></rect>
</svg>
```

Flow/activity icon:
```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
</svg>
```

Vendor/users icon:
```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
    <circle cx="9" cy="7" r="4"></circle>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
</svg>
```

Impact/alert icon:
```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="10"></circle>
    <line x1="12" y1="8" x2="12" y2="12"></line>
    <line x1="12" y1="16" x2="12.01" y2="16"></line>
</svg>
```

## Sources

### Primary (HIGH confidence)
- `spectrace/templates/admin/requirements/landing.html` - Current implementation
- `spectrace/templates/admin/requirements/_design_system.html` - CSS variables and components
- `spectrace/requirements/urls.py` - Available URL routes
- `spectrace/requirements/views.py` - Landing view context

### Secondary (MEDIUM confidence)
- `.planning/MILESTONES.md` - Feature history and value props
- `README.md` - User-facing description
- `spectrace/templates/admin/requirements/demo_hub.html` - Card patterns and icons

## Metadata

**Confidence breakdown:**
- Current state: HIGH - Direct file inspection
- Design patterns: HIGH - Reusing existing code
- Value proposition: MEDIUM - Subjective, may need user feedback
- Dark mode: HIGH - Verified pattern from Phase 24

**Research date:** 2026-02-03
**Valid until:** Stable - UI patterns don't change rapidly

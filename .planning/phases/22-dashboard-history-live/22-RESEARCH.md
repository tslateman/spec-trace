# Phase 22: Dashboard - History & Live Status - Research

**Researched:** 2026-02-02
**Domain:** Django admin dashboard views with Alpine.js interactivity
**Confidence:** HIGH

## Summary

Phase 22 extends the existing flow status dashboard to add comprehensive history and live monitoring capabilities. The codebase already has substantial infrastructure in place:

- `VerificationFlowRun` and `VerificationFlowStep` models with all necessary fields (status, timestamps, duration_ms)
- Data layer functions in `flow_status.py` (`get_flow_runs_data()`, `get_run_detail()`)
- Views in `views.py` (`flow_runs_view()`, `flow_run_detail_view()`)
- URL patterns at `/admin/flow-status/<flow_name>/` and `/admin/flow-status/run/<run_id>/`
- Design system with consistent styling (`_design_system.html`)
- Alpine.js already bundled for interactivity

**However, templates for these views don't exist yet** - the views render to non-existent template files. Additionally, there's no live status view for currently running flows, and filtering is minimal.

**Primary recommendation:** Create the missing templates using existing design system components, add URL-based filtering to the existing data layer, and implement a new live status view with Alpine.js polling (5-second interval for running flows).

## Standard Stack

The project uses established patterns that should be followed:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 5.x | Backend framework | Already in use |
| django-unfold | latest | Admin theme | Base templates extend `unfold/layouts/base.html` |
| Alpine.js | 3.x | Frontend interactivity | Already bundled, used in `index.html` |
| Tailwind CSS | 3.x | Styling (via unfold) | Design system uses CSS custom properties on top |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Django Paginator | built-in | List pagination | Already used in `flow_status.py` |
| Django Q objects | built-in | Complex filtering | Used in `get_flow_runs_data()` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Alpine.js polling | WebSocket/SSE | More complex, overkill for 5-second updates |
| URL params filtering | Django forms | URL params simpler, already pattern in codebase |
| Custom design | unfold components | Mix approach works - use design system classes |

**Installation:**
No new packages needed. All infrastructure exists.

## Architecture Patterns

### Recommended Template Structure
```
spectrace/templates/admin/requirements/
├── flow_status.html          # EXISTS - flow cards overview
├── flow_runs.html            # NEW - history list with filtering
├── flow_run_detail.html      # NEW - single run step timeline
└── flow_live.html            # NEW - live monitoring view
```

### Pattern 1: Design System Extension
**What:** All new templates extend unfold base and include design system partial
**When to use:** Every new admin template
**Example:**
```django
{% extends "unfold/layouts/base.html" %}
{% load i18n %}

{% block title %}{{ title }} | SpecTrace{% endblock %}

{% block content %}
{% include "admin/requirements/_design_system.html" %}

<div class="st-page-wrapper">
<div class="st-page st-container">
    <!-- Content here -->
</div>
</div>
{% endblock %}
```

### Pattern 2: URL-Based Filtering
**What:** Filter parameters in query string, preserved across pagination
**When to use:** List views with filters
**Example:**
```python
# In view
filters = {}
if request.GET.get('status'):
    filters['status'] = request.GET['status']
if request.GET.get('flow'):
    filters['flow'] = request.GET['flow']
if request.GET.get('date_from'):
    filters['date_from'] = parse_datetime(request.GET['date_from'])

# In data layer
queryset = VerificationFlowRun.objects.all()
if filters.get('status'):
    queryset = queryset.filter(status=filters['status'])
if filters.get('flow'):
    queryset = queryset.filter(flow__name=filters['flow'])
if filters.get('date_from'):
    queryset = queryset.filter(started_at__gte=filters['date_from'])
```

### Pattern 3: Alpine.js Polling for Live Status
**What:** setInterval with init/destroy lifecycle
**When to use:** Live monitoring view
**Example:**
```javascript
function liveStatusWidget() {
    return {
        runs: [],
        isLoading: false,
        timer: null,

        async init() {
            await this.fetchRuns();
            this.timer = setInterval(() => this.fetchRuns(), 5000);
        },

        destroy() {
            if (this.timer) clearInterval(this.timer);
        },

        async fetchRuns() {
            this.isLoading = true;
            try {
                const response = await fetch('/api/flow-runs/running/');
                const data = await response.json();
                this.runs = data.runs;
            } finally {
                this.isLoading = false;
            }
        }
    };
}
```

### Pattern 4: Step Pipeline Visualization
**What:** Horizontal step indicators showing progress
**When to use:** Flow run detail and live status
**Example:**
```html
<div class="flow-pipeline">
    {% for step in steps %}
    {% if not forloop.first %}
    <div class="flow-pipeline-connector"></div>
    {% endif %}
    <div class="flow-pipeline-step flow-pipeline-step--{{ step.status }}"
         title="{{ step.name }}">
    </div>
    {% endfor %}
</div>
```

### Anti-Patterns to Avoid
- **Inline styles over design system:** Use `st-*` classes from design system, not inline CSS
- **AJAX without CSRF:** Always include CSRF token in POST requests
- **Polling without cleanup:** Always clear intervals on component destroy
- **Missing templates:** Templates must exist for view render calls

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pagination | Custom offset logic | Django Paginator | Already used in `flow_status.py`, handles edge cases |
| Date filtering | Manual string parsing | Django dateparse | Handles ISO 8601, timezones |
| Polling timing | Manual setTimeout chains | setInterval + Alpine lifecycle | Memory-safe pattern |
| Status badges | Custom CSS classes | `st-badge--pass/fail/warn` | Design system consistency |
| Dark mode | Manual color switching | CSS custom properties | Design system handles via `html.dark` |

**Key insight:** The codebase has established patterns in `validation_runs.html` and `flow_status.html`. Copy these patterns rather than inventing new ones.

## Common Pitfalls

### Pitfall 1: Missing Template File
**What goes wrong:** View calls `render()` with template path that doesn't exist
**Why it happens:** Data layer and views created without corresponding templates
**How to avoid:** Always create template when creating view
**Warning signs:** 500 error with `TemplateDoesNotExist`

### Pitfall 2: Polling Memory Leak
**What goes wrong:** setInterval continues after component unmounts
**Why it happens:** No cleanup in Alpine destroy lifecycle
**How to avoid:** Always call `clearInterval(this.timer)` in destroy
**Warning signs:** Network tab shows continued API calls after navigation

### Pitfall 3: Filter State Lost on Pagination
**What goes wrong:** Click "Next page" and filters reset
**Why it happens:** Pagination links don't include current filter params
**How to avoid:** Include all filter params in pagination link href
**Warning signs:** User filters, clicks page 2, filters disappear

### Pitfall 4: N+1 Queries
**What goes wrong:** View becomes slow with many runs
**Why it happens:** Accessing related objects without prefetch
**How to avoid:** Use `select_related('flow')` and `prefetch_related('steps')`
**Warning signs:** Django Debug Toolbar shows 100+ queries

### Pitfall 5: Timezone Display Issues
**What goes wrong:** Timestamps show in wrong timezone
**Why it happens:** Template displays UTC, user expects local
**How to avoid:** Use Django's `date` filter with appropriate format, or display "X minutes ago" with JS
**Warning signs:** "Last run: 3:00 AM" when it's 11:00 AM locally

## Code Examples

### Flow Runs List Template Structure
```django
{# flow_runs.html #}
{% extends "unfold/layouts/base.html" %}
{% load i18n %}

{% block content %}
{% include "admin/requirements/_design_system.html" %}

<div class="st-page-wrapper">
<div class="st-page st-container">
    <!-- Breadcrumbs -->
    <nav class="st-breadcrumbs st-animate-in">
        <a href="{% url 'admin-flow-status' %}" class="st-breadcrumb-link">Flows</a>
        <span class="st-breadcrumb-sep">/</span>
        <span class="st-breadcrumb-current">{{ flow_def.display_name }}</span>
    </nav>

    <!-- Header -->
    <header class="st-flex-between mb-6 st-animate-in st-animate-delay-1">
        <div>
            <h1 class="st-heading-1">{{ flow_def.display_name }} History</h1>
            <p class="st-caption mt-1">{{ summary.total_runs }} total runs</p>
        </div>
    </header>

    <!-- Filters Card -->
    <div class="st-card st-animate-in st-animate-delay-2 mb-6">
        <div class="st-card-header">
            <h2 class="st-heading-3">Filters</h2>
        </div>
        <form method="get" class="st-card-body">
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--st-space-4); align-items: end;">
                <div>
                    <label class="st-input-label">Status</label>
                    <select name="status" class="st-select">
                        <option value="">All</option>
                        <option value="passed" {% if filters.status == 'passed' %}selected{% endif %}>Passed</option>
                        <option value="failed" {% if filters.status == 'failed' %}selected{% endif %}>Failed</option>
                        <option value="running" {% if filters.status == 'running' %}selected{% endif %}>Running</option>
                    </select>
                </div>
                <div>
                    <label class="st-input-label">Date From</label>
                    <input type="date" name="date_from" value="{{ filters.date_from }}" class="st-input">
                </div>
                <div>
                    <label class="st-input-label">Date To</label>
                    <input type="date" name="date_to" value="{{ filters.date_to }}" class="st-input">
                </div>
                <div class="st-cluster">
                    <button type="submit" class="st-btn st-btn--primary">Apply</button>
                    <a href="{% url 'admin-flow-runs' flow_def.name %}" class="st-btn st-btn--ghost">Clear</a>
                </div>
            </div>
        </form>
    </div>

    <!-- Runs Table -->
    <div class="st-card st-animate-in st-animate-delay-3">
        <table class="st-table">
            <thead>
                <tr>
                    <th>Run</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Duration</th>
                    <th>Steps</th>
                </tr>
            </thead>
            <tbody>
                {% for run in runs %}
                <tr>
                    <td>
                        <a href="{% url 'admin-flow-run-detail' run.id %}" class="st-mono" style="color: var(--st-accent-600);">
                            #{{ run.id }}
                        </a>
                    </td>
                    <td>
                        <span class="st-badge {% if run.status == 'passed' %}st-badge--pass{% elif run.status == 'failed' %}st-badge--fail{% else %}st-badge--warn{% endif %}">
                            {{ run.status|title }}
                        </span>
                    </td>
                    <td class="st-mono" style="font-size: 0.8125rem;">{{ run.started_at|date:"M j, H:i" }}</td>
                    <td class="st-mono">{% if run.duration_ms %}{{ run.duration_ms }}ms{% else %}-{% endif %}</td>
                    <td>
                        <span style="color: var(--st-pass);">{{ run.steps_passed }}</span> /
                        <span style="color: var(--st-fail);">{{ run.steps_failed }}</span>
                    </td>
                </tr>
                {% empty %}
                <tr>
                    <td colspan="5" style="text-align: center; padding: var(--st-space-10);">
                        No runs found.
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        {% if pagination.total_pages > 1 %}
        <div class="st-card-body" style="border-top: 1px solid var(--st-border);">
            <!-- Pagination links with filter params preserved -->
        </div>
        {% endif %}
    </div>
</div>
</div>
{% endblock %}
```

### Live Status Polling Component
```javascript
// Alpine.js component for live flow monitoring
function liveFlowMonitor() {
    return {
        runningFlows: [],
        lastUpdate: null,
        isPolling: true,
        timer: null,
        error: null,

        async init() {
            await this.fetchRunningFlows();
            this.startPolling();
        },

        destroy() {
            this.stopPolling();
        },

        startPolling() {
            if (this.timer) return;
            this.timer = setInterval(() => {
                if (this.isPolling) this.fetchRunningFlows();
            }, 5000);
        },

        stopPolling() {
            if (this.timer) {
                clearInterval(this.timer);
                this.timer = null;
            }
        },

        togglePolling() {
            this.isPolling = !this.isPolling;
            if (!this.isPolling) {
                this.stopPolling();
            } else {
                this.startPolling();
            }
        },

        async fetchRunningFlows() {
            try {
                const response = await fetch('/api/flow-runs/?status=running');
                if (!response.ok) throw new Error('Failed to fetch');
                const data = await response.json();
                this.runningFlows = data.runs || [];
                this.lastUpdate = new Date();
                this.error = null;
            } catch (err) {
                this.error = 'Failed to fetch running flows';
            }
        },

        get lastUpdateText() {
            if (!this.lastUpdate) return '';
            return 'Updated ' + this.formatRelativeTime(this.lastUpdate);
        },

        formatRelativeTime(date) {
            const seconds = Math.floor((new Date() - date) / 1000);
            if (seconds < 5) return 'just now';
            if (seconds < 60) return seconds + 's ago';
            return Math.floor(seconds / 60) + 'm ago';
        }
    };
}
```

### API Endpoint for Running Flows
```python
# New endpoint needed in api.py
@require_http_methods(["GET"])
@ratelimit(key='ip', rate=RATE_LIMIT_READ, block=True)
def get_running_flow_runs(request):
    """Get currently running flow runs for live monitoring."""
    runs = VerificationFlowRun.objects.filter(
        status=VerificationFlowStatus.RUNNING
    ).select_related('flow').prefetch_related('steps').order_by('-started_at')

    runs_data = []
    for run in runs:
        steps = list(run.steps.order_by('step_order'))
        completed_steps = [s for s in steps if s.completed_at]
        current_step = next((s for s in steps if not s.completed_at), None)

        runs_data.append({
            'id': run.id,
            'flow_name': run.flow.name,
            'flow_display_name': run.flow.display_name,
            'started_at': run.started_at.isoformat(),
            'total_steps': len(steps),
            'completed_steps': len(completed_steps),
            'current_step': current_step.name if current_step else None,
            'current_step_order': current_step.step_order if current_step else None,
        })

    return JsonResponse({'runs': runs_data})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inline CSS | CSS custom properties + design system | This project | Consistent dark mode, easier maintenance |
| Manual AJAX | Alpine.js x-data components | Alpine.js 3.x | Cleaner, declarative |
| jQuery polling | setInterval + destroy lifecycle | Alpine.js 3.x | No memory leaks |
| Server-side only | Client-side polling for live | Modern apps | Responsive UX |

**Deprecated/outdated:**
- jQuery: Not used in this project, use Alpine.js
- Inline styles: Use design system classes (st-*)

## Open Questions

Things that couldn't be fully resolved:

1. **What polling interval for live status?**
   - What we know: 5 seconds is common for dashboards
   - What's unclear: Server load tolerance, expected concurrent users
   - Recommendation: Start with 5 seconds, add rate limiting, monitor

2. **Should live view auto-navigate to detail on completion?**
   - What we know: Running flows complete unpredictably
   - What's unclear: User preference for auto-navigation
   - Recommendation: Don't auto-navigate, show completion badge with link

3. **Pagination size for history?**
   - What we know: Existing views use 25 per page
   - What's unclear: Typical flow run volume
   - Recommendation: Match existing (25), add per_page selector

## Sources

### Primary (HIGH confidence)
- `/Users/tslater/dev/spec-trace/spectrace/requirements/models.py` - VerificationFlowRun, VerificationFlowStep models
- `/Users/tslater/dev/spec-trace/spectrace/requirements/flow_status.py` - Data layer functions
- `/Users/tslater/dev/spec-trace/spectrace/requirements/views.py` - Existing view implementations
- `/Users/tslater/dev/spec-trace/spectrace/templates/admin/requirements/flow_status.html` - Template pattern
- `/Users/tslater/dev/spec-trace/spectrace/templates/admin/requirements/validation_runs.html` - Filtering pattern
- `/Users/tslater/dev/spec-trace/spectrace/templates/admin/requirements/_design_system.html` - CSS classes

### Secondary (MEDIUM confidence)
- [Alpine.js Polling Pattern](https://khalidabuhakmeh.com/alpinejs-polling-aspnet-core-apis-for-updates) - setInterval best practices
- [alpine-auto-interval plugin](https://github.com/KevinBatdorf/alpine-auto-interval) - Alternative polling approach

### Tertiary (LOW confidence)
- None - all patterns verified from codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from existing codebase
- Architecture: HIGH - patterns extracted from existing templates
- Pitfalls: HIGH - common Django/Alpine.js issues, verified in codebase

**Research date:** 2026-02-02
**Valid until:** 60 days (stable Django/Alpine.js patterns)

## Implementation Sequence Recommendation

1. **Create flow_runs.html template** (HIST-01, HIST-02)
   - Copy structure from validation_runs.html
   - Add status/date filters
   - Preserve filter params in pagination

2. **Create flow_run_detail.html template** (HIST-03, HIST-04)
   - Copy step timeline pattern from validation_run_detail.html
   - Add step timing, error messages
   - Add previous/next navigation

3. **Add date filtering to data layer**
   - Extend `get_flow_runs_data()` with date_from, date_to, status filters
   - Update view to parse filter params

4. **Create live status view and template** (LIVE-01 through LIVE-04)
   - New view function for live status page
   - New API endpoint for running flows
   - Alpine.js polling component
   - Progress indicator (completed steps / total)

5. **Add URL routing for live view**
   - `/admin/flow-status/live/` for live monitoring

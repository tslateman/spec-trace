# Phase 7: Dashboard Integration - Research

**Researched:** 2026-01-21
**Domain:** Django template integration, Alpine.js interactivity, TailwindCSS status badges
**Confidence:** HIGH

## Summary

This phase adds Linear integration health visibility to the existing SpecTrace dashboard. The APIs (POST `/api/integrations/linear/test-connection/` and GET `/api/integrations/linear/health/`) are already implemented in Phase 6. This phase focuses entirely on the frontend: displaying the health badge, last-checked timestamp, and a "Test Connection" button with loading state.

The established stack from prior phases is Django templates extending `unfold/layouts/base.html`, TailwindCSS for styling, and Alpine.js for interactivity (both included with django-unfold). The pattern follows existing dashboard code in `templates/admin/index.html` which uses TailwindCSS utility classes and Django template variables.

**Primary recommendation:** Add an "Integrations" card to the existing dashboard index.html template with Alpine.js x-data component that fetches health status on load and handles "Test Connection" button interactions with loading state. Use TailwindCSS color classes matching the existing status badge pattern (green/yellow/red).

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| django-unfold | >=0.76 | Admin template + Alpine.js + TailwindCSS | Already installed, provides Alpine.js and Tailwind |
| Alpine.js | 3.x (bundled) | Client-side interactivity | Included with django-unfold, no additional dependency |
| TailwindCSS | 3.x (bundled) | Styling | Included with django-unfold, already used in index.html |
| Native fetch API | Browser stdlib | API calls | No library needed, supported by all modern browsers |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Intl.RelativeTimeFormat | Browser stdlib | "Last checked 2 min ago" display | For timestamp display, browser-native |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Alpine.js | Vanilla JS | Alpine.js already available, cleaner reactive state |
| Alpine.js | HTMX | Alpine better for client-side state management (loading indicators) |
| Intl.RelativeTimeFormat | moment.js/dayjs | Browser API sufficient, no dependency needed |
| Inline fetch | Axios | fetch is standard, no additional payload |

**Installation:**
```bash
# No additional dependencies needed - all included with django-unfold
```

## Architecture Patterns

### Recommended Project Structure
```
spectrace/
├── templates/
│   └── admin/
│       └── index.html        # MODIFY: Add Integrations card
└── spectrace/
    └── urls.py               # Already has health endpoints
```

### Pattern 1: Alpine.js Component for Health Status
**What:** x-data component managing health state, loading state, and API calls
**When to use:** For the integrations health badge and test button
**Example:**
```html
<!-- Source: Alpine.js fetch patterns from codewithhugo.com -->
<div x-data="linearHealthWidget()" x-init="fetchHealth()">
    <!-- Health badge -->
    <span :class="statusClass" x-text="statusLabel"></span>

    <!-- Last checked timestamp -->
    <span x-show="lastChecked" x-text="lastCheckedText" class="text-sm text-base-500"></span>

    <!-- Test Connection button -->
    <button
        @click="testConnection()"
        :disabled="isLoading"
        class="px-3 py-1.5 bg-primary-600 hover:bg-primary-700 text-white rounded-lg disabled:opacity-50"
    >
        <span x-show="!isLoading">Test Connection</span>
        <span x-show="isLoading">Testing...</span>
    </button>
</div>

<script>
function linearHealthWidget() {
    return {
        status: 'unknown',      // healthy, degraded, unhealthy, unknown
        message: '',
        lastChecked: null,      // ISO timestamp
        isLoading: false,
        error: null,

        get statusLabel() {
            const labels = {
                healthy: 'Healthy',
                degraded: 'Degraded',
                unhealthy: 'Unhealthy',
                unknown: 'Unknown'
            };
            return labels[this.status] || 'Unknown';
        },

        get statusClass() {
            const classes = {
                healthy: 'status-passing',
                degraded: 'status-untested',
                unhealthy: 'status-failing',
                unknown: 'bg-base-200 text-base-600'
            };
            return 'text-xs px-2 py-1 rounded font-medium ' + (classes[this.status] || classes.unknown);
        },

        get lastCheckedText() {
            if (!this.lastChecked) return '';
            return 'Last checked ' + this.formatRelativeTime(new Date(this.lastChecked));
        },

        formatRelativeTime(date) {
            const now = new Date();
            const diffSeconds = Math.floor((now - date) / 1000);

            if (diffSeconds < 60) return 'just now';
            if (diffSeconds < 3600) return Math.floor(diffSeconds / 60) + ' min ago';
            if (diffSeconds < 86400) return Math.floor(diffSeconds / 3600) + ' hr ago';
            return Math.floor(diffSeconds / 86400) + ' days ago';
        },

        async fetchHealth() {
            try {
                const response = await fetch('/api/integrations/linear/health/');
                const data = await response.json();
                this.status = data.status || 'unknown';
                this.message = data.message || '';
                // Extract timestamp from first check if available
                if (data.checks && data.checks.length > 0) {
                    this.lastChecked = data.checks[0].timestamp;
                }
            } catch (e) {
                this.status = 'unknown';
                this.error = 'Failed to fetch health status';
            }
        },

        async testConnection() {
            this.isLoading = true;
            this.error = null;
            try {
                const response = await fetch('/api/integrations/linear/test-connection/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                this.status = data.status || 'unknown';
                this.message = data.message || '';
                if (data.checks && data.checks.length > 0) {
                    this.lastChecked = data.checks[0].timestamp;
                }
            } catch (e) {
                this.status = 'unknown';
                this.error = 'Connection test failed';
            } finally {
                this.isLoading = false;
            }
        }
    }
}
</script>
```

### Pattern 2: Health Status Badge with Color Coding
**What:** TailwindCSS badge matching existing status patterns in index.html
**When to use:** Displaying health status (healthy/degraded/unhealthy)
**Example:**
```html
<!-- Source: Existing index.html status badge pattern -->
<!-- Reuse the same status-* CSS classes already defined in index.html -->
<style>
    /* These already exist in index.html - no new CSS needed */
    .status-passing { background-color: #dcfce7; color: #166534; }
    .status-failing { background-color: #fee2e2; color: #991b1b; }
    .status-untested { background-color: #fef9c3; color: #854d0e; }
    .dark .status-passing { background-color: #052e16; color: #4ade80; }
    .dark .status-failing { background-color: #450a0a; color: #f87171; }
    .dark .status-untested { background-color: #422006; color: #facc15; }
</style>

<!-- Status badge mapping -->
<!-- healthy   -> status-passing (green) -->
<!-- degraded  -> status-untested (yellow) -->
<!-- unhealthy -> status-failing (red) -->
<!-- unknown   -> bg-base-200 (gray) -->
```

### Pattern 3: Loading State Button
**What:** Button with disabled state and loading indicator during API call
**When to use:** "Test Connection" button
**Example:**
```html
<!-- Source: Alpine.js patterns + existing dashboard button styling -->
<button
    @click="testConnection()"
    :disabled="isLoading"
    :class="isLoading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-primary-700'"
    class="px-4 py-2 bg-primary-600 text-white rounded-lg transition-colors flex items-center gap-2"
>
    <!-- Spinner SVG shown during loading -->
    <svg x-show="isLoading" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
    </svg>
    <span x-text="isLoading ? 'Testing...' : 'Test Connection'"></span>
</button>
```

### Pattern 4: Integrations Card Layout
**What:** Card component matching existing dashboard design
**When to use:** Adding the Integrations section to dashboard
**Example:**
```html
<!-- Source: Existing index.html Quick Actions section pattern -->
<div class="bg-white dark:bg-base-900 rounded-lg shadow border border-base-200 dark:border-base-800">
    <div class="p-4 border-b border-base-200 dark:border-base-800 flex justify-between items-center">
        <h2 class="text-lg font-semibold text-base-900 dark:text-white">Integrations</h2>
    </div>
    <div class="p-4">
        <!-- Linear integration row -->
        <div class="flex items-center justify-between" x-data="linearHealthWidget()" x-init="fetchHealth()">
            <div class="flex items-center gap-3">
                <!-- Linear icon/name -->
                <span class="font-medium text-base-900 dark:text-white">Linear</span>
                <!-- Status badge -->
                <span :class="statusClass" x-text="statusLabel"></span>
                <!-- Last checked -->
                <span x-show="lastChecked" x-text="lastCheckedText" class="text-sm text-base-500 dark:text-base-400"></span>
            </div>
            <button @click="testConnection()" :disabled="isLoading" ...>
                Test Connection
            </button>
        </div>
    </div>
</div>
```

### Anti-Patterns to Avoid
- **Don't poll automatically:** User-triggered refresh only (Test Connection button). Avoid setInterval that hits rate limits.
- **Don't show stale unknown status as error:** "Unknown" just means no cached result, not an error. Use neutral gray styling.
- **Don't block UI on initial load:** Use async fetch in x-init, let page render immediately.
- **Don't use external JS libraries:** Alpine.js and native fetch are sufficient, no need for Axios/jQuery.
- **Don't create separate integrations page:** Add to existing dashboard index.html for discoverability.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reactive UI state | Manual DOM manipulation | Alpine.js x-data | Already included, handles reactivity cleanly |
| Loading indicators | Custom CSS animations | TailwindCSS animate-spin | Built-in, consistent with framework |
| Status badge colors | New color variables | Existing status-* classes | Already defined in index.html, dark mode supported |
| Relative time display | External library | Simple Math + template literals | 4 lines of code sufficient for this use case |
| API calls | Axios/jQuery | Native fetch | No dependency needed, modern browsers all support it |

**Key insight:** The existing dashboard already has all the patterns needed. The Integrations card is structurally identical to the existing "Quick Reference" and "Requirements Tree" cards. Copy the patterns, don't invent new ones.

## Common Pitfalls

### Pitfall 1: CSRF Token Required for POST
**What goes wrong:** POST to test-connection returns 403 Forbidden
**Why it happens:** Django CSRF protection blocks POST without token
**How to avoid:** The test-connection endpoint already has @csrf_exempt (from Phase 6), so this is already handled. If it weren't, you'd need to include CSRF token in fetch headers.
**Warning signs:** 403 response, "CSRF verification failed" in response

### Pitfall 2: Alpine.js x-init vs x-data Order
**What goes wrong:** "fetchHealth is not defined" error
**Why it happens:** x-init runs before x-data methods are available if not properly structured
**How to avoid:** Define methods inside the x-data function, call them from x-init: `x-init="fetchHealth()"`
**Warning signs:** Console errors about undefined functions

### Pitfall 3: Dark Mode Badge Colors Not Updating
**What goes wrong:** Badge colors look wrong in dark mode
**Why it happens:** Using inline style colors instead of TailwindCSS classes
**How to avoid:** Use the existing `.dark .status-*` classes already defined in index.html
**Warning signs:** Green badge appears too bright in dark mode

### Pitfall 4: Button Stays Disabled After Error
**What goes wrong:** After a failed API call, button never re-enables
**Why it happens:** Missing finally block to reset isLoading
**How to avoid:** Always use try/catch/finally: `finally { this.isLoading = false }`
**Warning signs:** Button permanently disabled after network error

### Pitfall 5: Health Status Shows "Unknown" Permanently
**What goes wrong:** Badge always shows "Unknown" even after successful test
**Why it happens:** API returns status in 'status' field but code looks elsewhere
**How to avoid:** Match API response structure exactly: `data.status` is the status field
**Warning signs:** Test succeeds but badge doesn't update

### Pitfall 6: Timestamp Shows Wrong Time
**What goes wrong:** "Last checked 3 hours ago" when it was just checked
**Why it happens:** Comparing UTC timestamp to local time incorrectly
**How to avoid:** API returns ISO 8601 timestamps which JavaScript Date() handles correctly. Ensure `new Date(isoString)` is used.
**Warning signs:** Time off by timezone offset hours

### Pitfall 7: x-show Flickers on Load
**What goes wrong:** Hidden elements briefly visible before Alpine.js initializes
**Why it happens:** Alpine.js hasn't initialized yet when page first renders
**How to avoid:** Use x-cloak directive and corresponding CSS: `[x-cloak] { display: none !important; }`
**Warning signs:** Flash of unstyled content on page load

## Code Examples

Verified patterns from official sources:

### Complete Integrations Card
```html
<!-- Source: Existing index.html patterns + Alpine.js documentation -->
<!-- Add after Quick Actions section in templates/admin/index.html -->

<!-- Integrations Section -->
<div class="mt-6 bg-white dark:bg-base-900 rounded-lg shadow border border-base-200 dark:border-base-800">
    <div class="p-4 border-b border-base-200 dark:border-base-800">
        <h2 class="text-lg font-semibold text-base-900 dark:text-white">Integrations</h2>
    </div>
    <div class="p-4">
        <!-- Linear Integration -->
        <div class="flex items-center justify-between flex-wrap gap-3"
             x-data="linearHealthWidget()"
             x-init="fetchHealth()"
             x-cloak>
            <div class="flex items-center gap-3">
                <div class="flex items-center gap-2">
                    <span class="font-medium text-base-900 dark:text-white">Linear</span>
                    <!-- Health Status Badge -->
                    <span :class="statusClass" x-text="statusLabel"></span>
                </div>
                <!-- Last Checked Timestamp -->
                <span x-show="lastChecked"
                      x-text="lastCheckedText"
                      class="text-sm text-base-500 dark:text-base-400">
                </span>
            </div>
            <!-- Test Connection Button -->
            <button
                @click="testConnection()"
                :disabled="isLoading"
                class="px-4 py-2 bg-primary-600 text-white rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                :class="!isLoading && 'hover:bg-primary-700'"
            >
                <!-- Spinner -->
                <svg x-show="isLoading"
                     class="animate-spin h-4 w-4"
                     xmlns="http://www.w3.org/2000/svg"
                     fill="none"
                     viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
                <span x-text="isLoading ? 'Testing...' : 'Test Connection'"></span>
            </button>
        </div>

        <!-- Error message if any -->
        <div x-show="error" class="mt-2 text-sm text-red-600 dark:text-red-400" x-text="error"></div>
    </div>
</div>

<script>
function linearHealthWidget() {
    return {
        status: 'unknown',
        message: '',
        lastChecked: null,
        isLoading: false,
        error: null,

        get statusLabel() {
            const labels = {
                healthy: 'Healthy',
                degraded: 'Degraded',
                unhealthy: 'Unhealthy',
                unknown: 'Unknown'
            };
            return labels[this.status] || 'Unknown';
        },

        get statusClass() {
            const base = 'text-xs px-2 py-1 rounded font-medium';
            const statusClasses = {
                healthy: 'status-passing',
                degraded: 'status-untested',
                unhealthy: 'status-failing',
                unknown: 'bg-base-200 dark:bg-base-700 text-base-600 dark:text-base-400'
            };
            return base + ' ' + (statusClasses[this.status] || statusClasses.unknown);
        },

        get lastCheckedText() {
            if (!this.lastChecked) return '';
            const date = new Date(this.lastChecked);
            const now = new Date();
            const diffSeconds = Math.floor((now - date) / 1000);

            let relativeTime;
            if (diffSeconds < 60) relativeTime = 'just now';
            else if (diffSeconds < 3600) relativeTime = Math.floor(diffSeconds / 60) + ' min ago';
            else if (diffSeconds < 86400) relativeTime = Math.floor(diffSeconds / 3600) + ' hr ago';
            else relativeTime = Math.floor(diffSeconds / 86400) + ' days ago';

            return 'Last checked ' + relativeTime;
        },

        async fetchHealth() {
            try {
                const response = await fetch('/api/integrations/linear/health/');
                const data = await response.json();
                this.updateFromResponse(data);
            } catch (e) {
                this.status = 'unknown';
                // Don't show error for initial load - just means no cached data
            }
        },

        async testConnection() {
            this.isLoading = true;
            this.error = null;
            try {
                const response = await fetch('/api/integrations/linear/test-connection/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                this.updateFromResponse(data);
                if (!data.success) {
                    this.error = data.message || 'Connection test failed';
                }
            } catch (e) {
                this.status = 'unknown';
                this.error = 'Failed to connect to server';
            } finally {
                this.isLoading = false;
            }
        },

        updateFromResponse(data) {
            this.status = data.status || 'unknown';
            this.message = data.message || '';
            // Get timestamp from first check or use current time
            if (data.checks && data.checks.length > 0 && data.checks[0].timestamp) {
                this.lastChecked = data.checks[0].timestamp;
            } else if (data.success !== false) {
                // If successful but no timestamp, use now
                this.lastChecked = new Date().toISOString();
            }
        }
    }
}
</script>
```

### CSS for x-cloak (Prevent Flash)
```html
<!-- Add to <style> block in index.html -->
<style>
    [x-cloak] { display: none !important; }
    /* ... existing status-* styles ... */
</style>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| jQuery AJAX | Native fetch + Alpine.js | 2020+ | No jQuery dependency, cleaner syntax |
| Separate JS files | Inline Alpine.js components | Alpine.js 3.x | Better colocation, no build step |
| Manual DOM updates | Alpine.js reactive data | Alpine.js pattern | Automatic UI sync with state changes |
| moment.js for dates | Intl.RelativeTimeFormat | 2020+ (browser API) | No dependency needed |
| Polling for status | On-demand fetch + button | Modern UX | Respects rate limits, user-controlled |

**Deprecated/outdated:**
- **jQuery:** Not needed with Alpine.js available
- **moment.js:** Browser APIs sufficient for relative time
- **XMLHttpRequest:** Use native fetch instead

## Open Questions

Things that couldn't be fully resolved:

1. **Auto-refresh interval**
   - What we know: Requirements specify manual "Test Connection" button, no auto-refresh mentioned
   - What's unclear: Whether dashboard should auto-refresh health status on interval
   - Recommendation: Start with manual-only (button). Add auto-refresh later if users request it. Respects 60s cache TTL and avoids rate limit concerns.

2. **Multiple integrations display**
   - What we know: Only Linear integration exists now
   - What's unclear: Whether future integrations (GitHub, Jira) will be added
   - Recommendation: Structure the Integrations card to support multiple rows. Each integration is a separate Alpine.js component.

3. **Error detail display**
   - What we know: API returns detailed checks[] array with individual check results
   - What's unclear: How much detail to show on failure (simple message vs. full check list)
   - Recommendation: Show simple error message inline. Full details available via browser dev tools or separate diagnostics page if needed later.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `templates/admin/index.html` - Established patterns for dashboard cards, status badges
- Existing codebase: `requirements/api.py` - Phase 6 health check API response format
- [Alpine.js Documentation](https://alpinejs.dev/essentials/state) - x-data, x-init patterns
- [Code with Hugo: Alpine.js x-data fetching](https://codewithhugo.com/alpinejs-x-data-fetching/) - Fetch with loading state pattern

### Secondary (MEDIUM confidence)
- [Using Native Fetch with Alpine.js](https://www.wittyprogramming.dev/articles/using-native-fetch-with-alpinejs/) - POST/fetch patterns
- [Flowbite Indicators](https://flowbite.com/docs/components/indicators/) - Status indicator patterns
- [django-unfold PyPI](https://pypi.org/project/django-unfold/) - Confirms Alpine.js is included

### Tertiary (LOW confidence)
- [Intl.RelativeTimeFormat MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/RelativeTimeFormat) - Browser API for relative time (not using directly, but informed simple implementation)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already in use in the project
- Architecture: HIGH - Follows existing dashboard patterns exactly
- Pitfalls: HIGH - Based on common Alpine.js/fetch patterns and project-specific API details

**Research date:** 2026-01-21
**Valid until:** 2026-02-21 (30 days - stable patterns, all dependencies already installed)

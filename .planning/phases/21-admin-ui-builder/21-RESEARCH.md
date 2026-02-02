# Phase 21: Admin UI Builder - Research

**Researched:** 2026-02-02
**Domain:** Django Admin custom views, YAML file editing, form handling
**Confidence:** HIGH

## Summary

This phase builds a visual editor for flow YAML files within the Django admin. The project already has mature patterns for custom admin pages using django-unfold and Alpine.js, with extensive examples in the existing `flow_status.html`, `validation_run_detail.html`, and matrix views. YAML editing requires careful handling to preserve formatting and comments.

The recommended approach uses a custom admin view (not ModelAdmin) following the existing URL pattern in `requirements/urls.py`, with Alpine.js for dynamic step management and ruamel.yaml for round-trip YAML editing. Server-side validation reuses the existing `YAMLFlowParser` class.

**Primary recommendation:** Build as custom admin views extending the existing pattern in `requirements/views.py`, using the established design system and Alpine.js patterns.

## Standard Stack

The project already has the right dependencies for this phase.

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 5.2.x | Web framework | Project foundation |
| django-unfold | 0.76+ | Admin theme | Already integrated, provides base templates |
| PyYAML | 6.0.x | YAML parsing | Already used for flow parsing |
| Alpine.js | (via CDN) | Reactive UI | Already used throughout admin templates |

### Supporting (To Add)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ruamel.yaml | 0.18+ | Round-trip YAML | Preserves comments/formatting on save |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ruamel.yaml | PyYAML | PyYAML loses comments on round-trip; use ruamel for editing |
| Alpine.js | htmx | Alpine already used; consistent with existing UI |
| Custom form | django-jsonform | Flow schema is simple enough for custom solution |

**Installation:**
```bash
uv add ruamel.yaml
```

## Architecture Patterns

### Recommended Project Structure
```
spectrace/
├── requirements/
│   ├── views.py              # Add flow editor views (follow existing pattern)
│   ├── urls.py               # Add editor URLs (follow existing pattern)
│   └── forms.py              # Add FlowEditorForm
├── templates/
│   └── admin/requirements/
│       ├── flow_editor_list.html    # Flow file list
│       └── flow_editor_form.html    # Edit form with step management
```

### Pattern 1: Custom Admin View with URL Registration

The project already uses this pattern extensively. Custom views are registered in `requirements/urls.py` as `admin_urlpatterns`:

```python
# Source: /Users/tslater/dev/spec-trace/spectrace/requirements/urls.py
# Existing pattern - follow this exactly
admin_urlpatterns = [
    path("admin/flow-editor/", flow_editor_list_view, name="admin-flow-editor"),
    path("admin/flow-editor/<path:file_path>/", flow_editor_view, name="admin-flow-editor-edit"),
]
```

### Pattern 2: View Function with Template

```python
# Source: Existing views.py pattern
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def flow_editor_list_view(request):
    """List all YAML flow files for editing."""
    # Scan flows/ directory for YAML files
    context = {
        'title': 'Flow Editor',
        'flows': get_flow_files(),  # Returns list of file info
    }
    return render(request, 'admin/requirements/flow_editor_list.html', context)
```

### Pattern 3: Template Extending Unfold

```html
<!-- Source: Existing templates pattern -->
{% extends "unfold/layouts/base.html" %}
{% load i18n %}

{% block title %}{{ title }} | SpecTrace{% endblock %}

{% block content %}
{% include "admin/requirements/_design_system.html" %}

<div class="st-page-wrapper">
<div class="st-page st-container">
    <!-- Content using st-* design system classes -->
</div>
</div>
{% endblock %}
```

### Pattern 4: Alpine.js Dynamic List Management

```html
<!-- Pattern for step add/remove/reorder -->
<div x-data="stepEditor()">
    <template x-for="(step, index) in steps" :key="step.id">
        <div class="st-card">
            <input x-model="step.name" />
            <button @click="removeStep(index)">Remove</button>
            <button @click="moveUp(index)" :disabled="index === 0">Up</button>
            <button @click="moveDown(index)" :disabled="index === steps.length - 1">Down</button>
        </div>
    </template>
    <button @click="addStep()">Add Step</button>
</div>

<script>
function stepEditor() {
    return {
        steps: [],
        addStep() {
            this.steps.push({
                id: Date.now(),
                name: '',
                type: 'handler',
                display_name: '',
                handler: '',
                config: {}
            });
        },
        removeStep(index) {
            this.steps.splice(index, 1);
        },
        moveUp(index) {
            if (index > 0) {
                [this.steps[index], this.steps[index-1]] = [this.steps[index-1], this.steps[index]];
            }
        },
        moveDown(index) {
            if (index < this.steps.length - 1) {
                [this.steps[index], this.steps[index+1]] = [this.steps[index+1], this.steps[index]];
            }
        }
    };
}
</script>
```

### Anti-Patterns to Avoid

- **ModelAdmin for non-model data:** Flow YAML files are not database models. Use standalone views, not ModelAdmin.
- **Inline YAML textarea:** Don't just provide a raw YAML textarea. Build a structured form for better UX.
- **Losing comments:** Don't use PyYAML's safe_dump for output. Use ruamel.yaml to preserve formatting.
- **Client-side only validation:** Always validate server-side using existing `YAMLFlowParser`.

## Don't Hand-Roll

Problems with existing solutions in the codebase or standard libraries.

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing/validation | Custom parser | Existing `YAMLFlowParser` | Already validates all flow schema requirements |
| Round-trip YAML | PyYAML dump | `ruamel.yaml` | Preserves comments, formatting, key order |
| Design system | Custom CSS | Existing `_design_system.html` | Consistent look, dark mode support |
| Admin auth | Custom auth | `@staff_member_required` | Standard Django admin decorator |
| Step type validation | Custom validation | `YAMLFlowParser.VALID_STEP_TYPES` | Already defines: handler, api_call, assertion, wait |

**Key insight:** The existing `YAMLFlowParser` already handles all validation. Reuse it for the save action.

## Common Pitfalls

### Pitfall 1: Losing YAML Comments on Save

**What goes wrong:** PyYAML's `safe_dump` discards all comments.
**Why it happens:** PyYAML doesn't preserve round-trip information.
**How to avoid:** Use `ruamel.yaml` with typ='rt' (round-trip mode).
**Warning signs:** Comments disappear after editing a flow.

```python
# Correct approach
from ruamel.yaml import YAML
yaml = YAML()
yaml.preserve_quotes = True

with open(file_path) as f:
    doc = yaml.load(f)
# Modify doc...
with open(file_path, 'w') as f:
    yaml.dump(doc, f)
```

### Pitfall 2: Path Traversal Vulnerability

**What goes wrong:** User-provided file paths allow reading/writing outside flows directory.
**Why it happens:** Insufficient path validation.
**How to avoid:** Validate file path is within flows directory using `Path.resolve()`.
**Warning signs:** File paths containing `..` or absolute paths.

```python
# Correct approach
FLOWS_DIR = Path(settings.BASE_DIR).parent / "flows"

def validate_flow_path(file_path: str) -> Path:
    """Validate file path is within flows directory."""
    resolved = (FLOWS_DIR / file_path).resolve()
    if not resolved.is_relative_to(FLOWS_DIR):
        raise PermissionError("Access denied")
    if not resolved.suffix in ('.yaml', '.yml'):
        raise ValueError("Not a YAML file")
    return resolved
```

### Pitfall 3: Forgetting Hidden Form Fields for Step Order

**What goes wrong:** Step order not persisted on form submit.
**Why it happens:** Alpine.js state not synchronized with form data.
**How to avoid:** Use hidden input fields or serialize to JSON before submit.
**Warning signs:** Steps revert to original order after save.

```html
<!-- Serialize steps to hidden field before submit -->
<form @submit="$refs.stepsData.value = JSON.stringify(steps)">
    <input type="hidden" name="steps_json" x-ref="stepsData" />
</form>
```

### Pitfall 4: Breaking Existing Flow Runs

**What goes wrong:** Editing flow breaks historical run references.
**Why it happens:** Changing flow name or deleting steps that runs reference.
**How to avoid:** Warn when editing flows with existing runs; version flows.
**Warning signs:** Flow run detail pages show missing step data.

## Code Examples

Verified patterns from existing codebase.

### Reading Flow Files

```python
# Source: /Users/tslater/dev/spec-trace/spectrace/requirements/flows/parser.py
from pathlib import Path
from requirements.flows.parser import YAMLFlowParser, FlowParseError

def get_flow_files() -> list[dict]:
    """List all flow YAML files with their parsed state."""
    parser = YAMLFlowParser()
    flows_dir = Path(settings.BASE_DIR).parent / "flows"

    files = []
    for pattern in parser.FILE_PATTERNS:
        for yaml_file in sorted(flows_dir.glob(pattern)):
            try:
                flow = parser.parse_file(yaml_file)
                files.append({
                    'path': yaml_file.relative_to(flows_dir),
                    'name': flow.name if flow else None,
                    'title': flow.display_name if flow else None,
                    'valid': flow is not None,
                    'error': None,
                })
            except FlowParseError as e:
                files.append({
                    'path': yaml_file.relative_to(flows_dir),
                    'valid': False,
                    'error': str(e.message),
                })
    return files
```

### Editing Flow with ruamel.yaml

```python
from ruamel.yaml import YAML

def load_flow_for_editing(file_path: Path) -> dict:
    """Load flow YAML preserving formatting."""
    yaml = YAML()
    with open(file_path) as f:
        return yaml.load(f)

def save_flow(file_path: Path, data: dict) -> None:
    """Save flow YAML preserving comments and formatting."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(file_path, 'w') as f:
        yaml.dump(data, f)
```

### Form Validation Using Existing Parser

```python
from requirements.flows.parser import YAMLFlowParser, FlowParseError
from requirements.flows.definitions import FlowDef

def validate_flow_data(data: dict, file_path: Path) -> FlowDef | None:
    """Validate flow data using existing parser logic."""
    parser = YAMLFlowParser()
    try:
        return parser._validate_and_build_flow(data, file_path)
    except FlowParseError as e:
        raise ValidationError(e.message)
```

### Design System Classes (Existing)

```html
<!-- Source: /Users/tslater/dev/spec-trace/spectrace/templates/admin/requirements/_design_system.html -->

<!-- Cards -->
<div class="st-card">
    <div class="st-card-header">
        <h2 class="st-heading-3">Title</h2>
    </div>
    <div class="st-card-body">Content</div>
</div>

<!-- Buttons -->
<button class="st-btn st-btn--primary">Primary</button>
<button class="st-btn st-btn--secondary">Secondary</button>

<!-- Form inputs -->
<input type="text" class="st-input" />
<label class="st-input-label">Label</label>

<!-- Badges -->
<span class="st-badge st-badge--pass">Valid</span>
<span class="st-badge st-badge--fail">Invalid</span>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PyYAML for editing | ruamel.yaml for round-trip | Long-standing | Comments preserved |
| jQuery formsets | Alpine.js reactive data | 2020+ | Simpler, lighter |
| ModelAdmin for files | Custom views | Django pattern | Cleaner separation |

**Deprecated/outdated:**
- jQuery: Project uses Alpine.js already
- django-dynamic-formset: jQuery-based, not needed with Alpine

## Open Questions

1. **File creation workflow**
   - What we know: Editing existing files is straightforward
   - What's unclear: Should we allow creating new flows? What's the default template?
   - Recommendation: Start with edit-only, add create later if needed

2. **Syncing to database**
   - What we know: `sync_yaml_flows_to_db()` exists in `flows/sync.py`
   - What's unclear: Should save auto-trigger database sync?
   - Recommendation: Add "Sync to DB" button, don't auto-sync on every save

3. **Config field editing**
   - What we know: Step config is a freeform dict
   - What's unclear: How much structure to impose? JSON editor? Key-value pairs?
   - Recommendation: Start with simple textarea for JSON, iterate based on usage

## Sources

### Primary (HIGH confidence)
- Existing codebase: `requirements/flows/parser.py` - Complete parser with validation
- Existing codebase: `requirements/views.py` - Custom admin view patterns
- Existing codebase: `templates/admin/requirements/` - Template patterns
- [Unfold Custom Pages](https://unfoldadmin.com/docs/configuration/custom-pages/) - Official Unfold docs

### Secondary (MEDIUM confidence)
- [ruamel.yaml PyPI](https://pypi.org/project/ruamel.yaml/) - Round-trip YAML library
- [Alpine.js Sort Plugin](https://alpinejs.dev/plugins/sort) - Drag-and-drop sorting
- [SortableJS](https://github.com/SortableJS/Sortable) - Underlying sortable library

### Tertiary (LOW confidence)
- General patterns from web search for formset handling

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Already using these libraries
- Architecture: HIGH - Following existing codebase patterns exactly
- Pitfalls: HIGH - Based on known Django/YAML patterns

**Research date:** 2026-02-02
**Valid until:** 90 days (stable patterns, mature libraries)

# Phase 28: Onboarding Guide - Research

**Researched:** 2026-02-03
**Domain:** Technical onboarding documentation
**Confidence:** HIGH

## Summary

An effective onboarding guide bridges the gap between "I just installed this" and "I understand how to use this." For SpecTrace, new teams need to understand three core concepts: writing specs as markdown files, linking tests with pytest markers, and viewing verification status in the dashboard.

The project already has strong documentation foundations: a comprehensive about.html page, a spectrace_overview.html presentation, and sample specs/tests demonstrating the workflow. The onboarding guide should consolidate these into a single, progressive learning path accessible from the landing page.

Research into 2026 developer onboarding patterns reveals the "overview-detail" structure works best: start with broad concepts, drill down to specifics. Include copy-paste code examples, annotated screenshots showing expected results, and clear next steps.

**Primary recommendation:** Create a dedicated getting_started.html template following the progressive disclosure pattern: What → Why → How → See It Working → Next Steps.

## Standard Stack

The established libraries/tools for technical documentation in Django projects:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django Templates | 5.x | HTML rendering with template inheritance | Native Django integration, already in use |
| Markdown | N/A (content format) | Spec file format | Human-readable, version-controllable, already used for specs |
| Alpine.js | 3.x | Lightweight interactivity (optional) | Already used in spectrace_overview.html, 15KB footprint |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Syntax highlighting (highlight.js/prism) | Latest | Code example display | If including many code blocks with syntax coloring |
| Driver.js | 1.3.1 | Interactive tour overlays | Already in use on landing page for tours |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Static template | React/Vue component | Overkill for documentation page, adds build complexity |
| Custom syntax highlighter | Use browser native `<pre>` | Simpler but less visually appealing |
| Separate docs site | Inline Django template | Keep all docs in one place, easier maintenance |

**Installation:**
No additional packages required. Project already has Django templates and Alpine.js loaded in spectrace_overview.html.

## Architecture Patterns

### Recommended Project Structure
```
spectrace/templates/admin/requirements/
├── getting_started.html       # New: Onboarding guide
├── landing.html               # Existing: Entry point with link to guide
├── about.html                 # Existing: Deep dive on SpecTrace
├── spectrace_overview.html    # Existing: Slide presentation
└── _design_system.html        # Existing: Shared CSS variables
```

### Pattern 1: Progressive Disclosure Structure
**What:** Organize content in layers, revealing complexity gradually
**When to use:** When onboarding users to multi-step workflows
**Example:**
```django
<section class="guide-step" id="step-1">
    <h2>1. Write Your First Spec</h2>
    <p>Specs are markdown files with YAML frontmatter...</p>

    <!-- Code example -->
    <div class="code-example">
        <div class="code-example__label">specs/auth.md</div>
        <pre class="code-example__content">---
id: REQ-AUTH-001
title: User Login
verification_method: test
---

Users must authenticate with email and password.</pre>
    </div>

    <!-- Expected result -->
    <div class="result-preview">
        <div class="result-preview__label">What you'll see</div>
        <img src="{% static 'screenshots/parsed-spec.png' %}" alt="Parsed spec in dashboard">
    </div>
</section>
```

### Pattern 2: Code Example with Copy Button
**What:** Code blocks with one-click copy functionality
**When to use:** For all commands users need to run
**Example:**
```html
<div class="code-block" x-data="{ copied: false }">
    <button class="copy-btn" @click="navigator.clipboard.writeText($refs.code.textContent); copied = true; setTimeout(() => copied = false, 2000)">
        <span x-show="!copied">Copy</span>
        <span x-show="copied">Copied!</span>
    </button>
    <pre x-ref="code">python manage.py parse_specs specs/</pre>
</div>
```

### Pattern 3: Annotated Screenshots
**What:** Images with callouts pointing to UI elements
**When to use:** When showing expected dashboard results after setup
**Example:**
```html
<div class="screenshot-annotated">
    <img src="{% static 'screenshots/dashboard-after-setup.png' %}" alt="Dashboard">
    <div class="callout" style="top: 20%; left: 30%;">
        <div class="callout__number">1</div>
        <div class="callout__text">Your imported requirement appears here</div>
    </div>
    <div class="callout" style="top: 40%; left: 60%;">
        <div class="callout__number">2</div>
        <div class="callout__text">Green badge shows passing tests</div>
    </div>
</div>
```

### Anti-Patterns to Avoid
- **Wall of text before examples:** Show code early, explain after
- **Assuming prior knowledge:** Don't assume users know pytest markers or YAML syntax
- **Missing "what success looks like":** Every step needs "you should see..." guidance
- **Dead-end documentation:** Always provide next steps or related topics

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Code syntax highlighting | Custom regex-based highlighter | highlight.js or browser native | Edge cases: nested strings, escape sequences, multi-line |
| Copy-to-clipboard | Custom clipboard API wrapper | navigator.clipboard with fallback | Browser permissions, HTTPS requirements, fallback for old browsers |
| Progressive disclosure | Custom show/hide logic | Alpine.js x-show or details/summary | Accessibility, keyboard navigation, screen reader support |
| Scroll-to-section navigation | Custom scroll listener | CSS scroll-behavior: smooth + anchor links | Browser-native, respects user preferences (prefers-reduced-motion) |

**Key insight:** Documentation pages benefit from simplicity. Use native browser features and lightweight libraries (Alpine.js) over complex JavaScript frameworks.

## Common Pitfalls

### Pitfall 1: Documentation Drift
**What goes wrong:** Guide shows outdated commands or file paths that no longer exist
**Why it happens:** Documentation isn't tested like code; gets stale as codebase evolves
**How to avoid:**
- Source code examples directly from working sample files (specs/sample/, tests/sample/)
- Add CI check that verifies all file paths in docs exist
- Link to canonical source (README.md, about.html) for commands rather than duplicating
**Warning signs:** User reports "this command doesn't work" or "I don't see that button"

### Pitfall 2: Missing the "Why"
**What goes wrong:** Guide explains commands but users don't understand purpose
**Why it happens:** Author assumes context is obvious; users lack mental model
**How to avoid:**
- Start each section with problem statement: "To see verification status, SpecTrace needs test results..."
- Use "What → Why → How" structure for each step
- Include "What you just did" recap after technical steps
**Warning signs:** Users complete guide but can't explain what SpecTrace does

### Pitfall 3: No Screenshot of Success
**What goes wrong:** Users run commands but don't know if they worked correctly
**Why it happens:** Documentation shows inputs but not outputs
**How to avoid:**
- Every major step must include "you should see..." with screenshot
- Mark expected vs. actual clearly (callouts, annotations)
- Show both success and common failure states
**Warning signs:** Support questions like "Did this work? I see..." or "Is this right?"

### Pitfall 4: Copy-Paste Trap
**What goes wrong:** Code examples work in docs but fail in real usage
**Why it happens:** Examples use placeholder values without explaining what to change
**How to avoid:**
- Use realistic examples (specs/sample/SAMPLE-AUTH-001.md, not "your-spec.md")
- Mark placeholder values clearly: `parse_specs <YOUR_SPECS_DIR>/` with explanation
- Provide both generic template and concrete working example
**Warning signs:** Users paste commands verbatim and get file-not-found errors

### Pitfall 5: Overwhelming First Step
**What goes wrong:** Guide starts with complex setup (database, dependencies, configuration)
**Why it happens:** Author works backward from complete system
**How to avoid:**
- Assume project is already installed (link to README for setup)
- Start with smallest meaningful action: "Create one spec file"
- Build incrementally: spec → parse → link test → run → view
- Provide "quick start" that skips to sample data demo
**Warning signs:** Users give up before completing first section

## Code Examples

Verified patterns from official sources and project samples:

### Creating a Spec File
```markdown
<!-- Source: specs/sample/feature-auth/SAMPLE-AUTH-001.md -->
---
id: REQ-AUTH-001
title: User Authentication
priority: high
verification_method: test
tags: [authentication, security]
---

Users must authenticate with email and password before accessing protected resources.

## Acceptance Criteria
- Email validation checks format
- Password strength requirements enforced
- Session created on successful authentication
```

### Linking Tests with Pytest Markers
```python
# Source: tests/sample/test_sample_requirements.py
import pytest

@pytest.mark.requirement("REQ-AUTH-001")
def test_user_can_login():
    """Test successful login with valid credentials."""
    # Simulates successful login validation
    assert True

@pytest.mark.requirement("REQ-AUTH-001", "REQ-AUTH-002")
def test_login_creates_session():
    """Test can link to multiple requirements."""
    assert True
```

### Running the Complete Workflow
```bash
# Source: README.md workflow example
# 1. Import requirements from specs
python spectrace/manage.py parse_specs specs/

# 2. Run tests with JUnit output
pytest --junitxml=test_results.xml

# 3. Extract test-requirement links
python spectrace/manage.py extract_links --output links.json

# 4. Import results and compute status
python spectrace/manage.py import_results test_results.xml --links links.json

# 5. View dashboard
python spectrace/manage.py runserver
# Open http://localhost:8000/admin/
```

### Adding Link from Landing Page
```django
<!-- Source: spectrace/templates/admin/requirements/landing.html -->
<!-- Add as new feature card in .feature-highlights grid -->
<a href="{% url 'getting-started' %}" class="feature-highlight">
    <div class="feature-highlight__icon">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
            <polyline points="15 3 21 3 21 9"></polyline>
            <line x1="10" y1="14" x2="21" y2="3"></line>
        </svg>
    </div>
    <div class="feature-highlight__title">Getting Started</div>
    <div class="feature-highlight__desc">Step-by-step guide to integrate SpecTrace into your workflow</div>
</a>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate docs sites (ReadTheDocs, GitBook) | Embedded in-app documentation | 2024-2025 | Docs stay in sync with app version, no context switching |
| Static text tutorials | Interactive code examples with copy buttons | 2025 | Faster time-to-first-success, fewer copy-paste errors |
| Text-only walkthroughs | Annotated screenshots + video embeds | 2024+ | Visual learners onboard faster, lower support burden |
| Long-form guides | Progressive disclosure with skip-ahead links | 2025-2026 | Users choose their depth, power users skip basics |

**Deprecated/outdated:**
- PDF installation guides: No search, stale quickly, poor accessibility
- Wiki-style documentation: Becomes maze-like, hard to find getting-started path
- Video-only tutorials: No copy-paste, not indexable, accessibility issues

## Open Questions

Things that couldn't be fully resolved:

1. **Should screenshots be generated or hand-captured?**
   - What we know: Hand-captured screenshots go stale, generated screenshots require infrastructure
   - What's unclear: Whether project has budget/time for screenshot automation (Playwright, Puppeteer)
   - Recommendation: Start with hand-captured, add generation later if maintenance burden is high. Store screenshots in `spectrace/static/screenshots/onboarding/` with descriptive names.

2. **Should guide assume project is already set up?**
   - What we know: README has full installation instructions; landing page assumes server is running
   - What's unclear: Whether onboarding guide is for new developers setting up locally or stakeholders evaluating an existing deployment
   - Recommendation: Assume setup is complete (link to README for setup), focus on "using SpecTrace" not "installing SpecTrace." This matches landing page assumption (server is running at localhost:8000).

3. **How much to duplicate vs. link to existing docs?**
   - What we know: about.html covers concepts deeply, README.md has command reference
   - What's unclear: Balance between self-contained guide and DRY principle
   - Recommendation: Provide minimal working example inline, link to about.html for concepts and README.md for advanced usage. Prioritize "works without clicking away" over "never repeat anything."

## Sources

### Primary (HIGH confidence)
- [Django Templates Best Practices | LearnDjango](https://learndjango.com/tutorials/template-structure) - Template organization patterns
- [The Ultimate Guide to Django Templates | PyCharm Blog](https://blog.jetbrains.com/pycharm/2025/02/the-ultimate-guide-to-django-templates/) - 2025 Django template best practices
- [pytest Official Documentation - Good Integration Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html) - Pytest marker usage patterns
- [Developer Onboarding Guide Template: Day 1 to Week 4 (2026) | River](https://rivereditor.com/blogs/write-developer-onboarding-guide-30-days) - Progressive onboarding structure
- [Document360 - Developer Onboarding Best Practices](https://document360.com/blog/developer-onboarding-best-practices/) - Four-phase onboarding framework

### Secondary (MEDIUM confidence)
- [How to Write a Getting Started Guide | HeroThemes](https://herothemes.com/blog/getting-started-guide/) - Screenshot annotation best practices
- [Step-by-Step Guides: Creating Clear and Effective Instructions | UserGuiding](https://userguiding.com/blog/step-by-step-guides) - Visual instruction patterns
- [TechSmith - How to Create Step-By-Step Instructions](https://www.techsmith.com/blog/create-instructions-using-visuals/) - Using visuals in technical docs

### Project Files (HIGH confidence)
- `/Users/tslater/dev/spec-trace/spectrace/templates/admin/requirements/landing.html` - Existing landing page structure
- `/Users/tslater/dev/spec-trace/spectrace/templates/admin/requirements/about.html` - Comprehensive SpecTrace concepts page
- `/Users/tslater/dev/spec-trace/spectrace/templates/admin/requirements/spectrace_overview.html` - Presentation-style demo with Alpine.js
- `/Users/tslater/dev/spec-trace/README.md` - Workflow examples and command reference
- `/Users/tslater/dev/spec-trace/specs/sample/` - Working spec file examples
- `/Users/tslater/dev/spec-trace/tests/sample/test_sample_requirements.py` - Working pytest marker examples

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Django templates, Alpine.js, and markdown are established project choices
- Architecture: HIGH - Patterns verified from existing project templates (about.html, spectrace_overview.html)
- Pitfalls: HIGH - Based on 2026 documentation research and analysis of existing project structure
- Code examples: HIGH - All examples sourced from working project files or official documentation

**Research date:** 2026-02-03
**Valid until:** 30 days (stable technology stack, slow-moving documentation patterns)

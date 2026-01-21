# Phase 2: Test Integration - Research

**Researched:** 2026-01-20
**Domain:** pytest custom markers, programmatic test collection, Django management commands
**Confidence:** HIGH

## Summary

This phase implements a pytest marker-based system for annotating tests with requirement IDs, plus a Django management command to extract those annotations. The research confirms that pytest's native marker system supports the exact use case: `@pytest.mark.requirement("REQ-01", "REQ-02")` with access to args/kwargs via `item.iter_markers()`.

The extraction approach uses pytest's collection mechanism programmatically via `pytest.main(['--collect-only', ...], plugins=[CustomPlugin])`. This respects all pytest configuration (pytest.ini, conftest.py) and handles parametrized tests correctly. The plugin's `pytest_collection_modifyitems` hook receives all test items with full marker and location metadata.

**Primary recommendation:** Use native pytest markers with programmatic collection via a custom plugin. Output JSON to stdout (with optional file path) for composability with import step.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=9.0 (already installed) | Test framework with marker system | Native marker support, iter_markers API |
| pytest-django | >=4.11 (already installed) | Django integration | Already configured in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json (stdlib) | built-in | JSON output | Always - stdlib sufficient |
| pathlib (stdlib) | built-in | Path handling | Always - modern Python pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest markers | Custom decorator | Markers integrate with pytest ecosystem, selection, reporting |
| pytest.main() | subprocess | pytest.main() gives direct access to collected items |
| JSON output | Direct DB write | JSON enables dry-run, validation, composability |

**Installation:**
No additional packages needed - pytest and pytest-django already in dev dependencies.

## Architecture Patterns

### Recommended Project Structure
```
spectrace/
├── requirements/
│   ├── management/
│   │   └── commands/
│   │       └── extract_links.py    # Django management command
│   └── linker.py                    # Core extraction logic (optional)
├── conftest.py                       # Register 'requirement' marker
└── pytest_plugins/
    └── __init__.py                   # Collection plugin (if needed)
```

### Pattern 1: Marker Registration
**What:** Register custom marker to avoid warnings and enable validation
**When to use:** Always - prevents PytestUnknownMarkWarning

In `conftest.py` (project root):
```python
# Source: https://docs.pytest.org/en/stable/how-to/mark.html
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requirement(*req_ids, reason=None): link test to requirement IDs"
    )
```

Or in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "requirement(*req_ids, reason=None): link test to requirement IDs"
]
```

### Pattern 2: Programmatic Collection Plugin
**What:** Custom plugin to collect tests without running them
**When to use:** In the management command to extract links

```python
# Source: https://github.com/pytest-dev/pytest/discussions/2039
import pytest

class RequirementCollector:
    """Plugin to collect test-requirement links during pytest collection."""

    def __init__(self):
        self.links = []

    def pytest_collection_modifyitems(self, items):
        """Hook called after collection, receives all test items."""
        for item in items:
            # Get all requirement markers on this test
            for marker in item.iter_markers(name="requirement"):
                # marker.args = ("REQ-01", "REQ-02", ...)
                # marker.kwargs = {"reason": "tests login flow"}
                for req_id in marker.args:
                    self.links.append({
                        "test_id": item.nodeid,
                        "requirement_id": req_id,
                        "reason": marker.kwargs.get("reason"),
                        "file": str(item.path) if item.path else None,
                        "function": item.name,
                        "class": item.cls.__name__ if item.cls else None,
                    })
```

### Pattern 3: Invoking pytest Collection
**What:** Call pytest programmatically with collection-only mode
**When to use:** In management command

```python
# Source: https://docs.pytest.org/en/stable/how-to/usage.html
import pytest

def extract_requirement_links(test_path: str = None) -> list[dict]:
    """Extract requirement links from tests using pytest collection."""
    collector = RequirementCollector()

    args = [
        "--collect-only",      # Don't run tests
        "-p", "no:terminal",   # Suppress output
        "-q",                  # Quiet mode
    ]
    if test_path:
        args.append(test_path)

    # Run collection with our plugin
    pytest.main(args, plugins=[collector])

    return collector.links
```

### Pattern 4: Accessing Test Item Metadata
**What:** Extract comprehensive test metadata from pytest items
**When to use:** When building the JSON output

```python
# Source: https://docs.pytest.org/en/stable/_modules/_pytest/python.html
def get_test_metadata(item) -> dict:
    """Extract metadata from a pytest test item."""
    return {
        "nodeid": item.nodeid,           # Full path: module.py::Class::test[param]
        "name": item.name,                # Function name with params
        "file": str(item.path),           # Absolute file path
        "function": item.function.__name__, # Raw function name
        "class": item.cls.__name__ if item.cls else None,
        "module": item.module.__name__ if item.module else None,
        "location": item.location,        # (relpath, lineno, testname)
    }
```

### Anti-Patterns to Avoid
- **AST parsing for markers:** Don't parse Python files directly. Use pytest's collection which handles imports, parametrization, dynamic test generation correctly.
- **Running tests to extract links:** Use `--collect-only` to avoid test execution overhead and side effects.
- **Failing on unknown requirements:** Warn but don't fail - allows incremental adoption and doesn't block test runs.
- **Multiple pytest.main() calls in same process:** Can cause stale module issues. For our use case (single invocation per command), this is fine.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test discovery | Custom file scanning | pytest collection | Respects pytest.ini, conftest, parametrization |
| Marker parsing | AST analysis | iter_markers API | Handles inheritance, multiple markers, kwargs |
| Test identification | Path manipulation | item.nodeid | Handles parametrized tests, classes correctly |
| Output suppression | stderr redirect | `-p no:terminal` | Clean, official approach |

**Key insight:** pytest's collection mechanism handles edge cases (parametrized tests, class inheritance, conftest fixtures, dynamic generation) that custom parsing would miss or handle incorrectly.

## Common Pitfalls

### Pitfall 1: Warning on Unregistered Markers
**What goes wrong:** `PytestUnknownMarkWarning: Unknown pytest.mark.requirement`
**Why it happens:** Markers must be registered to avoid typo warnings
**How to avoid:** Register in conftest.py via `pytest_configure` hook or in pyproject.toml
**Warning signs:** Warning output when running pytest

### Pitfall 2: Missing Parametrized Test Variants
**What goes wrong:** Only base test captured, not `test_foo[param1]`, `test_foo[param2]`
**Why it happens:** Using AST parsing instead of pytest collection
**How to avoid:** Use pytest's collection mechanism which expands parametrization
**Warning signs:** Fewer links than expected for parametrized tests

### Pitfall 3: Database Access During Collection
**What goes wrong:** `RuntimeError: Database access not allowed`
**Why it happens:** pytest-django blocks DB by default, some fixtures may try to access
**How to avoid:** Collection-only mode shouldn't trigger DB fixtures, but if issues arise, use `--no-header --no-summary` flags
**Warning signs:** Errors mentioning database during `--collect-only`

### Pitfall 4: Relative vs Absolute Paths
**What goes wrong:** Inconsistent file paths in output
**Why it happens:** pytest can return paths relative to rootdir or absolute
**How to avoid:** Normalize paths using `item.path` (pathlib.Path) and decide on format (recommend: relative to project root)
**Warning signs:** Mix of absolute and relative paths in JSON output

### Pitfall 5: Stale Collection Results
**What goes wrong:** Changes to test files not reflected in collection
**Why it happens:** Python module caching when calling pytest.main() multiple times
**How to avoid:** For our use case (single invocation per command), not an issue. If hot-reload needed, use subprocess instead.
**Warning signs:** Same results after modifying test files (in interactive development)

## Code Examples

Verified patterns from official sources:

### Marker Usage in Tests
```python
# Source: https://docs.pytest.org/en/stable/how-to/mark.html
import pytest

@pytest.mark.requirement("REQ-AUTH-01")
def test_login_success():
    """Test successful login."""
    pass

@pytest.mark.requirement("REQ-AUTH-01", "REQ-AUTH-02", reason="tests full auth flow")
def test_login_with_mfa():
    """Test login with multi-factor authentication."""
    pass

class TestAuthentication:
    @pytest.mark.requirement("REQ-AUTH-03")
    def test_logout(self):
        """Test logout functionality."""
        pass

@pytest.mark.requirement("REQ-DATA-01")
@pytest.mark.parametrize("input,expected", [("a", 1), ("b", 2)])
def test_data_processing(input, expected):
    """Parametrized test - creates two test items, each linked to REQ-DATA-01."""
    pass
```

### Complete Management Command Structure
```python
# Source: Django management command pattern + pytest programmatic API
import json
import sys
from pathlib import Path

import pytest
from django.core.management.base import BaseCommand


class RequirementCollector:
    def __init__(self):
        self.links = []

    def pytest_collection_modifyitems(self, items):
        for item in items:
            for marker in item.iter_markers(name="requirement"):
                for req_id in marker.args:
                    self.links.append({
                        "test_nodeid": item.nodeid,
                        "requirement_id": req_id,
                        "reason": marker.kwargs.get("reason"),
                        "test_file": str(item.path.relative_to(Path.cwd())),
                        "test_function": item.name,
                        "test_class": item.cls.__name__ if item.cls else None,
                        "line_number": item.location[1] if item.location else None,
                    })


class Command(BaseCommand):
    help = "Extract requirement links from test files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", "-o",
            type=str,
            help="Output file path (default: stdout)"
        )
        parser.add_argument(
            "--path",
            type=str,
            help="Test path to scan (default: all tests)"
        )
        parser.add_argument(
            "-v", "--verbose",
            action="store_true",
            help="Show each test->requirement mapping"
        )

    def handle(self, *args, **options):
        collector = RequirementCollector()

        pytest_args = ["--collect-only", "-p", "no:terminal", "-q"]
        if options["path"]:
            pytest_args.append(options["path"])

        pytest.main(pytest_args, plugins=[collector])

        # Output
        output = {
            "version": "1.0",
            "links": collector.links,
            "summary": {
                "total_links": len(collector.links),
                "unique_tests": len(set(l["test_nodeid"] for l in collector.links)),
                "unique_requirements": len(set(l["requirement_id"] for l in collector.links)),
            }
        }

        if options["verbose"]:
            for link in collector.links:
                self.stdout.write(
                    f"  {link['test_nodeid']} -> {link['requirement_id']}"
                )

        json_output = json.dumps(output, indent=2)

        if options["output"]:
            Path(options["output"]).write_text(json_output)
            self.stdout.write(self.style.SUCCESS(
                f"Wrote {len(collector.links)} links to {options['output']}"
            ))
        else:
            self.stdout.write(json_output)
```

### JSON Output Schema
```json
{
  "version": "1.0",
  "links": [
    {
      "test_nodeid": "tests/test_auth.py::TestAuth::test_login[admin]",
      "requirement_id": "REQ-AUTH-01",
      "reason": "tests admin login flow",
      "test_file": "tests/test_auth.py",
      "test_function": "test_login[admin]",
      "test_class": "TestAuth",
      "line_number": 42
    }
  ],
  "summary": {
    "total_links": 15,
    "unique_tests": 10,
    "unique_requirements": 8
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `item.fspath` (py.path) | `item.path` (pathlib.Path) | pytest 7.0+ | Use pathlib throughout |
| `item.get_marker()` | `item.iter_markers()` | pytest 4.0+ | Deprecated old API |
| Manual marker registration | `pytest_configure` hook | Long established | Official pattern |

**Deprecated/outdated:**
- `item.fspath`: Use `item.path` instead (pathlib.Path)
- `item.get_marker()`: Use `item.iter_markers()` or `item.get_closest_marker()`
- `py.path.local`: Use `pathlib.Path`

## Open Questions

Things that couldn't be fully resolved:

1. **Requirement ID validation timing**
   - What we know: Decision is to warn on unknown IDs, not fail
   - What's unclear: Should validation happen during collection (via hook) or post-collection?
   - Recommendation: Post-collection validation in command - query DB for valid IDs, warn for mismatches

2. **Handling marker on class vs method**
   - What we know: Markers can be applied to classes, inherited by methods
   - What's unclear: Should class-level markers propagate to all methods in output?
   - Recommendation: Yes, use `iter_markers()` which handles inheritance automatically

3. **Multiple markers same requirement**
   - What we know: `@pytest.mark.requirement("REQ-01")` can appear multiple times
   - What's unclear: Should output deduplicate?
   - Recommendation: No - keep all for audit trail, let import step handle deduplication

## Sources

### Primary (HIGH confidence)
- [pytest markers documentation](https://docs.pytest.org/en/stable/how-to/mark.html) - marker registration, iter_markers API
- [pytest working with custom markers](https://docs.pytest.org/en/stable/example/markers.html) - args/kwargs access patterns
- [pytest nodes module](https://docs.pytest.org/en/stable/_modules/_pytest/nodes.html) - Item class, nodeid, path attributes
- [pytest GitHub discussion #2039](https://github.com/pytest-dev/pytest/discussions/2039) - programmatic --collect-only pattern

### Secondary (MEDIUM confidence)
- [pytest-django database docs](https://pytest-django.readthedocs.io/en/latest/database.html) - DB access during collection
- [pytest usage guide](https://docs.pytest.org/en/stable/how-to/usage.html) - pytest.main() API, exit codes

### Tertiary (LOW confidence)
- [traceability-matrices repo](https://github.com/burdiuz/traceability-matrices) - JSON schema inspiration (different ecosystem)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - using existing pytest/pytest-django, no new deps
- Architecture: HIGH - patterns verified from official docs and discussions
- Pitfalls: HIGH - documented issues from pytest GitHub

**Research date:** 2026-01-20
**Valid until:** 2026-04-20 (3 months - pytest stable, patterns well-established)

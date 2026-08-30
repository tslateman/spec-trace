# Claude Code Memory

## Architecture Patterns

### Circular Dependency Resolution

When modules have circular imports, extract shared types to a separate module:

```
Before:                          After:
health.py <──── engine.py        health_types.py
    │               │                   │
    └───(inline)────┘            ┌──────┴──────┐
                                 ↓             ↓
                            health.py     engine.py
```

**Key principle**: Both modules import types from a new `*_types.py` module, allowing all imports to be at module level with no inline workarounds.

Example from this codebase:
- `health_types.py` contains `VerificationCheck`, `TestConnectionResult`, `_get_timestamp`
- `health.py` imports from `health_types` and re-exports for backward compatibility
- `flows/engine.py` imports `VerificationCheck` from `health_types` instead of `health`

---

## Testing Patterns

### Naming Convention
```
test_{method}__{expected_behavior}
      ↑              ↑
  function      double underscore
```

Examples:
- `test_create_reservation__succeeds_with_valid_data`
- `test_create_reservation__raises_validation_error_when_dates_invalid`

### Mocking
- Mock at service boundaries, not internal logic
- **Always use `autospec=True`** with `@patch`
- Use `responses` library for HTTP mocking
- Extract complex mocks into reusable fixtures

```python
@patch("myapp.services.external_api.requests.post", autospec=True)
def test_send_notification__calls_api(mock_post):
    ...
```

### Determinism
- Use `@freeze_time("2025-01-15 12:00:00")` for time-dependent tests
- Use `faker` for realistic test data (seeded by pytest-randomly)
- Never use `random` or `datetime.now()` directly
- Never use `time.sleep()` in tests

### Anti-Patterns
- ❌ `unittest.TestCase` — use pytest functional style
- ❌ `@patch` without `autospec=True`
- ❌ Mocking Django ORM internals
- ❌ Inline imports within test functions
- ❌ Real network calls without mocking

---

## Feature Flag Pattern

### Gradual Rollout
```
Draft → Released → Production
  ↓         ↓           ↓
dev/test  versioned   all users
  only      rollout
```

### Testing Requirement
**Always test both enabled AND disabled states** — verify fallback behavior works correctly.

---

## Writing Style

### Core Principles (Strunk's Elements of Style)
- **Active voice.** "Agents claim tasks" not "Tasks are claimed by agents"
- **Positive form.** "He forgot" not "He did not remember"
- **Concrete language.** Name specific endpoints, models, states — not "various components"
- **Omit needless words.** Cut "In order to", "the fact that", "In this document we will explore"
- **Emphatic words at end.** "This addresses the stretch goal" not "The stretch goal is addressed by this"

### Document Structure (Briefs Style)
- Keep it short. Readable in under 5 minutes.
- State the problem first. No history front-loading.
- Include measurable target or objective.
- Open questions are fine. Uncertainty is honest.
- Brain dumps acceptable. Unstructured thoughts beat polished fluff.

### Anti-Patterns
- ❌ "In this document we will explore..." — just say the thing
- ❌ "It is important to note that..." — if it's important, it speaks for itself
- ❌ Generic descriptions — name the actual API endpoint, the actual model
- ❌ Hedging everything — "This could potentially help" → "This helps"
- ❌ AI slop — vague, safe, says everything and nothing

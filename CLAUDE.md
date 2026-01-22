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

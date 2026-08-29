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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **spec-trace** (5546 symbols, 9166 relationships, 243 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/spec-trace/context` | Codebase overview, check index freshness |
| `gitnexus://repo/spec-trace/clusters` | All functional areas |
| `gitnexus://repo/spec-trace/processes` | All execution flows |
| `gitnexus://repo/spec-trace/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

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

This project is indexed by GitNexus as **spec-trace** (3088 symbols, 7046 relationships, 175 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/spec-trace/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/spec-trace/context` | Codebase overview, check index freshness |
| `gitnexus://repo/spec-trace/clusters` | All functional areas |
| `gitnexus://repo/spec-trace/processes` | All execution flows |
| `gitnexus://repo/spec-trace/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

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

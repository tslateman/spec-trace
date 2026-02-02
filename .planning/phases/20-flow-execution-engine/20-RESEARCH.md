# Phase 20: Flow Execution Engine - Research

**Researched:** 2026-02-02
**Domain:** Flow execution, step executors, timeout handling
**Confidence:** HIGH

## Summary

The codebase already has a solid foundation for flow execution. The `SequentialFlowEngine` in `flows/engine.py` executes flows with `type=handler` steps and records results to `VerificationFlowRun` and `VerificationFlowStep` models. Phase 20 extends this engine to support additional step types (`api_call`, `assertion`, `wait`) and adds timeout handling.

The existing architecture follows a clean pattern: the engine iterates through steps, loads/executes handlers, and records results. The `FlowStepDef` dataclass already has `type` and `config` fields for non-handler steps. The challenge is implementing step executors that work within this framework.

**Primary recommendation:** Extend `SequentialFlowEngine.execute()` with a step type dispatcher that delegates to type-specific executor functions, keeping the existing handler pattern for backward compatibility.

## Standard Stack

### Core (Already in Codebase)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 5.x | ORM, management commands | Already used throughout |
| requests | 2.x | HTTP client for api_call steps | Already used in `linear.py` |
| PyYAML | 6.x | YAML parsing | Already used for flow definitions |

### Supporting (New for Phase 20)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `signal` (stdlib) | builtin | Per-step timeout on POSIX | Simple per-step timeout |
| `threading.Timer` (stdlib) | builtin | Cross-platform timeout fallback | Windows compatibility |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| signal-based timeout | `timeout-decorator` package | External dependency; signal works for synchronous code |
| per-step timeout | asyncio.timeout | Would require async refactor; synchronous is simpler |

**No new dependencies needed** - use stdlib signal/threading for timeouts, existing requests for HTTP.

## Architecture Patterns

### Recommended Project Structure
```
spectrace/requirements/
├── flows/
│   ├── engine.py           # Extend SequentialFlowEngine
│   ├── executors/          # NEW: Step type executors
│   │   ├── __init__.py
│   │   ├── api_call.py     # HTTP request executor
│   │   ├── assertion.py    # Value assertion executor
│   │   └── wait.py         # Delay executor
│   └── handlers/
│       └── linear.py       # Existing handlers (unchanged)
├── management/commands/
│   └── run_flow.py         # NEW: CLI command
└── services/
    └── flow_runner.py      # NEW: High-level runner service (optional)
```

### Pattern 1: Step Type Dispatcher

**What:** Route step execution based on `step_def['type']` field
**When to use:** In the engine's execution loop
**Example:**
```python
# In SequentialFlowEngine.execute()
STEP_EXECUTORS = {
    'handler': execute_handler_step,
    'api_call': execute_api_call_step,
    'assertion': execute_assertion_step,
    'wait': execute_wait_step,
}

def execute_step(self, step_def: dict, context: dict) -> tuple[VerificationCheck, dict]:
    """Execute a step based on its type."""
    step_type = step_def.get('type', 'handler')
    executor = STEP_EXECUTORS.get(step_type)
    if not executor:
        return VerificationCheck(
            name=step_def.get('name', 'unknown'),
            passed=False,
            error_message=f"Unknown step type: {step_type}"
        ), {}
    return executor(step_def, context)
```

### Pattern 2: Executor Function Signature

**What:** Consistent signature for all step executors
**When to use:** When implementing new step types
**Example:**
```python
def execute_api_call_step(
    step_def: dict,
    context: dict
) -> tuple[VerificationCheck, dict]:
    """Execute an HTTP request step.

    Args:
        step_def: Step definition with 'config' containing url, method, etc.
        context: Execution context (may contain base_url, headers, etc.)

    Returns:
        (VerificationCheck result, context updates dict)
    """
    config = step_def.get('config', {})
    url = config.get('url')
    method = config.get('method', 'GET').upper()
    expected_status = config.get('expected_status', 200)

    try:
        response = requests.request(method, url, timeout=config.get('timeout', 30))
        passed = response.status_code == expected_status
        return VerificationCheck(
            name=step_def.get('name', 'api_call'),
            passed=passed,
            details=f"Status {response.status_code}" if passed else None,
            error_message=f"Expected {expected_status}, got {response.status_code}" if not passed else None,
            response_status=response.status_code,
            response_body=response.text[:1000],  # Truncate
        ), {'last_response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text}
    except requests.RequestException as e:
        return VerificationCheck(
            name=step_def.get('name', 'api_call'),
            passed=False,
            error_message=str(e),
        ), {}
```

### Pattern 3: Timeout Context Manager

**What:** Wrap step execution with timeout
**When to use:** Per-step and per-flow timeout enforcement
**Example:**
```python
import signal
from contextlib import contextmanager

class StepTimeoutError(Exception):
    """Raised when a step exceeds its timeout."""
    pass

@contextmanager
def step_timeout(seconds: int):
    """Context manager for step timeout (POSIX only)."""
    def handler(signum, frame):
        raise StepTimeoutError(f"Step timed out after {seconds}s")

    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
```

### Pattern 4: Management Command for Flow Execution

**What:** Django management command to run flows
**When to use:** CLI-based flow execution
**Example:**
```python
# management/commands/run_flow.py
from django.core.management.base import BaseCommand, CommandError
from requirements.flows.engine import SequentialFlowEngine
from requirements.models import VerificationFlow, VerificationFlowSource

class Command(BaseCommand):
    help = 'Run a verification flow by ID or name'

    def add_arguments(self, parser):
        parser.add_argument('flow_id', help='Flow ID (numeric) or name')
        parser.add_argument('--context', type=str, help='JSON context string')
        parser.add_argument('--timeout', type=int, default=300, help='Flow timeout in seconds')

    def handle(self, *args, **options):
        flow_id = options['flow_id']

        # Look up by ID or name
        try:
            flow = VerificationFlow.objects.get(pk=int(flow_id))
        except (ValueError, VerificationFlow.DoesNotExist):
            try:
                flow = VerificationFlow.objects.get(name=flow_id)
            except VerificationFlow.DoesNotExist:
                raise CommandError(f"Flow not found: {flow_id}")

        # Parse context
        context = {}
        if options['context']:
            import json
            context = json.loads(options['context'])

        # Execute
        engine = SequentialFlowEngine()
        run = engine.execute(flow, context, source=VerificationFlowSource.MANUAL)

        # Output result
        self.stdout.write(f"Flow: {flow.name}")
        self.stdout.write(f"Status: {run.status}")
        for step in run.steps.order_by('step_order'):
            icon = '[PASS]' if step.passed else '[FAIL]'
            self.stdout.write(f"  {icon} {step.name}")
            if step.error_message:
                self.stdout.write(f"       Error: {step.error_message}")
```

### Anti-Patterns to Avoid
- **Async refactor:** Don't convert to asyncio just for timeouts - adds complexity without benefit for sequential execution
- **Global timeout only:** Must have per-step timeouts, not just per-flow
- **Catching all exceptions in executors:** Let `StepTimeoutError` propagate to engine for proper handling
- **Storing full response bodies:** Truncate to reasonable size (1000 chars) to avoid DB bloat

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP requests | Custom urllib code | `requests` library | Already used; handles encoding, sessions, errors |
| JSON comparison | Manual dict traversal | `jsonpath-ng` or simple key access | For assertion steps, use existing patterns |
| Timeout mechanism | Thread-based custom solution | `signal.alarm()` for POSIX | Built-in, reliable, no threading complexity |
| Step recording | Custom logging | Existing `VerificationFlowStep` model | Already has all needed fields |

**Key insight:** The existing `VerificationCheck` dataclass and `VerificationFlowStep` model already capture everything needed (passed, details, error_message, response_status, response_body). New executors just need to return `VerificationCheck` instances.

## Common Pitfalls

### Pitfall 1: Metadata Confusion in Steps JSON

**What goes wrong:** The `sync_yaml_flows_to_db` function stores metadata as the first element of the `steps` JSON array with a `_metadata` key. The engine needs to skip this when iterating.
**Why it happens:** Phase 19 added metadata storage as a workaround to avoid schema changes.
**How to avoid:** Filter steps in engine: `steps = [s for s in flow.steps if '_metadata' not in s]`
**Warning signs:** First step always fails with "unknown handler" or similar

### Pitfall 2: Signal Timeout Limitations

**What goes wrong:** `signal.alarm()` only works on POSIX systems (Linux, macOS), not Windows. Also only works from main thread.
**Why it happens:** Signal handling is OS-specific and Python's signal module reflects this.
**How to avoid:**
1. For development/testing on Windows, use `threading.Timer` as fallback
2. Check `sys.platform` and adjust behavior
3. Document that full timeout support requires POSIX
**Warning signs:** `ValueError: signal only works in main thread` errors

### Pitfall 3: Context Mutation Across Steps

**What goes wrong:** Steps modify the context dict in place, affecting subsequent steps unexpectedly.
**Why it happens:** Existing pattern is `context.update(ctx_updates)` which modifies in place.
**How to avoid:** This is actually intentional - steps like `check_authentication` add `client` to context for subsequent steps. Just be aware of it.
**Warning signs:** Unexpected values in context; test isolation issues

### Pitfall 4: Response Body Size

**What goes wrong:** Large API responses stored in `response_body` field bloat the database.
**Why it happens:** `api_call` steps may fetch large JSON payloads.
**How to avoid:** Truncate `response_body` to 1000-2000 characters in executor. Store full response in context if needed for assertions.
**Warning signs:** Database growth, slow queries on `VerificationFlowStep`

### Pitfall 5: Timeout vs Request Timeout

**What goes wrong:** Confusing per-step timeout (engine-level) with HTTP request timeout (requests library).
**Why it happens:** Both are called "timeout" but operate at different layers.
**How to avoid:**
- HTTP request timeout: Pass to `requests.request(timeout=X)`
- Step timeout: Engine wraps entire step execution with signal/timer
- Flow timeout: Engine tracks total elapsed time
**Warning signs:** Inconsistent timeout behavior between step types

## Code Examples

### Example 1: api_call Step Executor

```python
# Source: Pattern derived from existing linear.py HTTP patterns
import requests
from requirements.health_types import VerificationCheck

def execute_api_call_step(step_def: dict, context: dict) -> tuple[VerificationCheck, dict]:
    """Execute HTTP request and verify response."""
    config = step_def.get('config', {})
    name = step_def.get('name', 'api_call')

    # Build URL (support context variable substitution)
    url = config.get('url', '')
    base_url = context.get('base_url', '')
    if url.startswith('/') and base_url:
        url = base_url.rstrip('/') + url

    method = config.get('method', 'GET').upper()
    expected_status = config.get('expected_status', 200)
    headers = {**context.get('headers', {}), **config.get('headers', {})}
    body = config.get('body')
    timeout = config.get('timeout', 30)

    try:
        response = requests.request(
            method, url,
            headers=headers,
            json=body if body else None,
            timeout=timeout
        )

        passed = response.status_code == expected_status
        ctx_updates = {}

        # Store response for assertion steps
        if response.headers.get('content-type', '').startswith('application/json'):
            try:
                ctx_updates['last_response'] = response.json()
            except ValueError:
                ctx_updates['last_response'] = response.text
        else:
            ctx_updates['last_response'] = response.text

        return VerificationCheck(
            name=name,
            passed=passed,
            details=f"{method} {url} returned {response.status_code}" if passed else None,
            error_message=f"Expected {expected_status}, got {response.status_code}" if not passed else None,
            response_status=response.status_code,
            response_body=response.text[:1000],
        ), ctx_updates

    except requests.Timeout:
        return VerificationCheck(
            name=name,
            passed=False,
            error_message=f"Request timed out after {timeout}s",
        ), {}
    except requests.RequestException as e:
        return VerificationCheck(
            name=name,
            passed=False,
            error_message=f"Request failed: {e}",
        ), {}
```

### Example 2: assertion Step Executor

```python
# Source: Pattern derived from example-api-check.yaml config structure
def execute_assertion_step(step_def: dict, context: dict) -> tuple[VerificationCheck, dict]:
    """Assert a condition on the last response or context."""
    config = step_def.get('config', {})
    name = step_def.get('name', 'assertion')

    field = config.get('field')
    operator = config.get('operator', 'equals')
    expected = config.get('value')
    source = config.get('source', 'last_response')

    # Get value to check
    data = context.get(source)
    if data is None:
        return VerificationCheck(
            name=name,
            passed=False,
            error_message=f"No '{source}' in context",
        ), {}

    # Extract field (support nested with dot notation)
    actual = data
    for key in field.split('.'):
        if isinstance(actual, dict):
            actual = actual.get(key)
        else:
            actual = None
            break

    # Compare
    if operator == 'equals':
        passed = actual == expected
    elif operator == 'contains':
        passed = expected in str(actual)
    elif operator == 'exists':
        passed = actual is not None
    elif operator == 'not_empty':
        passed = bool(actual)
    else:
        return VerificationCheck(
            name=name,
            passed=False,
            error_message=f"Unknown operator: {operator}",
        ), {}

    return VerificationCheck(
        name=name,
        passed=passed,
        details=f"{field} {operator} {expected}: actual={actual}" if passed else None,
        error_message=f"Assertion failed: {field} {operator} {expected}, got {actual}" if not passed else None,
    ), {}
```

### Example 3: wait Step Executor

```python
# Source: Standard pattern for delay steps
import time

def execute_wait_step(step_def: dict, context: dict) -> tuple[VerificationCheck, dict]:
    """Wait for a specified duration."""
    config = step_def.get('config', {})
    name = step_def.get('name', 'wait')

    seconds = config.get('seconds', 1)

    time.sleep(seconds)

    return VerificationCheck(
        name=name,
        passed=True,
        details=f"Waited {seconds}s",
    ), {}
```

### Example 4: Extended Engine with Timeout

```python
# Source: Extension of existing engine.py
import signal
import sys
from datetime import UTC, datetime

class StepTimeoutError(Exception):
    """Step exceeded its timeout."""
    pass

class FlowTimeoutError(Exception):
    """Flow exceeded its total timeout."""
    pass

class SequentialFlowEngine:
    """Execute verification flows with step and flow timeouts."""

    DEFAULT_STEP_TIMEOUT = 60  # seconds
    DEFAULT_FLOW_TIMEOUT = 300  # seconds

    def execute(
        self,
        flow: VerificationFlow,
        context: dict,
        source: VerificationFlowSource = VerificationFlowSource.API,
        step_timeout: int | None = None,
        flow_timeout: int | None = None,
    ) -> VerificationFlowRun:
        step_timeout = step_timeout or self.DEFAULT_STEP_TIMEOUT
        flow_timeout = flow_timeout or self.DEFAULT_FLOW_TIMEOUT
        flow_start = datetime.now(UTC)

        run = VerificationFlowRun.objects.create(
            flow=flow,
            status=VerificationFlowStatus.RUNNING,
            context=self._sanitize_context_for_storage(context),
            source=source,
        )

        # Filter out metadata from steps
        steps = [s for s in flow.steps if '_metadata' not in s]

        for i, step_def in enumerate(steps):
            # Check flow timeout
            elapsed = (datetime.now(UTC) - flow_start).total_seconds()
            if elapsed > flow_timeout:
                self._record_timeout_step(run, i, step_def, "Flow timeout exceeded")
                run.status = VerificationFlowStatus.FAILED
                run.completed_at = timezone.now()
                run.save()
                return run

            # Execute with step timeout
            step_started = datetime.now(UTC)
            try:
                with self._step_timeout_context(step_timeout):
                    check, ctx_updates = self._execute_step(step_def, context)
            except StepTimeoutError:
                check = VerificationCheck(
                    name=step_def.get('name', f'step_{i}'),
                    passed=False,
                    error_message=f"Step timed out after {step_timeout}s"
                )
                ctx_updates = {}

            # Record and continue/exit as before...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Only handler steps | Multiple step types | Phase 19 | Parser supports api_call, assertion, wait |
| No timeout handling | Per-step + per-flow timeouts | Phase 20 | Prevents hung flows |
| Code-only flows | YAML + code flows | Phase 19 | More flexible flow definitions |

**Deprecated/outdated:**
- None in this codebase - the existing `SequentialFlowEngine` is current and well-structured

## Open Questions

1. **Windows timeout strategy**
   - What we know: `signal.alarm()` doesn't work on Windows
   - What's unclear: Is Windows support required for production?
   - Recommendation: Implement `threading.Timer` fallback, document limitation

2. **Assertion operators**
   - What we know: `example-api-check.yaml` uses `equals` operator
   - What's unclear: What operators are needed? (contains, regex, gt/lt?)
   - Recommendation: Start with `equals`, `contains`, `exists`, `not_empty`; add more as needed

3. **api_call authentication**
   - What we know: Context can contain headers
   - What's unclear: Should api_call support OAuth, API keys from config?
   - Recommendation: Support headers from context/config; defer OAuth to Phase 21+

4. **Error recovery**
   - What we know: Current engine does early-exit on failure
   - What's unclear: Should some steps be optional/continue-on-failure?
   - Recommendation: Keep early-exit for Phase 20; add `continue_on_failure` config later

## Sources

### Primary (HIGH confidence)
- `flows/engine.py` - Existing SequentialFlowEngine implementation
- `flows/definitions.py` - FlowDef, FlowStepDef dataclasses with type/config fields
- `flows/parser.py` - YAMLFlowParser showing valid step types
- `flows/handlers/linear.py` - Handler function signature pattern
- `health_types.py` - VerificationCheck dataclass
- `models.py` - VerificationFlow, VerificationFlowRun, VerificationFlowStep models

### Secondary (MEDIUM confidence)
- `flows/example-api-check.yaml` - Example api_call and assertion step configs
- `linear.py` - requests library usage patterns
- Python stdlib signal module documentation

### Tertiary (LOW confidence)
- [timeout-decorator PyPI](https://pypi.org/project/timeout-decorator/) - Background on timeout approaches
- [Better Stack Python Timeouts Guide](https://betterstack.com/community/guides/scaling-python/python-timeouts/) - Timeout patterns
- [Python asyncio.timeout docs](https://docs.python.org/3/library/asyncio-task.html) - Alternative async approach

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using existing codebase libraries
- Architecture: HIGH - Extending proven patterns from engine.py
- Pitfalls: HIGH - Based on actual codebase analysis
- Timeout handling: MEDIUM - Signal approach is standard but has platform limitations

**Research date:** 2026-02-02
**Valid until:** 60 days (stable domain, existing patterns)

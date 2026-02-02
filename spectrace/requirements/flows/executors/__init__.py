"""Step executors for verification flows.

Each executor function handles a specific step type (api_call, assertion, wait, handler)
and returns a (VerificationCheck, context_updates) tuple.

The STEP_EXECUTORS registry maps step types to their executor functions.
"""

from requirements.health_types import VerificationCheck

from .api_call import execute_api_call_step
from .assertion import execute_assertion_step
from .wait import execute_wait_step


def execute_handler_step(step_def: dict, context: dict) -> tuple[VerificationCheck, dict]:
    """Execute a handler step by loading and calling the handler function.

    Args:
        step_def: Step definition with 'handler' path and optional 'name'
        context: Execution context passed to handler

    Returns:
        Tuple of (VerificationCheck, context_updates)
    """
    # Import here to avoid circular import
    from requirements.flows.engine import load_handler

    step_name = step_def.get('name', 'handler')

    try:
        handler = load_handler(step_def['handler'])
        return handler(context)
    except KeyError:
        return VerificationCheck(
            name=step_name,
            passed=False,
            error_message="Handler step missing 'handler' field",
        ), {}
    except Exception as e:
        # Match original engine error format for backward compatibility
        return VerificationCheck(
            name=step_name,
            passed=False,
            error_message=f"Handler error: {type(e).__name__}: {e}",
        ), {}


# Registry mapping step types to executor functions
STEP_EXECUTORS: dict[str, callable] = {
    'handler': execute_handler_step,
    'api_call': execute_api_call_step,
    'assertion': execute_assertion_step,
    'wait': execute_wait_step,
}


def execute_step(step_def: dict, context: dict) -> tuple[VerificationCheck, dict]:
    """Dispatch step execution to the appropriate executor.

    Args:
        step_def: Step definition with 'type' (default 'handler') and type-specific config
        context: Execution context

    Returns:
        Tuple of (VerificationCheck, context_updates)
    """
    step_type = step_def.get('type', 'handler')
    step_name = step_def.get('name', f'{step_type}_step')

    executor = STEP_EXECUTORS.get(step_type)
    if executor is None:
        return VerificationCheck(
            name=step_name,
            passed=False,
            error_message=f"Unknown step type: {step_type}",
        ), {}

    return executor(step_def, context)

"""Wait executor for delay steps.

Pauses execution for a specified duration.
"""

import time

from spectrace_flows.types import VerificationCheck


def execute_wait_step(step_def: dict, context: dict) -> tuple[VerificationCheck, dict]:
    """Pause execution for a specified duration.

    Config options (from step_def):
        seconds: Number of seconds to wait (default: 1)

    Args:
        step_def: Step definition with wait config
        context: Execution context (not used)

    Returns:
        Tuple of (VerificationCheck, {}) - wait steps always pass
    """
    step_name = step_def.get("name", "wait")
    config = step_def.get("config", {})

    seconds = config.get("seconds", 1)

    try:
        time.sleep(seconds)
        return (
            VerificationCheck(
                name=step_name,
                passed=True,
                details=f"Waited {seconds} seconds",
            ),
            {},
        )
    except Exception as e:
        return (
            VerificationCheck(
                name=step_name,
                passed=False,
                error_message=f"Wait interrupted: {type(e).__name__}: {e}",
            ),
            {},
        )

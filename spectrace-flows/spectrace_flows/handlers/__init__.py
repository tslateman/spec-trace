"""Flow step handlers package.

Handlers are functions that execute individual verification steps.
Each handler follows the protocol:

    def handler(context: dict) -> tuple[VerificationCheck, dict]:
        '''
        Execute a verification step.

        Args:
            context: Execution context with config and results from prior steps

        Returns:
            - VerificationCheck: The step result
            - dict: Context updates for subsequent steps
        '''

This package provides base infrastructure for handlers.
Application-specific handlers (like Linear integration) should be defined
in the application code, not in this standalone package.
"""

from spectrace_flows.types import VerificationCheck

# Type alias for handler functions
HandlerFunc = callable[[dict], tuple[VerificationCheck, dict]]

__all__ = [
    "HandlerFunc",
]

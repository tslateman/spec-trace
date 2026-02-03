"""Flow step handlers package for Django integration.

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
"""

from requirements.flows.handlers.linear import (
    check_authentication,
    check_configuration,
    check_permissions,
)

__all__ = [
    "check_configuration",
    "check_authentication",
    "check_permissions",
]

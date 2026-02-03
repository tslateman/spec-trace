"""Sequential execution engine for verification flows (Django integration).

Re-exports from the standalone spectrace-flows package plus Django-specific
SequentialFlowEngine that uses DjangoFlowStorage by default.
"""

from typing import Union

from spectrace_flows import (
    FlowDef,
    FlowStepDef,
    FlowTimeoutError,
    SequentialFlowEngine as BaseSequentialFlowEngine,
    StepTimeoutError,
    load_handler,
)

from requirements.flows.django_storage import DjangoFlowStorage
from requirements.models import VerificationFlow, VerificationFlowSource

# Re-export for backward compatibility
__all__ = [
    "SequentialFlowEngine",
    "StepTimeoutError",
    "FlowTimeoutError",
    "load_handler",
]


def _django_model_to_flow_def(model: VerificationFlow) -> FlowDef:
    """Convert a VerificationFlow Django model to a FlowDef dataclass.

    Args:
        model: VerificationFlow model instance with steps as JSONField

    Returns:
        FlowDef dataclass suitable for the standalone engine
    """
    # Filter out metadata entries and convert dicts to FlowStepDef
    steps = []
    for step_dict in model.steps:
        if "_metadata" in step_dict:
            continue
        steps.append(
            FlowStepDef(
                name=step_dict.get("name", ""),
                handler=step_dict.get("handler", ""),
                display_name=step_dict.get("display_name", ""),
                description=step_dict.get("description", ""),
                type=step_dict.get("type", "handler"),
                config=step_dict.get("config", {}),
            )
        )

    return FlowDef(
        name=model.name,
        display_name=model.display_name,
        description=model.description,
        steps=steps,
        version=model.version,
    )


class SequentialFlowEngine(BaseSequentialFlowEngine):
    """Django-integrated flow engine using DjangoFlowStorage by default.

    This subclass provides backward compatibility with existing Django code
    that expects the engine to use Django ORM for storage.

    Accepts either:
    - FlowDef dataclass (from spectrace_flows package)
    - VerificationFlow Django model (for backward compatibility)

    For the standalone engine without Django, import from spectrace_flows directly.
    """

    def __init__(self, storage=None):
        """Initialize with Django storage by default.

        Args:
            storage: Optional custom storage. Defaults to DjangoFlowStorage.
        """
        if storage is None:
            storage = DjangoFlowStorage()
        super().__init__(storage=storage)

    def execute(
        self,
        flow: Union[FlowDef, VerificationFlow],
        context: dict,
        source=None,
        step_timeout: int = 60,
        flow_timeout: int = 300,
    ):
        """Execute a verification flow.

        Args:
            flow: Either a FlowDef dataclass or VerificationFlow Django model
            context: Initial execution context
            source: What triggered this run (FlowSource or VerificationFlowSource)
            step_timeout: Maximum seconds per step (default 60)
            flow_timeout: Maximum seconds for entire flow (default 300)

        Returns:
            VerificationFlowRun Django model for backward compatibility
        """
        from spectrace_flows import FlowSource

        from requirements.models import VerificationFlowRun

        # Convert Django model to FlowDef if needed
        if isinstance(flow, VerificationFlow):
            flow = _django_model_to_flow_def(flow)

        # Convert Django source enum to spectrace_flows enum if needed
        if source is None:
            source = FlowSource.API
        elif isinstance(source, VerificationFlowSource):
            source_map = {
                VerificationFlowSource.API: FlowSource.API,
                VerificationFlowSource.MANUAL: FlowSource.MANUAL,
                VerificationFlowSource.SCHEDULED: FlowSource.SCHEDULED,
            }
            source = source_map.get(source, FlowSource.API)

        # Execute using the base engine
        result = super().execute(
            flow=flow,
            context=context,
            source=source,
            step_timeout=step_timeout,
            flow_timeout=flow_timeout,
        )

        # For backward compatibility, return the Django model instance
        # when using DjangoFlowStorage
        if isinstance(self.storage, DjangoFlowStorage):
            return VerificationFlowRun.objects.get(pk=result.id)

        return result

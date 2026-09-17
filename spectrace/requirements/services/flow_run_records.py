"""Shaping an executed flow into the record the Worker stores, with no database attached."""

__all__ = ["flow_run_payload"]


def flow_run_payload(flow_name: str, run) -> dict:
    """Shape a `spectrace_flows` FlowRun into the record POST /flows/runs/ takes.

    Args:
        flow_name: The stored flow's name, which the run is recorded against.
        run: A FlowRun as `SequentialFlowEngine.execute` returns it.
    """
    return {
        "flow_name": flow_name,
        "status": run.status.value,
        "source": run.source.value,
        "context": run.context,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "steps": [
            {
                "step_order": step.step_order,
                "name": step.name,
                "passed": step.passed,
                "details": step.details,
                "error_message": step.error_message,
                "response_status": step.response_status,
                "response_body": step.response_body,
                "started_at": step.started_at.isoformat(),
                "completed_at": step.completed_at.isoformat(),
            }
            for step in run.steps
        ],
    }

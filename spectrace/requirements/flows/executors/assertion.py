"""Assertion executor for verification steps (Django integration).

Re-exports from the standalone spectrace-flows package.
"""

from spectrace_flows.executors.assertion import execute_assertion_step

__all__ = ["execute_assertion_step"]

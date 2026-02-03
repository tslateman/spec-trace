"""Wait executor for delay steps (Django integration).

Re-exports from the standalone spectrace-flows package.
"""

from spectrace_flows.executors.wait import execute_wait_step

__all__ = ["execute_wait_step"]

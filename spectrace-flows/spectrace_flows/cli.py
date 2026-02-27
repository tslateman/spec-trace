"""Command-line interface for spectrace-flows.

Provides a simple CLI for executing flows from YAML files or registered flows.
"""

import argparse
import json
import sys
from pathlib import Path

from .definitions import get_flow_by_name
from .engine import SequentialFlowEngine
from .parser import YAMLFlowParser
from .storage import InMemoryStorage
from .types import FlowSource


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="spectrace-flows",
        description="Execute verification flows",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Execute a flow")
    run_parser.add_argument(
        "flow",
        help="Flow name (registered) or path to YAML file",
    )
    run_parser.add_argument(
        "--context",
        "-c",
        help="JSON context string or @file.json",
        default="{}",
    )
    run_parser.add_argument(
        "--step-timeout",
        type=int,
        default=60,
        help="Per-step timeout in seconds (default: 60)",
    )
    run_parser.add_argument(
        "--flow-timeout",
        type=int,
        default=300,
        help="Total flow timeout in seconds (default: 300)",
    )

    # List command
    subparsers.add_parser("list", help="List registered flows")

    args = parser.parse_args()

    if args.command == "run":
        return run_flow(args)
    elif args.command == "list":
        return list_flows()
    else:
        parser.print_help()
        return 1


def run_flow(args) -> int:
    """Execute a flow and print results."""
    # Load context
    context = _load_context(args.context)

    # Find the flow
    flow = None

    # Check if it's a file path
    flow_path = Path(args.flow)
    if flow_path.exists() and flow_path.suffix in (".yaml", ".yml"):
        parser = YAMLFlowParser()
        flow = parser.parse_file(flow_path)
        if not flow:
            print(f"Error: Could not parse flow from {args.flow}", file=sys.stderr)
            return 1
    else:
        # Try to find registered flow
        flow = get_flow_by_name(args.flow)
        if not flow:
            print(f"Error: Flow '{args.flow}' not found", file=sys.stderr)
            return 1

    # Execute
    engine = SequentialFlowEngine(storage=InMemoryStorage())
    result = engine.execute(
        flow=flow,
        context=context,
        source=FlowSource.CLI,
        step_timeout=args.step_timeout,
        flow_timeout=args.flow_timeout,
    )

    # Print results
    print(f"\nFlow: {flow.display_name}")
    print(f"Status: {result.status.value.upper()}")
    print("\nSteps:")

    for step in result.steps:
        status_icon = "[PASS]" if step.passed else "[FAIL]"
        print(f"  {status_icon} {step.name}")
        if step.details:
            print(f"         {step.details}")
        if step.error_message:
            print(f"         Error: {step.error_message}")

    return 0 if result.status.value == "passed" else 1


def list_flows() -> int:
    """List all registered flows."""
    from .definitions import REGISTERED_FLOWS

    if not REGISTERED_FLOWS:
        print("No flows registered")
        return 0

    print("Registered flows:")
    for flow in REGISTERED_FLOWS:
        print(f"  {flow.name}: {flow.display_name}")
        if flow.description:
            print(f"    {flow.description}")
        print(f"    Steps: {len(flow.steps)}")

    return 0


def _load_context(context_arg: str) -> dict:
    """Load context from JSON string or file."""
    if context_arg.startswith("@"):
        # Load from file
        file_path = Path(context_arg[1:])
        with open(file_path) as f:
            return json.load(f)
    return json.loads(context_arg)


if __name__ == "__main__":
    sys.exit(main())

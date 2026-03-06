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
from .scenario_registry import REGISTERED_SCENARIOS, get_scenario_by_name
from .storage import InMemoryStorage
from .types import FlowSource


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="spectrace-flows",
        description="Execute verification flows and scenarios",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Flow: run
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

    # Flow: list
    subparsers.add_parser("list", help="List registered flows")

    # Scenario: list
    subparsers.add_parser("scenarios", help="List registered scenarios")

    # Scenario: run
    scenario_run_parser = subparsers.add_parser("scenario", help="Execute a scenario by name")
    scenario_run_parser.add_argument("name", help="Registered scenario name")
    scenario_run_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

    if args.command == "run":
        return run_flow(args)
    elif args.command == "list":
        return list_flows()
    elif args.command == "scenarios":
        return list_scenarios()
    elif args.command == "scenario":
        return run_scenario(args)
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


def list_scenarios() -> int:
    """List all registered scenarios."""
    if not REGISTERED_SCENARIOS:
        print("No scenarios registered")
        return 0

    print("Registered scenarios:")
    for scenario_cls in REGISTERED_SCENARIOS:
        print(f"  {scenario_cls.name}: {scenario_cls.description or '(no description)'}")
        if scenario_cls.requirements:
            print(f"    Requirements: {', '.join(scenario_cls.requirements)}")
        fixture_names = [f.__name__ for f in scenario_cls.fixtures]
        if fixture_names:
            print(f"    Fixtures: {', '.join(fixture_names)}")

    return 0


def run_scenario(args) -> int:
    """Execute a scenario and print results."""
    scenario_cls = get_scenario_by_name(args.name)
    if not scenario_cls:
        print(f"Error: Scenario '{args.name}' not found", file=sys.stderr)
        return 1

    scenario = scenario_cls()
    result = scenario.run()

    if args.format == "json":
        import dataclasses

        output = {
            "name": result.name,
            "passed": result.passed,
            "error": result.error,
            "assertions": [dataclasses.asdict(a) for a in result.assertions],
        }
        print(json.dumps(output, indent=2, default=str))
        return 0 if result.passed else 1

    # Text output
    status = "PASSED" if result.passed else "FAILED"
    print(f"\nScenario: {scenario_cls.name}")
    if scenario_cls.description:
        print(f"  {scenario_cls.description}")
    print(f"Status: {status}")

    if result.error:
        print(f"Error: {result.error}")

    if result.assertions:
        print("\nAssertions:")
        for check in result.assertions:
            icon = "[PASS]" if check.passed else "[FAIL]"
            print(f"  {icon} {check.name}")
            if check.details:
                print(f"         {check.details}")
            if check.error_message:
                print(f"         Error: {check.error_message}")

    return 0 if result.passed else 1


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

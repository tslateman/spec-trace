#!/usr/bin/env python3
"""List and display available demos from the catalog."""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


def load_demos():
    """Load demos from the manifest file."""
    manifest_path = Path(__file__).parent.parent / "demos.yaml"
    if not manifest_path.exists():
        print(f"Error: demos.yaml not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path) as f:
        return yaml.safe_load(f)["demos"]


def print_list(demos, verbose=False):
    """Print a summary table of all demos."""
    print("\n Available Demos\n")
    print(f"{'ID':<25} {'Duration':<12} {'Name'}")
    print("-" * 70)

    for demo in demos:
        duration = demo.get("duration", "—")
        print(f"{demo['id']:<25} {duration:<12} {demo['name']}")

    print()
    if not verbose:
        print("Run with --verbose for full details, or --show <id> for one demo.\n")


def print_demo_detail(demo):
    """Print full details for a single demo."""
    print(f"\n{'=' * 70}")
    print(f" {demo['name']}")
    print(f"{'=' * 70}\n")

    print(f"ID:          {demo['id']}")
    print(f"Duration:    {demo.get('duration', '—')}")
    print(f"Entry point: {demo['entry_point']}")

    if demo.get("description"):
        print(f"\nDescription:\n  {demo['description'].strip()}")

    if demo.get("audience"):
        print("\nAudience:")
        for a in demo["audience"]:
            print(f"  • {a}")

    if demo.get("prerequisites"):
        print("\nPrerequisites:")
        for p in demo["prerequisites"]:
            print(f"  • {p}")

    if demo.get("talking_points"):
        print("\nTalking Points:")
        for tp in demo["talking_points"]:
            print(f"  • {tp}")

    if demo.get("urls"):
        print("\nURLs:")
        for url in demo["urls"]:
            print(f"  • {url}")

    if demo.get("files"):
        print("\nKey Files:")
        for f in demo["files"]:
            print(f"  • {f}")

    print()


def run_demo(demo):
    """Execute a demo's entry point."""
    entry = demo["entry_point"]

    # Handle different entry point types
    if entry.startswith("Follow ") or entry.startswith("Browse "):
        print(f"\nThis demo is manual: {entry}")
        print("Open the referenced file or directory to proceed.\n")
        return

    print(f"\nRunning: {entry}\n")
    print("-" * 70)

    # Split compound commands (&&) and run them
    commands = entry.split(" && ")
    for cmd in commands:
        # Skip 'open' commands on non-macOS or if not interactive
        if cmd.strip().startswith("open "):
            url = cmd.replace("open ", "").strip()
            print(f"Open in browser: {url}")
            continue

        result = subprocess.run(cmd, shell=True)
        if result.returncode != 0:
            print(f"\nCommand failed with exit code {result.returncode}")
            sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="List and run demos from the catalog.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/list_demos.py              # List all demos
  python scripts/list_demos.py --verbose    # Show full details for all
  python scripts/list_demos.py --show agent-pipeline
  python scripts/list_demos.py --run spectrace-workflow
        """,
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show full details for all demos"
    )
    parser.add_argument("--show", "-s", metavar="ID", help="Show details for a specific demo")
    parser.add_argument("--run", "-r", metavar="ID", help="Run a specific demo")
    parser.add_argument(
        "--audience",
        "-a",
        metavar="TERM",
        help="Filter demos by audience (case-insensitive search)",
    )

    args = parser.parse_args()
    demos = load_demos()

    # Filter by audience if specified
    if args.audience:
        term = args.audience.lower()
        demos = [
            d
            for d in demos
            if any(term in a.lower() for a in d.get("audience", []))
        ]
        if not demos:
            print(f"No demos found for audience matching '{args.audience}'")
            sys.exit(1)

    # Show single demo
    if args.show:
        demo = next((d for d in demos if d["id"] == args.show), None)
        if not demo:
            print(f"Demo '{args.show}' not found. Available: {[d['id'] for d in demos]}")
            sys.exit(1)
        print_demo_detail(demo)
        return

    # Run single demo
    if args.run:
        demo = next((d for d in demos if d["id"] == args.run), None)
        if not demo:
            print(f"Demo '{args.run}' not found. Available: {[d['id'] for d in demos]}")
            sys.exit(1)
        print_demo_detail(demo)
        run_demo(demo)
        return

    # List all demos
    if args.verbose:
        for demo in demos:
            print_demo_detail(demo)
    else:
        print_list(demos)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Demo script showcasing the SpecTrace workflow.

This script demonstrates the full traceability flow:
1. Parse markdown specs into the database
2. Show the requirement hierarchy
3. Extract test-requirement links
4. Run tests and show results
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import django

# Add spectrace to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SPECTRACE_DIR = PROJECT_ROOT / "spectrace"

sys.path.insert(0, str(SPECTRACE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spectrace.settings")
django.setup()

from requirements.models import Requirement


def banner(text: str) -> None:
    """Print a section banner."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")
    sys.stdout.flush()


def run_command(cmd: list[str], capture: bool = False) -> str:
    """Run a command and optionally capture output."""
    result = subprocess.run(
        cmd,
        cwd=SPECTRACE_DIR,
        capture_output=capture,
        text=True,
    )
    return result.stdout or ""


def step_1_parse_specs() -> None:
    """Parse spec files into the database."""
    banner("Step 1: Parse Specification Files")

    specs_dir = PROJECT_ROOT / "specs"
    print(f"Specs directory: {specs_dir}\n")

    # Show spec files
    print("Spec files found:")
    for spec_file in sorted(specs_dir.rglob("*.md")):
        rel_path = spec_file.relative_to(specs_dir)
        print(f"  - {rel_path}")

    print("\nParsing specs into database...")
    sys.stdout.flush()
    run_command(["python", "manage.py", "parse_specs", str(specs_dir), "--clear"])
    print("Done!")


def step_2_show_requirements() -> None:
    """Display the requirement hierarchy from the database."""
    banner("Step 2: Requirement Hierarchy")

    requirements = Requirement.objects.all()
    print(f"Total requirements: {requirements.count()}\n")

    for req in requirements:
        indent = "  " * (req.depth - 1)
        parent = req.get_parent()
        parent_info = f" (child of {parent.external_id})" if parent else ""
        tags = ", ".join(req.tags) if req.tags else "none"

        print(f"{indent}{req.external_id}: {req.title}")
        print(f"{indent}  Priority: {req.priority} | Tags: {tags}{parent_info}")
        print()


def step_3_extract_links() -> None:
    """Extract test-requirement links from pytest markers."""
    banner("Step 3: Extract Test-Requirement Links")

    print("Scanning tests for @pytest.mark.requirement markers...\n")

    output = run_command(
        ["python", "manage.py", "extract_links"],
        capture=True,
    )

    # Parse JSON from output (skip any warning lines)
    lines = output.strip().split("\n")
    json_start = next(i for i, line in enumerate(lines) if line.startswith("{"))
    json_str = "\n".join(lines[json_start:])
    data = json.loads(json_str)

    # Show warnings if any
    warnings = [line for line in lines[:json_start] if line.startswith("Warning:")]
    if warnings:
        print("Warnings (requirement IDs not in database):")
        for warning in warnings:
            print(f"  {warning}")
        print()

    # Show links grouped by requirement
    links_by_req: dict[str, list[dict]] = {}
    for link in data["links"]:
        req_id = link["requirement_id"]
        if req_id not in links_by_req:
            links_by_req[req_id] = []
        links_by_req[req_id].append(link)

    print("Links found:")
    for req_id, links in sorted(links_by_req.items()):
        print(f"\n  {req_id}:")
        for link in links:
            test_name = link["test_function"]
            if link["test_class"]:
                test_name = f"{link['test_class']}.{test_name}"
            reason = f' ({link["reason"]})' if link["reason"] else ""
            print(f"    - {test_name}{reason}")

    print(f"\nSummary: {data['summary']['total_links']} links, "
          f"{data['summary']['unique_tests']} tests, "
          f"{data['summary']['unique_requirements']} requirements")


def step_4_run_tests() -> None:
    """Run pytest and show results."""
    banner("Step 4: Run Tests")

    print("Running pytest...\n")
    sys.stdout.flush()
    subprocess.run(
        ["pytest", "-v", "--tb=short"],
        cwd=PROJECT_ROOT,
    )


def step_5_summary() -> None:
    """Show final summary."""
    banner("Demo Complete")

    print("SpecTrace connects your requirements to verified tests:\n")
    print("  specs/*.md  -->  parse_specs  -->  Database")
    print("                                        ^")
    print("  tests/*.py  -->  extract_links  ------+")
    print("                                        |")
    print("  pytest      -->  Results  -->  Dashboard (Phase 3)")
    print()
    print("Next steps:")
    print("  - Visit http://localhost:8000/admin to see requirements")
    print("  - Add more specs in specs/ directory")
    print("  - Link tests with @pytest.mark.requirement('REQ-XXX')")
    print()


def main() -> None:
    """Run the full demo."""
    print("\n" + "="*60)
    print("  SpecTrace Demo")
    print("  Requirements Traceability System")
    print("="*60)

    step_1_parse_specs()
    step_2_show_requirements()
    step_3_extract_links()
    step_4_run_tests()
    step_5_summary()


if __name__ == "__main__":
    main()

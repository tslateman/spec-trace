#!/usr/bin/env python
"""Demo script for the Document Pipeline example.

This script demonstrates spec-trace's full capabilities using a realistic
document processing pipeline scenario with:
- Nested requirement hierarchy (3 levels)
- Multiple verification methods (test, inapp, both)
- Passing, failing, and skipped tests
- SLO integration with OpenSLO YAML files
- Various pytest patterns (parametrized, async, class-based, xfail)

Usage:
    python scripts/demo_pipeline.py [--skip-tests]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import django

# Add spectrace to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SPECTRACE_DIR = PROJECT_ROOT / "spectrace"
EXAMPLE_DIR = PROJECT_ROOT / "examples" / "document-pipeline"

sys.path.insert(0, str(SPECTRACE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spectrace.settings")
django.setup()

from requirements.models import SLO, Requirement, VerificationMethod


def banner(text: str) -> None:
    """Print a section banner."""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}\n")
    sys.stdout.flush()


def info(text: str) -> None:
    """Print info text."""
    print(f"  {text}")
    sys.stdout.flush()


def run_command(cmd: list[str], capture: bool = False, cwd: Path | None = None) -> str:
    """Run a command and optionally capture output."""
    result = subprocess.run(
        cmd,
        cwd=cwd or SPECTRACE_DIR,
        capture_output=capture,
        text=True,
    )
    return result.stdout or ""


def step_1_overview() -> None:
    """Show example overview."""
    banner("Document Pipeline Example Overview")

    info("This example demonstrates a realistic document processing pipeline with:")
    info("")
    info("  Requirement Hierarchy:")
    info("    DOC-001 (Pipeline Root)")
    info("    ├── DOC-ING-001 (Ingestion Subsystem)")
    info("    │   ├── DOC-ING-002 (File Validation) ......... test")
    info("    │   ├── DOC-ING-003 (Virus Scanning) .......... inapp")
    info("    │   └── DOC-ING-004 (Metadata Extraction) ..... test (failing)")
    info("    ├── DOC-TRF-001 (Transform Subsystem)")
    info("    │   ├── DOC-TRF-002 (PDF Conversion) .......... test")
    info("    │   ├── DOC-TRF-003 (Image Optimization) ...... test")
    info("    │   └── DOC-TRF-004 (OCR Processing) .......... test (skipped)")
    info("    ├── DOC-STR-001 (Storage Subsystem)")
    info("    │   └── DOC-STR-002 (Encryption at Rest) ...... test")
    info("    └── DOC-DEL-001 (Delivery Subsystem)")
    info("        └── DOC-DEL-002 (CDN Integration) ......... inapp")
    info("")
    info("  SLOs:")
    info("    - API Availability (99.9% target)")
    info("    - Processing Latency (p99 < 5s)")


def step_2_import_specs() -> None:
    """Import spec files into the database."""
    banner("Step 1: Import Specification Files")

    specs_dir = EXAMPLE_DIR / "specs"
    info(f"Specs directory: {specs_dir}\n")

    # Show spec files
    info("Spec files found:")
    for spec_file in sorted(specs_dir.rglob("*.md")):
        rel_path = spec_file.relative_to(specs_dir)
        info(f"  - {rel_path}")

    print("\n  Importing specs into database...")
    sys.stdout.flush()
    run_command(["python", "manage.py", "parse_specs", str(specs_dir), "--clear"])
    info("Done!")


def step_3_show_hierarchy() -> None:
    """Display the requirement hierarchy from the database."""
    banner("Step 2: Requirement Hierarchy in Database")

    requirements = Requirement.objects.filter(external_id__startswith="DOC-")
    info(f"Total requirements: {requirements.count()}\n")

    # Build display with verification method
    def display_method(method: str) -> str:
        colors = {
            VerificationMethod.TEST: "test",
            VerificationMethod.INAPP: "inapp",
            VerificationMethod.BOTH: "both",
        }
        return colors.get(method, "unspecified")

    for req in requirements.order_by("external_id"):
        indent = "  " * req.depth
        method = display_method(req.verification_method)
        parent = req.get_parent()
        parent_info = f" [parent: {parent.external_id}]" if parent else " [root]"

        info(f"{indent}{req.external_id}: {req.title}")
        info(f"{indent}  method: {method}{parent_info}")
        print()


def step_4_import_slos() -> None:
    """Import SLO files."""
    banner("Step 3: Import SLO Definitions")

    slos_dir = EXAMPLE_DIR / "slos"
    info(f"SLO directory: {slos_dir}\n")

    # Show SLO files
    info("SLO files found:")
    for slo_file in sorted(slos_dir.glob("*.yaml")):
        info(f"  - {slo_file.name}")

    print("\n  Importing SLOs...")
    sys.stdout.flush()
    run_command(["python", "manage.py", "import_slos", str(slos_dir)])
    info("Done!")

    # Show imported SLOs
    slos = SLO.objects.all()
    if slos.exists():
        print("\n  Imported SLOs:")
        for slo in slos:
            linked_reqs = ", ".join(r.external_id for r in slo.requirements.all())
            info(f"    {slo.name}: {slo.target * 100:.1f}% target")
            info(f"      Linked to: {linked_reqs or 'none'}")


def step_5_run_tests(skip: bool = False) -> None:
    """Run example tests and import results."""
    banner("Step 4: Run Tests")

    if skip:
        info("Skipping test execution (--skip-tests flag)")
        return

    tests_dir = EXAMPLE_DIR / "tests"
    junit_output = PROJECT_ROOT / "test-results-pipeline.xml"

    info(f"Test directory: {tests_dir}\n")
    info("Running pytest with JUnit output...\n")
    sys.stdout.flush()

    # Run pytest with JUnit XML output
    subprocess.run(
        [
            "pytest",
            str(tests_dir),
            "-v",
            "--tb=short",
            f"--junitxml={junit_output}",
        ],
        cwd=PROJECT_ROOT,
    )

    # Import test results
    if junit_output.exists():
        print("\n  Importing test results into spec-trace...")
        sys.stdout.flush()
        run_command(["python", "manage.py", "import_results", str(junit_output)])
        info("Done!")


def step_6_show_status() -> None:
    """Show verification status of requirements."""
    banner("Step 5: Verification Status Summary")

    requirements = Requirement.objects.filter(external_id__startswith="DOC-")

    # Group by verification status
    status_groups = {}
    for req in requirements:
        status = req.verification_status
        if status not in status_groups:
            status_groups[status] = []
        status_groups[status].append(req)

    for status, reqs in sorted(status_groups.items()):
        info(f"{status.upper()} ({len(reqs)}):")
        for req in reqs:
            info(f"  - {req.external_id}: {req.title}")
        print()

    # Show summary
    info("This demonstrates spec-trace's ability to track:")
    info("  - Requirements verified by automated tests")
    info("  - Requirements requiring in-app validation")
    info("  - Passing, failing, and untested requirements")
    info("  - SLO-linked requirements for operational metrics")


def step_7_ci_example() -> None:
    """Show CI/CD integration example."""
    banner("CI/CD Integration Example")

    ci_file = EXAMPLE_DIR / "ci" / "github-actions.yml"
    info(f"Example CI workflow: {ci_file}\n")
    info("The workflow demonstrates:")
    info("  1. Running tests with JUnit XML output")
    info("  2. Importing specs and SLOs into spec-trace")
    info("  3. Importing test results")
    info("  4. Generating traceability reports")
    info("  5. Quality gates based on requirement status")


def step_8_summary() -> None:
    """Show final summary."""
    banner("Demo Complete")

    info("Document Pipeline example showcases spec-trace features:")
    print()
    info("  Feature                    | How Demonstrated")
    info("  ---------------------------|----------------------------------")
    info("  Nested hierarchy           | DOC-001 → DOC-ING-001 → DOC-ING-002")
    info("  verification_method: test  | Most requirements")
    info("  verification_method: inapp | DOC-ING-003, DOC-DEL-002")
    info("  verification_method: both  | DOC-001 (root requirement)")
    info("  Passing status             | DOC-ING-002, DOC-TRF-002, etc.")
    info("  Failing status             | DOC-ING-004 (intentional failure)")
    info("  Untested status            | DOC-TRF-004 (only skipped tests)")
    info("  SLO integration            | 2 OpenSLO YAML files")
    info("  Parametrized tests         | File type validation")
    info("  xfail tests                | GPS extraction edge case")
    info("  Async tests                | Concurrent upload validation")
    info("  Class-based tests          | TestPDFConversion")
    info("  Multi-requirement tests    | Integration tests")
    print()
    info("Next steps:")
    info("  - Run: python spectrace/manage.py runserver")
    info("  - Visit: http://localhost:8000/admin to explore requirements")
    info("  - Review: examples/document-pipeline/README.md for walkthrough")
    print()


def main() -> None:
    """Run the full demo."""
    parser = argparse.ArgumentParser(
        description="Demo the Document Pipeline example for spec-trace"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running pytest (useful if tests already run)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  Spec-Trace: Document Pipeline Demo")
    print("  Realistic Requirements Traceability Example")
    print("=" * 70)

    step_1_overview()
    step_2_import_specs()
    step_3_show_hierarchy()
    step_4_import_slos()
    step_5_run_tests(skip=args.skip_tests)
    step_6_show_status()
    step_7_ci_example()
    step_8_summary()


if __name__ == "__main__":
    main()

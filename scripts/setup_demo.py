#!/usr/bin/env python
"""Idempotent demo setup script for SpecTrace.

This script sets up a complete demo environment with:
- Database migrations
- Demo requirements from specs/
- Demo tests with JUnit results
- Test-requirement linkages
- A demo admin user

Safe to run multiple times - will reset demo data to a known state.

Usage:
    python scripts/setup_demo.py
    # Or from spectrace directory:
    python ../scripts/setup_demo.py
"""
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and print output."""
    print(f"  → {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            print(f"    {line}")
    if result.stderr and result.returncode != 0:
        for line in result.stderr.strip().split('\n'):
            print(f"    [err] {line}")
    if check and result.returncode != 0:
        print(f"  ✗ Command failed with exit code {result.returncode}")
        sys.exit(1)
    return result


def main():
    # Find project root (directory containing specs/ and spectrace/)
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    spectrace_dir = project_root / "spectrace"
    specs_dir = project_root / "specs"

    # Verify we're in the right place
    if not spectrace_dir.exists():
        print(f"Error: spectrace directory not found at {spectrace_dir}")
        sys.exit(1)
    if not specs_dir.exists():
        print(f"Error: specs directory not found at {specs_dir}")
        sys.exit(1)

    print("=" * 60)
    print("SpecTrace Demo Setup")
    print("=" * 60)
    print(f"Project root: {project_root}")
    print()

    # Set up Django environment
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spectrace.settings")
    sys.path.insert(0, str(spectrace_dir))

    # 1. Run migrations
    print("[1/6] Running database migrations...")
    run_command(
        ["python", "manage.py", "migrate", "--verbosity=0"],
        cwd=spectrace_dir
    )
    print("  ✓ Migrations complete")
    print()

    # 2. Import specs (clear and reimport)
    print("[2/6] Importing requirements from specs...")
    run_command(
        ["python", "manage.py", "parse_specs", str(specs_dir), "--clear"],
        cwd=spectrace_dir
    )
    print()

    # 3. Run tests and generate JUnit XML
    print("[3/6] Running tests and generating JUnit XML...")
    result = run_command(
        ["python", "-m", "pytest", "tests/test_example.py",
         "--junitxml=test_results.xml", "-v", "--tb=no"],
        cwd=spectrace_dir,
        check=False  # Tests may fail intentionally
    )
    print("  ✓ Test results written to test_results.xml")
    print()

    # 4. Extract test-requirement links
    print("[4/6] Extracting test-requirement links...")
    run_command(
        ["python", "manage.py", "extract_links", "--path", "tests/", "-o", "links.json"],
        cwd=spectrace_dir
    )
    print()

    # 5. Import test results
    print("[5/6] Importing test results and updating verification status...")
    run_command(
        ["python", "manage.py", "import_results", "test_results.xml", "--links", "links.json"],
        cwd=spectrace_dir
    )
    print()

    # 6. Create demo admin user (idempotent)
    print("[6/6] Creating demo admin user...")
    # Use Django's management command to create superuser
    create_user_script = """
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('  ✓ Created admin user (username: admin, password: admin)')
else:
    print('  ✓ Admin user already exists')
"""
    result = subprocess.run(
        ["python", "-c", create_user_script],
        cwd=spectrace_dir,
        capture_output=True,
        text=True,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "spectrace.settings"}
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr:
        print(f"  [warn] {result.stderr.strip()}")
    print()

    # Summary
    print("=" * 60)
    print("Demo Setup Complete!")
    print("=" * 60)
    print()
    print("Start the server:")
    print("  cd spectrace && python manage.py runserver")
    print()
    print("Then visit:")
    print("  http://localhost:8000/admin/")
    print()
    print("Login credentials:")
    print("  Username: admin")
    print("  Password: admin")
    print()
    print("What you'll see:")
    print("  - Dashboard with requirements tree and verification status")
    print("  - Some requirements passing (green)")
    print("  - Some requirements failing (red)")
    print("  - Some requirements untested (gray with yellow highlight)")
    print()


if __name__ == "__main__":
    main()

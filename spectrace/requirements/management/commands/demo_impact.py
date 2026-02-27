"""Management command: end-to-end impact demo.

Runs five steps in sequence:
  1. Set up demo data (branch, test links)
  2. Impact analysis (changed reqs, affected tests, risk score)
  3. Run affected tests via pytest
  4. Import results and update verification statuses
  5. Coverage summary
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q

from requirements.importer import import_junit_xml, update_test_requirement_links
from requirements.models import Requirement
from requirements.services.impact_analyzer import ImpactAnalyzer, setup_impact_demo
from requirements.status import update_all_verification_statuses


def banner(text, step, stdout):
    """Print a numbered section banner."""
    stdout.write(f"\n{'=' * 70}")
    stdout.write(f"  Step {step}: {text}")
    stdout.write(f"{'=' * 70}\n")


class Command(BaseCommand):
    help = "Run the impact demo: spec change → impact → tests → coverage"

    def add_arguments(self, parser):
        parser.add_argument(
            "--step",
            type=int,
            default=5,
            help="Run through step N then stop (default: all 5)",
        )
        parser.add_argument(
            "--skip-setup",
            action="store_true",
            default=False,
            help="Skip step 1 (setup) on reruns",
        )

    def handle(self, *args, **options):
        max_step = options["step"]
        skip_setup = options["skip_setup"]

        self.stdout.write(f"\n{'=' * 70}")
        self.stdout.write("  SpecTrace Impact Demo")
        self.stdout.write("  spec change → impact → tests → coverage")
        self.stdout.write(f"{'=' * 70}")

        # Step 1: Setup
        if max_step >= 1:
            if skip_setup:
                self.stdout.write("\n  (skipping setup — --skip-setup)")
            else:
                self._step_1_setup()

        # Step 2: Impact analysis
        if max_step >= 2:
            self._step_2_impact()
        else:
            return

        # Step 3: Run tests
        if max_step >= 3:
            junit_path = self._step_3_run_tests()
        else:
            return

        # Step 4: Import results
        if max_step >= 4:
            self._step_4_import(junit_path)
        else:
            return

        # Step 5: Coverage summary
        if max_step >= 5:
            self._step_5_coverage()

        self.stdout.write(f"\n{'=' * 70}")
        self.stdout.write("  Demo complete.")
        self.stdout.write(f"{'=' * 70}\n")

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _step_1_setup(self):
        banner("Set up demo data", 1, self.stdout)

        result = setup_impact_demo()

        if result["specs_committed"]:
            self.stdout.write("  Specs committed to git")
        self.stdout.write(f"  Test links created: {result['test_links_created']}")
        self.stdout.write(f"  Demo branch: {result['demo_branch']}")
        self.stdout.write(self.style.SUCCESS("  Done."))

    def _step_2_impact(self):
        banner("Impact analysis", 2, self.stdout)

        analyzer = ImpactAnalyzer()
        result = analyzer.analyze("main", "demo/impact-analysis")

        # Changed requirements
        self.stdout.write(f"\n  Changed requirements: {len(result.changed_requirements)}")
        for req_id in result.changed_requirements:
            self.stdout.write(f"    • {req_id}")

        # Affected tests
        self.stdout.write(f"\n  Affected tests: {len(result.affected_tests)}")
        for test in sorted(result.affected_tests):
            self.stdout.write(f"    ✗ {test}")

        # Risk
        risk_styles = {
            "low": self.style.SUCCESS,
            "medium": self.style.WARNING,
            "high": self.style.WARNING,
            "critical": self.style.ERROR,
        }
        style_fn = risk_styles.get(result.risk_level, self.style.WARNING)
        self.stdout.write(
            style_fn(f"\n  Risk: {result.risk_level.upper()} ({result.risk_score:.2f})")
        )

        return result

    def _step_3_run_tests(self):
        banner("Run affected tests", 3, self.stdout)

        junit_file = tempfile.NamedTemporaryFile(
            suffix=".xml", prefix="spectrace-demo-", delete=False
        )
        junit_path = junit_file.name
        junit_file.close()

        self.stdout.write("  Running pytest on tests/sample/ ...")
        self.stdout.write(f"  JUnit XML: {junit_path}\n")

        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/sample/",
                "-v",
                "--tb=short",
                "-m",
                "requirement or demo",
                f"--junitxml={junit_path}",
            ],
            cwd=self._repo_root(),
        )

        self.stdout.write(self.style.SUCCESS("\n  Tests finished."))
        return junit_path

    def _step_4_import(self, junit_path):
        banner("Import results", 4, self.stdout)

        self.stdout.write("  Importing JUnit XML...")
        test_run = import_junit_xml(junit_path)
        self.stdout.write(f"  Test run created: {test_run.results.count()} results")

        self.stdout.write("  Updating test-requirement links...")
        link_result = update_test_requirement_links(test_run)
        self.stdout.write(f"  Links updated: {link_result['updated_count']}")

        self.stdout.write("  Updating verification statuses...")
        status_counts = update_all_verification_statuses(test_run)
        self.stdout.write(f"  Statuses: {status_counts}")

        self.stdout.write(self.style.SUCCESS("  Done."))

    def _step_5_coverage(self):
        banner("Coverage summary", 5, self.stdout)

        metrics = Requirement.objects.aggregate(
            total=Count("id"),
            non_draft=Count("id", filter=~Q(status="draft")),
            passing=Count("id", filter=Q(verification_status="passing")),
            failing=Count("id", filter=Q(verification_status="failing")),
            untested=Count("id", filter=Q(verification_status="untested")),
            avg_structure=Avg("structure_completeness"),
        )

        total = metrics["total"]
        passing = metrics["passing"]
        failing = metrics["failing"]
        untested = metrics["untested"]

        if total > 0:
            verif_pct = (passing / total) * 100
        else:
            verif_pct = 0.0

        self.stdout.write(f"  Total requirements: {total}")
        self.stdout.write(self.style.SUCCESS(f"  Passing:  {passing}"))
        self.stdout.write(self.style.ERROR(f"  Failing:  {failing}"))
        self.stdout.write(f"  Untested: {untested}")
        self.stdout.write(f"  Verification rate: {verif_pct:.1f}%")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _repo_root():
        """Return the repository root (parent of spectrace/)."""
        return Path(__file__).resolve().parents[4]

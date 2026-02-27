"""Tests for demo_impact management command."""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command

from requirements.services.impact_analyzer import ImpactResult


def _make_impact_result(**overrides):
    """Build an ImpactResult with sensible defaults."""
    defaults = {
        "changed_requirements": ["REQ-001"],
        "affected_tests": ["tests/test_foo.py::test_bar"],
        "hierarchy_expansion": {},
        "dependency_expansion": {},
        "risk_score": 0.15,
        "risk_level": "low",
    }
    defaults.update(overrides)
    return ImpactResult(**defaults)


SETUP_PATH = "requirements.management.commands.demo_impact.setup_impact_demo"
ANALYZER_PATH = "requirements.management.commands.demo_impact.ImpactAnalyzer"
SUBPROCESS_PATH = "requirements.management.commands.demo_impact.subprocess"
IMPORT_XML_PATH = "requirements.management.commands.demo_impact.import_junit_xml"
UPDATE_LINKS_PATH = "requirements.management.commands.demo_impact.update_test_requirement_links"
UPDATE_STATUS_PATH = "requirements.management.commands.demo_impact.update_all_verification_statuses"


class TestDemoImpactCommand:
    """Tests for demo_impact management command."""

    @patch(SETUP_PATH, autospec=True)
    def test_demo_impact__step_1_calls_setup(self, mock_setup, db):
        """Step 1 calls setup_impact_demo."""
        mock_setup.return_value = {
            "specs_committed": False,
            "test_links_created": 3,
            "demo_branch": "demo/impact-analysis",
            "base_ref": "main",
            "head_ref": "demo/impact-analysis",
        }

        out = StringIO()
        call_command("demo_impact", "--step", "1", stdout=out)

        mock_setup.assert_called_once()
        output = out.getvalue()
        assert "Test links created: 3" in output

    @patch(SETUP_PATH, autospec=True)
    def test_demo_impact__skip_setup(self, mock_setup, db):
        """--skip-setup skips step 1."""
        out = StringIO()
        call_command("demo_impact", "--step", "1", "--skip-setup", stdout=out)

        mock_setup.assert_not_called()
        assert "skipping setup" in out.getvalue()

    @patch(ANALYZER_PATH, autospec=True)
    @patch(SETUP_PATH, autospec=True)
    def test_demo_impact__step_2_runs_analysis(self, mock_setup, MockAnalyzer, db):
        """Step 2 runs ImpactAnalyzer.analyze and displays results."""
        mock_setup.return_value = {
            "specs_committed": False,
            "test_links_created": 0,
            "demo_branch": "demo/impact-analysis",
            "base_ref": "main",
            "head_ref": "demo/impact-analysis",
        }
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = _make_impact_result()
        MockAnalyzer.return_value = mock_analyzer

        out = StringIO()
        call_command("demo_impact", "--step", "2", stdout=out)

        mock_analyzer.analyze.assert_called_once_with("main", "demo/impact-analysis")
        output = out.getvalue()
        assert "REQ-001" in output
        assert "Risk: LOW" in output

    @patch(SUBPROCESS_PATH, autospec=True)
    @patch(ANALYZER_PATH, autospec=True)
    @patch(SETUP_PATH, autospec=True)
    def test_demo_impact__step_3_runs_pytest(self, mock_setup, MockAnalyzer, mock_subprocess, db):
        """Step 3 invokes pytest on tests/sample/."""
        mock_setup.return_value = {
            "specs_committed": False,
            "test_links_created": 0,
            "demo_branch": "demo/impact-analysis",
            "base_ref": "main",
            "head_ref": "demo/impact-analysis",
        }
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = _make_impact_result()
        MockAnalyzer.return_value = mock_analyzer

        out = StringIO()
        call_command("demo_impact", "--step", "3", stdout=out)

        # Verify subprocess.run was called with pytest args
        mock_subprocess.run.assert_called_once()
        args = mock_subprocess.run.call_args
        cmd = args[0][0]  # first positional arg is the command list
        assert "pytest" in " ".join(cmd)
        assert "tests/sample/" in cmd

    @patch(UPDATE_STATUS_PATH, autospec=True)
    @patch(UPDATE_LINKS_PATH, autospec=True)
    @patch(IMPORT_XML_PATH, autospec=True)
    @patch(SUBPROCESS_PATH, autospec=True)
    @patch(ANALYZER_PATH, autospec=True)
    @patch(SETUP_PATH, autospec=True)
    def test_demo_impact__full_flow(
        self,
        mock_setup,
        MockAnalyzer,
        mock_subprocess,
        mock_import_xml,
        mock_update_links,
        mock_update_status,
        db,
    ):
        """Full 5-step flow calls all services and shows all sections."""
        # Step 1
        mock_setup.return_value = {
            "specs_committed": True,
            "test_links_created": 5,
            "demo_branch": "demo/impact-analysis",
            "base_ref": "main",
            "head_ref": "demo/impact-analysis",
        }

        # Step 2
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = _make_impact_result()
        MockAnalyzer.return_value = mock_analyzer

        # Step 4
        mock_run = MagicMock()
        mock_run.results.count.return_value = 4
        mock_import_xml.return_value = mock_run
        mock_update_links.return_value = {"updated_count": 3, "status_changes": []}
        mock_update_status.return_value = {"passing": 2, "failing": 1, "untested": 1}

        out = StringIO()
        call_command("demo_impact", stdout=out)

        output = out.getvalue()

        # All five sections present
        assert "Step 1" in output
        assert "Step 2" in output
        assert "Step 3" in output
        assert "Step 4" in output
        assert "Step 5" in output
        assert "Demo complete" in output

        # Services called
        mock_setup.assert_called_once()
        mock_analyzer.analyze.assert_called_once()
        mock_subprocess.run.assert_called_once()
        mock_import_xml.assert_called_once()
        mock_update_links.assert_called_once()
        mock_update_status.assert_called_once()

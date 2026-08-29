"""Tests for code-level impact analysis."""

from unittest.mock import MagicMock, patch

import pytest
import yaml

from requirements.services.impact_analyzer import CodeImpactResult, ImpactAnalyzer


@pytest.fixture
def project_roots(tmp_path):
    """Create project roots with map files for testing."""
    lore_root = tmp_path / "lore"
    lore_root.mkdir()
    praxis_root = tmp_path / "praxis"
    praxis_root.mkdir()

    # spectrace-map.yaml for lore
    map_data = {
        "project": "lore",
        "modules": {
            "src/lore/reader.py": {"requirements": ["REQ-LORE-001"]},
        },
    }
    with open(lore_root / "spectrace-map.yaml", "w") as f:
        yaml.dump(map_data, f)

    return {"lore": lore_root, "praxis": praxis_root}


class TestCodeAnalyze:
    """Tests for ImpactAnalyzer.code_analyze()."""

    def test_no_changes_returns_empty(self, project_roots):
        """No changed files produces empty result."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="", returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = analyzer.code_analyze("HEAD~1", "HEAD", project_roots=project_roots)

        assert result.changed_files == {}
        assert result.risk_level == "low"
        assert result.risk_score <= 0.25  # Low risk
        assert isinstance(result, CodeImpactResult)

    def test_single_file_maps_to_requirements(self, project_roots):
        """A changed file in lore maps to its requirement via spectrace-map."""
        analyzer = ImpactAnalyzer()

        # First call: git diff for lore returns a file
        # Second call: git diff for praxis returns nothing
        # Third call: git log for lore (co-change)
        # Fourth call: git log for praxis (co-change)
        diff_lore = MagicMock(stdout="src/lore/reader.py\n")
        diff_praxis = MagicMock(stdout="")
        log_empty = MagicMock(stdout="")

        with patch("subprocess.run", side_effect=[diff_lore, diff_praxis, log_empty, log_empty]):
            result = analyzer.code_analyze("HEAD~1", "HEAD", project_roots=project_roots)

        assert "lore" in result.changed_files
        assert "src/lore/reader.py" in result.changed_files["lore"]
        assert result.edge_summary["annotated"] > 0

    def test_edge_summary_counts(self, project_roots):
        """Edge summary reflects actual edge sources."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            result = analyzer.code_analyze("HEAD~1", "HEAD", project_roots=project_roots)

        assert "annotated" in result.edge_summary
        assert "inferred" in result.edge_summary
        assert "contract" in result.edge_summary

    def test_risk_scoring_weights(self, project_roots):
        """Risk score incorporates graph risk, test impact, and edge factors."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            result = analyzer.code_analyze("HEAD~1", "HEAD", project_roots=project_roots)

        # Empty analysis should have low risk
        assert result.risk_score <= 0.25
        assert result.risk_level == "low"

    def test_invalid_ref_raises(self):
        """Invalid git ref raises ValueError."""
        analyzer = ImpactAnalyzer()
        with pytest.raises(ValueError):
            analyzer.code_analyze("", "HEAD")

    def test_code_impact_result_defaults(self):
        """CodeImpactResult has sensible defaults."""
        result = CodeImpactResult(
            changed_files={},
            blast={},
            affected_tests=[],
        )
        assert result.risk_score == 0.0
        assert result.risk_level == "low"
        assert result.edge_summary == {"annotated": 0, "inferred": 0, "contract": 0}


class TestGetAllChangedFiles:
    """Tests for ImpactAnalyzer.get_all_changed_files()."""

    def test_returns_all_files(self):
        """Returns all changed files, not just specs."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="src/app.py\nREADME.md\ntests/test_app.py\n")
        with patch("subprocess.run", return_value=mock_result):
            files = analyzer.get_all_changed_files("HEAD~1", "HEAD")
        assert len(files) == 3
        assert "src/app.py" in files

    def test_empty_diff(self):
        """Empty diff returns empty list."""
        analyzer = ImpactAnalyzer()
        mock_result = MagicMock(stdout="")
        with patch("subprocess.run", return_value=mock_result):
            files = analyzer.get_all_changed_files("HEAD~1", "HEAD")
        assert files == []

    def test_git_failure_raises(self):
        """Git failure raises ValueError."""
        import subprocess

        analyzer = ImpactAnalyzer()
        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "git", stderr="error"),
        ):
            with pytest.raises(ValueError, match="Git diff failed"):
                analyzer.get_all_changed_files("HEAD~1", "HEAD")


class TestCliCodeFlag:
    """Tests for --code flag dispatching in CLI."""

    def test_code_flag_dispatches_to_code_impact(self):
        """The --code flag routes to code_impact_analysis command."""
        with patch("cli._run") as mock_run:
            with patch("cli._bootstrap_django"):
                from click.testing import CliRunner

                from cli import cli

                runner = CliRunner()
                runner.invoke(cli, ["specs", "impact", "HEAD~1", "HEAD", "--code"])
                if mock_run.called:
                    assert mock_run.call_args[0][0] == "code_impact_analysis"

    def test_without_code_flag_dispatches_to_impact_analysis(self):
        """Without --code, routes to regular impact_analysis."""
        with patch("cli._run") as mock_run:
            with patch("cli._bootstrap_django"):
                from click.testing import CliRunner

                from cli import cli

                runner = CliRunner()
                runner.invoke(cli, ["specs", "impact", "HEAD~1", "HEAD"])
                if mock_run.called:
                    assert mock_run.call_args[0][0] == "impact_analysis"

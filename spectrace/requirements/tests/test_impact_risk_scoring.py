"""Tests that risk reflects the change, not the size of the graph around it."""

from unittest.mock import MagicMock, patch

import pytest
import yaml

from requirements.services.impact_analyzer import (
    EDGE_FACTOR_SATURATION,
    EDGE_SOURCE_WEIGHTS,
    ImpactAnalyzer,
    count_traversed_edges,
    traversed_edge_factor,
)
from requirements.services.impact_graph import (
    BlastResult,
    EdgeSource,
    GraphEdge,
    ImpactGraph,
)


def edge(source_id, target_id, source=EdgeSource.ANNOTATED, project="p"):
    return GraphEdge(source_id=source_id, target_id=target_id, source=source, project=project)


def write_map(root, project, modules):
    root.mkdir(exist_ok=True)
    (root / "spectrace-map.yaml").write_text(
        yaml.dump(
            {
                "project": project,
                "modules": {path: {"requirements": reqs} for path, reqs in modules.items()},
            }
        )
    )


def analyze_one_file(roots, path):
    """Run a single-project analysis whose diff holds exactly one file."""
    diff = MagicMock(stdout=f"{path}\n")
    log = MagicMock(stdout="")
    with patch("subprocess.run", side_effect=[diff, log]):
        return ImpactAnalyzer().code_analyze("HEAD~1", "HEAD", project_roots=roots)


class TestTraversedEdgeFactor:
    def test_traversed_edge_factor__is_zero_when_nothing_was_traversed(self):
        assert traversed_edge_factor(BlastResult()) == 0.0

    def test_traversed_edge_factor__rises_with_the_edges_traversed(self):
        few = BlastResult(traversed_edges=[edge("a", "REQ-1")])
        many = BlastResult(traversed_edges=[edge(f"m{n}", f"REQ-{n}") for n in range(5)])

        assert traversed_edge_factor(many) > traversed_edge_factor(few)

    def test_traversed_edge_factor__saturates_at_one(self):
        crowd = [edge(f"m{n}", f"REQ-{n}") for n in range(int(EDGE_FACTOR_SATURATION) * 10)]

        assert traversed_edge_factor(BlastResult(traversed_edges=crowd)) == 1.0

    def test_traversed_edge_factor__trusts_an_annotated_edge_over_an_inferred_one(self):
        annotated = BlastResult(traversed_edges=[edge("a", "REQ-1", EdgeSource.ANNOTATED)])
        inferred = BlastResult(traversed_edges=[edge("a", "REQ-1", EdgeSource.GIT_INFERRED)])
        contract = BlastResult(traversed_edges=[edge("a", "REQ-1", EdgeSource.CONTRACT)])

        assert traversed_edge_factor(annotated) > traversed_edge_factor(contract)
        assert traversed_edge_factor(contract) > traversed_edge_factor(inferred)

    def test_traversed_edge_factor__weighs_every_edge_source(self):
        assert set(EDGE_SOURCE_WEIGHTS) == set(EdgeSource)

    def test_traversed_edge_factor__counts_a_cross_project_edge_above_a_local_one(self):
        crossing = edge("a", "REQ-1")
        local = BlastResult(traversed_edges=[crossing])
        across = BlastResult(traversed_edges=[crossing], cross_project_edges=[crossing])

        assert traversed_edge_factor(across) > traversed_edge_factor(local)


class TestBlastRadiusTraversal:
    def test_blast_radius__records_the_edges_it_crossed(self):
        graph = ImpactGraph()
        graph.add_edge(edge("src/a.py", "REQ-A"))

        blast = graph.blast_radius(["src/a.py"])

        assert [(e.source_id, e.target_id) for e in blast.traversed_edges] == [
            ("src/a.py", "REQ-A")
        ]

    def test_blast_radius__records_no_edge_when_the_change_reaches_nothing(self):
        graph = ImpactGraph()
        graph.add_edge(edge("src/a.py", "REQ-A"))
        graph.add_edge(edge("src/b.py", "REQ-B"))

        assert graph.blast_radius(["CHANGELOG.md"]).traversed_edges == []

    def test_blast_radius__leaves_edges_outside_the_radius_untraversed(self):
        graph = ImpactGraph()
        graph.add_edge(edge("src/a.py", "REQ-A"))
        for n in range(50):
            graph.add_edge(edge(f"unrelated/{n}.py", f"REQ-U{n}"))

        blast = graph.blast_radius(["src/a.py"])

        assert len(blast.traversed_edges) == 1
        assert len(graph.edges) == 51

    def test_blast_radius__records_nothing_for_an_empty_change(self):
        graph = ImpactGraph()
        graph.add_edge(edge("src/a.py", "REQ-A"))

        assert graph.blast_radius([]).traversed_edges == []


class TestRiskIgnoresGraphSize:
    def test_code_analyze__scores_a_diff_that_maps_to_nothing_as_no_risk(self, tmp_path):
        write_map(tmp_path / "one", "one", {"src/mapped.py": ["REQ-M-001"]})

        result = analyze_one_file({"one": tmp_path / "one"}, "CHANGELOG.md")

        assert result.blast["affected_requirements"] == []
        assert result.affected_tests == []
        assert result.risk_score == 0.0
        assert result.risk_level == "low"

    def test_code_analyze__holds_that_score_as_the_graph_grows(self, tmp_path):
        small = tmp_path / "small"
        large = tmp_path / "large"
        write_map(small, "p", {"src/mapped.py": ["REQ-M-001"]})
        write_map(
            large,
            "p",
            {f"src/mod{n}.py": [f"REQ-M-{n:03d}"] for n in range(200)},
        )

        on_small = analyze_one_file({"p": small}, "CHANGELOG.md")
        on_large = analyze_one_file({"p": large}, "CHANGELOG.md")

        assert on_large.edge_summary["annotated"] > on_small.edge_summary["annotated"]
        assert on_large.risk_score == on_small.risk_score == 0.0

    @pytest.mark.django_db
    def test_code_analyze__scores_a_mapped_change_above_an_unmapped_one(self, tmp_path):
        write_map(
            tmp_path / "p",
            "p",
            {f"src/mod{n}.py": [f"REQ-M-{n:03d}"] for n in range(30)},
        )
        roots = {"p": tmp_path / "p"}

        mapped = analyze_one_file(roots, "src/mod0.py")
        unmapped = analyze_one_file(roots, "CHANGELOG.md")

        assert mapped.risk_score > unmapped.risk_score

    @pytest.mark.django_db
    def test_code_analyze__scores_a_wider_change_above_a_narrower_one(self, tmp_path):
        modules = {f"src/mod{n}.py": [f"REQ-M-{n:03d}"] for n in range(30)}
        modules["src/hub.py"] = [f"REQ-M-{n:03d}" for n in range(30)]
        write_map(tmp_path / "p", "p", modules)
        roots = {"p": tmp_path / "p"}

        wide = analyze_one_file(roots, "src/hub.py")
        narrow = analyze_one_file(roots, "src/mod0.py")

        assert wide.risk_score > narrow.risk_score


class TestTraversedEdgeCounts:
    def test_count_traversed_edges__counts_nothing_for_an_untouched_graph(self):
        assert count_traversed_edges(BlastResult()) == {
            "annotated": 0,
            "inferred": 0,
            "contract": 0,
            "dependency": 0,
        }

    def test_count_traversed_edges__splits_the_count_by_source(self):
        blast = BlastResult(
            traversed_edges=[
                edge("a", "REQ-1", EdgeSource.ANNOTATED),
                edge("b", "REQ-2", EdgeSource.ANNOTATED),
                edge("c", "REQ-3", EdgeSource.GIT_INFERRED),
                edge("d", "REQ-4", EdgeSource.CONTRACT),
                edge("e", "REQ-5", EdgeSource.DEPENDENCY),
            ]
        )

        assert count_traversed_edges(blast) == {
            "annotated": 2,
            "inferred": 1,
            "contract": 1,
            "dependency": 1,
        }

    def test_code_analyze__reports_no_carrying_edges_for_an_unmapped_diff(self, tmp_path):
        write_map(tmp_path / "p", "p", {f"src/mod{n}.py": [f"REQ-M-{n:03d}"] for n in range(40)})

        result = analyze_one_file({"p": tmp_path / "p"}, "CHANGELOG.md")

        assert result.traversed_edges == {
            "annotated": 0,
            "inferred": 0,
            "contract": 0,
            "dependency": 0,
        }
        assert result.edge_summary["annotated"] > 0

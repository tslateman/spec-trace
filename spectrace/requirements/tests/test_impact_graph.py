"""Tests for impact graph service."""

from requirements.services.impact_graph import (
    EdgeSource,
    GraphEdge,
    ImpactGraph,
    ImpactGraphBuilder,
)


class TestImpactGraph:
    """Tests for ImpactGraph BFS and blast radius."""

    def test_empty_graph_returns_empty_result(self):
        graph = ImpactGraph()
        result = graph.blast_radius(["some-file.py"])
        assert result.affected_requirements == []
        assert result.affected_modules == []
        assert result.affected_projects == set()
        assert result.risk_score == 0.0
        assert result.risk_level == "low"

    def test_single_hop_blast_radius(self):
        graph = ImpactGraph()
        graph.add_edge(
            GraphEdge(
                source_id="src/lore.py",
                target_id="REQ-LORE-001",
                source=EdgeSource.ANNOTATED,
                project="lore",
            )
        )
        result = graph.blast_radius(["src/lore.py"])
        assert "REQ-LORE-001" in result.affected_requirements

    def test_multi_hop_blast_radius(self):
        graph = ImpactGraph()
        graph.add_edge(
            GraphEdge(
                source_id="src/lore.py",
                target_id="src/synthesis.py",
                source=EdgeSource.ANNOTATED,
                project="lore",
            )
        )
        graph.add_edge(
            GraphEdge(
                source_id="src/synthesis.py",
                target_id="REQ-SYNTH-001",
                source=EdgeSource.ANNOTATED,
                project="praxis",
            )
        )
        result = graph.blast_radius(["src/lore.py"])
        assert "REQ-SYNTH-001" in result.affected_requirements
        assert "src/synthesis.py" in result.affected_modules

    def test_depth_limit_respected(self):
        graph = ImpactGraph()
        # Chain: a -> b -> c -> d -> REQ-DEEP (4 hops)
        graph.add_edge(GraphEdge("a", "b", EdgeSource.ANNOTATED))
        graph.add_edge(GraphEdge("b", "c", EdgeSource.ANNOTATED))
        graph.add_edge(GraphEdge("c", "d", EdgeSource.ANNOTATED))
        graph.add_edge(GraphEdge("d", "REQ-DEEP", EdgeSource.ANNOTATED))

        # max_depth=2 should not reach REQ-DEEP (4 hops away)
        result = graph.blast_radius(["a"], max_depth=2)
        assert "REQ-DEEP" not in result.affected_requirements

    def test_cross_project_edge_detection(self):
        graph = ImpactGraph()
        graph.add_edge(
            GraphEdge(
                source_id="lore:src/lore/reader.py",
                target_id="praxis:src/praxis/lore.py",
                source=EdgeSource.DEPENDENCY,
                weight=1.0,
                project="praxis",
                directed=True,
            )
        )
        graph.add_edge(
            GraphEdge(
                source_id="praxis:src/praxis/lore.py",
                target_id="praxis:REQ-PRAXIS-001",
                source=EdgeSource.ANNOTATED,
                weight=1.0,
                project="praxis",
            )
        )
        result = graph.blast_radius(["lore:src/lore/reader.py"])

        assert len(result.cross_project_edges) == 1
        assert result.cross_project_edges[0].target_id == "praxis:src/praxis/lore.py"

    def test_cross_project_edges__ignores_an_edge_inside_one_project(self):
        graph = ImpactGraph()
        graph.add_edge(
            GraphEdge(
                source_id="praxis:src/praxis/lore.py",
                target_id="praxis:REQ-PRAXIS-001",
                source=EdgeSource.ANNOTATED,
                weight=1.0,
                project="praxis",
            )
        )

        result = graph.blast_radius(["praxis:src/praxis/lore.py"])

        assert result.cross_project_edges == []

    def test_blast_radius__does_not_walk_a_directed_edge_backwards(self):
        graph = ImpactGraph()
        graph.add_edge(
            GraphEdge(
                source_id="lore:src/lore/reader.py",
                target_id="praxis:src/praxis/lore.py",
                source=EdgeSource.DEPENDENCY,
                weight=1.0,
                project="praxis",
                directed=True,
            )
        )

        forward = graph.blast_radius(["lore:src/lore/reader.py"])
        backward = graph.blast_radius(["praxis:src/praxis/lore.py"])

        assert "praxis:src/praxis/lore.py" in forward.affected_modules
        assert backward.affected_modules == []

    def test_cycle_does_not_infinite_loop(self):
        graph = ImpactGraph()
        graph.add_edge(GraphEdge("a", "b", EdgeSource.ANNOTATED))
        graph.add_edge(GraphEdge("b", "c", EdgeSource.ANNOTATED))
        graph.add_edge(GraphEdge("c", "a", EdgeSource.ANNOTATED))
        # Should terminate without error
        result = graph.blast_radius(["a"])
        assert isinstance(result.risk_score, float)

    def test_node_count(self):
        graph = ImpactGraph()
        graph.add_edge(GraphEdge("a", "b", EdgeSource.ANNOTATED))
        graph.add_edge(GraphEdge("b", "c", EdgeSource.ANNOTATED))
        assert graph.node_count == 3

    def test_edges_property(self):
        graph = ImpactGraph()
        e = GraphEdge("a", "b", EdgeSource.ANNOTATED)
        graph.add_edge(e)
        assert len(graph.edges) == 1
        assert graph.edges[0].source_id == "a"

    def test_affected_requirements_from_files(self):
        graph = ImpactGraph()
        graph.add_edge(
            GraphEdge(
                source_id="src/lore.py",
                target_id="REQ-LORE-001",
                source=EdgeSource.ANNOTATED,
            )
        )
        reqs = graph.affected_requirements(["src/lore.py"])
        assert "REQ-LORE-001" in reqs


class TestBlastResultRisk:
    """Tests for risk scoring."""

    def test_low_risk_for_small_changes(self):
        graph = ImpactGraph()
        graph.add_edge(GraphEdge("a.py", "REQ-1", EdgeSource.ANNOTATED, project="p"))
        result = graph.blast_radius(["a.py"])
        assert result.risk_level == "low"

    def test_higher_risk_for_many_affected(self):
        graph = ImpactGraph()
        for i in range(15):
            graph.add_edge(GraphEdge(f"mod_{i}.py", f"REQ-{i}", EdgeSource.ANNOTATED, project="p"))
            graph.add_edge(
                GraphEdge("trigger.py", f"mod_{i}.py", EdgeSource.ANNOTATED, project="p")
            )
        result = graph.blast_radius(["trigger.py"])
        assert result.risk_score > 0.25


class TestImpactGraphBuilder:
    """Tests for ImpactGraphBuilder."""

    def test_build_empty(self):
        builder = ImpactGraphBuilder({})
        graph = builder.build()
        assert graph.node_count == 0

    def test_build_combines_all_sources(self):
        builder = ImpactGraphBuilder({})
        annotated = [GraphEdge("a", "b", EdgeSource.ANNOTATED)]
        inferred = [GraphEdge("c", "d", EdgeSource.GIT_INFERRED)]
        contract = [GraphEdge("e", "f", EdgeSource.CONTRACT)]
        graph = builder.build(annotated, inferred, contract)
        assert len(graph.edges) == 3

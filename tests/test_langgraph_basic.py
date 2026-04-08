"""Tests for LangGraph graph structure and state schema."""

from uuid import uuid4

from app.services.graph.builder import create_skill_execution_graph
from app.services.graph.state import SkillGraphState


class TestGraphCreation:
    """Tests for graph building."""

    def test_create_graph_memory_backend(self) -> None:
        graph = create_skill_execution_graph(checkpointer_type="memory")
        assert graph is not None

    def test_graph_has_nodes(self) -> None:
        graph = create_skill_execution_graph(checkpointer_type="memory")
        graph_def = graph.get_graph()
        # Exclude __start__ and __end__
        node_names = {
            n.id if hasattr(n, "id") else str(n)
            for n in graph_def.nodes
            if str(getattr(n, "id", n)) not in ("__start__", "__end__")
        }
        assert len(node_names) > 0, "Graph should have at least one user-defined node"

    def test_graph_has_edges(self) -> None:
        graph = create_skill_execution_graph(checkpointer_type="memory")
        graph_def = graph.get_graph()
        assert len(graph_def.edges) > 0, "Graph should have edges"


class TestGraphState:
    """Tests for SkillGraphState."""

    def test_create_state(self) -> None:
        state = SkillGraphState(
            document="Test document",
            schema_id="test_schema",
            execution_id=str(uuid4()),
            vendor=None,
            model=None,
            validation_result=None,
            human_feedback=None,
            next_action=None,
        )
        assert state.status == "running"
        assert state.current_group == 1
        assert state.document == "Test document"

    def test_state_defaults(self) -> None:
        state = SkillGraphState(
            document="doc",
            schema_id="s",
            execution_id="e",
            vendor=None,
            model=None,
            validation_result=None,
            human_feedback=None,
            next_action=None,
        )
        assert state.skill_results == []
        assert state.completed_groups == []
        assert state.errors == []
        assert state.quality_score == 100
        assert state.retry_count == 0

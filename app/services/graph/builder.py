"""
LangGraph builder for skill execution workflow.

This module constructs the StateGraph that orchestrates skill execution.
"""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from app.services.graph import nodes
from app.services.graph.state import SkillGraphState


def create_skill_execution_graph(
    checkpointer_type: Literal["memory", "sqlite"] = "sqlite",
    checkpoint_db_path: str = "./data/checkpoints.db"
) -> StateGraph:
    """Create the main skill execution StateGraph.

    Args:
        checkpointer_type: Type of checkpointer to use ("memory" or "sqlite")
        checkpoint_db_path: Path to SQLite database for checkpointing

    Returns:
        Compiled StateGraph ready for execution
    """

    # Initialize the graph with our state schema
    workflow = StateGraph(SkillGraphState)

    # ===== Add all nodes =====
    workflow.add_node("initialize", nodes.initialize_execution)
    workflow.add_node("execute_group", nodes.execute_skill_group)
    workflow.add_node("merge_results", nodes.merge_skill_results)
    workflow.add_node("validate", nodes.validate_results)
    workflow.add_node("human_review", nodes.human_review_node)
    workflow.add_node("router", nodes.route_next_action)
    workflow.add_node("checkpoint", nodes.save_checkpoint)

    # ===== Define edges (execution flow) =====

    # Start with initialization
    workflow.set_entry_point("initialize")

    # After initialization, execute first group
    workflow.add_edge("initialize", "execute_group")

    # After executing group, merge results
    workflow.add_edge("execute_group", "merge_results")

    # After merging, save checkpoint
    workflow.add_edge("merge_results", "checkpoint")

    # After checkpoint, route to next action
    workflow.add_edge("checkpoint", "router")

    # Conditional routing from router
    workflow.add_conditional_edges(
        "router",
        _route_decision,
        {
            "execute_next_group": "execute_group",
            "validate": "validate",
            "human_review": "human_review",
            "retry": "execute_group",
            "complete": END
        }
    )

    # After validation, route again (might need human review)
    workflow.add_edge("validate", "router")

    # Human review creates an interrupt - execution pauses here
    # When resumed with human feedback, continue to validation
    workflow.add_edge("human_review", "validate")

    # ===== Configure checkpointer =====
    if checkpointer_type == "memory":
        checkpointer = MemorySaver()
    elif checkpointer_type == "sqlite":
        checkpointer = SqliteSaver.from_conn_string(checkpoint_db_path)
    else:
        checkpointer = MemorySaver()

    # Compile the graph
    compiled_graph = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"]  # Pause before human review
    )

    return compiled_graph


def _route_decision(state: SkillGraphState) -> str:
    """Determine which edge to take from the router node.

    This function is called by LangGraph to determine the next node
    based on the current state.

    Args:
        state: Current graph state

    Returns:
        Name of the next node to execute
    """
    next_action = state.next_action

    if next_action == "execute_next_group":
        return "execute_next_group"
    elif next_action == "retry":
        return "retry"
    elif next_action == "human_review":
        return "human_review"
    elif next_action == "complete":
        # Check if we need validation first
        if not state.validation_result:
            return "validate"
        return "complete"
    else:
        # Default to validation
        return "validate"


def create_dynamic_selection_graph(
    checkpointer_type: Literal["memory", "sqlite"] = "memory"
) -> StateGraph:
    """Create a graph variant with dynamic skill selection.

    This graph first analyzes the document to determine which
    skills are most relevant, then executes only those skills.

    Args:
        checkpointer_type: Type of checkpointer to use

    Returns:
        Compiled StateGraph with dynamic selection
    """
    workflow = StateGraph(SkillGraphState)

    workflow.add_node("initialize", nodes.initialize_execution)
    workflow.add_node("analyze", nodes.analyze_document_and_select_skills)
    workflow.add_node("execute_group", nodes.execute_skill_group)
    workflow.add_node("merge_results", nodes.merge_skill_results)
    workflow.add_node("validate", nodes.validate_results)
    workflow.add_node("router", nodes.route_next_action)

    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "analyze")
    workflow.add_edge("analyze", "execute_group")
    workflow.add_edge("execute_group", "merge_results")
    workflow.add_edge("merge_results", "router")

    workflow.add_conditional_edges(
        "router",
        _route_decision,
        {
            "execute_next_group": "execute_group",
            "validate": "validate",
            "complete": END
        }
    )

    workflow.add_edge("validate", "router")

    # Configure checkpointer
    if checkpointer_type == "memory":
        checkpointer = MemorySaver()
    else:
        checkpointer = SqliteSaver.from_conn_string("./data/checkpoints_dynamic.db")

    return workflow.compile(checkpointer=checkpointer)

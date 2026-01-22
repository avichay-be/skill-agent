"""
GraphExecutor - LangGraph-based skill execution service.

This replaces the original SkillExecutor with LangGraph orchestration.
"""

import logging
from typing import Any, AsyncIterator, Dict, Optional
from uuid import uuid4

from app.core.config import get_settings
from app.models.execution import (
    ExecutionMetadata,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
    TokenUsage,
)
from app.services.graph.builder import create_skill_execution_graph
from app.services.graph.state import SkillGraphState
from app.services.skill_registry import get_registry

logger = logging.getLogger(__name__)


class GraphExecutor:
    """Executes skills using LangGraph StateGraph orchestration.

    This executor replaces the traditional SkillExecutor with a
    LangGraph-based implementation that supports:
    - Checkpointing and resumption
    - Streaming progress updates
    - Human-in-the-loop workflows
    - Conditional branching and loops
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

        # Create the compiled graph
        self.graph = create_skill_execution_graph(
            checkpointer_type="sqlite",
            checkpoint_db_path="./data/checkpoints.db"
        )

    async def execute(self, request) -> "ExecutionResponse":
        """Execute extraction using LangGraph.

        This is the main entry point that replaces SkillExecutor.execute().

        Args:
            request: ExecutionRequest with document and skill_name

        Returns:
            ExecutionResponse with results
        """
        from uuid import uuid4

        from app.models.execution import ExecutionMetadata, ExecutionResponse, ExecutionStatus

        execution_id = str(uuid4())

        # Create initial state
        initial_state = SkillGraphState(
            document=request.document,
            schema_id=request.skill_name,
            execution_id=execution_id,
            vendor=request.vendor,
            model=request.model
        )

        try:
            # Run the graph
            config = {"configurable": {"thread_id": execution_id}}

            final_state = await self.graph.ainvoke(
                initial_state.model_dump(),
                config=config
            )

            # Convert graph state to ExecutionResponse
            return self._state_to_response(final_state, request.skill_name)

        except Exception as e:
            logger.exception(f"Graph execution failed: {e}")
            return ExecutionResponse(
                status=ExecutionStatus.FAILED,
                skill_name=request.skill_name,
                error=str(e),
                metadata=ExecutionMetadata()
            )

    async def execute_streaming(
        self,
        request: ExecutionRequest
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute with streaming progress updates.

        This yields progress events as the graph executes, enabling
        real-time UI updates.

        Args:
            request: ExecutionRequest with document and skill_name

        Yields:
            Progress event dictionaries
        """
        execution_id = str(uuid4())

        initial_state = SkillGraphState(
            document=request.document,
            schema_id=request.skill_name,
            execution_id=execution_id,
            vendor=request.vendor,
            model=request.model
        )

        config = {"configurable": {"thread_id": execution_id}}

        # Stream updates from the graph
        async for event in self.graph.astream(
            initial_state.model_dump(),
            config=config
        ):
            # Each event contains the node name and updated state
            node_name = list(event.keys())[0]
            node_state = event[node_name]

            # Yield progress event
            yield {
                "type": "node_completed",
                "node": node_name,
                "progress": node_state.get("progress_events", []),
                "status": node_state.get("status", "running"),
                "execution_id": execution_id
            }

    async def resume_execution(
        self,
        execution_id: str,
        human_feedback: Optional[Dict[str, Any]] = None
    ) -> ExecutionResponse:
        """Resume a paused execution (e.g., after human review).

        This leverages LangGraph's checkpointing to resume from where
        the execution was interrupted.

        Args:
            execution_id: ID of the execution to resume
            human_feedback: Optional feedback from human reviewer

        Returns:
            ExecutionResponse with final results
        """
        config = {"configurable": {"thread_id": execution_id}}

        # Update state with human feedback if provided
        if human_feedback:
            update = {"human_feedback": human_feedback, "human_review_required": False}
            await self.graph.aupdate_state(config, update)

        # Resume execution
        final_state = await self.graph.ainvoke(None, config=config)

        # Convert to response
        schema_id = final_state.get("schema_id", "unknown")
        return self._state_to_response(final_state, schema_id)

    def _state_to_response(
        self,
        state: Dict[str, Any],
        skill_name: str
    ) -> ExecutionResponse:
        """Convert graph state to ExecutionResponse.

        Args:
            state: Final graph state
            skill_name: Name of the skill/schema executed

        Returns:
            ExecutionResponse formatted for API
        """
        registry = get_registry()
        schema = registry.get_schema_or_raise(skill_name)

        # Determine status
        if state.get("status") == "completed":
            skill_results = state.get("skill_results", [])
            failed = [r for r in skill_results if not r.success]

            if len(failed) == len(skill_results) and len(skill_results) > 0:
                status = ExecutionStatus.FAILED
            elif failed:
                status = ExecutionStatus.PARTIAL
            else:
                status = ExecutionStatus.COMPLETED
        elif state.get("status") == "paused":
            status = ExecutionStatus.PENDING
        else:
            status = ExecutionStatus.FAILED

        # Build metadata
        started_at = state.get("started_at")
        completed_at = state.get("completed_at")

        token_usage_dict = state.get("token_usage", {})
        token_usage = TokenUsage(
            input_tokens=token_usage_dict.get("input_tokens", 0),
            output_tokens=token_usage_dict.get("output_tokens", 0),
            total_tokens=token_usage_dict.get("total_tokens", 0)
        )

        processing_time_ms = None
        if started_at and completed_at:
            processing_time_ms = int(
                (completed_at - started_at).total_seconds() * 1000
            )

        skill_results = state.get("skill_results", [])

        metadata = ExecutionMetadata(
            execution_id=state.get("execution_id"),
            started_at=started_at,
            completed_at=completed_at,
            token_usage=token_usage,
            processing_time_ms=processing_time_ms,
            git_commit=schema.git_commit,
            schema_version=schema.config.version,
            token_usage_by_skill={
                r.skill_id: TokenUsage(**r.token_usage)
                for r in skill_results if r.token_usage
            },
            models_used=list(set(r.model_used for r in skill_results)),
            vendors_used=list(set(r.vendor_used for r in skill_results))
        )

        # Get errors from failed skills
        failed_skills = [r for r in skill_results if not r.success]
        error_msg = None
        if failed_skills:
            error_msg = "; ".join(r.error or "" for r in failed_skills)
        elif state.get("errors"):
            error_msg = "; ".join(state.get("errors", []))

        return ExecutionResponse(
            status=status,
            skill_name=skill_name,
            data=state.get("merged_data"),
            validation=state.get("validation_result"),
            metadata=metadata,
            skill_results=skill_results,
            error=error_msg
        )


def get_graph_executor() -> GraphExecutor:
    """Get graph executor instance for dependency injection.

    Returns:
        GraphExecutor instance
    """
    return GraphExecutor()

"""Workflow Executor - Chains multiple schemas sequentially."""

import json
import logging
import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from app.models.execution import ExecutionRequest, ExecutionResponse, ExecutionStatus, TokenUsage
from app.models.workflow import (
    LoadedWorkflow,
    OnFailure,
    WorkflowConfig,
    WorkflowExecutionMetadata,
    WorkflowExecutionRequest,
    WorkflowExecutionResponse,
    WorkflowExecutionStatus,
    WorkflowStepConfig,
    WorkflowStepResult,
)
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)


class WorkflowExecutorError(Exception):
    """Error during workflow execution."""


class WorkflowExecutor:
    """Executes workflows by chaining schema executions sequentially."""

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or get_registry()

    def resolve_workflow(self, request: WorkflowExecutionRequest) -> LoadedWorkflow:
        """Resolve a saved or ephemeral workflow from the request."""
        if request.workflow_id and request.schema_ids:
            raise WorkflowExecutorError("Provide either workflow_id or schema_ids, not both")

        if request.schema_ids:
            return self._build_composed_workflow(request)

        if not request.workflow_id:
            raise WorkflowExecutorError("Either workflow_id or schema_ids must be provided")

        loaded_workflow = self.registry.get_workflow(request.workflow_id)
        if not loaded_workflow:
            raise WorkflowExecutorError(f"Workflow '{request.workflow_id}' not found")
        return loaded_workflow

    def _build_composed_workflow(self, request: WorkflowExecutionRequest) -> LoadedWorkflow:
        """Build an ephemeral workflow from a list of schema IDs."""
        schema_ids = request.schema_ids or []
        if len(schema_ids) < 2:
            raise WorkflowExecutorError("Dynamic workflows require at least 2 schema_ids")

        missing = [schema_id for schema_id in schema_ids if not self.registry.get_schema(schema_id)]
        if missing:
            raise WorkflowExecutorError(f"Workflow references missing schemas: {missing}")

        workflow_id = self._build_composed_workflow_id(schema_ids)
        workflow_name = request.workflow_name or f"Composed workflow: {' -> '.join(schema_ids)}"
        workflow_description = (
            request.workflow_description
            or "Ephemeral workflow generated from the requested schema sequence."
        )
        steps = [
            WorkflowStepConfig(
                step_id=f"step_{idx + 1}_{self._slugify(schema_id)}",
                schema_id=schema_id,
                name=f"Run {schema_id}",
            )
            for idx, schema_id in enumerate(schema_ids)
        ]

        return LoadedWorkflow(
            config=WorkflowConfig(
                workflow_id=workflow_id,
                version="dynamic",
                name=workflow_name,
                description=workflow_description,
                steps=steps,
            ),
            git_commit=self.registry.current_commit or "dynamic",
            source_path="dynamic:composed",
        )

    def _build_composed_workflow_id(self, schema_ids: list[str]) -> str:
        """Build a stable identifier for an ephemeral composed workflow."""
        return "dynamic--" + "--".join(self._slugify(schema_id) for schema_id in schema_ids)

    def _slugify(self, value: str) -> str:
        """Convert identifiers into workflow-safe slugs."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
        return slug or "schema"

    async def execute(self, request: WorkflowExecutionRequest) -> WorkflowExecutionResponse:
        """Execute a workflow by running each step sequentially.

        The JSON output of each step is serialized to text and becomes the
        document input for the next step.

        Args:
            request: Workflow execution request.

        Returns:
            WorkflowExecutionResponse with all step results.
        """
        loaded_workflow = self.resolve_workflow(request)
        config = loaded_workflow.config
        execution_id = str(uuid4())
        start_time = time.monotonic()
        started_at = datetime.now(timezone.utc)

        step_results: list[WorkflowStepResult] = []
        current_doc = request.document
        last_successful_data: dict[str, object] | None = None
        total_input_tokens = 0
        total_output_tokens = 0
        total_total_tokens = 0
        final_status = WorkflowExecutionStatus.COMPLETED
        error_msg: str | None = None

        logger.info(
            f"Starting workflow '{config.workflow_id}' ({config.name}), "
            f"{len(config.steps)} steps, execution_id={execution_id}"
        )

        for idx, step in enumerate(config.steps):
            logger.info(
                f"Workflow step {idx + 1}/{len(config.steps)}: "
                f"'{step.name}' (schema={step.schema_id})"
            )

            exec_request = ExecutionRequest(
                document=current_doc,
                skill_name=step.schema_id,
                vendor=request.vendor,
                model=request.model,
                options=request.options,
                save_to_cosmos=request.save_to_cosmos,
            )

            try:
                from app.services.graph_executor import get_graph_executor

                response = await get_graph_executor().execute(exec_request)
            except Exception as e:
                logger.error(f"Workflow step '{step.step_id}' raised exception: {e}")
                response = ExecutionResponse(
                    status=ExecutionStatus.FAILED,
                    skill_name=step.schema_id,
                    error=str(e),
                )

            step_result = WorkflowStepResult(
                step_id=step.step_id,
                schema_id=step.schema_id,
                step_index=idx,
                execution_response=response,
            )
            step_results.append(step_result)

            # Accumulate token usage
            usage = response.metadata.token_usage
            total_input_tokens += usage.input_tokens
            total_output_tokens += usage.output_tokens
            total_total_tokens += usage.total_tokens

            step_succeeded = response.status in (
                ExecutionStatus.COMPLETED,
                ExecutionStatus.PARTIAL,
            )

            if step_succeeded:
                if response.data is not None:
                    last_successful_data = response.data
                    current_doc = json.dumps(response.data, ensure_ascii=False)
                logger.info(f"Workflow step '{step.step_id}' completed successfully")
            else:
                logger.warning(f"Workflow step '{step.step_id}' failed: {response.error}")
                if step.on_failure == OnFailure.STOP:
                    final_status = WorkflowExecutionStatus.FAILED
                    error_msg = (
                        f"Step '{step.step_id}' failed and on_failure=stop: {response.error}"
                    )
                    break
                else:
                    # on_failure=continue: keep previous current_doc, move on
                    final_status = WorkflowExecutionStatus.PARTIAL
                    logger.info(
                        f"Continuing workflow despite step '{step.step_id}' failure "
                        f"(on_failure=continue)"
                    )

        completed_at = datetime.now(timezone.utc)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        metadata = WorkflowExecutionMetadata(
            execution_id=execution_id,
            workflow_id=config.workflow_id,
            started_at=started_at,
            completed_at=completed_at,
            processing_time_ms=elapsed_ms,
            total_token_usage=TokenUsage(
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                total_tokens=total_total_tokens,
            ),
            steps_completed=len(step_results),
            steps_total=len(config.steps),
            git_commit=loaded_workflow.git_commit,
        )

        return WorkflowExecutionResponse(
            status=final_status,
            workflow_id=config.workflow_id,
            workflow_name=config.name,
            data=last_successful_data,
            metadata=metadata,
            step_results=step_results,
            error=error_msg,
        )


def get_workflow_executor() -> WorkflowExecutor:
    """Get workflow executor instance for dependency injection."""
    return WorkflowExecutor()

"""
LangGraph node implementations for skill execution.

Each node is a function that takes state and returns updated state.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, cast

from app.core.config import get_settings
from app.models.skill import Skill, SkillExecutionResult
from app.services.execution_utils import (
    deep_merge as _deep_merge_impl,
)
from app.services.execution_utils import (
    execute_single_skill as _execute_single_skill_impl,
)
from app.services.execution_utils import (
    get_default_model_for_vendor as _get_default_model_for_vendor_impl,
)
from app.services.execution_utils import (
    get_nested_value as _get_nested_value_impl,
)
from app.services.execution_utils import (
    merge_results,
    validate_output,
)
from app.services.execution_utils import (
    run_validation_rule as _run_validation_rule_impl,
)
from app.services.graph.state import SkillGraphState
from app.services.llm_client import LLMClientFactory
from app.services.skill_registry import get_registry

logger = logging.getLogger(__name__)


def _state_get(state: SkillGraphState | dict[str, Any], key: str, default: Any = None) -> Any:
    """Read state values from either a dict or SkillGraphState instance."""
    if isinstance(state, SkillGraphState):
        return getattr(state, key, default)
    return state.get(key, default)


def _item_get(value: Any, key: str, default: Any = None) -> Any:
    """Read values from either a dict or an object with attributes."""
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


# ===== 1. Initialization Node =====
async def initialize_execution(state: SkillGraphState | dict[str, Any]) -> dict[str, Any]:
    """Initialize execution by loading schema and planning execution.

    This node:
    - Loads the schema from registry
    - Gets all active skills
    - Groups skills by parallel_group
    - Sets up the execution plan
    """
    registry = get_registry()
    schema = registry.get_schema_or_raise(_state_get(state, "schema_id"))

    # Get active skills grouped by parallel_group
    skills_by_group = schema.get_skills_by_group()
    active_skills = schema.get_active_skills()

    # Determine execution order
    groups = sorted(skills_by_group.keys())

    logger.info(f"Initialized execution: {len(active_skills)} skills in {len(groups)} groups")

    return {
        "pending_skills": [s.id for s in active_skills],
        "current_group": groups[0] if groups else 1,
        "status": "running",
        "progress_events": [
            {
                "type": "execution_started",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_skills": len(active_skills),
                "groups": groups,
            }
        ],
    }


# ===== 2. Parallel Skill Execution Node =====
async def execute_skill_group(state: SkillGraphState | dict[str, Any]) -> dict[str, Any]:
    """Execute all skills in the current parallel group concurrently.

    This is the core execution node that maintains backward compatibility
    with the current parallel_group concept.
    """
    registry = get_registry()
    settings = get_settings()
    schema = registry.get_schema_or_raise(_state_get(state, "schema_id"))

    # Get skills for current group
    skills_by_group = schema.get_skills_by_group()
    current_group = _state_get(state, "current_group")
    current_skills = skills_by_group.get(current_group, [])

    logger.info(f"Executing group {current_group} with {len(current_skills)} skills")

    # Determine default vendor and model
    vendor = _state_get(state, "vendor") or settings.default_vendor
    model = _state_get(state, "model")

    # Execute skills in parallel using asyncio.gather
    tasks = [
        _execute_single_skill(
            skill=skill,
            document=_state_get(state, "document"),
            default_vendor=vendor,
            default_model=model,
            settings=settings,
        )
        for skill in current_skills
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    skill_results = []
    for skill, result in zip(current_skills, results):
        if isinstance(result, Exception):
            skill_results.append(
                SkillExecutionResult(
                    skill_id=skill.id,
                    success=False,
                    error=str(result),
                    execution_time_ms=0,
                    model_used="unknown",
                    vendor_used="unknown",
                )
            )
        else:
            skill_results.append(cast(SkillExecutionResult, result))

    # Calculate token usage
    total_tokens = sum(
        r.token_usage.get("total_tokens", 0) for r in skill_results if r.success and r.token_usage
    )

    current_token_usage = _state_get(state, "token_usage", {})
    if hasattr(current_token_usage, "model_dump"):
        current_token_usage = current_token_usage.model_dump()
    updated_token_usage = {
        "input_tokens": current_token_usage.get("input_tokens", 0)
        + sum(
            r.token_usage.get("input_tokens", 0)
            for r in skill_results
            if r.success and r.token_usage
        ),
        "output_tokens": current_token_usage.get("output_tokens", 0)
        + sum(
            r.token_usage.get("output_tokens", 0)
            for r in skill_results
            if r.success and r.token_usage
        ),
        "total_tokens": current_token_usage.get("total_tokens", 0) + total_tokens,
    }

    return {
        "skill_results": skill_results,
        "completed_groups": [current_group],
        "token_usage": updated_token_usage,
        "progress_events": [
            {
                "type": "group_completed",
                "group": current_group,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "successful_results": len([r for r in skill_results if r.success]),
                "total_results": len(skill_results),
            }
        ],
    }


# ===== 3. Merge Results Node =====
async def merge_skill_results(state: SkillGraphState | dict[str, Any]) -> dict[str, Any]:
    """Merge skill results according to schema strategy.

    Applies MERGE_DEEP, FIRST_WINS, or LAST_WINS strategy.
    """
    registry = get_registry()
    schema = registry.get_schema_or_raise(_state_get(state, "schema_id"))
    strategy = schema.config.post_processing.merge_strategy

    # Get only successful results with data
    new_results = [r for r in _state_get(state, "skill_results", []) if r.success and r.data]
    merged = merge_results(new_results, strategy, initial=_state_get(state, "merged_data", {}))

    return {
        "merged_data": merged,
        "progress_events": [
            {
                "type": "merge_completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fields": len(merged),
                "strategy": strategy.value,
            }
        ],
    }


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    return _deep_merge_impl(base, update)


async def _execute_single_skill(
    skill: Skill,
    document: str,
    default_vendor: str,
    default_model: str | None,
    settings: Any,
) -> SkillExecutionResult:
    """Execute a single skill with shared retry logic."""
    return await _execute_single_skill_impl(
        skill, document, default_vendor, default_model, settings
    )


def _get_default_model_for_vendor(vendor: str, settings: Any) -> str:
    """Get the default model for a specific vendor."""
    return _get_default_model_for_vendor_impl(vendor, settings)


def _run_validation_rule(rule: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Run a single validation rule."""
    return _run_validation_rule_impl(rule, data)


def _get_nested_value(data: dict[str, Any], path: str) -> Any | None:
    """Get a nested value from a dictionary using dot notation."""
    return _get_nested_value_impl(data, path)


# ===== 4. Validation Node =====
async def validate_results(state: SkillGraphState | dict[str, Any]) -> dict[str, Any]:
    """Validate merged results against schema rules.

    Runs Pydantic validation and custom validation rules.
    """
    registry = get_registry()
    schema = registry.get_schema_or_raise(_state_get(state, "schema_id"))
    merged_data = _state_get(state, "merged_data", {})
    validation = validate_output(merged_data, schema)

    # Determine if human review is needed
    human_review = validation.status == "FAIL" and len(validation.errors) > 0

    return {
        "validation_result": validation,
        "quality_score": validation.quality_score,
        "human_review_required": human_review,
        "progress_events": [
            {
                "type": "validation_completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": validation.status,
                "errors": len(validation.errors),
                "warnings": len(validation.warnings),
            }
        ],
    }


# ===== 5. Human Review Node =====
async def human_review_node(state: SkillGraphState | dict[str, Any]) -> dict[str, Any]:
    """Pause execution for human review.

    This node creates an interrupt that pauses the graph until
    a human reviewer provides feedback via update_state().
    """
    logger.info(f"Pausing execution {_state_get(state, 'execution_id')} for human review")

    validation_result = _state_get(state, "validation_result")

    return {
        "status": "paused",
        "progress_events": [
            {
                "type": "human_review_requested",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "reason": "validation_failed",
                "errors": _item_get(validation_result, "errors", []) if validation_result else [],
            }
        ],
    }


# ===== 6. Conditional Router Node =====
async def route_next_action(state: SkillGraphState | dict[str, Any]) -> dict[str, Any]:
    """Determine the next action based on current state.

    This enables conditional branching:
    - If more groups to execute -> continue to next group
    - If validation failed and retries available -> retry
    - If human review required -> pause
    - Otherwise -> complete
    """
    registry = get_registry()
    schema = registry.get_schema_or_raise(_state_get(state, "schema_id"))
    skills_by_group = schema.get_skills_by_group()
    all_groups = sorted(skills_by_group.keys())

    # Check if more groups to execute
    completed_groups = _state_get(state, "completed_groups", [])
    remaining_groups = [g for g in all_groups if g not in completed_groups]

    if remaining_groups:
        next_action = "execute_next_group"
        next_group = remaining_groups[0]
        return {"next_action": next_action, "current_group": next_group}

    # All groups completed - check validation
    validation_result = _state_get(state, "validation_result")
    if validation_result:
        if _item_get(validation_result, "status") == "FAIL":
            retry_count = _state_get(state, "retry_count", 0)
            max_retries = _state_get(state, "max_retries", 2)

            if retry_count < max_retries:
                return {
                    "next_action": "retry",
                    "should_retry": True,
                    "retry_count": retry_count + 1,
                }
            elif _state_get(state, "human_review_required", False):
                return {"next_action": "human_review"}

    return {
        "next_action": "complete",
        "status": "completed",
        "completed_at": datetime.now(timezone.utc),
    }


# ===== 7. Checkpoint Node =====
async def save_checkpoint(state: SkillGraphState | dict[str, Any]) -> dict[str, Any]:
    """Save execution checkpoint for recovery.

    LangGraph handles this automatically with the checkpointer,
    but we can also add custom checkpoint logic here.
    """
    logger.info(f"Checkpoint saved for execution {_state_get(state, 'execution_id')}")

    return {
        "progress_events": [
            {
                "type": "checkpoint_saved",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "current_group": _state_get(state, "current_group"),
                "completed_groups": _state_get(state, "completed_groups", []),
            }
        ]
    }


# ===== 8. Dynamic Skill Selection Node (Optional) =====
async def analyze_document_and_select_skills(
    state: SkillGraphState | dict[str, Any],
) -> dict[str, Any]:
    """Analyze document to dynamically select which skills to run.

    This is a new capability enabled by LangGraph - we can use an LLM
    to analyze the document and decide which skills are most relevant.
    """
    settings = get_settings()
    registry = get_registry()
    schema = registry.get_schema_or_raise(_state_get(state, "schema_id"))

    # Use a fast model for document analysis
    client = LLMClientFactory.get_client("gemini", "gemini-2.0-flash-exp", settings)

    # Get available skills
    available_skills = schema.get_active_skills()
    skill_descriptions = "\n".join([f"- {s.id}: {s.name}" for s in available_skills])

    analysis_prompt = f"""Analyze this document and determine which extraction skills are most relevant.

Available skills:
{skill_descriptions}

Document preview (first 1000 chars):
{_state_get(state, "document")[:1000]}

Return a JSON object with:
{{
    "relevant_skills": ["skill_id1", "skill_id2", ...],
    "reasoning": "Brief explanation of why these skills were selected"
}}
"""

    result, _ = await client.extract_json(
        "You are a document analysis expert.", analysis_prompt, temperature=0.0
    )

    selected_skill_ids = result.get("relevant_skills", [])

    logger.info(
        f"Dynamic selection: {len(selected_skill_ids)}/{len(available_skills)} skills selected"
    )

    return {
        "pending_skills": selected_skill_ids,
        "progress_events": [
            {
                "type": "skills_selected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "selected": selected_skill_ids,
                "reasoning": result.get("reasoning", ""),
            }
        ],
    }

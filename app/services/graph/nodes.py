"""
LangGraph node implementations for skill execution.

Each node is a function that takes state and returns updated state.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.models.schema import MergeStrategy
from app.models.skill import Skill, SkillExecutionResult
from app.services.llm_client import LLMClientError, LLMClientFactory
from app.services.skill_registry import get_registry

logger = logging.getLogger(__name__)


# ===== 1. Initialization Node =====
async def initialize_execution(state: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize execution by loading schema and planning execution.

    This node:
    - Loads the schema from registry
    - Gets all active skills
    - Groups skills by parallel_group
    - Sets up the execution plan
    """
    registry = get_registry()
    schema = registry.get_schema_or_raise(state["schema_id"])

    # Get active skills grouped by parallel_group
    skills_by_group = schema.get_skills_by_group()
    active_skills = schema.get_active_skills()

    # Determine execution order
    groups = sorted(skills_by_group.keys())

    logger.info(
        f"Initialized execution: {len(active_skills)} skills in {len(groups)} groups"
    )

    return {
        "pending_skills": [s.id for s in active_skills],
        "current_group": groups[0] if groups else 1,
        "status": "running",
        "progress_events": [{
            "type": "execution_started",
            "timestamp": datetime.utcnow().isoformat(),
            "total_skills": len(active_skills),
            "groups": groups
        }]
    }


# ===== 2. Parallel Skill Execution Node =====
async def execute_skill_group(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute all skills in the current parallel group concurrently.

    This is the core execution node that maintains backward compatibility
    with the current parallel_group concept.
    """
    registry = get_registry()
    settings = get_settings()
    schema = registry.get_schema_or_raise(state["schema_id"])

    # Get skills for current group
    skills_by_group = schema.get_skills_by_group()
    current_skills = skills_by_group.get(state["current_group"], [])

    logger.info(
        f"Executing group {state['current_group']} with {len(current_skills)} skills"
    )

    # Determine default vendor and model
    vendor = state.get("vendor") or settings.default_vendor
    model = state.get("model")

    # Execute skills in parallel using asyncio.gather
    tasks = [
        _execute_single_skill(
            skill=skill,
            document=state["document"],
            vendor=vendor,
            model=model,
            settings=settings
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
                    vendor_used="unknown"
                )
            )
        else:
            skill_results.append(result)

    # Calculate token usage
    total_tokens = sum(
        r.token_usage.get("total_tokens", 0)
        for r in skill_results if r.success and r.token_usage
    )

    current_token_usage = state.get("token_usage", {})
    updated_token_usage = {
        "input_tokens": current_token_usage.get("input_tokens", 0) + sum(
            r.token_usage.get("input_tokens", 0)
            for r in skill_results if r.success and r.token_usage
        ),
        "output_tokens": current_token_usage.get("output_tokens", 0) + sum(
            r.token_usage.get("output_tokens", 0)
            for r in skill_results if r.success and r.token_usage
        ),
        "total_tokens": current_token_usage.get("total_tokens", 0) + total_tokens
    }

    return {
        "skill_results": skill_results,
        "completed_groups": [state["current_group"]],
        "token_usage": updated_token_usage,
        "progress_events": [{
            "type": "group_completed",
            "group": state["current_group"],
            "timestamp": datetime.utcnow().isoformat(),
            "successful_results": len([r for r in skill_results if r.success]),
            "total_results": len(skill_results)
        }]
    }


async def _execute_single_skill(
    skill: Skill,
    document: str,
    vendor: str,
    model: Optional[str],
    settings
) -> SkillExecutionResult:
    """Execute a single skill with retries.

    This function replicates the logic from SkillExecutor._execute_single_skill
    """
    effective_vendor = skill.get_effective_vendor(vendor)
    effective_model = skill.get_effective_model(model)

    # Get default model for vendor if not specified
    if not effective_model or effective_model == "":
        effective_model = _get_default_model_for_vendor(effective_vendor, settings)
        logger.info(f"Resolved model to {effective_model} for vendor {effective_vendor}")

    start_time = time.time()
    last_error: Optional[str] = None
    retries = 0

    for attempt in range(skill.config.retry_count + 1):
        try:
            client = LLMClientFactory.get_client(effective_vendor, effective_model, settings)

            # Execute with timeout
            data, usage = await asyncio.wait_for(
                client.extract_json(
                    skill.prompt,
                    document,
                    temperature=skill.config.temperature,
                ),
                timeout=skill.config.timeout_seconds
            )

            execution_time = int((time.time() - start_time) * 1000)

            logger.info(
                f"Skill '{skill.id}' completed in {execution_time}ms "
                f"(tokens: {usage.total_tokens})"
            )

            return SkillExecutionResult(
                skill_id=skill.id,
                success=True,
                data=data,
                token_usage=usage.model_dump(),
                execution_time_ms=execution_time,
                model_used=effective_model or "default",
                vendor_used=effective_vendor,
                retries=retries,
            )

        except asyncio.TimeoutError:
            last_error = f"Timeout after {skill.config.timeout_seconds}s"
            retries = attempt + 1
            logger.warning(f"Skill '{skill.id}' timed out, attempt {retries}")

        except LLMClientError as e:
            last_error = str(e)
            retries = attempt + 1
            logger.warning(f"Skill '{skill.id}' failed: {e}, attempt {retries}")

        except Exception as e:
            last_error = str(e)
            retries = attempt + 1
            logger.exception(f"Skill '{skill.id}' unexpected error: {e}")

        # Small delay before retry
        if attempt < skill.config.retry_count:
            await asyncio.sleep(1 * (attempt + 1))

    # All retries exhausted
    execution_time = int((time.time() - start_time) * 1000)
    return SkillExecutionResult(
        skill_id=skill.id,
        success=False,
        error=last_error,
        execution_time_ms=execution_time,
        model_used=effective_model or "default",
        vendor_used=effective_vendor,
        retries=retries,
    )


def _get_default_model_for_vendor(vendor: str, settings) -> str:
    """Get the default model for a specific vendor."""
    vendor_lower = vendor.lower()

    if vendor_lower == "anthropic":
        return settings.anthropic_model
    elif vendor_lower == "openai":
        return settings.openai_model
    elif vendor_lower == "gemini":
        return settings.gemini_model
    else:
        logger.warning(f"Unknown vendor '{vendor}', defaulting to Anthropic")
        return settings.anthropic_model


# ===== 3. Merge Results Node =====
async def merge_skill_results(state: Dict[str, Any]) -> Dict[str, Any]:
    """Merge skill results according to schema strategy.

    Applies MERGE_DEEP, FIRST_WINS, or LAST_WINS strategy.
    """
    registry = get_registry()
    schema = registry.get_schema_or_raise(state["schema_id"])
    strategy = schema.config.post_processing.merge_strategy

    merged = state.get("merged_data", {}).copy()

    # Get only successful results with data
    new_results = [
        r for r in state.get("skill_results", [])
        if r.success and r.data
    ]

    for result in new_results:
        if strategy == MergeStrategy.FIRST_WINS:
            # Only add keys that don't exist
            for key, value in result.data.items():
                if key not in merged:
                    merged[key] = value

        elif strategy == MergeStrategy.LAST_WINS:
            # Overwrite existing keys
            merged.update(result.data)

        elif strategy == MergeStrategy.MERGE_DEEP:
            # Deep merge
            merged = _deep_merge(merged, result.data)

    return {
        "merged_data": merged,
        "progress_events": [{
            "type": "merge_completed",
            "timestamp": datetime.utcnow().isoformat(),
            "fields": len(merged),
            "strategy": strategy.value
        }]
    }


def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()

    for key, value in update.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


# ===== 4. Validation Node =====
async def validate_results(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validate merged results against schema rules.

    Runs Pydantic validation and custom validation rules.
    """
    registry = get_registry()
    schema = registry.get_schema_or_raise(state["schema_id"])
    merged_data = state.get("merged_data", {})

    errors: List[str] = []
    warnings: List[str] = []
    checks: List[Dict[str, Any]] = []

    # Validate against Pydantic model if available
    if schema.output_model:
        try:
            schema.output_model(**merged_data)
            checks.append({
                "name": "pydantic_validation",
                "status": "passed",
            })
        except Exception as e:
            errors.append(f"Pydantic validation failed: {e}")
            checks.append({
                "name": "pydantic_validation",
                "status": "failed",
                "error": str(e),
            })

    # Run custom validation rules
    for rule in schema.config.post_processing.validation_rules:
        check_result = _run_validation_rule(rule, merged_data)
        checks.append(check_result)

        if check_result["status"] == "failed":
            if rule.severity == "error":
                errors.append(f"{rule.name}: {check_result.get('error', 'Failed')}")
            else:
                warnings.append(f"{rule.name}: {check_result.get('error', 'Warning')}")

    # Calculate quality score
    quality_score = 100 - (len(errors) * 15) - (len(warnings) * 5)
    quality_score = max(0, min(100, quality_score))

    # Determine status
    if errors:
        status = "FAIL"
    elif warnings:
        status = "REVIEW"
    else:
        status = "PASS"

    from app.models.execution import ValidationResult
    validation = ValidationResult(
        status=status,
        quality_score=quality_score,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )

    # Determine if human review is needed
    human_review = status == "FAIL" and len(errors) > 0

    return {
        "validation_result": validation,
        "quality_score": quality_score,
        "human_review_required": human_review,
        "progress_events": [{
            "type": "validation_completed",
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "errors": len(errors),
            "warnings": len(warnings)
        }]
    }


def _run_validation_rule(rule, data: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single validation rule."""
    try:
        if rule.type == "sum_check":
            expected_field = rule.params.get("expected")
            operands = rule.params.get("operands", [])

            expected_value = _get_nested_value(data, expected_field)
            calculated = 0

            for op in operands:
                if op.startswith("-"):
                    calculated -= _get_nested_value(data, op[1:]) or 0
                else:
                    calculated += _get_nested_value(data, op) or 0

            if expected_value == calculated:
                return {"name": rule.name, "status": "passed"}
            else:
                return {
                    "name": rule.name,
                    "status": "failed",
                    "error": f"Expected {expected_value}, calculated {calculated}",
                }

        elif rule.type == "required":
            fields = rule.params.get("fields", [])
            missing = [
                f for f in fields if _get_nested_value(data, f) is None
            ]

            if missing:
                return {
                    "name": rule.name,
                    "status": "failed",
                    "error": f"Missing fields: {missing}",
                }
            return {"name": rule.name, "status": "passed"}

        elif rule.type == "range_check":
            field = rule.params.get("field")
            min_val = rule.params.get("min")
            max_val = rule.params.get("max")

            value = _get_nested_value(data, field)

            if value is None:
                return {"name": rule.name, "status": "skipped", "reason": "Field not found"}

            if (min_val is not None and value < min_val) or (
                max_val is not None and value > max_val
            ):
                return {
                    "name": rule.name,
                    "status": "failed",
                    "error": f"Value {value} outside range [{min_val}, {max_val}]",
                }
            return {"name": rule.name, "status": "passed"}

        else:
            return {"name": rule.name, "status": "skipped", "reason": f"Unknown rule type: {rule.type}"}

    except Exception as e:
        return {"name": rule.name, "status": "error", "error": str(e)}


def _get_nested_value(data: Dict[str, Any], path: str) -> Optional[Any]:
    """Get a nested value from a dictionary using dot notation."""
    parts = path.split(".")
    current = data

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current


# ===== 5. Human Review Node =====
async def human_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pause execution for human review.

    This node creates an interrupt that pauses the graph until
    a human reviewer provides feedback via update_state().
    """
    logger.info(f"Pausing execution {state['execution_id']} for human review")

    return {
        "status": "paused",
        "progress_events": [{
            "type": "human_review_requested",
            "timestamp": datetime.utcnow().isoformat(),
            "reason": "validation_failed",
            "errors": state.get("validation_result", {}).get("errors", []) if state.get("validation_result") else []
        }]
    }


# ===== 6. Conditional Router Node =====
async def route_next_action(state: Dict[str, Any]) -> Dict[str, Any]:
    """Determine the next action based on current state.

    This enables conditional branching:
    - If more groups to execute -> continue to next group
    - If validation failed and retries available -> retry
    - If human review required -> pause
    - Otherwise -> complete
    """
    registry = get_registry()
    schema = registry.get_schema_or_raise(state["schema_id"])
    skills_by_group = schema.get_skills_by_group()
    all_groups = sorted(skills_by_group.keys())

    # Check if more groups to execute
    completed_groups = state.get("completed_groups", [])
    remaining_groups = [g for g in all_groups if g not in completed_groups]

    if remaining_groups:
        next_action = "execute_next_group"
        next_group = remaining_groups[0]
        return {
            "next_action": next_action,
            "current_group": next_group
        }

    # All groups completed - check validation
    validation_result = state.get("validation_result")
    if validation_result:
        if validation_result.status == "FAIL":
            retry_count = state.get("retry_count", 0)
            max_retries = state.get("max_retries", 2)

            if retry_count < max_retries:
                return {
                    "next_action": "retry",
                    "should_retry": True,
                    "retry_count": retry_count + 1
                }
            elif state.get("human_review_required", False):
                return {
                    "next_action": "human_review"
                }

    return {
        "next_action": "complete",
        "status": "completed",
        "completed_at": datetime.utcnow()
    }


# ===== 7. Checkpoint Node =====
async def save_checkpoint(state: Dict[str, Any]) -> Dict[str, Any]:
    """Save execution checkpoint for recovery.

    LangGraph handles this automatically with the checkpointer,
    but we can also add custom checkpoint logic here.
    """
    logger.info(f"Checkpoint saved for execution {state['execution_id']}")

    return {
        "progress_events": [{
            "type": "checkpoint_saved",
            "timestamp": datetime.utcnow().isoformat(),
            "current_group": state.get("current_group"),
            "completed_groups": state.get("completed_groups", [])
        }]
    }


# ===== 8. Dynamic Skill Selection Node (Optional) =====
async def analyze_document_and_select_skills(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze document to dynamically select which skills to run.

    This is a new capability enabled by LangGraph - we can use an LLM
    to analyze the document and decide which skills are most relevant.
    """
    settings = get_settings()
    registry = get_registry()
    schema = registry.get_schema_or_raise(state["schema_id"])

    # Use a fast model for document analysis
    client = LLMClientFactory.get_client("gemini", "gemini-2.0-flash-exp", settings)

    # Get available skills
    available_skills = schema.get_active_skills()
    skill_descriptions = "\n".join([
        f"- {s.id}: {s.name}"
        for s in available_skills
    ])

    analysis_prompt = f"""Analyze this document and determine which extraction skills are most relevant.

Available skills:
{skill_descriptions}

Document preview (first 1000 chars):
{state['document'][:1000]}

Return a JSON object with:
{{
    "relevant_skills": ["skill_id1", "skill_id2", ...],
    "reasoning": "Brief explanation of why these skills were selected"
}}
"""

    result, _ = await client.extract_json(
        "You are a document analysis expert.",
        analysis_prompt,
        temperature=0.0
    )

    selected_skill_ids = result.get("relevant_skills", [])

    logger.info(
        f"Dynamic selection: {len(selected_skill_ids)}/{len(available_skills)} skills selected"
    )

    return {
        "pending_skills": selected_skill_ids,
        "progress_events": [{
            "type": "skills_selected",
            "timestamp": datetime.utcnow().isoformat(),
            "selected": selected_skill_ids,
            "reasoning": result.get("reasoning", "")
        }]
    }

"""Shared execution helpers for schema and graph executors."""

import asyncio
import logging
import time
from typing import Any

from app.core.config import Settings
from app.models.execution import TokenUsage, ValidationResult
from app.models.schema import LoadedSchema, MergeStrategy, ValidationRule
from app.models.skill import Skill, SkillExecutionResult
from app.services.llm_client import LLMClientError, LLMClientFactory

logger = logging.getLogger(__name__)


def get_default_model_for_vendor(vendor: str, settings: Settings) -> str:
    """Get the default model for a specific vendor."""
    vendor_lower = vendor.lower()

    if vendor_lower == "anthropic":
        return settings.anthropic_model
    if vendor_lower == "openai":
        return settings.openai_model
    if vendor_lower == "gemini":
        return settings.gemini_model

    logger.warning("Unknown vendor '%s', defaulting to Anthropic", vendor)
    return settings.anthropic_model


async def execute_single_skill(
    skill: Skill,
    document: str,
    default_vendor: str,
    default_model: str | None,
    settings: Settings,
) -> SkillExecutionResult:
    """Execute a single skill with retries."""
    vendor = skill.get_effective_vendor(default_vendor)
    model = skill.get_effective_model(default_model)

    if not model:
        model = get_default_model_for_vendor(vendor, settings)
        logger.info("Resolved model to %s for vendor %s", model, vendor)

    start_time = time.time()
    last_error: str | None = None
    retries = 0

    for attempt in range(skill.config.retry_count + 1):
        try:
            client = LLMClientFactory.get_client(vendor, model, settings)
            data, usage = await asyncio.wait_for(
                client.extract_json(
                    skill.prompt,
                    document,
                    temperature=skill.config.temperature,
                ),
                timeout=skill.config.timeout_seconds,
            )

            execution_time = int((time.time() - start_time) * 1000)
            logger.info(
                "Skill '%s' completed in %sms (tokens: %s)",
                skill.id,
                execution_time,
                usage.total_tokens,
            )

            return SkillExecutionResult(
                skill_id=skill.id,
                success=True,
                data=data,
                token_usage=usage.model_dump(),
                execution_time_ms=execution_time,
                model_used=model or "default",
                vendor_used=vendor,
                retries=retries,
            )
        except asyncio.TimeoutError:
            last_error = f"Timeout after {skill.config.timeout_seconds}s"
            retries = attempt + 1
            logger.warning("Skill '%s' timed out, attempt %s", skill.id, retries)
        except LLMClientError as exc:
            last_error = str(exc)
            retries = attempt + 1
            logger.warning("Skill '%s' failed: %s, attempt %s", skill.id, exc, retries)
        except Exception as exc:
            last_error = str(exc)
            retries = attempt + 1
            logger.exception("Skill '%s' unexpected error: %s", skill.id, exc)

        if attempt < skill.config.retry_count:
            await asyncio.sleep(1 * (attempt + 1))

    execution_time = int((time.time() - start_time) * 1000)
    return SkillExecutionResult(
        skill_id=skill.id,
        success=False,
        error=last_error,
        execution_time_ms=execution_time,
        model_used=model or "default",
        vendor_used=vendor,
        retries=retries,
    )


def merge_results(
    results: list[SkillExecutionResult],
    strategy: MergeStrategy,
    initial: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge successful skill outputs with the configured strategy."""
    merged = dict(initial or {})

    for result in results:
        if not result.success or not result.data:
            continue

        if strategy == MergeStrategy.FIRST_WINS:
            for key, value in result.data.items():
                if key not in merged:
                    merged[key] = value
        elif strategy == MergeStrategy.LAST_WINS:
            merged.update(result.data)
        elif strategy == MergeStrategy.MERGE_DEEP:
            merged = deep_merge(merged, result.data)

    return merged


def deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()

    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def sum_token_usage(results: list[SkillExecutionResult]) -> TokenUsage:
    """Sum token usage across all results."""
    total = TokenUsage()

    for result in results:
        if result.token_usage:
            total.input_tokens += result.token_usage.get("input_tokens", 0)
            total.output_tokens += result.token_usage.get("output_tokens", 0)
            total.total_tokens += result.token_usage.get("total_tokens", 0)

    return total


def validate_output(data: dict[str, Any], schema: LoadedSchema) -> ValidationResult:
    """Validate merged output against schema rules."""
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    if schema.output_model:
        try:
            schema.output_model(**data)
            checks.append({"name": "pydantic_validation", "status": "passed"})
        except Exception as exc:
            errors.append(f"Pydantic validation failed: {exc}")
            checks.append(
                {
                    "name": "pydantic_validation",
                    "status": "failed",
                    "error": str(exc),
                }
            )

    for rule in schema.config.post_processing.validation_rules:
        check_result = run_validation_rule(rule, data)
        checks.append(check_result)

        if check_result["status"] == "failed":
            if rule.severity == "error":
                errors.append(f"{rule.name}: {check_result.get('error', 'Failed')}")
            else:
                warnings.append(f"{rule.name}: {check_result.get('error', 'Warning')}")

    quality_score = max(0, min(100, 100 - (len(errors) * 15) - (len(warnings) * 5)))

    if errors:
        status = "FAIL"
    elif warnings:
        status = "REVIEW"
    else:
        status = "PASS"

    return ValidationResult(
        status=status,
        quality_score=quality_score,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )


def run_validation_rule(rule: ValidationRule, data: dict[str, Any]) -> dict[str, Any]:
    """Run a single validation rule."""
    try:
        if rule.type == "sum_check":
            expected_field = rule.params.get("expected")
            operands = rule.params.get("operands", [])
            expected_value = get_nested_value(data, expected_field) if expected_field else None
            calculated = 0

            for operand in operands:
                if operand.startswith("-"):
                    calculated -= get_nested_value(data, operand[1:]) or 0
                else:
                    calculated += get_nested_value(data, operand) or 0

            if expected_value == calculated:
                return {"name": rule.name, "status": "passed"}
            return {
                "name": rule.name,
                "status": "failed",
                "error": f"Expected {expected_value}, calculated {calculated}",
            }

        if rule.type == "required":
            fields = rule.params.get("fields", [])
            missing = [field for field in fields if get_nested_value(data, field) is None]
            if missing:
                return {
                    "name": rule.name,
                    "status": "failed",
                    "error": f"Missing fields: {missing}",
                }
            return {"name": rule.name, "status": "passed"}

        if rule.type == "range_check":
            field = rule.params.get("field")
            min_val = rule.params.get("min")
            max_val = rule.params.get("max")
            value = get_nested_value(data, field) if field else None

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

        return {
            "name": rule.name,
            "status": "skipped",
            "reason": f"Unknown rule type: {rule.type}",
        }
    except Exception as exc:
        return {"name": rule.name, "status": "error", "error": str(exc)}


def get_nested_value(data: dict[str, Any], path: str) -> Any | None:
    """Get a nested value from a dictionary using dot notation."""
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current

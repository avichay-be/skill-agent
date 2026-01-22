"""Skill Executor - Orchestrates LLM calls with parallel execution."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import Settings, get_settings
from app.models.execution import (
    ExecutionMetadata,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
    TokenUsage,
    ValidationResult,
)
from app.models.schema import LoadedSchema, MergeStrategy, ValidationRule
from app.models.skill import Skill, SkillExecutionResult
from app.services.llm_client import LLMClientError, LLMClientFactory
from app.services.skill_registry import SkillRegistry, get_registry

logger = logging.getLogger(__name__)


class ExecutorError(Exception):
    """Error during skill execution."""

    pass


class SkillExecutor:
    """Executes skills against documents using LLMs."""

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        settings: Optional[Settings] = None,
    ):
        self.registry = registry or get_registry()
        self.settings = settings or get_settings()

    def _get_default_model_for_vendor(self, vendor: str) -> str:
        """Get the default model for a specific vendor.

        Args:
            vendor: LLM vendor name (anthropic, openai, gemini).

        Returns:
            Default model string for the vendor.
        """
        vendor_lower = vendor.lower()

        if vendor_lower == "anthropic":
            return self.settings.anthropic_model
        elif vendor_lower == "openai":
            return self.settings.openai_model
        elif vendor_lower == "gemini":
            return self.settings.gemini_model
        else:
            # Fallback to anthropic for unknown vendors
            logger.warning(f"Unknown vendor '{vendor}', defaulting to Anthropic")
            return self.settings.anthropic_model

    async def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        """Execute extraction using specified skill.

        Args:
            request: Execution request with document and skill_name.

        Returns:
            Execution response with results.
        """
        start_time = time.time()
        metadata = ExecutionMetadata(started_at=datetime.utcnow())

        try:
            # Get schema by skill_name
            schema = self.registry.get_schema_or_raise(request.skill_name)
            metadata.git_commit = schema.git_commit
            metadata.schema_version = schema.config.version

            # Get all active skills in the schema
            skills_to_run = schema.get_active_skills()

            if not skills_to_run:
                return ExecutionResponse(
                    status=ExecutionStatus.FAILED,
                    skill_name=request.skill_name,
                    error="No active skills to execute",
                    metadata=metadata,
                )

            # Determine vendor and model
            vendor = request.vendor or self.settings.default_vendor
            model = request.model or self._get_default_model_for_vendor(vendor)
            logger.info(f"Executing with vendor={vendor}, model={model}")

            # Execute skills in parallel groups
            skill_results = await self._execute_skills(
                skills_to_run,
                request.document,
                vendor,
                model,
            )

            # Merge results
            merged_data = self._merge_results(skill_results, schema)

            # Validate if schema has output model
            validation = None
            if schema.output_model:
                validation = self._validate_output(merged_data, schema)

            # Calculate final status
            failed_skills = [r for r in skill_results if not r.success]
            if len(failed_skills) == len(skill_results):
                status = ExecutionStatus.FAILED
            elif failed_skills:
                status = ExecutionStatus.PARTIAL
            else:
                status = ExecutionStatus.COMPLETED

            # Compute metadata
            end_time = time.time()
            metadata.completed_at = datetime.utcnow()
            metadata.processing_time_ms = int((end_time - start_time) * 1000)
            metadata.token_usage = self._sum_token_usage(skill_results)
            metadata.token_usage_by_skill = {
                r.skill_id: TokenUsage(**r.token_usage) for r in skill_results
            }
            metadata.models_used = list(set(r.model_used for r in skill_results))
            metadata.vendors_used = list(set(r.vendor_used for r in skill_results))

            return ExecutionResponse(
                status=status,
                skill_name=request.skill_name,
                data=merged_data,
                validation=validation,
                metadata=metadata,
                skill_results=skill_results,
                error="; ".join(r.error or "" for r in failed_skills) if failed_skills else None,
            )

        except Exception as e:
            logger.exception(f"Execution failed: {e}")
            metadata.completed_at = datetime.utcnow()
            metadata.processing_time_ms = int((time.time() - start_time) * 1000)

            return ExecutionResponse(
                status=ExecutionStatus.FAILED,
                skill_name=request.skill_name,
                error=str(e),
                metadata=metadata,
            )

    async def _execute_skills(
        self,
        skills: List[Skill],
        document: str,
        default_vendor: str,
        default_model: Optional[str],
    ) -> List[SkillExecutionResult]:
        """Execute skills in parallel groups.

        Args:
            skills: List of skills to execute.
            document: Document content.
            default_vendor: Default LLM vendor.
            default_model: Default model.

        Returns:
            List of execution results.
        """
        # Group by parallel_group
        groups: Dict[int, List[Skill]] = {}
        for skill in skills:
            group = skill.config.parallel_group
            if group not in groups:
                groups[group] = []
            groups[group].append(skill)

        # Execute groups in order
        all_results: List[SkillExecutionResult] = []

        for group_num in sorted(groups.keys()):
            group_skills = groups[group_num]
            logger.info(f"Executing parallel group {group_num} with {len(group_skills)} skills")

            # Execute all skills in this group concurrently
            tasks = [
                self._execute_single_skill(skill, document, default_vendor, default_model)
                for skill in group_skills
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for skill, result in zip(group_skills, results):
                if isinstance(result, Exception):
                    all_results.append(
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
                    all_results.append(result)

        return all_results

    async def _execute_single_skill(
        self,
        skill: Skill,
        document: str,
        default_vendor: str,
        default_model: Optional[str],
    ) -> SkillExecutionResult:
        """Execute a single skill with retries.

        Args:
            skill: Skill to execute.
            document: Document content.
            default_vendor: Default vendor.
            default_model: Default model.

        Returns:
            Skill execution result.
        """
        vendor = skill.get_effective_vendor(default_vendor)
        model = skill.get_effective_model(default_model)

        # Ensure we have the actual model name for logging
        # Handle both None and empty string
        if not model or model == "":
            model = self._get_default_model_for_vendor(vendor)
            logger.info(f"Resolved model to {model} for vendor {vendor}")

        start_time = time.time()
        last_error: Optional[str] = None
        retries = 0

        for attempt in range(skill.config.retry_count + 1):
            try:
                client = LLMClientFactory.get_client(vendor, model, self.settings)

                # Execute with timeout
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
                    f"Skill '{skill.id}' completed in {execution_time}ms "
                    f"(tokens: {usage.total_tokens})"
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
            model_used=model or "default",
            vendor_used=vendor,
            retries=retries,
        )

    def _merge_results(
        self,
        results: List[SkillExecutionResult],
        schema: LoadedSchema,
    ) -> Dict[str, Any]:
        """Merge skill results according to schema strategy.

        Args:
            results: List of skill results.
            schema: Schema with merge configuration.

        Returns:
            Merged data dictionary.
        """
        strategy = schema.config.post_processing.merge_strategy
        merged: Dict[str, Any] = {}

        for result in results:
            if not result.success or not result.data:
                continue

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
                merged = self._deep_merge(merged, result.data)

        return merged

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries.

        Args:
            base: Base dictionary.
            update: Dictionary to merge in.

        Returns:
            Merged dictionary.
        """
        result = base.copy()

        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _sum_token_usage(self, results: List[SkillExecutionResult]) -> TokenUsage:
        """Sum token usage across all results."""
        total = TokenUsage()

        for result in results:
            if result.token_usage:
                total.input_tokens += result.token_usage.get("input_tokens", 0)
                total.output_tokens += result.token_usage.get("output_tokens", 0)
                total.total_tokens += result.token_usage.get("total_tokens", 0)

        return total

    def _validate_output(
        self,
        data: Dict[str, Any],
        schema: LoadedSchema,
    ) -> ValidationResult:
        """Validate output against schema's Pydantic model.

        Args:
            data: Extracted data.
            schema: Schema with output model.

        Returns:
            Validation result.
        """
        errors: List[str] = []
        warnings: List[str] = []
        checks: List[Dict[str, Any]] = []

        # Validate against Pydantic model if available
        if schema.output_model:
            try:
                schema.output_model(**data)
                checks.append(
                    {
                        "name": "pydantic_validation",
                        "status": "passed",
                    }
                )
            except Exception as e:
                errors.append(f"Pydantic validation failed: {e}")
                checks.append(
                    {
                        "name": "pydantic_validation",
                        "status": "failed",
                        "error": str(e),
                    }
                )

        # Run custom validation rules
        for rule in schema.config.post_processing.validation_rules:
            check_result = self._run_validation_rule(rule, data)
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

        return ValidationResult(
            status=status,
            quality_score=quality_score,
            checks=checks,
            errors=errors,
            warnings=warnings,
        )

    def _run_validation_rule(
        self,
        rule: "ValidationRule",
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run a single validation rule.

        Args:
            rule: Validation rule configuration.
            data: Data to validate.

        Returns:
            Check result dictionary.
        """

        try:
            if rule.type == "sum_check":
                # Check if a field equals the sum of other fields
                expected_field = rule.params.get("expected")
                operands = rule.params.get("operands", [])

                expected_value = self._get_nested_value(data, expected_field)
                calculated = 0

                for op in operands:
                    if op.startswith("-"):
                        calculated -= self._get_nested_value(data, op[1:]) or 0
                    else:
                        calculated += self._get_nested_value(data, op) or 0

                if expected_value == calculated:
                    return {"name": rule.name, "status": "passed"}
                else:
                    return {
                        "name": rule.name,
                        "status": "failed",
                        "error": f"Expected {expected_value}, calculated {calculated}",
                    }

            elif rule.type == "required":
                # Check required fields exist
                fields = rule.params.get("fields", [])
                missing = [f for f in fields if self._get_nested_value(data, f) is None]

                if missing:
                    return {
                        "name": rule.name,
                        "status": "failed",
                        "error": f"Missing fields: {missing}",
                    }
                return {"name": rule.name, "status": "passed"}

            elif rule.type == "range_check":
                # Check value is within range
                field = rule.params.get("field")
                min_val = rule.params.get("min")
                max_val = rule.params.get("max")

                value = self._get_nested_value(data, field)

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
                return {
                    "name": rule.name,
                    "status": "skipped",
                    "reason": f"Unknown rule type: {rule.type}",
                }

        except Exception as e:
            return {"name": rule.name, "status": "error", "error": str(e)}

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Optional[Any]:
        """Get a nested value from a dictionary using dot notation.

        Args:
            data: Dictionary to search.
            path: Dot-separated path (e.g., "financial.revenue").

        Returns:
            Value at path or None.
        """
        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current


# Convenience function
def get_executor() -> SkillExecutor:
    """Get executor instance."""
    return SkillExecutor()

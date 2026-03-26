# Comprehensive Codebase Refactoring Plan

> **For Claude:** REQUIRED: Follow this plan phase-by-phase. Each phase is independently shippable.
> **Codebase:** Skill Agent - FastAPI + LangGraph + Pydantic v2 service

**Goal:** Eliminate code duplication, fix known issues, improve test coverage, add observability, and simplify the architecture by removing the legacy executor.

**Architecture:** The service uses a dual executor system (legacy SkillExecutor + LangGraph GraphExecutor) with shared business logic duplicated between them. This plan consolidates into a single LangGraph executor, extracts shared utilities, adds structured logging and observability, and raises test coverage from ~54% to 80%+.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, Pydantic v2, SQLite checkpointing, Anthropic/OpenAI/Gemini LLM clients

**Prerequisites:** All 4 prior phases (security, datetime, pydantic, file upload) are complete. 108+ tests passing, 54% coverage, mypy strict clean, ruff clean.

---

## Relevant Codebase Files

### Core Architecture
- `app/main.py` (lines 1-179) - Entry point, middleware, exception handlers
- `app/core/config.py` (lines 1-138) - Settings via pydantic-settings
- `app/core/exceptions.py` (lines 1-59) - Custom exception hierarchy
- `app/core/security.py` (lines 1-56) - API key auth
- `app/core/rate_limiter.py` (lines 1-26) - Rate limiting

### Routes (6 files)
- `app/api/routes/execute.py` (lines 1-418) - Execution endpoints (418 lines, largest route file)
- `app/api/routes/workflows.py` (lines 1-218) - Workflow endpoints
- `app/api/routes/admin.py` (lines 1-127) - Admin endpoints
- `app/api/routes/schemas.py` (lines 1-76) - Schema endpoints
- `app/api/routes/skills.py` (lines 1-63) - Skill endpoints
- `app/api/routes/webhooks.py` (lines 1-184) - Webhook endpoints
- `app/api/file_uploads.py` (lines 1-62) - Shared file upload helper

### Services (8 files)
- `app/services/executor.py` (lines 1-558) - **LEGACY** executor (558 lines)
- `app/services/graph_executor.py` (lines 1-293) - LangGraph executor
- `app/services/graph/nodes.py` (lines 1-636) - Graph node implementations (636 lines, largest file)
- `app/services/graph/builder.py` (lines 1-185) - Graph construction
- `app/services/graph/state.py` (lines 1-97) - Graph state schema
- `app/services/llm_client.py` (lines 1-492) - LLM client factory + 3 vendor clients
- `app/services/skill_registry.py` (lines 1-405) - Singleton skill registry
- `app/services/git_loader.py` (lines 1-358) - Git-based skill loading
- `app/services/batch_executor.py` (lines 1-315) - Anthropic Batch API
- `app/services/workflow_executor.py` (lines 1-240) - Multi-schema workflow chaining
- `app/services/cosmosdb.py` (lines 1-184) - Azure CosmosDB persistence
- `app/services/github_client.py` (lines 1-206) - GitHub REST API client

### Models (6 files)
- `app/models/execution.py` (lines 1-132) - Execution models
- `app/models/events.py` (lines 1-94) - Event models
- `app/models/schema.py` (lines 1-110) - Schema models
- `app/models/skill.py` (lines 1-77) - Skill models
- `app/models/workflow.py` (lines 1-147) - Workflow models
- `app/models/cicd.py` (lines 1-158) - CI/CD models (unused in production)

### Tests (18 files)
- `tests/conftest.py` - Shared fixtures
- `tests/test_coverage_boost.py` - Large omnibus coverage file (~700+ lines)
- `tests/test_regressions.py` - Regression tests
- Plus 15 other test files

### Configuration
- `pyproject.toml` - Build, test, lint, mypy config
- `Dockerfile` - Multi-stage build
- `.pre-commit-config.yaml` - Pre-commit hooks
- `.github/workflows/ci-v2.yml` - CI pipeline

---

## Phase 1: Extract Shared Execution Logic (Eliminate Duplication)

> **Exit Criteria:** All duplicated logic between `executor.py` and `graph/nodes.py` is extracted into shared utility modules. Both executors use the shared code. All tests pass.

### Problem Statement
The following logic is duplicated nearly verbatim between `app/services/executor.py` and `app/services/graph/nodes.py`:

1. **`_execute_single_skill`** - 80 lines duplicated (executor.py:215-307, nodes.py:167-246)
2. **`_get_default_model_for_vendor`** - 15 lines duplicated (executor.py:43-63, nodes.py:249-261)
3. **`_merge_results` / `_deep_merge`** - 35 lines duplicated (executor.py:309-364, nodes.py:265-317)
4. **`_validate_output` / `_run_validation_rule` / `_get_nested_value`** - 100 lines duplicated (executor.py:378-551, nodes.py:321-485)

**Total duplication: ~230 lines of business logic that must be kept in sync.**

### Task 1.1: Create shared execution utilities module

**Files:**
- Create: `app/services/execution_utils.py`

**Step 1: Write failing test**

```python
# tests/test_execution_utils.py
"""Tests for shared execution utility functions."""
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.services.execution_utils import (
    execute_single_skill,
    get_default_model_for_vendor,
    merge_skill_results,
    deep_merge,
    validate_output,
    run_validation_rule,
    get_nested_value,
)

def test_get_default_model_for_vendor_anthropic():
    settings = MagicMock()
    settings.anthropic_model = "claude-sonnet-4-20250514"
    assert get_default_model_for_vendor("anthropic", settings) == "claude-sonnet-4-20250514"

def test_get_default_model_for_vendor_unknown():
    settings = MagicMock()
    settings.anthropic_model = "claude-sonnet-4-20250514"
    assert get_default_model_for_vendor("unknown", settings) == "claude-sonnet-4-20250514"

def test_deep_merge():
    base = {"a": {"b": 1, "c": 2}}
    update = {"a": {"d": 3}}
    result = deep_merge(base, update)
    assert result == {"a": {"b": 1, "c": 2, "d": 3}}

def test_get_nested_value():
    data = {"a": {"b": {"c": 42}}}
    assert get_nested_value(data, "a.b.c") == 42
    assert get_nested_value(data, "nonexistent") is None
```

**Step 2:** Run test, verify fails: `pytest tests/test_execution_utils.py -v --no-cov` -- Expected: FAIL (module not found)

**Step 3: Implement shared module**

Create `app/services/execution_utils.py` extracting the following functions from `executor.py`:
- `get_default_model_for_vendor(vendor: str, settings: Any) -> str`
- `execute_single_skill(skill, document, vendor, model, settings) -> SkillExecutionResult`
- `merge_skill_results(results, strategy) -> Dict[str, Any]`
- `deep_merge(base, update) -> Dict[str, Any]`
- `validate_output(data, schema) -> ValidationResult`
- `run_validation_rule(rule, data) -> Dict[str, Any]`
- `get_nested_value(data, path) -> Optional[Any]`

**Step 4:** Run test, verify passes: `pytest tests/test_execution_utils.py -v --no-cov`

**Step 5:** Commit: `git commit -m "refactor: extract shared execution utilities"`

### Task 1.2: Rewire executor.py to use shared utilities

**Files:**
- Modify: `app/services/executor.py`

**Step 1:** Replace duplicated methods in `SkillExecutor` with imports from `execution_utils`

**Step 2:** Run all tests: `pytest tests/ -v` -- Expected: all pass

**Step 3:** Commit: `git commit -m "refactor: rewire legacy executor to use shared utils"`

### Task 1.3: Rewire graph/nodes.py to use shared utilities

**Files:**
- Modify: `app/services/graph/nodes.py`

**Step 1:** Replace duplicated functions in nodes.py with imports from `execution_utils`

**Step 2:** Run all tests: `pytest tests/ -v` -- Expected: all pass

**Step 3:** Commit: `git commit -m "refactor: rewire graph nodes to use shared utils"`

### Validation

Run: `pytest tests/ -v --cov=app --cov-report=term-missing`
Run: `mypy app`
Run: `ruff check .`

---

## Phase 2: Remove Legacy Executor

> **Exit Criteria:** The `USE_LANGGRAPH` toggle and legacy `SkillExecutor` are removed. All execution goes through `GraphExecutor`. The `/execute/legacy` endpoint is deprecated/removed. All tests pass.

### Problem Statement
The dual executor system (`SkillExecutor` + `GraphExecutor`) exists only for rollback safety. LangGraph has been the default since migration. Maintaining two code paths doubles bug surface and slows development. The `USE_LANGGRAPH` flag defaults to `True` and has been in production for months.

### ADR: Remove Legacy Executor

**Context:** The codebase maintains two parallel execution engines. The legacy `SkillExecutor` (`executor.py`, 558 lines) duplicates logic now in `GraphExecutor`. The `USE_LANGGRAPH` env var defaults to True.

**Decision:** Remove the legacy executor and the `USE_LANGGRAPH` toggle. All execution will use `GraphExecutor`.

**Consequences:**
- **Positive:** ~560 lines of code removed, single execution path, simpler testing
- **Negative:** No instant rollback path (mitigated: the shared utils from Phase 1 make the graph executor reliable)
- **Alternatives Considered:** Keep legacy as fallback -- rejected because duplicated code is a maintenance burden and both paths should produce identical results

### Task 2.1: Remove `/execute/legacy` endpoint

**Files:**
- Modify: `app/api/routes/execute.py` -- Remove `execute_extraction_legacy` function and route
- Modify: `tests/test_security.py` -- Remove `test_legacy_endpoint_has_rate_limit_decorator`

**Step 1:** Remove the `/execute/legacy` endpoint (lines 273-317 in execute.py)
**Step 2:** Remove test references
**Step 3:** Run: `pytest tests/ -v`
**Step 4:** Commit: `git commit -m "refactor: remove /execute/legacy endpoint"`

### Task 2.2: Remove `USE_LANGGRAPH` toggle and legacy executor selection

**Files:**
- Modify: `app/api/routes/execute.py` -- Remove if/else branching on `use_langgraph`
- Modify: `app/core/config.py` -- Remove `use_langgraph: bool` setting
- Modify: `app/services/workflow_executor.py` -- Remove if/else branching on `use_langgraph`
- Remove: `app/services/executor.py` -- Delete the entire file (after Phase 1 extracts shared logic)

**Step 1:** Update execute.py to always use `get_graph_executor()` (remove `get_executor()` calls)
**Step 2:** Update workflow_executor.py to always use `get_graph_executor()`
**Step 3:** Remove `use_langgraph` from config.py
**Step 4:** Delete executor.py
**Step 5:** Update imports in any remaining references
**Step 6:** Run: `pytest tests/ -v`
**Step 7:** Commit: `git commit -m "refactor: remove legacy executor and USE_LANGGRAPH toggle"`

### Task 2.3: Update tests referencing legacy executor

**Files:**
- Modify: `tests/test_executor.py` -- Rewrite to test shared execution_utils instead
- Modify: `tests/test_coverage_boost.py` -- Remove legacy executor tests
- Modify: `tests/test_regressions.py` -- Update if references to executor.py exist

**Step 1:** Rewrite test_executor.py to cover execution_utils functions
**Step 2:** Run: `pytest tests/ -v --cov=app`
**Step 3:** Commit: `git commit -m "test: update tests for single executor architecture"`

### Validation

Run: `pytest tests/ -v --cov=app --cov-report=term-missing`
Run: `mypy app`
Run: `ruff check .`
Expected: All pass, no references to `executor.py` or `USE_LANGGRAPH` remain.

---

## Phase 3: Fix Known Infrastructure Issues

> **Exit Criteria:** SQLite checkpoint dir auto-creates, git tokens are sanitized from logs, and the CI/CD model dead code is removed. All tests pass.

### Task 3.1: Auto-create SQLite checkpoint directory

**Files:**
- Modify: `app/services/graph_executor.py` (line 52, `_checkpointer_context`)

**Problem:** `SQLite checkpoint directory (./data/) must pre-exist or initialization fails` (from patterns.md).

**Step 1: Write failing test**
```python
# In tests/test_regressions.py or new file
@pytest.mark.asyncio
async def test_graph_executor_creates_checkpoint_dir(tmp_path):
    """GraphExecutor should auto-create the checkpoint directory."""
    db_path = tmp_path / "subdir" / "checkpoints.db"
    executor = GraphExecutor(settings=SimpleNamespace(
        checkpoint_backend="sqlite",
        checkpoint_db_path=str(db_path),
    ))
    # Should not raise FileNotFoundError
    async with executor._checkpointer_context() as cp:
        assert cp is not None
    assert db_path.parent.exists()
```

**Step 2:** Run test, verify fails

**Step 3:** Add `Path(checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)` before the `AsyncSqliteSaver.from_conn_string` call in `_checkpointer_context`.

**Step 4:** Run test, verify passes
**Step 5:** Commit: `git commit -m "fix: auto-create SQLite checkpoint directory"`

### Task 3.2: Sanitize git tokens from log output

**Files:**
- Modify: `app/services/git_loader.py` (line 56, `_get_clone_url`)

**Problem:** Git tokens embedded in URLs can leak in GitPython logs.

**Step 1: Write test**
```python
def test_clone_url_not_logged_with_token(caplog):
    """Token should not appear in log output."""
    # Verify _get_clone_url result is not directly logged
```

**Step 2:** Add a `_safe_url` property to GitLoader that strips the token for logging purposes. Use it in all logger.info calls that reference the URL.

**Step 3:** In `clone_or_pull()`, replace `logger.info(f"Cloning {self.settings.github_repo_url}")` with `logger.info(f"Cloning {self._safe_url}")`.

**Step 4:** Run tests, verify passes
**Step 5:** Commit: `git commit -m "security: sanitize git tokens from log output"`

### Task 3.3: Remove unused CI/CD dead code

**Files:**
- Evaluate: `app/models/cicd.py` (158 lines)
- Evaluate: `app/services/graph/cicd/state.py` (80 lines)
- Evaluate: `app/services/graph/cicd/__init__.py`
- Evaluate: `app/services/github_client.py` (206 lines)

**Problem:** The CI/CD subagent feature (`enable_cicd_subagent: bool = False`) has models, state, and a GitHub client but no graph nodes, no routes, and no tests exercising the actual pipeline. The `github_client.py` is only imported in coverage tests, not in production code. This is ~444 lines of dead code.

**Step 1:** Verify no production import path leads to cicd/ or github_client.py:
```bash
grep -r "from app.services.graph.cicd" app/  # Should only find __init__.py
grep -r "from app.services.github_client" app/  # Should find nothing in routes/services
grep -r "cicd" app/api/  # Should find nothing
```

**Step 2:** If confirmed dead, remove the files and update `app/models/__init__.py`
**Step 3:** Remove corresponding test code in test_coverage_boost.py
**Step 4:** Run: `pytest tests/ -v --cov=app`
**Step 5:** Commit: `git commit -m "refactor: remove unused CI/CD subagent dead code"`

### Validation

Run: `pytest tests/ -v --cov=app --cov-report=term-missing`
Run: `mypy app`

---

## Phase 4: Add Structured Logging and Observability

> **Exit Criteria:** All log output is structured JSON (in non-debug mode), request ID middleware propagates correlation IDs, and key metrics are logged at service boundaries. Tests verify logging behavior.

### Task 4.1: Add request ID middleware

**Files:**
- Create: `app/core/middleware.py`
- Modify: `app/main.py`

**Step 1: Write test**
```python
def test_response_includes_request_id(app_client):
    response = app_client.get("/health")
    assert "X-Request-ID" in response.headers
```

**Step 2:** Implement RequestIDMiddleware that:
- Reads `X-Request-ID` from incoming request (or generates UUID)
- Stores it in a contextvars.ContextVar
- Adds it to response headers
- Makes it available to logging via a filter

**Step 3:** Add the middleware to `create_app()` in main.py
**Step 4:** Run tests
**Step 5:** Commit: `git commit -m "feat: add request ID middleware for correlation"`

### Task 4.2: Add structured JSON logging

**Files:**
- Modify: `app/main.py` (logging configuration, lines 22-26)

**Step 1:** Replace basicConfig with a structured logging setup:
- In production (`debug=False`): JSON format with timestamp, level, logger, message, request_id
- In development (`debug=True`): Human-readable format (current behavior)

**Step 2:** Add request_id to all log records via a logging.Filter that reads the ContextVar

**Step 3:** Run tests
**Step 4:** Commit: `git commit -m "feat: structured JSON logging with request ID"`

### Task 4.3: Add execution metrics logging

**Files:**
- Modify: `app/services/graph_executor.py`
- Modify: `app/services/workflow_executor.py`

**Step 1:** At the end of each execution, log a structured metrics event:
```python
logger.info("execution_complete", extra={
    "execution_id": execution_id,
    "schema_id": request.skill_name,
    "status": response.status.value,
    "duration_ms": response.metadata.processing_time_ms,
    "total_tokens": response.metadata.token_usage.total_tokens,
    "skills_count": len(response.skill_results),
})
```

**Step 2:** Run tests
**Step 3:** Commit: `git commit -m "feat: add execution metrics logging"`

### Validation

Run: `pytest tests/ -v --cov=app --cov-report=term-missing`
Run: `mypy app`

---

## Phase 5: Improve Test Coverage and Quality

> **Exit Criteria:** Test coverage reaches 75%+ overall, route coverage reaches 60%+ for all route files, and the test suite is reorganized with clear naming conventions.

### Task 5.1: Split the omnibus test_coverage_boost.py

**Files:**
- Modify: `tests/test_coverage_boost.py` (~700+ lines, covers 6+ modules)

**Problem:** `test_coverage_boost.py` is a monolithic file covering LLM client, GitHub client, graph executor, workflow executor, graph nodes, and CI/CD models. It should be split into focused test files.

**Step 1:** Move tests into existing or new focused files:
- LLM client tests -> `tests/test_llm_client.py` (merge with test_llm_json_parsing.py and test_llm_client_cache.py)
- Graph executor tests -> `tests/test_graph_executor.py`
- Workflow executor tests -> merge into `tests/test_workflow.py`
- Graph node tests -> `tests/test_graph_nodes.py`
- GitHub client tests -> `tests/test_github_client.py` (or remove if Phase 3.3 removes the code)

**Step 2:** Delete test_coverage_boost.py
**Step 3:** Run: `pytest tests/ -v --cov=app`
**Step 4:** Commit: `git commit -m "test: split omnibus coverage file into focused test modules"`

### Task 5.2: Add missing route tests

**Files:**
- Modify: `tests/test_api.py` -- Add tests for untested endpoints

**Problem:** Route coverage is low (25-77%). Key untested paths:
- `POST /execute` with valid skill (actual execution mock)
- `POST /execute/stream` (SSE streaming)
- `POST /execute/resume/{id}` (human review)
- `POST /admin/initialize` and `POST /admin/reload`
- `POST /schemas/{id}/reload`
- Error paths for all endpoints

**Step 1:** Add test for each untested route, using mocked executors
**Step 2:** Run: `pytest tests/test_api.py -v --cov=app/api --cov-report=term-missing`
**Step 3:** Commit: `git commit -m "test: add missing route tests for execute, admin, schemas"`

### Task 5.3: Fix test_langgraph_basic.py and test_langgraph_comparison.py

**Files:**
- Modify: `tests/test_langgraph_basic.py` -- Convert from script to pytest tests
- Modify: `tests/test_langgraph_comparison.py` -- Convert from script to pytest tests

**Problem:** These files use `print()` statements and `sys.exit()` instead of pytest assertions. They are scripts, not proper tests, and `test_langgraph_basic.py` tries to access `executor.graph` which does not exist.

**Step 1:** Convert to proper pytest test functions with assertions
**Step 2:** Run: `pytest tests/test_langgraph_basic.py tests/test_langgraph_comparison.py -v`
**Step 3:** Commit: `git commit -m "test: convert langgraph scripts to proper pytest tests"`

### Validation

Run: `pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=75`
Run: `mypy app`

---

## Phase 6: Code Quality and Minor Refactors

> **Exit Criteria:** Type annotations tightened, import hygiene improved, and minor code smells resolved. All checks pass.

### Task 6.1: Replace `Dict`, `List`, `Optional`, `Tuple` with built-in generics

**Files:**
- All files in `app/` using `from typing import Dict, List, Optional, Tuple`

**Problem:** Python 3.11+ supports `dict`, `list`, `tuple`, `X | None` natively. The codebase mixes old-style `Dict[str, Any]` with new-style `dict[str, Any]`. Standardize on built-in generics.

**Step 1:** Replace across all files:
- `Dict[` -> `dict[`
- `List[` -> `list[`
- `Tuple[` -> `tuple[`
- `Optional[X]` -> `X | None`
- Remove unused `from typing import Dict, List, Optional, Tuple` imports

**Step 2:** Run: `mypy app && ruff check . && pytest tests/ -v`
**Step 3:** Commit: `git commit -m "refactor: use built-in generic types (PEP 585/604)"`

### Task 6.2: Move TimeoutMiddleware out of main.py

**Files:**
- Modify: `app/main.py` -- Move class out
- Create or modify: `app/core/middleware.py`

**Problem:** `TimeoutMiddleware` (lines 29-49 in main.py) is business logic in the app factory module. It should live in `app/core/middleware.py` alongside the RequestIDMiddleware from Phase 4.

**Step 1:** Move the class, update imports
**Step 2:** Run: `pytest tests/ -v`
**Step 3:** Commit: `git commit -m "refactor: move TimeoutMiddleware to core/middleware"`

### Task 6.3: Consolidate singleton patterns

**Files:**
- Review: `app/services/skill_registry.py` -- Uses `__new__` + `_lock` singleton
- Review: `app/services/batch_executor.py` -- Uses module-level `_batch_executor` global
- Review: `app/services/cosmosdb.py` -- Uses module-level `_cosmosdb_service` global

**Problem:** Three different singleton patterns are used. Standardize on one approach (either `__new__`-based or module-level global with getter).

**Decision:** Keep `SkillRegistry`'s `__new__` pattern as-is (it needs `reset()` for tests). Standardize `batch_executor` and `cosmosdb` to use the same `_instance: Optional[T]` + `get_*()` pattern for consistency.

**Step 1:** Review and align patterns
**Step 2:** Run tests
**Step 3:** Commit: `git commit -m "refactor: standardize singleton patterns"`

### Task 6.4: Add `__all__` exports to service modules

**Files:**
- Modify: `app/services/__init__.py`
- Modify: `app/core/__init__.py`

**Step 1:** Add explicit `__all__` lists to package init files
**Step 2:** Run: `mypy app && pytest tests/`
**Step 3:** Commit: `git commit -m "refactor: add __all__ exports to packages"`

### Validation

Run: `pytest tests/ -v --cov=app --cov-report=term-missing`
Run: `mypy app`
Run: `ruff check . && ruff format --check .`

---

## Phase 7: Dockerfile and Deployment Improvements

> **Exit Criteria:** Dockerfile is updated for removed files, requirements.txt is auto-generated, and health check is improved.

### Task 7.1: Improve Dockerfile

**Files:**
- Modify: `Dockerfile`

**Changes:**
1. Add `mkdir -p /app/data` to ensure SQLite checkpoint dir exists (complements Phase 3.1)
2. Add `COPY requirements.txt* ./` is already there, but add a generation step to `pyproject.toml` or document the sync requirement
3. The `|| pip install ...` fallback on line 25 is missing `slowapi`, `langgraph`, `langgraph-checkpoint-sqlite`, `langchain-core`, `pyyaml` - add them to the fallback list

**Step 1:** Update Dockerfile
**Step 2:** Run: `docker build -t skill-agent:test .` (if Docker available)
**Step 3:** Commit: `git commit -m "fix: update Dockerfile for missing deps and checkpoint dir"`

### Task 7.2: Add requirements.txt generation to CI

**Files:**
- Modify: `.github/workflows/ci-v2.yml`

**Problem:** Dockerfile uses `requirements.txt` but it can drift from `pyproject.toml` (documented in memory). Add a CI check.

**Step 1:** Add a step that runs `pip compile` or verifies requirements.txt matches pyproject.toml deps
**Step 2:** Commit: `git commit -m "ci: add requirements.txt sync check"`

---

## Risks

| Risk | P (1-5) | I (1-5) | Score | Mitigation |
|------|---------|---------|-------|------------|
| Removing legacy executor breaks a production fallback path | 3 | 4 | 12 | Phase 1 extracts shared logic first; comprehensive test coverage before removal |
| CI/CD dead code removal affects unreleased feature | 2 | 3 | 6 | Verify with git blame; feature flag is disabled and code is unreachable |
| Structured logging breaks log parsers | 2 | 3 | 6 | Only JSON in production mode; development keeps human-readable |
| Test reorganization introduces import issues | 2 | 2 | 4 | Run full test suite after each file move |
| SQLite checkpoint dir fix changes deployment behavior | 1 | 2 | 2 | Auto-create is strictly additive; no behavior change if dir exists |

---

## Success Criteria

- [ ] Zero code duplication between executors (Phase 1)
- [ ] Single execution path (no USE_LANGGRAPH toggle) (Phase 2)
- [ ] SQLite checkpoint dir auto-creates (Phase 3.1)
- [ ] Git tokens never appear in logs (Phase 3.2)
- [ ] Request ID in all responses and logs (Phase 4.1)
- [ ] Structured JSON logging in production (Phase 4.2)
- [ ] Test coverage >= 75% (Phase 5)
- [ ] Route coverage >= 60% for all route files (Phase 5)
- [ ] All typing uses built-in generics (Phase 6.1)
- [ ] All checks pass: `pytest`, `mypy app`, `ruff check .`, `ruff format --check .`

---

## Execution Order and Dependencies

```
Phase 1 (Extract shared logic)
    |
    v
Phase 2 (Remove legacy executor) -- depends on Phase 1
    |
    v
Phase 3 (Fix infra issues) -- independent, can run after Phase 1
    |
    v
Phase 4 (Observability) -- independent
    |
    v
Phase 5 (Test coverage) -- should run after Phase 2 (fewer code paths to test)
    |
    v
Phase 6 (Code quality) -- independent, can run anytime
    |
    v
Phase 7 (Dockerfile/CI) -- independent, can run anytime
```

Phases 3, 4, 6, and 7 are independent and can be executed in any order after Phase 2.

---

## Estimated Effort

| Phase | Tasks | Estimated LOC Changed | Risk |
|-------|-------|-----------------------|------|
| 1: Extract shared logic | 3 | ~300 new, ~200 removed | Medium |
| 2: Remove legacy executor | 3 | ~600 removed | Medium |
| 3: Fix infra issues | 3 | ~50 new, ~500 removed (dead code) | Low |
| 4: Observability | 3 | ~150 new | Low |
| 5: Test coverage | 3 | ~500 new/reorganized | Low |
| 6: Code quality | 4 | ~200 changed | Low |
| 7: Dockerfile/CI | 2 | ~20 changed | Low |
| **Total** | **21** | **~1200 net reduction** | |

---

### Memory Notes (For Workflow-Final Persistence)

**Learnings:**
- The codebase has ~230 lines of duplicated business logic between executor.py and graph/nodes.py
- CI/CD subagent (cicd.py, cicd/state.py, github_client.py) is ~444 lines of dead code with no routes or production imports
- test_langgraph_basic.py and test_langgraph_comparison.py are scripts (print-based), not proper pytest tests
- test_coverage_boost.py is a ~700+ line omnibus file covering 6+ modules that should be split
- The Dockerfile fallback pip install list is missing several dependencies (slowapi, langgraph, etc.)
- Three different singleton patterns are used across the services layer
- Python 3.11+ built-in generics (dict, list, X | None) are used inconsistently

**Patterns:**
- Shared execution logic should live in `app/services/execution_utils.py`
- Middleware classes should live in `app/core/middleware.py`, not in main.py
- Request ID should be propagated via contextvars.ContextVar for logging correlation

**Verification:**
- Plan: `docs/plans/2026-03-19-refactoring-plan.md` with 8/10 confidence

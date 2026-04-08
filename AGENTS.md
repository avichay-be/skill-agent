# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Skill Agent is a FastAPI service that dynamically loads extraction skills from a Git repository (or local filesystem) and executes them against documents using multiple LLM providers (Anthropic Codex, OpenAI GPT, Google Gemini). It uses LangGraph for workflow orchestration with checkpointing, streaming, human-in-the-loop review, and conditional branching.

## Commands

```bash
# Install
pip install -e ".[dev]"

# Run dev server
python -m uvicorn app.main:app --reload

# Tests (runs with --cov=app --cov-fail-under=45 by default via pyproject.toml)
pytest
pytest tests/test_executor.py          # single file
pytest tests/test_executor.py::test_name  # single test
pytest -m "not integration"            # skip integration tests

# Lint & format
ruff check .          # lint
ruff check --fix .    # lint with auto-fix
ruff format .         # format
ruff format --check . # format check only

# Type checking
mypy app

# Pre-commit (runs ruff + mypy + whitespace/yaml checks)
pre-commit run --all-files
```

## Architecture

**Entry point**: `app/main.py` — FastAPI app with lifespan management that auto-initializes the skill registry on startup.

**Route → Service → Model layering**:
- `app/api/routes/` — HTTP endpoints (admin, execute, schemas, skills, webhooks)
- `app/services/` — Business logic (executor, graph_executor, git_loader, llm_client, skill_registry)
- `app/models/` — Pydantic data contracts (execution, events, schema, skill)
- `app/core/` — Config (pydantic-settings), exceptions, security middleware

**Dual executor system**: Controlled by `USE_LANGGRAPH` env var (default: True).
- `GraphExecutor` (LangGraph) in `app/services/graph_executor.py` — state graph with nodes: initialize → execute_group → merge_results → validate → human_review, with conditional routing
- `SkillExecutor` (legacy) in `app/services/executor.py` — asyncio.gather-based parallel execution
- Graph internals live in `app/services/graph/` (state.py, builder.py, nodes.py)

**SkillRegistry** (`app/services/skill_registry.py`): Singleton that loads skills from Git or local path. Skills are organized as schemas containing groups of parallel skills. Thread-safe with locking.

**LLMClientFactory** (`app/services/llm_client.py`): Factory pattern abstracting Anthropic, OpenAI, and Gemini clients behind a common interface.

**Skill structure** (in `skills-library/` or remote Git repo):
```
{schema_id}/
├── schema.json      # Schema config: skill definitions, parallel groups, timeouts
├── models.py        # Pydantic output models (optional)
└── prompts/
    └── skill_name.md  # LLM prompt templates
```

Skills within a schema are assigned to parallel groups (1, 2, 3...). All skills in group 1 execute concurrently, then group 2, etc.

## Code Style

- Python 3.11+, mypy strict mode
- Ruff: line-length 100, E501 ignored, double quotes, space indent
- Fully async throughout — all I/O uses async/await
- Type annotations required on all functions (mypy strict)
- LangGraph state uses `Annotated[list[T], add]` reducers for accumulating results

## Configuration

Settings in `app/core/config.py` via pydantic-settings. Key env vars:
- `REQUIRE_API_KEY` / `API_KEYS` — Authentication (disabled by default)
- `GITHUB_REPO_URL` / `GITHUB_TOKEN` / `LOCAL_SKILLS_PATH` — Skill source
- `DEFAULT_VENDOR` — LLM provider: "anthropic", "openai", or "gemini" (default: gemini)
- `USE_LANGGRAPH` — Toggle LangGraph executor (default: True)
- `ENABLE_STREAMING` / `ENABLE_HUMAN_REVIEW` / `ENABLE_DYNAMIC_SELECTION` — Feature flags

## Documentation

Detailed docs live in `.Codex/` directory (numbered 01-09), covering LangGraph migration, deployment, Azure setup, and integration testing.
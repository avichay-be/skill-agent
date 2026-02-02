# Skill Agent

Event-driven skill loader and executor for LLM-based document extraction.

## Overview

Skill Agent is a FastAPI service that dynamically loads extraction skills from a Git repository (or local filesystem) and executes them against documents using multiple LLM providers (Anthropic Claude, OpenAI GPT, Google Gemini). It uses LangGraph for workflow orchestration with checkpointing, streaming, human-in-the-loop review, and conditional branching.

### Key Features

- **Git-based skill management** — Skills stored as markdown prompts + JSON config, auto-reloaded via webhook
- **Multi-vendor LLM support** — Anthropic Claude, OpenAI GPT, Google Gemini
- **LangGraph orchestration** — State graph with checkpointing, streaming, conditional routing, and human-in-the-loop
- **Parallel execution** — Skills execute in configurable parallel groups
- **Pydantic output models** — Type-safe extraction results
- **API key authentication** — Optional secure access control

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env   # Edit with your API keys and settings

# Run
python -m uvicorn app.main:app --reload

# Initialize the skill registry
curl -X POST http://localhost:8000/api/v1/admin/initialize
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/admin/initialize` | POST | Initialize skill registry |
| `/api/v1/admin/reload` | POST | Reload skills from Git |
| `/api/v1/admin/config` | GET | Get non-sensitive config |
| `/api/v1/skills` | GET | List all skills |
| `/api/v1/skills/{id}` | GET | Get skill details |
| `/api/v1/schemas` | GET | List all schemas |
| `/api/v1/schemas/{id}` | GET | Get schema with skills |
| `/api/v1/execute` | POST | Execute extraction |
| `/api/v1/execute/stream` | POST | Streaming execution |
| `/api/v1/execute/pause` | POST | Pause for human review |
| `/api/v1/execute/resume` | POST | Resume paused execution |
| `/api/v1/webhooks/git` | POST | Git push webhook |

## Example: Execute Extraction

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "document": "Your document content here...",
    "schema_id": "entity_extractor",
    "vendor": "anthropic"
  }'
```

## Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Description | Default |
|----------|-------------|---------|
| `REQUIRE_API_KEY` | Enable API key auth | `false` |
| `API_KEYS` | Comma-separated API keys | — |
| `LOCAL_SKILLS_PATH` | Local skills directory | — |
| `GITHUB_REPO_URL` | Skills Git repository URL | — |
| `GITHUB_TOKEN` | GitHub access token | — |
| `DEFAULT_VENDOR` | LLM vendor (`anthropic`, `openai`, `gemini`) | `gemini` |
| `USE_LANGGRAPH` | Enable LangGraph executor | `true` |
| `ENABLE_STREAMING` | Enable SSE streaming | `true` |
| `ENABLE_HUMAN_REVIEW` | Enable human-in-the-loop | `false` |

## Adding Skills

Each skill schema is a directory in the skills library:

```
skills-library/your_schema/
├── schema.json      # Schema config: skill definitions, parallel groups, timeouts
├── models.py        # Pydantic output models (optional)
└── prompts/
    └── skill_name.md  # LLM prompt template
```

Skills are assigned to parallel groups (1, 2, 3...). All skills in group 1 run concurrently, then group 2, etc. See `.claude/01-README.md` for detailed instructions on creating skills.

## Documentation

Detailed documentation lives in the `.claude/` directory covering LangGraph migration, deployment, Azure setup, and more.

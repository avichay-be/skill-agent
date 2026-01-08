# Skill Agent

Event-driven skill loader and executor for LLM-based document extraction.

## Overview

Skill Agent is a FastAPI service that dynamically loads extraction skills from a Git repository and executes them against documents using multiple LLM providers (Anthropic, OpenAI, Google Gemini).

### Key Features

- **Git-based skill management** - Skills are stored as markdown prompts + JSON config in a Git repo
- **Multi-vendor LLM support** - Anthropic Claude, OpenAI GPT, Google Gemini
- **Parallel execution** - Skills execute in configurable parallel groups
- **Webhook integration** - Auto-reload skills on Git push
- **Pydantic output models** - Type-safe extraction results
- **API key authentication** - Secure access control

## Quick Start

### 1. Install Dependencies

```bash
cd skill-agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

### 3. Run the Service

```bash
# Development
python -m uvicorn app.main:app --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Initialize the Registry

```bash
curl -X POST http://localhost:8000/api/v1/admin/initialize \
  -H "X-API-Key: your-api-key"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/health` | GET | Health check |
| `/api/v1/admin/initialize` | POST | Initialize skill registry |
| `/api/v1/admin/reload` | POST | Reload skills from Git |
| `/api/v1/skills` | GET | List all skills |
| `/api/v1/skills/{id}` | GET | Get skill details |
| `/api/v1/schemas` | GET | List all schemas |
| `/api/v1/schemas/{id}` | GET | Get schema with skills |
| `/api/v1/execute` | POST | Execute extraction |
| `/api/v1/webhooks/git` | POST | Git push webhook |

## Execute Extraction

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "document": "Your document content here...",
    "schema_id": "example_extraction",
    "vendor": "anthropic"
  }'
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEYS` | Comma-separated API keys | `dev-api-key` |
| `GITHUB_REPO_URL` | Skills repository URL | - |
| `GITHUB_TOKEN` | GitHub access token | - |
| `GITHUB_BRANCH` | Branch to watch | `main` |
| `LOCAL_SKILLS_PATH` | Local skills directory | - |
| `DEFAULT_VENDOR` | Default LLM vendor | `anthropic` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GOOGLE_API_KEY` | Google API key | - |

## Project Structure

```
skill-agent/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── api/routes/             # API endpoints
│   ├── models/                 # Pydantic models
│   ├── services/               # Business logic
│   └── core/                   # Config, auth, exceptions
├── skills-library/             # Example skills
└── tests/                      # Test suite
```

---

# Adding New Skills

This guide explains how to add new extraction skills to the Skill Agent system.

## Skill Structure

Each skill schema is a directory containing:

```
skills-library/
└── your_schema/
    ├── schema.json          # Schema configuration
    ├── models.py            # Pydantic output models
    └── prompts/
        ├── skill_1.md       # Skill prompt
        ├── skill_2.md
        └── ...
```

## Step-by-Step Guide

### Step 1: Create Schema Directory

```bash
mkdir -p skills-library/your_schema/prompts
```

### Step 2: Create schema.json

Define the schema configuration:

```json
{
  "schema_id": "your_schema",
  "version": "1.0.0",
  "name": "Your Schema Name",
  "description": "Description of what this schema extracts",
  "output_model": "models.YourOutputModel",

  "skills": [
    {
      "id": "skill_name",
      "name": "Human Readable Skill Name",
      "prompt_file": "prompts/skill_name.md",
      "parallel_group": 1,
      "timeout_seconds": 45,
      "retry_count": 2,
      "output_fields": ["field1", "field2"],
      "temperature": 0.0
    }
  ],

  "post_processing": {
    "merge_strategy": "merge_deep",
    "validation_rules": []
  }
}
```

#### Skill Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique skill identifier |
| `name` | string | Yes | Human-readable name |
| `prompt_file` | string | Yes | Path to prompt markdown file |
| `parallel_group` | int | No | Execution order (1 = first, default: 1) |
| `timeout_seconds` | int | No | Max execution time (default: 45) |
| `retry_count` | int | No | Retries on failure (default: 2) |
| `output_fields` | array | No | Fields this skill extracts |
| `vendor` | string | No | Preferred LLM vendor |
| `model` | string | No | Preferred model |
| `temperature` | float | No | LLM temperature (default: 0.0) |
| `status` | string | No | `active`, `disabled`, `draft` |

#### Merge Strategies

- `merge_deep` - Deep merge all skill outputs (default)
- `first_wins` - First skill's value wins on conflict
- `last_wins` - Last skill's value wins on conflict

### Step 3: Create Prompt Files

Create markdown files for each skill in `prompts/`:

```markdown
# Skill Title

You are an expert at extracting [type] information.

## Task

Extract the following from the document:

1. **field1**: Description of field1
2. **field2**: Description of field2

## Guidelines

- Guideline 1
- Guideline 2
- If a field cannot be determined, set it to null

## Output Format

Return a JSON object:

```json
{
  "field1": "value or null",
  "field2": "value or null"
}
```

## Important

- Return ONLY valid JSON, no markdown formatting
- Use null for missing values
```

### Step 4: Create Pydantic Models (Optional)

Create `models.py` for type-safe output validation:

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class ExtractedItem(BaseModel):
    name: str
    value: Optional[str] = None

class YourOutputModel(BaseModel):
    """Combined output from all skills."""

    field1: str = Field(..., description="Description")
    field2: Optional[str] = None
    items: List[ExtractedItem] = Field(default_factory=list)

    class Config:
        populate_by_name = True
```

### Step 5: Test Your Schema

```bash
# Reload the registry
curl -X POST http://localhost:8000/api/v1/admin/reload \
  -H "X-API-Key: your-key"

# Check schema loaded
curl http://localhost:8000/api/v1/schemas/your_schema \
  -H "X-API-Key: your-key"

# Test extraction
curl -X POST http://localhost:8000/api/v1/execute \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "document": "Test document...",
    "schema_id": "your_schema"
  }'
```

---

# Agent Instructions for Adding Skills

This section provides instructions for AI agents to programmatically add new skills.

## Agent Workflow

### 1. Analyze Requirements

Before creating a skill, understand:
- What data needs to be extracted
- Document type and structure
- Required output format
- Validation rules needed

### 2. Create Skill Files

Use file write operations to create:

```
skills-library/{schema_id}/
├── schema.json
├── models.py
└── prompts/
    └── {skill_id}.md
```

### 3. Schema.json Template

```json
{
  "schema_id": "{schema_id}",
  "version": "1.0.0",
  "name": "{Human Readable Name}",
  "description": "{What this schema extracts}",
  "output_model": "models.{OutputModelClass}",
  "skills": [
    {
      "id": "{skill_id}",
      "name": "{Skill Name}",
      "prompt_file": "prompts/{skill_id}.md",
      "parallel_group": 1,
      "timeout_seconds": 45,
      "retry_count": 2,
      "output_fields": ["{field1}", "{field2}"]
    }
  ],
  "post_processing": {
    "merge_strategy": "merge_deep",
    "validation_rules": []
  }
}
```

### 4. Prompt Template

```markdown
# {Skill Title}

You are an expert at extracting {domain} information from documents.

## Task

Extract the following information:

{For each field:}
- **{field_name}**: {description}

## Output Format

Return a JSON object:

```json
{
  {For each field:}
  "{field_name}": {type_hint}
}
```

## Important

- Return ONLY valid JSON
- Use null for missing values
- {Additional constraints}
```

### 5. Models.py Template

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class {OutputModelClass}(BaseModel):
    {For each field:}
    {field_name}: {type} = Field({default}, description="{description}")
```

### 6. Validation Rules

Add validation rules to catch extraction errors:

```json
{
  "validation_rules": [
    {
      "id": "required_check",
      "name": "Required Fields",
      "type": "required",
      "params": {"fields": ["field1", "field2"]},
      "severity": "error"
    },
    {
      "id": "sum_check",
      "name": "Sum Validation",
      "type": "sum_check",
      "params": {
        "expected": "total",
        "operands": ["part1", "part2"]
      },
      "severity": "error"
    },
    {
      "id": "range_check",
      "name": "Value Range",
      "type": "range_check",
      "params": {"field": "percentage", "min": 0, "max": 100},
      "severity": "warning"
    }
  ]
}
```

### 7. Parallel Execution Groups

Organize skills into parallel groups for optimal performance:

- **Group 1**: Independent skills that can run simultaneously
- **Group 2**: Skills that depend on Group 1 results
- **Group N**: Further dependencies

```json
{
  "skills": [
    {"id": "metadata", "parallel_group": 1},
    {"id": "summary", "parallel_group": 1},
    {"id": "entities", "parallel_group": 1},
    {"id": "analysis", "parallel_group": 2}
  ]
}
```

### 8. Commit and Push

After creating skill files:

```bash
git add skills-library/{schema_id}/
git commit -m "Add {schema_id} extraction schema"
git push origin main
```

The webhook will automatically reload the registry.

### 9. Verify Deployment

```bash
# Check schema is loaded
curl -s http://localhost:8000/api/v1/schemas/{schema_id} \
  -H "X-API-Key: key" | jq .

# Test with sample document
curl -X POST http://localhost:8000/api/v1/execute \
  -H "X-API-Key: key" \
  -H "Content-Type: application/json" \
  -d '{"document": "...", "schema_id": "{schema_id}"}'
```

## Best Practices

1. **Clear prompts** - Be specific about expected output format
2. **Use parallel groups** - Maximize throughput with independent skills
3. **Add validation** - Catch extraction errors early
4. **Type safety** - Define Pydantic models for output validation
5. **Reasonable timeouts** - Set based on document complexity
6. **Retry logic** - Handle transient LLM failures
7. **Field documentation** - Describe each field in prompts
8. **Test thoroughly** - Verify with real documents before deployment

## Example: Invoice Extraction

```
skills-library/invoice/
├── schema.json
├── models.py
└── prompts/
    ├── header.md      # Invoice number, date, vendor
    ├── line_items.md  # Products, quantities, prices
    └── totals.md      # Subtotal, tax, total
```

See `skills-library/example_extraction/` for a complete working example.

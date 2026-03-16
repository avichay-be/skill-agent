# Skill Authoring Guide

Instructions for creating, updating, or replacing skills in the `skills-library/` directory.

## Directory Structure

Each skill belongs to a **schema** — a directory containing the skill config, Pydantic output model, and prompt files:

```
skills-library/
└── {schema_id}/
    ├── schema.json          # Schema config: skills, groups, validation
    ├── models.py            # Pydantic v2 output model
    └── prompts/
        └── {skill_name}.md  # LLM prompt template
```

A schema can contain **one or more skills**. Skills within a schema share the same output model and validation rules.

---

## 1. schema.json

Defines the schema and its skills.

```json
{
  "schema_id": "my_extractor",
  "version": "1.0.0",
  "name": "Human-Readable Name",
  "description": "What this schema does",
  "output_model": "models.MyResult",

  "skills": [
    {
      "id": "extract_data",
      "name": "Extract Data",
      "prompt_file": "prompts/extract.md",
      "parallel_group": 1,
      "timeout_seconds": 60,
      "retry_count": 2,
      "output_fields": ["field1", "field2"],
      "vendor": null,
      "model": null,
      "temperature": 0.0,
      "status": "active"
    }
  ],

  "post_processing": {
    "merge_strategy": "merge_deep",
    "validation_rules": [
      {
        "id": "field1_required",
        "name": "Field1 is required",
        "type": "required",
        "params": {"fields": ["field1"]},
        "severity": "error"
      }
    ]
  }
}
```

### Field Reference

#### Schema fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_id` | string | yes | Unique ID, must match directory name |
| `version` | string | yes | Semver version |
| `name` | string | yes | Human-readable name |
| `description` | string | no | What this schema does |
| `output_model` | string | no | Python path to Pydantic model, e.g. `"models.MyResult"` |
| `skills` | array | yes | List of skill configs |
| `post_processing` | object | no | Merge strategy and validation rules |

#### Skill config fields
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | required | Unique skill identifier |
| `name` | string | required | Human-readable name |
| `prompt_file` | string | required | Relative path to prompt .md file |
| `parallel_group` | int | `1` | Execution order (group 1 runs first, then 2, etc.) |
| `timeout_seconds` | int | `45` | Max execution time per attempt |
| `retry_count` | int | `2` | Number of retries on failure |
| `output_fields` | string[] | `[]` | JSON fields this skill extracts |
| `vendor` | string\|null | `null` | LLM vendor override (`"anthropic"`, `"openai"`, `"gemini"`, or `null` for default) |
| `model` | string\|null | `null` | Model override (or `null` for vendor default) |
| `temperature` | float | `0.0` | LLM temperature (0.0 = deterministic) |
| `status` | string | `"active"` | `"active"`, `"disabled"`, or `"draft"` |

#### Merge strategies
| Strategy | Behavior |
|----------|----------|
| `merge_deep` | Deep-merge all skill outputs (default, recommended) |
| `first_wins` | Keep first value for each key |
| `last_wins` | Keep last value for each key |

#### Validation rule types
| Type | Params | Description |
|------|--------|-------------|
| `required` | `{"fields": ["path.to.field"]}` | Check that fields exist and are non-null |
| `range_check` | `{"field": "score", "min": 0, "max": 100}` | Check numeric range |
| `sum_check` | `{"fields": [...], "expected_field": "total"}` | Verify sum matches |

Severity: `"error"` (blocks completion) or `"warning"` (informational).

---

## 2. models.py

Pydantic v2 output model that validates the LLM response.

### Rules
- Use `BaseModel` from pydantic
- Use `ConfigDict(populate_by_name=True)` on models with aliases
- Use `Field(alias="camelCase")` when LLM returns camelCase but Python uses snake_case
- Use `Optional[T] = None` for fields that may be missing
- The top-level class name must match `output_model` in schema.json (e.g. `"models.MyResult"` → class `MyResult`)

### Template

```python
"""Pydantic output model for {description}."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class NestedItem(BaseModel):
    """Nested data item."""

    name: str = Field(..., description="Item name")
    value: Optional[str] = Field(None, description="Item value")


class MyResult(BaseModel):
    """Top-level extraction result."""

    model_config = ConfigDict(populate_by_name=True)

    # Required fields use Field(...)
    title: str = Field(..., description="Document title")

    # Optional fields use Optional[T] = None
    author: Optional[str] = Field(None, description="Author name")

    # camelCase alias for LLM output → snake_case Python
    key_points: List[str] = Field(
        default_factory=list, alias="keyPoints", description="Key points"
    )

    # Nested objects
    items: List[NestedItem] = Field(default_factory=list, description="Extracted items")
```

### Important patterns
- **Required field**: `field: str = Field(..., description="...")`
- **Optional field**: `field: Optional[str] = Field(None, description="...")`
- **List with default**: `field: List[str] = Field(default_factory=list, ...)`
- **Alias**: `field: str = Field(..., alias="camelCase", description="...")`
- **`populate_by_name=True`**: Required on any model using aliases — allows both `key_points` and `keyPoints` to work. Note: does NOT inherit to nested models, must be set on each.

---

## 3. prompts/{skill_name}.md

The LLM prompt template. The document content is passed separately as the user message.

### Template

```markdown
# {Task Title}

You are an expert at {domain}. {Brief role description}.

## Task

Extract the following from the provided document:

1. **fieldName1**: Description of what to extract
2. **fieldName2**: Description of what to extract

## Guidelines

- Specific extraction rules
- Edge case handling
- Language/format requirements

## Output Format

```json
{
  "fieldName1": "example value",
  "fieldName2": ["example", "items"]
}
```

## Important

- Return ONLY valid JSON, no markdown or explanations
- Use null for missing values
- {Any other critical rules}
```

### Prompt rules
- Field names in the prompt must match `output_fields` in schema.json and aliases in models.py
- Always include the JSON output format example
- Always end with "Return ONLY valid JSON"
- The prompt is sent as the system message; the document is the user message
- Keep prompts focused — one clear task per skill

---

## 4. Multi-Skill Schemas

A schema can have multiple skills that run in parallel groups:

```json
{
  "skills": [
    {
      "id": "extract_header",
      "prompt_file": "prompts/header.md",
      "parallel_group": 1,
      "output_fields": ["title", "author", "date"]
    },
    {
      "id": "extract_body",
      "prompt_file": "prompts/body.md",
      "parallel_group": 1,
      "output_fields": ["summary", "keyPoints"]
    },
    {
      "id": "extract_financials",
      "prompt_file": "prompts/financials.md",
      "parallel_group": 2,
      "output_fields": ["revenue", "expenses"]
    }
  ]
}
```

- **Group 1**: `extract_header` and `extract_body` run in parallel
- **Group 2**: `extract_financials` runs after group 1 completes
- Results are merged using the `merge_strategy`
- Each skill has its own prompt file but shares the same output model

---

## 5. Creating a New Skill+Schema

Step-by-step:

1. **Create the directory**:
   ```
   skills-library/{schema_id}/
   skills-library/{schema_id}/prompts/
   ```

2. **Write `models.py`** — define the Pydantic output model

3. **Write `prompts/{name}.md`** — write the LLM prompt with JSON output format

4. **Write `schema.json`** — wire everything together:
   - Set `schema_id` matching the directory name
   - Set `output_model` to `"models.ClassName"`
   - Define skills pointing to prompt files
   - Add validation rules for required fields

5. **Deploy**:
   ```bash
   git add skills-library/{schema_id}/
   git commit -m "Add {schema_id} skill"
   git push
   ```
   Then reload:
   ```bash
   curl -X POST https://skill-agent-app.livelycliff-37840c5f.eastus.azurecontainerapps.io/api/v1/webhooks/reload
   ```

6. **Test**:
   ```bash
   curl -X POST https://skill-agent-app.livelycliff-37840c5f.eastus.azurecontainerapps.io/api/v1/execute \
     -H "Content-Type: application/json" \
     -d '{
       "document": "Your test document text here...",
       "skill_name": "{schema_id}"
     }'
   ```

---

## 6. Updating an Existing Skill

To update a skill's prompt, model, or config:

1. Edit the relevant file(s) in `skills-library/{schema_id}/`
2. Push to main: `git add . && git commit -m "Update {schema_id}" && git push`
3. Reload: `curl -X POST .../api/v1/webhooks/reload`

No container rebuild required — the app pulls the latest from GitHub on reload.

---

## 7. Converting a .skill File

When given a `.skill` file or skill description, produce all three files:

1. Parse the skill definition to identify:
   - What data needs to be extracted (→ output fields, model, prompt)
   - Domain context (→ prompt system instructions)
   - Required vs optional fields (→ model + validation rules)

2. Generate `schema.json` with appropriate timeouts and retry counts:
   - Simple extraction: `timeout_seconds: 30-45`
   - Complex/long documents: `timeout_seconds: 60-120`
   - `retry_count: 2` is a good default

3. Generate `models.py` following Pydantic v2 patterns above

4. Generate `prompts/{name}.md` with clear JSON output format

5. Place in `skills-library/{schema_id}/` directory structure

---

## Quick Reference: Existing Skills

| Schema ID | Skills | Description |
|-----------|--------|-------------|
| `entity_extractor` | `extract_entities` | People, orgs, locations, dates |
| `metadata_extractor` | `extract_metadata` | Title, author, date, type, content |
| `summarizer` | `generate_summary` | Summary + key points |
| `valuation_report_analyzer` | `analyze_report` | Israeli real estate report extraction |

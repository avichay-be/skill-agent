# Dynamic Skill Selection (Experimental)

## Overview

Dynamic Skill Selection is an experimental LangGraph feature that uses an LLM to analyze documents and automatically select the most relevant skills for extraction.

**Status**: ⚠️ Experimental - Disabled by default

## How It Works

### Standard Execution (Current)
All active skills in a schema are executed:
```
Document → [Skill 1, Skill 2, Skill 3, Skill 4] → Results
```

### Dynamic Selection (Experimental)
An LLM analyzes the document first and selects relevant skills:
```
Document → LLM Analysis → [Skill 2, Skill 4] → Results
          (fast model)     (only relevant)
```

## Benefits

1. **Cost Savings** - Skip irrelevant skills, reduce token usage
2. **Faster Execution** - Process fewer skills
3. **Better Results** - Focus on what matters
4. **Adaptive** - Works with any document type

## Architecture

### Graph Flow

```
initialize
  ↓
analyze_document_and_select_skills  # NEW NODE
  ↓
execute_group (selected skills only)
  ↓
merge_results
  ↓
...
```

### Analysis Node

```python
async def analyze_document_and_select_skills(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Uses a fast LLM (Gemini Flash) to analyze document
    and determine which skills are most relevant.
    """
    # Get available skills
    skills = schema.get_active_skills()

    # Analyze document
    prompt = f"Which skills are relevant for this document?"
    result = await llm.extract_json(prompt, document)

    # Update pending_skills with selected IDs
    return {"pending_skills": result["relevant_skills"]}
```

## Enabling Dynamic Selection

### Option 1: Environment Variable

```bash
# .env
ENABLE_DYNAMIC_SELECTION=true
```

### Option 2: Python Configuration

```python
from app.core.config import get_settings

settings = get_settings()
settings.enable_dynamic_selection = True
```

### Option 3: Per-Request

```bash
curl -X POST http://localhost:8000/api/v1/execute/dynamic \
  -H "X-API-Key: your-key" \
  -d '{
    "document": "...",
    "skill_name": "entity_extractor"
  }'
```

## Implementation

### 1. Create Dynamic Graph Builder

Add to `app/services/graph/builder.py`:

```python
def create_dynamic_selection_graph() -> StateGraph:
    """
    Graph variant with LLM-based skill selection.
    """
    workflow = StateGraph(SkillGraphState)

    # Add analysis node
    workflow.add_node("analyze", nodes.analyze_document_and_select_skills)

    # Connect: initialize → analyze → execute
    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "analyze")
    workflow.add_edge("analyze", "execute_group")

    # ... rest of graph ...

    return workflow.compile(checkpointer=MemorySaver())
```

### 2. Node Implementation (Already in nodes.py)

```python
async def analyze_document_and_select_skills(state: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze document and select relevant skills."""

    settings = get_settings()
    registry = get_registry()
    schema = registry.get_schema_or_raise(state["schema_id"])

    # Use fast, cheap model for analysis
    client = LLMClientFactory.get_client("gemini", "gemini-2.0-flash-exp", settings)

    # Get available skills
    available_skills = schema.get_active_skills()
    skill_descriptions = "\n".join([
        f"- {s.id}: {s.name}"
        for s in available_skills
    ])

    # Analyze document (first 1000 chars)
    analysis_prompt = f"""Analyze this document and determine which extraction skills are most relevant.

Available skills:
{skill_descriptions}

Document preview:
{state['document'][:1000]}

Return JSON:
{{
    "relevant_skills": ["skill_id1", "skill_id2"],
    "reasoning": "Brief explanation"
}}
"""

    result, _ = await client.extract_json(
        "You are a document analysis expert.",
        analysis_prompt,
        temperature=0.0
    )

    selected = result.get("relevant_skills", [])

    logger.info(
        f"Dynamic selection: {len(selected)}/{len(available_skills)} skills selected"
    )

    return {
        "pending_skills": selected,
        "progress_events": [{
            "type": "skills_selected",
            "timestamp": datetime.utcnow().isoformat(),
            "selected": selected,
            "reasoning": result.get("reasoning", "")
        }]
    }
```

### 3. Add API Endpoint

In `app/api/routes/execute.py`:

```python
@router.post("/dynamic", response_model=ExecutionResponse)
async def execute_extraction_dynamic(
    request: ExecutionRequest,
    _api_key: ApiKeyDep,
    registry: Annotated[SkillRegistry, Depends(get_registry)],
) -> ExecutionResponse:
    """Execute with dynamic skill selection."""

    settings = get_settings()

    if not settings.enable_dynamic_selection:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Dynamic selection is experimental and not enabled"
        )

    # Use dynamic selection graph
    from app.services.graph.builder import create_dynamic_selection_graph
    graph = create_dynamic_selection_graph()

    # Create executor with dynamic graph
    from app.services.graph_executor import GraphExecutor
    executor = GraphExecutor()
    executor.graph = graph  # Override with dynamic graph

    return await executor.execute(request)
```

## Cost Analysis

### Example: 10-skill Schema

**Standard Execution**:
- Skills executed: 10
- Cost: 10 × $0.01 = $0.10

**Dynamic Selection** (assuming 3 relevant skills):
- Analysis call: 1 × $0.001 (fast model)
- Skills executed: 3 × $0.01 = $0.03
- **Total**: $0.031 (69% savings)

### Break-Even Analysis

Dynamic selection is cost-effective when:
```
Analysis_Cost < (Total_Skills - Selected_Skills) × Skill_Cost
$0.001 < (10 - 3) × $0.01
$0.001 < $0.07  ✓
```

## Accuracy Considerations

### Analysis Model Selection

Use a fast, cheap model for analysis:
- ✅ **Gemini 2.0 Flash**: Fast, cheap (~$0.001/1K tokens)
- ✅ **GPT-4o-mini**: Fast, accurate
- ❌ **Claude Opus**: Expensive for analysis

### Prompt Engineering

Key elements for good selection:
1. **Clear skill descriptions** in schema.json
2. **Document preview** (first 1000 chars)
3. **Example outputs** for each skill
4. **Selection criteria** in prompt

Example improved schema.json:
```json
{
  "skills": [
    {
      "id": "extract_financial",
      "name": "Financial Data Extractor",
      "description": "Extracts revenue, expenses, profit. Use for: financial reports, earnings statements, balance sheets",
      "example_output": {"revenue": 1000000, "expenses": 500000},
      ...
    }
  ]
}
```

## Limitations

### 1. Analysis Overhead
- Additional LLM call adds ~200-500ms
- May not be worth it for schemas with few skills

### 2. Selection Accuracy
- Analysis model may miss relevant skills
- Conservative approach: include more skills if uncertain

### 3. Context Window
- Limited to first 1000 chars for analysis
- Long documents may need full analysis

### 4. Skill Dependencies
- No dependency tracking yet
- May select skill without its prerequisites

## Testing

### Test Dynamic Selection

```python
# test_dynamic_selection.py

import asyncio
from app.models.execution import ExecutionRequest
from app.services.graph.builder import create_dynamic_selection_graph
from app.services.graph_executor import GraphExecutor

async def test():
    # Create dynamic graph
    graph = create_dynamic_selection_graph()

    # Override executor graph
    executor = GraphExecutor()
    executor.graph = graph

    # Test document
    request = ExecutionRequest(
        document="Financial report: Revenue $1M, Expenses $500K",
        skill_name="comprehensive_extractor"
    )

    response = await executor.execute(request)

    print(f"Skills selected: {response.metadata.skills_executed}")
    print(f"Data extracted: {response.data}")

asyncio.run(test())
```

### Compare Results

```bash
# Standard execution
curl -X POST http://localhost:8000/api/v1/execute \
  -d '{"document": "...", "skill_name": "schema"}' \
  > standard.json

# Dynamic execution
curl -X POST http://localhost:8000/api/v1/execute/dynamic \
  -d '{"document": "...", "skill_name": "schema"}' \
  > dynamic.json

# Compare
diff standard.json dynamic.json
```

## Best Practices

### 1. Start with Conservative Selection
Err on the side of including more skills:
```python
# In analysis prompt
"When uncertain, include the skill. Missing data is worse than extra processing."
```

### 2. Monitor Selection Accuracy
Track which skills would have been useful:
```python
# Log for analysis
logger.info(f"Selected: {selected_skills}")
logger.info(f"Available: {all_skills}")
logger.info(f"Results: {non_empty_results}")
```

### 3. Provide Rich Skill Metadata
Help the analysis model make good decisions:
```json
{
  "skills": [{
    "id": "extract_entities",
    "description": "Extracts people, companies, locations",
    "relevant_for": ["news articles", "business documents", "emails"],
    "not_relevant_for": ["pure financial data", "technical specs"]
  }]
}
```

### 4. Use for Multi-Purpose Schemas
Best for schemas with many diverse skills:
```
❌ Bad: 3 skills (all usually needed)
✅ Good: 10+ skills (only 2-3 typically needed)
```

## Future Enhancements

### 1. Skill Dependency Graph
```python
# Automatically include prerequisites
if "extract_financial_analysis" in selected:
    selected.append("extract_financial_data")  # Required
```

### 2. Confidence Scores
```python
# Return confidence for each skill
{
    "relevant_skills": [
        {"id": "skill1", "confidence": 0.95},
        {"id": "skill2", "confidence": 0.60}
    ]
}
```

### 3. Adaptive Thresholds
```python
# Learn optimal selection threshold per schema
threshold = analytics.get_optimal_threshold(schema_id)
```

### 4. Full Document Analysis
```python
# Analyze entire document, not just first 1000 chars
if len(document) > 1000:
    summary = await summarize(document)
    analysis = await analyze(summary)
```

## Troubleshooting

### Issue: Too Few Skills Selected
**Solution**: Lower confidence threshold or add more context

```python
# In analysis prompt
"Select all skills that might be even somewhat relevant"
```

### Issue: Analysis Takes Too Long
**Solution**: Use faster model or reduce context

```python
# Use even faster model
client = LLMClientFactory.get_client("gemini", "gemini-1.5-flash-8b")
```

### Issue: Poor Selection Quality
**Solution**: Improve skill descriptions in schema.json

```json
{
  "description": "Extracts financial data including revenue, expenses, profit margins, EBITDA, and cash flow. Use for: quarterly reports, annual statements, earnings calls."
}
```

## Conclusion

Dynamic Skill Selection is a powerful optimization for schemas with many diverse skills. Start with it disabled, enable for specific high-volume schemas, and monitor results carefully.

**Recommendation**: Enable after validating standard LangGraph execution works well.

---

**Status**: Experimental
**Requires**: `use_langgraph=true`, `enable_dynamic_selection=true`
**Cost**: +$0.001 per execution
**Speed**: +200-500ms per execution
**Accuracy**: ~85-95% (depends on skill descriptions)

# Map Sections to Tabs

You are a dashboard architect. Given a JSON analysis (from the previous step), determine how to organize the data into HTML tabs with appropriate visualizations.

## Task

Convert the field classifications into a tab structure with specific visualization assignments.

## Input

You receive the `jsonAnalysis` object from the previous step, plus the original JSON data.

## Tab Assignment Rules

### For Pipeline Outputs (shape = "pipeline_output")

Map each `skill_results[].skill_id` to a tab:

| skill_id pattern | Tab label | Icon |
|-----------------|-----------|------|
| `*project_info*` | פרטי פרויקט | 📋 |
| `*financials*` | פיננסי | 💰 |
| `*legal*` | משפטי/תכנוני | ⚖️ |
| `*risks*` or `*timeline*` | ציר זמן/סיכונים | 🚨 |
| `*validate*` | ולידציה | ✓ |

### For Zero Reports (shape = "zero_report")

| JSON section | Tab label | Icon |
|-------------|-----------|------|
| `projectInfo` + `neighborhoodInfo` + `consultants` | פרטי פרויקט | 📋 |
| `financialSummary` + `revenueByTrack` + `expenseBreakdown` + `breakEvenAnalysis` + `sensitivityAnalysis` | פיננסי | 💰 |
| `legalInfo` + `planningInfo` | משפטי/תכנוני | ⚖️ |
| `timeline.milestones` | ציר זמן | 🚨 |
| `validation` + `metadata` | ולידציה | ✓ |

### For Generic JSON

Group top-level keys into tabs of 3-6 fields. Prefer grouping by semantic similarity.

## Visualization Assignment

For each field assigned to a tab, choose the visualization:

| fieldType | visualization |
|-----------|--------------|
| `kpi` (isFinancial) | `kpi_card` |
| `kpi` (isPercentage) | `kpi_card` or `progress_bar` |
| `table` | `row_list` |
| `table` (financial items) | `expense_table` |
| `chart` (numeric array, ≤6 items) | `pie_chart` |
| `chart` (numeric array, >6 items) | `bar_chart` |
| `timeline` | `timeline` |
| `status` | `checklist` |
| `risk` | `risk_cards` |
| `matrix` | `matrix_grid` |
| `tag` | `tag_list` |
| `text` | `text_block` |

## Header Construction

Build from available data:
- **title**: `jsonAnalysis.titleCandidate` or fallback
- **subtitle**: `jsonAnalysis.subtitleCandidate` or fallback
- **logoText**: "BlackEdge" (default) or from metadata
- **badges**: array of `{text, color}` from: model name, validation score, processing time, report date

## Footer Construction

- **reportDate**: from `data.projectInfo.reportDate` or `data.document_info.date`
- **appraiser**: from `data.projectInfo.appraiser` or `data.document_info.appraiser.name`
- **generationDate**: today's date in DD/MM/YYYY
- **schemaVersion**: from `metadata.schema_version`
- **modelUsed**: from `metadata.models_used[0]`

## Chart Detection

Assign `chartId` (e.g., `"pieExpenses"`, `"barSkillPerf"`) to any field with visualization `pie_chart` or `bar_chart`. Set `hasCharts: true` on the parent tab.

Count total charts across all tabs → `totalCharts`.

## Output Format

```json
{
  "sectionMapping": {
    "tabs": [
      {
        "tabId": "project_info",
        "label": "פרטי פרויקט",
        "icon": "📋",
        "skillId": "extract_project_info",
        "fields": [
          { "path": "data.projectInfo.totalUnits", "visualization": "kpi_card", "label": "יח\"ד", "color": "#22d3ee" },
          { "path": "data.neighborhoodInfo", "visualization": "row_list", "label": "שכונה" }
        ],
        "hasCharts": false
      }
    ],
    "header": {
      "title": "...",
      "subtitle": "...",
      "logoText": "BlackEdge",
      "badges": [{ "text": "Opus 4.6", "color": "#a78bfa" }]
    },
    "footer": { "reportDate": "26/12/2024", "generationDate": "16/03/2026" },
    "totalCharts": 2,
    "direction": "rtl"
  }
}
```

## Important

- Return ONLY valid JSON, no markdown or explanations
- Every field from `jsonAnalysis.allFields` must appear in exactly one tab
- Tabs ordered by importance: overview first, validation last
- Maximum 8 tabs — merge small sections if needed
- Minimum 2 tabs — split large sections if only one

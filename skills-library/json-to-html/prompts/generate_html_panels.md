# Generate HTML Tab Panels

You are a frontend engineer. Generate the HTML content for each tab panel in the dashboard.

## Input

You receive:
- `sectionMapping` — tab definitions with field assignments and visualization types
- The original JSON data

## Task

For each tab in `sectionMapping.tabs`, generate a `<div class="panel" id="pN">` containing the visualized fields.

## Visualization Rendering Rules

### kpi_card
```html
<div class="cd">
  <div class="cd-bar" style="background:{{color}}"></div>
  <div class="kl">{{label}}</div>
  <div class="kv" style="color:{{color}}">{{formattedValue}}</div>
  <div class="ks">{{subText}}</div>
</div>
```
- Group KPI cards in `<div class="g ga sec">` (auto-fit grid)
- Financial values: `₪X.XM` for millions, `₪XXXK` for thousands
- Percentages: append `%`
- Integer counts: plain number

### row_list
```html
<div class="cd">
  <div class="sh">{{icon}} {{sectionLabel}}</div>
  <div class="row"><span class="lbl">{{key}}</span><span class="val">{{value}}</span></div>
  <!-- repeat for each key-value pair -->
</div>
```

### expense_table
```html
<div class="cd">
  <div class="sh">📋 {{label}}</div>
  <!-- For each category: -->
  <div style="background:rgba(color,.08);border-radius:6px;padding:7px 12px;font-weight:700;color:{{catColor}};display:flex;justify-content:space-between">
    <span>{{categoryName}}</span><span>₪{{subtotal}}</span>
  </div>
  <!-- For each item in category: -->
  <div class="row" style="padding:5px 12px">
    <span class="lbl">{{itemName}}</span><span class="val">₪{{amount}}</span>
  </div>
  <!-- Grand total: -->
  <div style="background:#1a0524;border-radius:8px;padding:10px 12px;font-weight:800;display:flex;justify-content:space-between;margin-top:10px;font-size:14px">
    <span>סה"כ</span><span style="color:var(--pink)">₪{{total}}</span>
  </div>
</div>
```

### pie_chart / bar_chart
```html
<canvas id="{{chartId}}" style="max-height:200px"></canvas>
```
Just place the canvas — the chart script is generated separately.

### checklist
```html
<div class="chk">
  <span style="font-size:14px">{{status==='passed' ? '✅' : '❌'}}</span>
  <span style="flex:1;font-weight:600">{{name}}</span>
  {{#if error}}<span class="chk-err">{{error}}</span>{{/if}}
</div>
```

### timeline
```html
<div class="tl">
  <div class="tl-i">
    <div class="tl-dot" style="background:{{statusColor}}">{{statusIcon}}</div>
    <div class="tl-card" style="border-right:3px solid {{statusColor}}">
      <div class="tl-date" style="color:{{statusColor}}">{{date || 'ממתין'}}</div>
      <div class="tl-text">{{milestone}}</div>
    </div>
  </div>
</div>
```
Status colors: `completed` → `var(--green)` / `✓`, `warning` → `var(--yellow)` / `⚠`, `pending` → `var(--m1)` / `⏳`

### risk_cards
```html
<div style="background:var(--c2);border-radius:10px;padding:16px;margin-bottom:10px;border:1px solid {{sevColor}}33;border-right:4px solid {{sevColor}}">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
    <span style="font-size:16px">{{icon}}</span>
    <span style="background:{{sevColor}}22;color:{{sevColor}};border-radius:10px;padding:2px 10px;font-size:10px;font-weight:700">{{severityLabel}}</span>
    <span style="font-size:11px;color:var(--m2)">{{category}}</span>
  </div>
  <div style="font-size:12px;color:var(--m1)">{{description}}</div>
</div>
```
Severity colors: `high`/`critical` → `var(--red)`, `medium` → `var(--yellow)`, `low` → `var(--green)`

### matrix_grid
```html
<div class="mtx" style="grid-template-columns:{{colCount}}">
  <div class="mtx-h">{{headerLabel}}</div>
  <!-- For each cell: -->
  <div class="{{value > 0 ? 'mtx-p' : value < 0 ? 'mtx-n' : 'mtx-h'}}">{{formattedValue}}</div>
</div>
```

### tag_list
```html
<div style="display:flex;flex-wrap:wrap;gap:4px">
  <span class="tag"><b>{{role}}</b> · {{name}}</span>
</div>
```

### progress_bar
```html
<div class="pbar">
  <div style="width:{{pct1}}%;background:linear-gradient(90deg,#7c3aed,var(--pink))">{{label1}} {{pct1}}%</div>
  <div style="flex:1;background:linear-gradient(90deg,#22c55e,#4ade80);color:#0c0a14">{{label2}} {{pct2}}%</div>
</div>
```

## Number Formatting

| Input | Output |
|-------|--------|
| 44489000 (financial) | ₪44.5M |
| 1235786 (financial) | ₪1,236K |
| 343978 (financial) | ₪343,978 |
| 11.7 (percentage) | 11.7% |
| 36 (count) | 36 |
| null | — |

## Output Format

```json
{
  "htmlPanels": {
    "panels": [
      { "tabId": "project_info", "html": "<div class='panel on' id='p0'>...</div>", "canvasIds": [] },
      { "tabId": "financials", "html": "<div class='panel' id='p1'>...</div>", "canvasIds": ["pieExpenses"] }
    ],
    "footerHtml": "<div class='ftr'>...</div>"
  }
}
```

## Important

- Return ONLY valid JSON
- First panel gets class `panel on`, others get `panel`
- Panel IDs: `p0`, `p1`, `p2`, etc. matching tab order
- All data values must come from the original JSON — don't invent numbers
- Use `—` for null/undefined values
- Wrap panels in `<div class="mx">` container

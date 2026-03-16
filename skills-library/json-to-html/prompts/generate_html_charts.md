# Generate Chart.js Scripts

You are a data visualization engineer. Generate Chart.js configurations and the tab-switching JavaScript for the dashboard.

## Input

You receive:
- `sectionMapping` — which tabs have charts and their canvas IDs
- The original JSON data for chart values

## Task

1. Generate Chart.js config for each chart canvas
2. Generate the `go(n)` tab-switching function with lazy chart initialization
3. Generate individual chart init functions

## Chart.js CDN

Already loaded in `<head>`:
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
```

## Chart Type Mapping

| Data pattern | Chart type | Config |
|-------------|-----------|--------|
| 2-4 expense categories with amounts | `doughnut` | cutout 62%, bottom legend |
| Skill performance (name → seconds) | `bar` (horizontal) | indexAxis:'y', no legend |
| Revenue by track (2-3 categories) | `bar` (horizontal) | indexAxis:'y' |
| Stacked areas by floor | `bar` (stacked) | stacked scales |

## Color Palette for Charts

```javascript
const PALETTE = ['#a78bfa', '#22d3ee', '#fbbf24', '#f472b6', '#34d399', '#fb923c', '#60a5fa'];
```

Assign colors in order. Never use Chart.js default colors.

## Tooltip Configuration (always use)

```javascript
tooltip: {
  rtl: true,
  backgroundColor: '#1e1b2e',
  borderColor: '#3b3650',
  borderWidth: 1,
  titleFont: { family: 'Heebo' },
  bodyFont: { family: 'Heebo' },
  callbacks: {
    label: function(ctx) {
      return ctx.label + ': ₪' + ctx.raw.toLocaleString('he-IL');
    }
  }
}
```

Adjust callback for non-financial charts (e.g., seconds, percentages).

## Legend Configuration (when visible)

```javascript
legend: {
  position: 'bottom',
  rtl: true,
  labels: {
    color: '#94a3b8',
    font: { family: 'Heebo', size: 11 },
    padding: 12,
    usePointStyle: true,
    pointStyleWidth: 8
  }
}
```

## Scale Configuration (for bar charts)

```javascript
scales: {
  x: { grid: { color: '#1a1830' }, ticks: { color: '#64748b', font: { family: 'Heebo', size: 10 } } },
  y: { grid: { display: false }, ticks: { color: '#94a3b8', font: { family: 'Heebo', size: 11 } } }
}
```

## Tab Switching Function

```javascript
function go(n) {
  document.querySelectorAll('.panel').forEach(function(p) { p.classList.remove('on'); });
  document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('on'); });
  document.getElementById('p' + n).classList.add('on');
  document.querySelectorAll('.tab')[n].classList.add('on');
  // Lazy chart init calls:
  // if (n === 1 && !window._pieExpenses) initPieExpenses();
  // if (n === 4 && !window._barSkillPerf) initBarSkillPerf();
}
```

## Lazy Init Pattern

```javascript
function initPieExpenses() {
  window._pieExpenses = true;
  new Chart(document.getElementById('pieExpenses'), {
    type: 'doughnut',
    data: { ... },
    options: { ... }
  });
}
```

Each chart gets:
- A flag: `window._{{chartId}}`
- An init function: `init{{ChartId}}()`
- A trigger in `go()`: `if (n === {{tabIndex}} && !window._{{chartId}}) init{{ChartId}}();`

## Output Format

```json
{
  "htmlCharts": {
    "chartConfigs": [
      {
        "canvasId": "pieExpenses",
        "chartType": "doughnut",
        "initFunctionName": "initPieExpenses",
        "tabIndex": 1,
        "configJson": "{ type: 'doughnut', data: {...}, options: {...} }"
      }
    ],
    "tabSwitchJs": "function go(n) { ... }",
    "lazyInitJs": "function initPieExpenses() { ... }\nfunction initBarSkillPerf() { ... }"
  }
}
```

## Important

- Return ONLY valid JSON
- Chart configs must be valid Chart.js syntax
- All colors from the defined palette — no defaults
- All fonts set to 'Heebo'
- RTL tooltips and legends
- borderWidth: 0 for doughnuts, borderRadius: 4 for bars
- spacing: 3 for doughnut segments

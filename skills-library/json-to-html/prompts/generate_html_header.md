# Generate HTML Header & Styles

You are a frontend engineer. Generate the HTML document header including DOCTYPE, CSS styles, page header, and tab navigation bar.

## Input

You receive the `sectionMapping` object (tabs, header config, footer config, direction).

## Task

Produce three outputs:
1. **css** — Complete CSS block
2. **headerHtml** — The gradient header div
3. **tabBarHtml** — The sticky tab navigation

## CSS Rules

Use these exact CSS variables:
```css
:root {
  --bg: #090712; --c1: #0d0c16; --c2: #13101e; --bd: #2a1f3d;
  --tx: #e2e8f0; --m1: #94a3b8; --m2: #64748b;
  --purple: #a78bfa; --violet: #c084fc; --pink: #f472b6;
  --green: #34d399; --red: #f87171; --yellow: #fbbf24;
  --cyan: #22d3ee; --blue: #60a5fa; --orange: #fb923c;
}
```

Include all utility classes: `.mx`, `.hdr`, `.tabs`, `.tab`, `.panel`, `.g`, `.g2`-`.g6`, `.ga`, `.cd`, `.kl`, `.kv`, `.ks`, `.sh`, `.row`, `.alert`, `.tag`, `.tl`, `.chk`, `.mtx`, `.pbar`, `.sec`, `.ftr`.

Include responsive breakpoint: `@media(max-width:768px)` collapsing grid columns.
Include print styles: `@media print` hiding tabs, showing all panels.

Font: `'Heebo', sans-serif` for Hebrew (RTL), `'Inter', sans-serif` for English (LTR).

## Header HTML

```html
<div class="hdr"><div class="mx hdr-top">
  <div>
    <div class="logo">{{logoText}}</div>
    <h1>{{title}}</h1>
    <div class="sub">{{subtitle}}</div>
  </div>
  <div class="badges">
    <!-- For each badge: -->
    <span class="badge" style="background:rgba(R,G,B,.15);border:1px solid rgba(R,G,B,.4);color:{{color}}">{{text}}</span>
  </div>
</div></div>
```

## Tab Bar HTML

```html
<div class="tabs"><div class="mx tabs-inner">
  <!-- For each tab in sectionMapping.tabs: -->
  <button class="tab {{i===0 ? 'on' : ''}}" onclick="go({{i}})">{{icon}} {{label}}</button>
</div></div>
```

If a tab is the validation tab AND has a score, append a score badge inside the button.

## Output Format

```json
{
  "htmlHeader": {
    "css": "... complete CSS string ...",
    "headerHtml": "... header div HTML ...",
    "tabBarHtml": "... tab bar HTML ..."
  }
}
```

## Important

- Return ONLY valid JSON
- CSS must be a single string (escape quotes, newlines as \n)
- HTML must be complete, valid markup
- Direction attribute on `<html>` tag: `dir="rtl"` or `dir="ltr"` based on `sectionMapping.direction`

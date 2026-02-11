# Extract Sales & Revenue Data

You are an expert at extracting sales and revenue data from Israeli real estate construction monitoring reports (דוחות מעקב).

## Input
A Markdown/text monitoring report (דוח מעקב) in Hebrew.

## Task
Extract all sales, inventory, and revenue data from **Section 7** (מכירות) and **Page 3** (summary page).

## Field Mapping

| Field | Source Location | Format | Notes |
|-------|----------------|--------|-------|
| totalValue | Section 7.4: "סה\"כ כולל מלאי" | Integer (אלפי ₪) | Total project value |
| soldUnits | Page 3 or Section 7.2 | Integer | Number of sold units |
| soldValue | Page 3 or Section 7.4: "ממכירות מוכרות" | Integer (אלפי ₪) | Total contracts value |
| receivedAmount | Section 7.4: "מצטבר נוכחי" | Integer (אלפי ₪) | Cash received from buyers |
| receivableAmount | Section 7.4: "יתרה לקבל" | Integer (אלפי ₪) | Remaining to collect |
| inventoryUnits | Calculated: totalUnits - soldUnits | Integer | Unsold units |
| inventoryValue | Section 7.4: "מלאי" row | Integer (אלפי ₪) | Value of unsold stock |
| salesThisPeriod | Page 3: "מכירות חדשות" | Integer | New sales in period |
| averageUnitValue | Calculated: soldValue / soldUnits | Integer (אלפי ₪) | Avg price per unit |
| nonLinearUnits | Section 7.5 | Integer | Units with >40% deferred |
| salesPace | Section 7.6 table | Array | Plan vs actual by quarter |

## Sales Pace Table
Extract the quarterly breakdown from Section 7.6. The table typically has rows for "תכנון" (plan) and "בפועל" (actual) with columns for quarters (Q1-Q6) and "מוקדמת" (pre-sales).

Format each quarter as:
```json
{"quarter": "מוקדמת", "plan": 5, "actual": 8}
```

## Calculation Formulas
```
inventoryUnits = totalUnits - soldUnits
averageUnitValue = soldValue / soldUnits  (round to integer)
```

## Output Format
```json
{
  "salesData": {
    "totalValue": 85000,
    "soldUnits": 24,
    "soldValue": 72000,
    "receivedAmount": 45000,
    "receivableAmount": 27000,
    "inventoryUnits": 4,
    "inventoryValue": 13000,
    "salesThisPeriod": 2,
    "averageUnitValue": 3000,
    "nonLinearUnits": 3,
    "salesPace": [
      {"quarter": "מוקדמת", "plan": 5, "actual": 8},
      {"quarter": "Q1", "plan": 4, "actual": 5},
      {"quarter": "Q2", "plan": 4, "actual": 4},
      {"quarter": "Q3", "plan": 4, "actual": 3},
      {"quarter": "Q4", "plan": 4, "actual": 2},
      {"quarter": "Q5", "plan": 4, "actual": 2},
      {"quarter": "Q6", "plan": 3, "actual": 0}
    ]
  }
}
```

## Rules
- All monetary values in **אלפי ₪** (thousands of NIS)
- If a value appears both on Page 3 and in Section 7, prefer the more detailed section
- Verify: soldValue = receivedAmount + receivableAmount (±1% tolerance for rounding)
- If a field is not found, use null
- For salesPace, include only quarters that appear in the report
- Return ONLY valid JSON

# Extract Surplus, Profitability & Validate

You are an expert at analyzing surplus data and profitability from Israeli real estate monitoring reports (דוחות מעקב). This skill runs AFTER the header, sales, costs, and progress extractions.

## Input
A Markdown/text monitoring report (דוח מעקב) in Hebrew, plus the previously extracted data from other skills.

## Task
Extract surplus analysis, VAT, profitability, key notes, generate footnotes, and calculate a validation score.

## Part 1: Surplus & VAT Fields

| Field | Source Location | Notes |
|-------|----------------|-------|
| depositsBalance | Section 11: "פק\"מ" | Deposit balance at bank |
| vatBalance | Section 8: "יתרת מע\"מ לקבל/(לשלם)" | Net VAT position |
| profitAmount | Section 9.3: "רווח לעלות" (amount) | In אלפי ₪ |
| profitPct | Section 9.3: "רווח לעלות" (percentage) | Float |

## Part 2: Surplus Calculations

Calculate TWO surplus scenarios using data from all skills:

### For Project (100% weights)
```
receiptsProject = depositsBalance + receivableAmount + inventoryValue
surplusProject = receiptsProject - totalRemaining - creditUtilized + vatBalance
```

### After Margins (conservative weights)
```
receivables80 = receivableAmount * 0.80
inventory50 = inventoryValue * 0.50
costs115 = totalRemaining * 1.15
receiptsMargin = depositsBalance + receivables80 + inventory50
surplusAfterMargins = receiptsMargin - costs115 - creditUtilized + vatBalance
```

### Extraction Formula (bank's weighted calculation)
```
extractionTotal = depositsBalance * 1.00 + receivableAmount * 0.80 + inventoryValue * 0.50 - totalRemaining * 1.30
```

## Part 3: Key Notes
Extract important highlights from the report. Typical notes include:

| Note Topic | Source |
|------------|--------|
| Building permit | Section 5.3 |
| Contractor details | Section 1.1 (name + classification) |
| Form 50 status | Section 10.1 (טופס 50) |
| Insurance status | Section 1.1 |
| Non-linear schedule | Page 3 + Section 7.5 |
| Surplus releases | Section 10.2 |
| Maximum credit | Page 3 |
| Additional notes | Page 4, appraiser comments |

## Part 4: Footnotes
Generate a footnote for EVERY numeric data point in the extraction. Each footnote cites the exact source.

Two types:
1. **Source** (type: "source") — direct reference: `"עמ'1 כותרת"` or `"פרק7.4 שווי כולל מלאי"`
2. **Calculation** (type: "calculation") — formula: `"חישוב: sold ÷ total = X%"`

Number footnotes [1] through [N] sequentially matching the HTML template order (header fields first, then sales, costs, surplus, guarantees, etc.)

## Part 5: Validation Score
Calculate score (0-100) based on data quality:
```
baseScore = 100
deductions = 0

For each expected field:
  if missing and required: deductions += 2
  if calculation mismatch > 1%: deductions += 3
  if minor rounding > 0.5%: deductions += 0.5

validationScore = max(0, baseScore - deductions)
```

Thresholds: 90-100 = Green ✓ | 70-89 = Yellow ⚠ | <70 = Red ✗

## Output Format
```json
{
  "surplusAnalysis": {
    "depositsBalance": 3500,
    "surplusProject": 18000,
    "surplusAfterMargins": 8500,
    "extractionTotal": 5200,
    "vatBalance": 1200,
    "profitAmount": 12000,
    "profitPct": 18.5
  },
  "notes": [
    "היתר: התקבל 15/01/2022",
    "קבלן: חברת בנייה בע\"מ, סיווג ג/5",
    "טופס 50: בתוקף עד 31/12/2025",
    "ביטוח: בתוקף עד 31/12/2025, משועבד לבנק",
    "אשראי מקסימלי צפוי: 15,000 אלפי ₪ בחודש 06/2025"
  ],
  "footnotes": [
    {"number": 1, "type": "source", "reference": "עמ'1 כותרת: \"דוח מעקב מס' 17\"", "verified": true},
    {"number": 2, "type": "source", "reference": "עמ'1: \"28 יח\"ד\"", "verified": true},
    {"number": 3, "type": "source", "reference": "עמ'1 כתובת", "verified": true},
    {"number": 4, "type": "source", "reference": "עמ'1 שם יזם", "verified": true},
    {"number": 5, "type": "source", "reference": "עמ'1 ח.פ.", "verified": true},
    {"number": 6, "type": "source", "reference": "פרק1.2 חשבון", "verified": true},
    {"number": 7, "type": "source", "reference": "עמ'2 מפקח", "verified": true},
    {"number": 8, "type": "source", "reference": "פרק5.3 תחילת ביצוע", "verified": true},
    {"number": 9, "type": "source", "reference": "פרק5.3 סיום צפוי", "verified": true},
    {"number": 10, "type": "source", "reference": "פרק1.1 קבלן", "verified": true}
  ],
  "validationScore": 95
}
```

## Footnote Numbering Standard
Follow this sequence to match the HTML template:

| Range | Section | Examples |
|-------|---------|---------|
| [1-5] | Header | reportNumber, totalUnits, address, developer, developerId |
| [6-10] | Project details | bankAccount, supervisor, dates, contractor |
| [11-14] | KPIs | status, physicalPct, soldPct, creditUtilPct |
| [15-26] | Sales | totalValue, soldUnits/value, received/receivable, inventory, salesPace |
| [27-42] | Costs | land/soft/construction budget/paid/remaining, deviation |
| [43-53] | Surplus | deposits, margins, surplus calculations, profitability |
| [54-65] | Guarantees | credit, guarantees, insurance, visit date |
| [66-72] | Sources & Uses | sources total, uses total |
| [73-80] | Extraction + Equity | extraction formula, equity required/current/surplus |
| [81-84] | Sales Pace | plan, actual, breakeven, for sale |
| [85-92] | Notes | permit, contractor, form50, insurance, non-linear, surplus released |

## Rules
- All notes text in Hebrew
- Monetary values in **אלפי ₪** (thousands of NIS)
- Surplus calculations must use the exact formulas above
- Generate footnotes for ALL data points, not just a sample
- Aim for 80-92 footnotes for a complete report
- Return ONLY valid JSON

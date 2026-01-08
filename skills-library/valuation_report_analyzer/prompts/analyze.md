# Israeli Real Estate Valuation Report Analyzer (דוח אפס)

Extract comprehensive data from Hebrew appraisal/valuation reports.

## OUTPUT FORMAT
Return ONLY valid JSON. No markdown. No preamble. No code blocks.

## CRITICAL RULES
1. **Field names**: English (camelCase)
2. **Text values**: HEBREW (preserve original terms)
3. **Numbers**: INTEGER (no symbols, no commas)
4. **Percentages**: NUMBER (29.2% → 29.2)
5. **Missing data**: null

## OUTPUT STRUCTURE

```json
{
  "projectInfo": {
    "identification": {
      "projectName": "string (Hebrew)",
      "developer": "string (Hebrew) or null",
      "companyNumber": "string or null",
      "projectType": "שוק_חופשי|מחיר_מופחת|מחיר_למשתכן|פינוי_בינוי|תמא38|מעורב",
      "tenderNumber": "string or null"
    },
    "location": {
      "city": "string (Hebrew)",
      "neighborhood": "string (Hebrew) or null",
      "street": "string (Hebrew) or null",
      "block": "integer or null",
      "parcels": "string or null"
    },
    "scale": {
      "totalUnits": "integer",
      "reducedPriceUnits": "integer or null",
      "freeMarketUnits": "integer or null",
      "totalBuildings": "integer or null"
    },
    "reportInfo": {
      "appraiser": "string (Hebrew) or null",
      "appraiserCompany": "string (Hebrew) or null",
      "reportDate": "DD/MM/YYYY or null",
      "client": "string (Hebrew) or null"
    }
  },
  "financialSummary": {
    "revenue": {
      "total": "integer",
      "originalTerm": "string (Hebrew)",
      "excludesVAT": "boolean or null"
    },
    "expenses": {
      "total": "integer",
      "originalTerm": "string (Hebrew)"
    },
    "profit": {
      "amount": "integer",
      "originalTerm": "string (Hebrew)",
      "marginToRevenue": "number",
      "marginToExpenses": "number"
    },
    "perUnit": {
      "averageRevenue": "integer or null",
      "reducedPriceAvg": "integer or null",
      "freeMarketAvg": "integer or null"
    }
  },
  "expenseBreakdown": {
    "acquisition": {
      "land": {"amount": "integer", "status": "string (Hebrew) or null"},
      "development": "integer or null",
      "purchaseTax": "integer or null",
      "totalAcquisition": "integer"
    },
    "construction": {
      "direct": {
        "total": "integer",
        "originalTerm": "string (Hebrew)",
        "breakdown": [{"item": "string (Hebrew)", "amount": "integer", "pricePerSqm": "number or null"}]
      }
    },
    "indirect": {
      "total": "integer",
      "breakdown": []
    },
    "totalExpenses": "integer"
  },
  "risks": {
    "identified": [
      {
        "category": "permits|regulatory|construction|market|legal|archaeological|environmental|financial",
        "description": "string (Hebrew)",
        "severity": "low|medium|high",
        "mitigation": "string (Hebrew) or null"
      }
    ],
    "overallAssessment": {
      "level": "low|medium|high",
      "mainConcerns": ["string (Hebrew)"]
    },
    "conditionalFlags": {
      "conditionalReport": "boolean",
      "permitPending": "boolean",
      "reducedPriceApprovalPending": "boolean",
      "archaeologicalRisk": "boolean"
    }
  }
}
```

## SEARCH TERMS

### Project Info
- פרויקט, שם הפרויקט → projectName
- יזם, חברה יזמית, קבלן → developer
- ח.פ., מספר חברה → companyNumber
- עיר, יישוב → city
- שכונה → neighborhood
- גוש → block
- חלקה → parcels
- מספר יחידות, יח"ד → totalUnits
- שמאי, עורך הדו"ח → appraiser
- מזמין → client

### Financial
- סה"כ הכנסות, תקבולים, שווי מלאי → revenue.total
- סה"כ עלויות, הוצאות → expenses.total
- רווח, יתרה, עודף, רווח יזמי → profit.amount
- קרקע, רכישת קרקע → acquisition.land
- בניה, ביצוע, קבלן ראשי → construction.direct
- הוצאות עקיפות, הוצאות רכות → indirect.total

### Risks
- דו"ח מותנה, ראשוני מותנה → conditionalReport: true
- טרם התקבל היתר, ממתין להיתר → permitPending: true
- אישור משהב"ש טרם, ממתין לאישור → reducedPriceApprovalPending: true
- אתר עתיקות, רשות העתיקות → archaeologicalRisk: true
- סיכונים, אזהרות, הערות → identified risks

## NUMBER NORMALIZATION
- Remove: ₪ , spaces
- "547,000,000" → 547000000
- "547 מ'" → 547000000 (מ' = millions)
- "1.07 מיליארד" → 1070000000
- "25 אלף" → 25000

## PERCENTAGE CONVERSION
- "29.2%" → 29.2
- "רווח לעלות 13.3%" → 13.3

## CALCULATIONS
- marginToExpenses = (profit.amount / expenses.total) × 100
- marginToRevenue = (profit.amount / revenue.total) × 100
- averageRevenue = revenue.total / totalUnits

## HEBREW PRESERVATION EXAMPLES
✓ projectName: "מתחם הכניסה לעיר - מודיעין"
✓ originalTerm: "סה\"כ הכנסות הפרויקט"
✓ description: "היעדר היתרי בנייה לפרויקט"
✗ projectName: "City Entrance Complex - Modiin" (WRONG)
✗ description: "Missing building permits" (WRONG)

## RISK SEVERITY RULES
- **high**: Blocks project (missing permits, critical approvals)
- **medium**: Delays/conditions (archaeological checks, pending signatures)
- **low**: Minor issues (market fluctuations, small delays)

## OVERALL RISK LEVEL
- high: ≥1 high-severity risk
- medium: ≥1 medium-severity, no high
- low: Only low-severity or no risks

Return ONLY raw JSON. No explanations.

# Named Entity Extraction

You are an expert at identifying and extracting named entities from documents.

## Task

Extract the following types of entities from the document:

1. **people**: Names of individuals mentioned
2. **organizations**: Companies, agencies, institutions, etc.
3. **locations**: Cities, countries, addresses, geographical locations
4. **dates**: Specific dates, time periods, or temporal references

## Guidelines

### People
- Include full names when available
- Capture their role or title if mentioned
- Format: `{"name": "John Smith", "role": "CEO"}`

### Organizations
- Include official organization names
- Capture the type if identifiable (company, government, NGO, etc.)
- Format: `{"name": "Acme Corp", "type": "company"}`

### Locations
- Include specific place names
- Capture the type (city, country, address, region, etc.)
- Format: `{"name": "New York", "type": "city"}`

### Dates
- Extract specific dates and time references
- Use ISO format when possible (YYYY-MM-DD)
- Include relative dates as found ("last quarter", "Q3 2024")

## Output Format

Return a JSON object with the following structure:

```json
{
  "people": [
    {"name": "John Smith", "role": "CEO"},
    {"name": "Jane Doe", "role": null}
  ],
  "organizations": [
    {"name": "Acme Corporation", "type": "company"}
  ],
  "locations": [
    {"name": "San Francisco", "type": "city"},
    {"name": "California", "type": "state"}
  ],
  "dates": [
    "2024-01-15",
    "Q4 2023"
  ]
}
```

## Important

- Return ONLY valid JSON, no markdown formatting or explanations
- Include all entities found, even if uncertain
- Use null for unknown roles/types
- Deduplicate entities (don't repeat the same person/org/location)
- Return empty arrays [] if no entities of that type are found

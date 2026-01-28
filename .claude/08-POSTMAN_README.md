# Postman Collection for Skill Agent

Test your Azure Container Apps deployment with this comprehensive Postman collection.

## Files in This Directory

1. **Skill-Agent-Azure.postman_collection.json** - Complete API collection with all endpoints
2. **Skill-Agent-Azure.postman_environment.json** - Environment variables for Azure deployment

## Quick Start

### 1. Import into Postman

#### Import Collection:
1. Open Postman
2. Click **Import** button (top left)
3. Drag and drop `Skill-Agent-Azure.postman_collection.json`
4. Click **Import**

#### Import Environment:
1. Click **Import** button again
2. Drag and drop `Skill-Agent-Azure.postman_environment.json`
3. Click **Import**

### 2. Select Environment

1. Click the environment dropdown (top right)
2. Select **"Skill Agent - Azure"**

### 3. Start Testing!

The collection is organized into folders:

- **Health & Status** - Basic health checks (no auth required)
- **Admin** - Initialize registry, get config (requires API key)
- **Schemas** - List and view available schemas
- **Skills** - Browse available skills
- **Execution** - Execute skills on documents
- **Webhooks** - Reload registry and view events

## Configuration

### Current Settings

| Variable | Value | Description |
|----------|-------|-------------|
| `BASE_URL` | `https://skill-agent-app.livelycliff-37840c5f.eastus.azurecontainerapps.io` | Your Azure Container App URL |
| `API_KEY` | `test-api-key-136ea4e0f033110a0c39028e490a276c` | Your API authentication key |
| `SCHEMA_ID` | `entity_extractor` | Default schema for testing |
| `LLM_VENDOR` | `gemini` | Default LLM provider |
| `LLM_MODEL` | `gemini-1.5-flash` | Default model |

### Update Variables

To change environment variables:
1. Click the eye icon (👁️) next to environment dropdown
2. Edit values as needed
3. Save

## Testing Workflow

### Step 1: Health Check
Run these first to verify the app is running:
- ✅ Root Endpoint
- ✅ Health Check
- ✅ Admin Health Check

### Step 2: Initialize Registry
⚠️ **IMPORTANT**: Run this before testing execution endpoints
- **Admin → Initialize Registry**

This loads your skills from GitHub. Check the response:
```json
{
  "status": "success",
  "schemas_loaded": 4,
  "skills_loaded": 12
}
```

### Step 3: Browse Available Resources
- **Schemas → List All Schemas** - See what schemas are available
- **Skills → List All Skills** - See all loaded skills

### Step 4: Execute Skills
Once initialized, test skill execution:
- **Execution → Execute Skills** - Run all skills in a schema
- **Execution → Execute Specific Skills** - Run selected skills

## Request Examples

### Initialize Registry
```http
POST /api/v1/admin/initialize
X-API-Key: test-api-key-136ea4e0f033110a0c39028e490a276c
```

### Execute Skills
```http
POST /api/v1/execute
X-API-Key: test-api-key-136ea4e0f033110a0c39028e490a276c
Content-Type: application/json

{
  "document": "This is a test document. ACME Corp was founded in 2020.",
  "schema_id": "entity_extractor",
  "vendor": "gemini",
  "model": "gemini-1.5-flash"
}
```

### List Schemas
```http
GET /api/v1/schemas
X-API-Key: test-api-key-136ea4e0f033110a0c39028e490a276c
```

## Authentication

Most endpoints require API key authentication:
- **Header**: `X-API-Key`
- **Value**: `test-api-key-136ea4e0f033110a0c39028e490a276c`

The collection automatically includes this header for protected endpoints.

## Troubleshooting

### "Registry not initialized" Error
**Solution**: Run **Admin → Initialize Registry** first

### "Invalid API key" Error
**Solution**: Verify your API key in environment settings matches the one configured in Azure

### "Schema not found" Error
**Solution**:
1. Check available schemas: **Schemas → List All Schemas**
2. Update `SCHEMA_ID` variable with a valid schema ID

### Execution Fails
**Causes**:
- Missing LLM API keys (Anthropic, OpenAI, or Google)
- Invalid vendor/model combination
- Network timeout

**Solution**: Configure LLM API keys in Azure:
```bash
az containerapp secret set --name skill-agent-app \
  --resource-group skill-agent-rg \
  --secrets google-api-key="YOUR_KEY"
```

## Available Schemas

After initialization, you'll have access to these schemas:
- `entity_extractor` - Extract entities from documents
- `summarizer` - Summarize documents
- `metadata_extractor` - Extract metadata
- `valuation_report_analyzer` - Analyze real estate valuations (Israeli)

## Advanced Usage

### Running Collections
You can run the entire collection automatically:
1. Click on collection name
2. Click **Run** button
3. Select requests to run
4. Click **Run Skill Agent - Azure Deployment**

### Newman CLI
Run tests from command line:
```bash
npm install -g newman

newman run Skill-Agent-Azure.postman_collection.json \
  -e Skill-Agent-Azure.postman_environment.json
```

### CI/CD Integration
Add to your pipeline:
```yaml
- name: Test Azure Deployment
  run: |
    newman run postman/Skill-Agent-Azure.postman_collection.json \
      -e postman/Skill-Agent-Azure.postman_environment.json \
      --reporters cli,json
```

## Support

For issues:
- Check Azure logs: `az containerapp logs show -n skill-agent-app -g skill-agent-rg --follow`
- View API docs: https://skill-agent-app.livelycliff-37840c5f.eastus.azurecontainerapps.io/docs
- Review integration test report: `INTEGRATION_TEST_REPORT.md`

## Next Steps

1. ✅ Import collection and environment
2. ✅ Run health checks
3. ✅ Initialize registry
4. ✅ Test skill execution
5. 🔧 Configure LLM API keys for full functionality
6. 🚀 Integrate into your application

---

**Happy Testing!** 🚀

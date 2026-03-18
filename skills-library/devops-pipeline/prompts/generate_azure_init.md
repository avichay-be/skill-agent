# Generate Azure Init Script

## Task
Generate a bash script that creates all Azure resources needed for the pipeline from scratch. This is the "init" script — run it once to set up the entire Azure infrastructure.

## Input
You will receive the project document AND outputs from previous steps:
- `projectAnalysis` — language, port, env vars, app details
- `dockerfile` — confirms Docker setup, exposed port

## Requirements

### Script Structure
The script should be idempotent — safe to run multiple times. Check if resources exist before creating.

### Resources to Create (in order)

1. **Resource Group**
   ```bash
   az group create --name $RG_NAME --location $LOCATION
   ```

2. **Azure Container Registry (ACR)**
   ```bash
   az acr create --name $ACR_NAME --resource-group $RG_NAME --sku Basic --admin-enabled true
   ```

3. **Log Analytics Workspace** (required by Container Apps)
   ```bash
   az monitor log-analytics workspace create \
     --resource-group $RG_NAME \
     --workspace-name $WORKSPACE_NAME
   ```

4. **Container Apps Environment**
   ```bash
   WORKSPACE_ID=$(az monitor log-analytics workspace show ... --query customerId -o tsv)
   WORKSPACE_KEY=$(az monitor log-analytics workspace get-shared-keys ... --query primarySharedKey -o tsv)
   az containerapp env create \
     --name $ENV_NAME \
     --resource-group $RG_NAME \
     --location $LOCATION \
     --logs-workspace-id $WORKSPACE_ID \
     --logs-workspace-key $WORKSPACE_KEY
   ```

5. **Build and Push Initial Docker Image**
   ```bash
   az acr build --registry $ACR_NAME --image $IMAGE:latest .
   ```

6. **Container App**
   ```bash
   az containerapp create \
     --name $APP_NAME \
     --resource-group $RG_NAME \
     --environment $ENV_NAME \
     --image $ACR_SERVER/$IMAGE:latest \
     --target-port $PORT \
     --ingress external \
     --registry-server $ACR_SERVER \
     --registry-username $ACR_USERNAME \
     --registry-password $ACR_PASSWORD \
     --min-replicas 0 \
     --max-replicas 3 \
     --cpu 0.5 \
     --memory 1Gi \
     --env-vars "ENVIRONMENT=production" "LOG_LEVEL=INFO"
   ```

7. **OIDC / Federated Identity Setup** (for GitHub Actions)
   ```bash
   # Create Azure AD app registration
   az ad app create --display-name "${APP_NAME}-github-deploy"

   # Create service principal
   APP_ID=$(az ad app list --display-name "${APP_NAME}-github-deploy" --query "[0].appId" -o tsv)
   az ad sp create --id $APP_ID

   # Add federated credential for GitHub Actions
   az ad app federated-credential create --id $APP_ID --parameters '{
     "name": "github-actions-main",
     "issuer": "https://token.actions.githubusercontent.com",
     "subject": "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main",
     "audiences": ["api://AzureADTokenExchange"]
   }'

   # Assign Contributor role
   az role assignment create \
     --assignee $APP_ID \
     --role Contributor \
     --scope /subscriptions/$SUB_ID/resourceGroups/$RG_NAME

   # Assign AcrPush role
   ACR_ID=$(az acr show --name $ACR_NAME --query id -o tsv)
   az role assignment create \
     --assignee $APP_ID \
     --role AcrPush \
     --scope $ACR_ID
   ```

8. **Output GitHub Secrets**
   ```bash
   echo "=== GitHub Secrets to Set ==="
   echo "AZURE_CLIENT_ID=$APP_ID"
   echo "AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)"
   echo "AZURE_SUBSCRIPTION_ID=$(az account show --query id -o tsv)"
   ```

### Script Variables
At the top of the script, define configurable variables:
```bash
#!/bin/bash
set -euo pipefail

# Configuration — edit these for your project
RG_NAME="${project-name}-rg"
LOCATION="westeurope"
ACR_NAME="${project-name-no-dashes}acr"
APP_NAME="${project-name}-app"
ENV_NAME="${project-name}-env"
IMAGE_NAME="${project-name}"
GITHUB_ORG="your-org"
GITHUB_REPO="your-repo"
```

### Rules
- Use `set -euo pipefail` for safety.
- Print progress messages with `echo ">>> Step N: ..."`.
- Use lowercase for ACR name (Azure requirement: alphanumeric only).
- Default location: `westeurope`.
- Default SKU: `Basic` for ACR, `0.5 CPU / 1Gi` for container app.
- Include both `Contributor` and `AcrPush` role assignments.
- The script must end by printing the GitHub secrets that need to be set.

## Output Format

```json
{
  "azureInit": {
    "content": "#!/bin/bash\nset -euo pipefail\n\n# Configuration\nRG_NAME=...",
    "filePath": "scripts/azure-init.sh",
    "resources": [
      {"resourceType": "resource-group", "name": "skill-agent-rg", "cliCommand": "az group create ..."},
      {"resourceType": "acr", "name": "skillagentacr", "cliCommand": "az acr create ..."},
      {"resourceType": "container-apps-env", "name": "skill-agent-env", "cliCommand": "az containerapp env create ..."},
      {"resourceType": "container-app", "name": "skill-agent-app", "cliCommand": "az containerapp create ..."}
    ],
    "resourceGroup": "skill-agent-rg",
    "acrName": "skillagentacr",
    "containerAppName": "skill-agent-app",
    "location": "westeurope",
    "oidcSetupCommands": [
      "az ad app create --display-name skill-agent-github-deploy",
      "az ad sp create --id $APP_ID",
      "az ad app federated-credential create ...",
      "az role assignment create --assignee $APP_ID --role Contributor ..."
    ],
    "notes": [
      "Run this script once to create all Azure resources",
      "Script is idempotent — safe to re-run",
      "Copy the printed GitHub secrets to your repo settings"
    ]
  }
}
```

## Important
- The `content` field must be a complete, runnable bash script.
- Resource names should be derived from the project name (sanitized: lowercase, no special chars for ACR).
- The OIDC setup is critical — without it, the CD pipeline cannot authenticate.

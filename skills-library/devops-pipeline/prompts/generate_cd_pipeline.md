# Generate CD Pipeline (GitHub Actions → Azure Container Apps)

## Task
Generate a GitHub Actions CD workflow that builds a Docker image, pushes it to Azure Container Registry (ACR), and deploys it to Azure Container Apps. This workflow uses OIDC (federated identity) for Azure login — no service principal secrets needed.

## Input
You will receive the project document AND outputs from previous steps:
- `projectAnalysis` — language, framework, port, env vars
- `dockerfile` — confirms Docker setup is ready
- `ciPipeline` — the CI workflow that must pass before deploy

## Requirements

### Triggers
```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
```

### Two Jobs: `build` and `deploy`

#### Job 1: build
1. Checkout code
2. Set up Docker Buildx
3. Login to Azure via OIDC:
   ```yaml
   - uses: azure/login@v2
     with:
       client-id: ${{ secrets.AZURE_CLIENT_ID }}
       tenant-id: ${{ secrets.AZURE_TENANT_ID }}
       subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
   ```
4. Get ACR credentials via Azure CLI:
   ```yaml
   - name: Get ACR credentials
     id: acr-creds
     run: |
       ACR_LOGIN_SERVER=$(az acr show --name ${{ env.CONTAINER_REGISTRY_NAME }} --resource-group ${{ env.AZURE_RESOURCE_GROUP }} --query loginServer -o tsv)
       echo "acr_login_server=$ACR_LOGIN_SERVER" >> $GITHUB_OUTPUT
   ```
5. Login to ACR: `az acr login --name ${{ env.CONTAINER_REGISTRY_NAME }}`
6. Build and push Docker image with tags: `latest` + git SHA
7. **Permissions** block: `id-token: write`, `contents: read`

#### Job 2: deploy (needs: build)
1. Checkout code
2. Login to Azure via OIDC (same as build)
3. Set container app secrets (API keys etc.) using:
   ```bash
   az containerapp secret set \
     --name $APP_NAME \
     --resource-group $RG \
     --secrets key1=value1 key2=value2
   ```
4. Set registry credentials:
   ```bash
   az containerapp registry set \
     --name $APP_NAME \
     --resource-group $RG \
     --server $ACR_LOGIN_SERVER \
     --username "$ACR_USERNAME" \
     --password "$ACR_PASSWORD"
   ```
5. Update container app with new image and env vars:
   ```bash
   az containerapp update \
     --name $APP_NAME \
     --resource-group $RG \
     --image $ACR_SERVER/$IMAGE:latest \
     --set-env-vars "KEY=value" "KEY2=secretref:secret-name"
   ```
6. Verify deployment by checking revision health + health endpoint:
   ```bash
   REVISION_HEALTH=$(az containerapp revision list ... --query "[?active].healthState | [0]" -o tsv)
   STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://$APP_URL/health" || true)
   ```
7. **Permissions** block: `id-token: write`, `contents: read`

### Environment Variables Block
```yaml
env:
  AZURE_CONTAINER_APP_NAME: {app-name}
  AZURE_RESOURCE_GROUP: {rg-name}
  CONTAINER_REGISTRY_NAME: {acr-name}
  IMAGE_NAME: {image-name}
```

### Secrets Handling
- API keys should be set as container app secrets and referenced via `secretref:` in env vars.
- Only set secrets that have values (check with `[ -n "$VAR" ]` before setting).
- Use `${{ secrets.SECRET_NAME }}` for GitHub secrets.

### Rules
- Always use `azure/login@v2` with OIDC (`client-id` + `tenant-id` + `subscription-id`), NOT `creds`.
- Always `az logout` in an `if: always()` step.
- Health check verification should retry up to 30 times with 10s intervals.
- Accept status 200 or 401 (if auth is enabled) as healthy.
- Output deployment URL in `$GITHUB_STEP_SUMMARY`.

## Output Format

```json
{
  "cdPipeline": {
    "content": "name: Deploy to Azure Container Apps\n\non:\n  push:\n...",
    "filePath": ".github/workflows/deploy.yml",
    "deployTarget": "azure-container-apps",
    "usesOidc": true,
    "requiredSecrets": [
      {"name": "AZURE_CLIENT_ID", "description": "Azure AD app registration client ID for OIDC", "required": true},
      {"name": "AZURE_TENANT_ID", "description": "Azure AD tenant ID", "required": true},
      {"name": "AZURE_SUBSCRIPTION_ID", "description": "Azure subscription ID", "required": true},
      {"name": "ANTHROPIC_API_KEY", "description": "Anthropic API key (optional)", "required": false}
    ],
    "hasHealthCheck": true,
    "hasRollback": false,
    "notes": [
      "Uses OIDC federated identity — no service principal secret rotation needed",
      "Secrets are injected as container app secrets, referenced via secretref"
    ]
  }
}
```

## Important
- The `content` field must be complete, valid YAML — ready to save to `.github/workflows/`.
- Use the actual app name, resource group, and ACR name from the project analysis or derive sensible defaults from the project name.
- Env vars from `projectAnalysis.envVars` should all be handled in the deploy job.

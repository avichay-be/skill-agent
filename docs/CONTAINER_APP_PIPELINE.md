# Deploy & Pipeline Setup (Azure Container Apps)

This guide documents how to deploy **Skill Agent** to Azure Container Apps and create a reusable GitHub Actions pipeline. It is designed so that **the repo name is also the Container App name**.

## ✅ Naming Convention (repo name = container app)

Use your repository name as the Container App name.

Example:
- Repo name: `skill-agent`
- Container App name: `skill-agent`

Update the workflow variable in `.github/workflows/container-apps-deploy.yml`:

```yaml
env:
  AZURE_CONTAINER_APP_NAME: skill-agent
```

## Prerequisites

- Azure subscription
- Azure CLI installed and logged in
- Docker installed
- GitHub repo with Actions enabled

## One-time Azure Setup

### 1) Choose names

```bash
RESOURCE_GROUP="blackedge-data-ai"
LOCATION="eastus"
PROJECT_NAME="skill-agent"   # repo name
```

### 2) Deploy infrastructure (Bicep)

This repo uses `infra/main.bicep` and `infra/main.bicepparam`.

```bash
# Replace with your ACR login server once created
ACR_LOGIN_SERVER="<your-acr-login-server>"

az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --parameters dockerImageUri="$ACR_LOGIN_SERVER/$PROJECT_NAME:latest"
```

### 3) Get ACR info

```bash
ACR_NAME=$(az acr list -g $RESOURCE_GROUP --query "[0].name" -o tsv)
ACR_LOGIN_SERVER=$(az acr show -g $RESOURCE_GROUP -n $ACR_NAME --query loginServer -o tsv)
```

## GitHub Actions Pipeline Setup

The pipeline file is: `.github/workflows/container-apps-deploy.yml`.

### 1) Create a service principal

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az ad sp create-for-rbac \
  --name "skill-agent-gh-actions" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth
```

Copy the JSON output. You’ll use it for `AZURE_CREDENTIALS`.

### 2) Add GitHub secrets

Go to GitHub → **Settings** → **Secrets and variables** → **Actions**, and add:

| Secret | Value |
|---|---|
| `AZURE_CREDENTIALS` | JSON from `az ad sp create-for-rbac` |
| `ACR_PASSWORD` | `az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv` |
| `GITHUB_REPO_URL` | `https://github.com/<org>/<repo>` |

> Note: `ACR_NAME` and `ACR_LOGIN_SERVER` are discovered automatically in the workflow.

### 3) Ensure workflow uses repo name

Update `.github/workflows/container-apps-deploy.yml` to match repo name:

```yaml
env:
  AZURE_CONTAINER_APP_NAME: skill-agent
  AZURE_RESOURCE_GROUP: blackedge-data-ai
  IMAGE_NAME: skill-agent
```

## Deploy via GitHub Actions

Push to `main` (or run manually from Actions). The pipeline will:

1. Build & push Docker image to ACR
2. Update the Container App with the new image
3. Verify health endpoint

## Manual Image Push (optional)

```bash
az acr login --name $ACR_NAME

docker build -t $ACR_LOGIN_SERVER/$PROJECT_NAME:latest .
docker push $ACR_LOGIN_SERVER/$PROJECT_NAME:latest
```

## Verify deployment

```bash
APP_URL=$(az containerapp show -g $RESOURCE_GROUP -n $PROJECT_NAME --query properties.configuration.ingress.fqdn -o tsv)

echo "https://$APP_URL"
```

---

### Notes

- The Bicep template creates a unique ACR name automatically.
- If you want a predictable registry name, update `infra/main.bicep` `acrName` variable.
- The health check endpoint used by the pipeline is `/health`.

# Azure Container Apps Deployment Guide

Deploy the Skill Agent as a containerized application using Azure Container Apps - a modern, serverless container platform.

## Table of Contents
- [Why Container Apps?](#why-container-apps)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Manual Setup](#manual-setup)
- [GitHub Actions CI/CD](#github-actions-cicd)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Scaling](#scaling)

## Why Container Apps?

Azure Container Apps is recommended over traditional App Service for:
- **Serverless scaling**: Scale to zero when not in use
- **Cost-effective**: Pay only for what you use
- **Kubernetes-powered**: Without the complexity
- **Built-in load balancing**: Automatic traffic distribution
- **Container-native**: Full Docker support
- **Better observability**: Integrated with Azure Monitor

## Prerequisites

- Azure account with active subscription ([Get free account](https://azure.microsoft.com/free/))
- Azure CLI installed (`az` command)
- Docker installed and running
- Git repository (for CI/CD)

### Install Azure CLI

```bash
# macOS
brew install azure-cli

# Windows (PowerShell)
winget install -e --id Microsoft.AzureCLI

# Linux
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### Install Docker

Download from [docker.com](https://www.docker.com/products/docker-desktop)

## Quick Start

### Option 1: Automated Deployment Script

The fastest way to deploy:

```bash
# Make the script executable
chmod +x scripts/deploy-container-apps.sh

# Run deployment
./scripts/deploy-container-apps.sh
```

The script will:
1. ✅ Create resource group
2. ✅ Create container registry
3. ✅ Build and push Docker image
4. ✅ Deploy Container Apps infrastructure
5. ✅ Configure environment variables
6. ✅ Provide you with the app URL and credentials

**That's it!** Your app will be running at the provided URL.

### Option 2: Manual Step-by-Step

If you prefer manual control, follow the [Manual Setup](#manual-setup) section below.

## Manual Setup

### 1. Login to Azure

```bash
az login
```

### 2. Set Variables

```bash
# Configure these values
RESOURCE_GROUP="skill-agent-rg"
LOCATION="eastus"
CONTAINER_REGISTRY_NAME="skillagentreg$(whoami)$RANDOM"
CONTAINER_APP_NAME="skill-agent-app"
ENVIRONMENT_NAME="skill-agent-env"
IMAGE_NAME="skill-agent"
```

### 3. Create Resource Group

```bash
az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION
```

### 4. Create Container Registry

```bash
az acr create \
    --resource-group $RESOURCE_GROUP \
    --name $CONTAINER_REGISTRY_NAME \
    --sku Basic \
    --admin-enabled true
```

### 5. Build and Push Container Image

```bash
# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show \
    --name $CONTAINER_REGISTRY_NAME \
    --resource-group $RESOURCE_GROUP \
    --query loginServer -o tsv)

# Login to ACR
az acr login --name $CONTAINER_REGISTRY_NAME

# Build image
docker build -t $ACR_LOGIN_SERVER/$IMAGE_NAME:latest .

# Push image
docker push $ACR_LOGIN_SERVER/$IMAGE_NAME:latest
```

### 6. Deploy Infrastructure with Bicep

```bash
az deployment group create \
    --resource-group $RESOURCE_GROUP \
    --template-file infra/container-apps.bicep \
    --parameters \
        environmentName=$ENVIRONMENT_NAME \
        containerAppName=$CONTAINER_APP_NAME \
        containerRegistryName=$CONTAINER_REGISTRY_NAME \
        location=$LOCATION \
        containerImage="$IMAGE_NAME:latest" \
        anthropicApiKey="your-anthropic-key" \
        openaiApiKey="your-openai-key" \
        googleApiKey="your-google-key" \
        githubRepoUrl="https://github.com/yourusername/your-skills-repo"
```

### 7. Get Application URL

```bash
APP_URL=$(az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query properties.configuration.ingress.fqdn -o tsv)

echo "Application URL: https://$APP_URL"
echo "API Docs: https://$APP_URL/docs"
```

## GitHub Actions CI/CD

### Setup Automatic Deployments

1. **Get ACR Password**

```bash
ACR_PASSWORD=$(az acr credential show \
    --name $CONTAINER_REGISTRY_NAME \
    --resource-group $RESOURCE_GROUP \
    --query passwords[0].value -o tsv)

echo $ACR_PASSWORD
```

2. **Create Service Principal for GitHub**

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az ad sp create-for-rbac \
    --name "skill-agent-github-actions" \
    --role contributor \
    --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
    --sdk-auth
```

**Copy the entire JSON output!**

3. **Add GitHub Secrets**

Go to: `https://github.com/YOUR_USERNAME/skill-agent/settings/secrets/actions`

Add these secrets:

| Secret Name | Value | Description |
|------------|-------|-------------|
| `AZURE_CREDENTIALS` | JSON from step 2 | Azure authentication |
| `ACR_PASSWORD` | Password from step 1 | Container registry access |
| `GITHUB_REPO_URL` | Your skills repo URL | Skills repository location |

4. **Update Workflow Variables**

Edit `.github/workflows/container-apps-deploy.yml`:

```yaml
env:
  AZURE_CONTAINER_APP_NAME: skill-agent-app  # Your app name
  AZURE_RESOURCE_GROUP: skill-agent-rg       # Your resource group
  CONTAINER_REGISTRY_NAME: skillagentreg     # Your registry (without suffix)
  IMAGE_NAME: skill-agent
```

5. **Deploy**

```bash
# Push to main branch
git add .
git commit -m "Configure Azure Container Apps deployment"
git push origin main
```

GitHub Actions will automatically:
- Build the Docker image
- Push to Azure Container Registry
- Deploy to Azure Container Apps
- Run health checks

## Configuration

### Environment Variables

Set environment variables using Azure CLI:

```bash
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --set-env-vars \
        ANTHROPIC_API_KEY=secretref:anthropic-api-key \
        OPENAI_API_KEY=secretref:openai-api-key \
        GOOGLE_API_KEY=secretref:google-api-key \
        GITHUB_REPO_URL="https://github.com/user/repo" \
        APP_NAME="Skill Agent" \
        LOG_LEVEL=INFO
```

### Update Secrets

```bash
az containerapp secret set \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --secrets \
        anthropic-api-key="new-key-value" \
        openai-api-key="new-key-value"
```

### Update Container Image

After building a new image:

```bash
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --image $ACR_LOGIN_SERVER/$IMAGE_NAME:latest
```

## Monitoring

### View Logs

```bash
# Stream logs in real-time
az containerapp logs show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --follow

# View recent logs
az containerapp logs show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --tail 100
```

### Check Application Status

```bash
# Get app details
az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP

# Check health endpoint
APP_URL=$(az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query properties.configuration.ingress.fqdn -o tsv)

curl https://$APP_URL/health
```

### View Metrics in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Container App
3. Select "Metrics" from the left menu
4. View CPU, memory, requests, and response times

## Troubleshooting

### Application Not Starting

**Check container logs:**
```bash
az containerapp logs show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --follow
```

**Verify image was pushed:**
```bash
az acr repository show \
    --name $CONTAINER_REGISTRY_NAME \
    --image $IMAGE_NAME:latest
```

**Check environment variables:**
```bash
az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query properties.template.containers[0].env
```

### Image Pull Errors

**Verify registry credentials:**
```bash
az acr credential show \
    --name $CONTAINER_REGISTRY_NAME \
    --resource-group $RESOURCE_GROUP
```

**Update container app with correct credentials:**
```bash
ACR_PASSWORD=$(az acr credential show \
    --name $CONTAINER_REGISTRY_NAME \
    --resource-group $RESOURCE_GROUP \
    --query passwords[0].value -o tsv)

az containerapp registry set \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --server $ACR_LOGIN_SERVER \
    --username $CONTAINER_REGISTRY_NAME \
    --password $ACR_PASSWORD
```

### GitHub Actions Deployment Fails

**Verify secrets are set correctly:**
- Check `AZURE_CREDENTIALS` is valid JSON
- Ensure `ACR_PASSWORD` is current

**Check service principal permissions:**
```bash
az role assignment list \
    --assignee <clientId-from-AZURE_CREDENTIALS>
```

### High Memory/CPU Usage

**View current resource allocation:**
```bash
az containerapp show \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "properties.template.containers[0].resources"
```

**Update resource allocation:**
```bash
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --cpu 1.0 \
    --memory 2Gi
```

## Scaling

### Manual Scaling

**Set replica count:**
```bash
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --min-replicas 2 \
    --max-replicas 10
```

### Auto-scaling

Auto-scaling is configured in the Bicep template based on:
- **HTTP requests**: Scales based on concurrent requests
- **CPU usage**: Scales when CPU exceeds threshold
- **Memory usage**: Scales when memory exceeds threshold

**Update scaling rules:**
```bash
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --scale-rule-name http-scaling \
    --scale-rule-type http \
    --scale-rule-http-concurrency 100
```

### Scale to Zero

Container Apps can scale to zero when idle:

```bash
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --min-replicas 0 \
    --max-replicas 10
```

**Note:** First request after scaling to zero will have cold start delay (~10-30 seconds).

## Cost Optimization

### Pricing Model

Container Apps pricing is based on:
- **vCPU-seconds**: $0.000024 per vCPU-second
- **GiB-seconds**: $0.000004 per GiB-second
- **HTTP requests**: $0.40 per million requests

### Cost-Saving Tips

1. **Enable scale-to-zero** for dev/staging environments
2. **Use smaller resource allocations** (0.25 vCPU, 0.5 GiB)
3. **Use B-series VMs** for burstable workloads
4. **Set up auto-shutdown** for non-production environments

### Stop Container App (to save costs)

```bash
# Stop all replicas
az containerapp revision deactivate \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --revision <revision-name>

# Or scale to zero
az containerapp update \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --min-replicas 0 \
    --max-replicas 0
```

## Advanced Configuration

### Custom Domain

```bash
# Add custom domain
az containerapp hostname add \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --hostname yourdomain.com

# Add SSL certificate
az containerapp ssl upload \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --hostname yourdomain.com \
    --certificate-file cert.pfx \
    --password <password>
```

### Multiple Containers (Sidecar Pattern)

Edit `infra/container-apps.bicep` to add additional containers:

```bicep
containers: [
  {
    name: 'skill-agent'
    image: '...'
    // main container config
  }
  {
    name: 'redis-sidecar'
    image: 'redis:alpine'
    resources: {
      cpu: json('0.25')
      memory: '0.5Gi'
    }
  }
]
```

### Revisions and Traffic Splitting

```bash
# List revisions
az containerapp revision list \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP

# Split traffic between revisions
az containerapp ingress traffic set \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --revision-weight latest=80 previous=20
```

## Cleanup

### Delete Everything

```bash
# Delete resource group (removes all resources)
az group delete \
    --name $RESOURCE_GROUP \
    --yes --no-wait
```

### Delete Specific Resources

```bash
# Delete container app only
az containerapp delete \
    --name $CONTAINER_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --yes

# Delete container registry only
az acr delete \
    --name $CONTAINER_REGISTRY_NAME \
    --resource-group $RESOURCE_GROUP \
    --yes
```

## Additional Resources

- [Azure Container Apps Documentation](https://docs.microsoft.com/azure/container-apps/)
- [Bicep Documentation](https://docs.microsoft.com/azure/azure-resource-manager/bicep/)
- [Docker Documentation](https://docs.docker.com/)
- [GitHub Actions for Azure](https://docs.microsoft.com/azure/developer/github/github-actions)

## Support

**Need help?**
- Check logs: `az containerapp logs show -n $CONTAINER_APP_NAME -g $RESOURCE_GROUP --follow`
- Review [Azure Container Apps Troubleshooting](https://docs.microsoft.com/azure/container-apps/troubleshooting)
- Open an issue in the repository

---

**Congratulations!** You've successfully deployed Skill Agent to Azure Container Apps! 🎉

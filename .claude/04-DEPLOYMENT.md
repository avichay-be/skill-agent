# Azure Deployment Guide

This guide walks you through setting up CI/CD for deploying the Skill Agent FastAPI application to Azure App Service using GitHub Actions.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Azure Setup](#azure-setup)
- [GitHub Secrets Configuration](#github-secrets-configuration)
- [Deployment Workflow](#deployment-workflow)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, ensure you have:
- Azure account with an active subscription
- Azure CLI installed (`az` command)
- GitHub repository with this code
- Admin access to the GitHub repository

## Azure Setup

### 1. Install Azure CLI

If you don't have Azure CLI installed:

```bash
# macOS
brew install azure-cli

# Windows
# Download from https://aka.ms/installazurecliwindows

# Linux
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### 2. Login to Azure

```bash
az login
```

### 3. Create Azure Resources

Run the following commands to create the necessary Azure resources:

```bash
# Set variables
RESOURCE_GROUP="skill-agent-rg"
LOCATION="eastus"
APP_SERVICE_PLAN="skill-agent-plan"
WEBAPP_NAME="skill-agent-app"  # Must be globally unique
WEBAPP_NAME_STAGING="skill-agent-app-staging"  # For staging environment

# Create resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

# Create App Service Plan (Linux, Python 3.11)
az appservice plan create \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --is-linux \
  --sku B1

# Create Web App for Production
az webapp create \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --runtime "PYTHON:3.11"

# Create Web App for Staging (optional)
az webapp create \
  --name $WEBAPP_NAME_STAGING \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --runtime "PYTHON:3.11"

# Configure Web App startup command
az webapp config set \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --startup-file "startup.sh"

az webapp config set \
  --name $WEBAPP_NAME_STAGING \
  --resource-group $RESOURCE_GROUP \
  --startup-file "startup.sh"

# Enable logging
az webapp log config \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --application-logging filesystem \
  --detailed-error-messages true \
  --failed-request-tracing true \
  --web-server-logging filesystem

az webapp log config \
  --name $WEBAPP_NAME_STAGING \
  --resource-group $RESOURCE_GROUP \
  --application-logging filesystem \
  --detailed-error-messages true \
  --failed-request-tracing true \
  --web-server-logging filesystem
```

### 4. Create Service Principal for GitHub Actions

Create a service principal with contributor access to deploy to Azure:

```bash
# Get subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Create service principal
az ad sp create-for-rbac \
  --name "skill-agent-github-actions" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth
```

**Important:** Copy the entire JSON output - you'll need it for GitHub Secrets.

The output will look like this:
```json
{
  "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "clientSecret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "subscriptionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

## GitHub Secrets Configuration

### 1. Add Secrets to GitHub Repository

Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

#### Required Secrets for Production:

1. **AZURE_CREDENTIALS**
   - Value: The entire JSON output from the service principal creation above

2. **AZURE_WEBAPP_NAME**
   - Value: Your production web app name (e.g., `skill-agent-app`)

#### Optional Secrets for Staging:

3. **AZURE_CREDENTIALS_STAGING** (if using staging environment)
   - Value: Same JSON as AZURE_CREDENTIALS or create a separate service principal

4. **AZURE_WEBAPP_NAME_STAGING**
   - Value: Your staging web app name (e.g., `skill-agent-app-staging`)

### 2. Verify Secrets

Ensure all required secrets are added:
- Go to Settings → Secrets and variables → Actions
- Verify you see: `AZURE_CREDENTIALS` and `AZURE_WEBAPP_NAME`

## Environment Variables

### Configure App Settings in Azure

Set environment variables for your application:

```bash
# Set application settings
az webapp config appsettings set \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    APP_NAME="Skill Agent" \
    LOG_LEVEL="INFO" \
    PYTHONPATH="/home/site/wwwroot" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"

# Add your custom environment variables
az webapp config appsettings set \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    ANTHROPIC_API_KEY="your-anthropic-key" \
    OPENAI_API_KEY="your-openai-key" \
    GOOGLE_API_KEY="your-google-key" \
    GITHUB_REPO_URL="https://github.com/yourusername/your-skills-repo"
```

For staging:
```bash
az webapp config appsettings set \
  --name $WEBAPP_NAME_STAGING \
  --resource-group $RESOURCE_GROUP \
  --settings \
    APP_NAME="Skill Agent Staging" \
    LOG_LEVEL="DEBUG" \
    PYTHONPATH="/home/site/wwwroot" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"
```

## Deployment Workflow

### Automatic Deployment (Production)

The workflow automatically deploys to production when you push to the `main` branch:

```bash
git push origin main
```

### Manual Deployment

You can manually trigger deployments from GitHub:

1. Go to your repository on GitHub
2. Click **Actions** tab
3. Select **Deploy to Azure App Service** workflow
4. Click **Run workflow**
5. Choose environment (production or staging)
6. Click **Run workflow** button

### Deployment Process

The CI/CD pipeline:
1. **Build & Test** - Runs linting, type checking, and tests
2. **Package** - Creates deployment artifact
3. **Deploy** - Deploys to Azure App Service
4. **Verify** - Provides deployment URL

## Accessing Your Application

After successful deployment:

### Production
```
https://<your-webapp-name>.azurewebsites.net
```

### API Documentation
```
https://<your-webapp-name>.azurewebsites.net/docs
```

### Check Deployment Status

```bash
# View deployment logs
az webapp log tail \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP

# Check app status
az webapp show \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query state
```

## Troubleshooting

### View Application Logs

```bash
# Stream logs in real-time
az webapp log tail \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP

# Download logs
az webapp log download \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --log-file app-logs.zip
```

### Common Issues

#### 1. Application Fails to Start

**Check startup command:**
```bash
az webapp config show \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query appCommandLine
```

**Verify startup.sh is executable:**
Make sure your startup.sh has proper permissions in the repository.

#### 2. Dependencies Not Installing

**Check build logs:**
```bash
az webapp log deployment show \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP
```

**Verify requirements.txt** is in the root directory.

#### 3. Environment Variables Not Set

**List all app settings:**
```bash
az webapp config appsettings list \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP
```

#### 4. GitHub Actions Deployment Fails

**Check secrets:**
- Verify `AZURE_CREDENTIALS` is properly formatted JSON
- Ensure `AZURE_WEBAPP_NAME` matches your actual web app name

**Check service principal permissions:**
```bash
az role assignment list \
  --assignee <clientId-from-AZURE_CREDENTIALS>
```

### SSH into Web App

For advanced troubleshooting:

```bash
az webapp ssh \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP
```

## Scaling

### Scale Up (Vertical Scaling)

Upgrade to a more powerful App Service Plan:

```bash
az appservice plan update \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --sku S1  # or P1V2, P2V2, P3V2 for production
```

### Scale Out (Horizontal Scaling)

Add more instances:

```bash
az appservice plan update \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --number-of-workers 3
```

### Enable Autoscaling

```bash
az monitor autoscale create \
  --resource-group $RESOURCE_GROUP \
  --resource $APP_SERVICE_PLAN \
  --resource-type Microsoft.Web/serverfarms \
  --name autoscale-plan \
  --min-count 1 \
  --max-count 5 \
  --count 1
```

## Cost Optimization

### Use Deployment Slots

Instead of separate staging app, use deployment slots (requires Standard tier or higher):

```bash
# Create staging slot
az webapp deployment slot create \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --slot staging

# Swap slots (promote staging to production)
az webapp deployment slot swap \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --slot staging
```

### Stop Apps When Not Needed

```bash
# Stop staging app to save costs
az webapp stop \
  --name $WEBAPP_NAME_STAGING \
  --resource-group $RESOURCE_GROUP

# Start when needed
az webapp start \
  --name $WEBAPP_NAME_STAGING \
  --resource-group $RESOURCE_GROUP
```

## Custom Domain & SSL

### Add Custom Domain

```bash
# Map custom domain
az webapp config hostname add \
  --webapp-name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --hostname yourdomain.com

# Enable SSL
az webapp config ssl bind \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --certificate-thumbprint <thumbprint> \
  --ssl-type SNI
```

### Free Managed Certificate

Azure provides free managed SSL certificates for custom domains (requires Standard tier or higher).

## Monitoring

### Enable Application Insights

```bash
# Create Application Insights
az monitor app-insights component create \
  --app skill-agent-insights \
  --location $LOCATION \
  --resource-group $RESOURCE_GROUP \
  --application-type web

# Connect to Web App
INSTRUMENTATION_KEY=$(az monitor app-insights component show \
  --app skill-agent-insights \
  --resource-group $RESOURCE_GROUP \
  --query instrumentationKey -o tsv)

az webapp config appsettings set \
  --name $WEBAPP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings APPINSIGHTS_INSTRUMENTATIONKEY=$INSTRUMENTATION_KEY
```

## Cleanup

To delete all Azure resources:

```bash
az group delete \
  --name $RESOURCE_GROUP \
  --yes --no-wait
```

## Additional Resources

- [Azure App Service Documentation](https://docs.microsoft.com/azure/app-service/)
- [GitHub Actions for Azure](https://docs.microsoft.com/azure/developer/github/github-actions)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Azure CLI Reference](https://docs.microsoft.com/cli/azure/)

## Support

For issues related to:
- **Deployment**: Check GitHub Actions logs
- **Application**: Check Azure App Service logs
- **Azure Resources**: Use Azure Portal or Azure CLI

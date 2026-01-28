# Azure Deployment - Quick Start Guide

Get your Skill Agent application deployed to Azure in 5 minutes!

## Prerequisites
- Azure account ([Get free account](https://azure.microsoft.com/free/))
- GitHub account
- Azure CLI installed

## Quick Setup

### 1. Login to Azure
```bash
az login
```

### 2. Create Azure Resources (One Command!)
```bash
# Set your unique app name (must be globally unique!)
APP_NAME="skill-agent-$(whoami)-$RANDOM"

# Create everything
az group create --name skill-agent-rg --location eastus && \
az appservice plan create --name skill-agent-plan --resource-group skill-agent-rg --is-linux --sku B1 && \
az webapp create --name $APP_NAME --resource-group skill-agent-rg --plan skill-agent-plan --runtime "PYTHON:3.11" && \
az webapp config set --name $APP_NAME --resource-group skill-agent-rg --startup-file "startup.sh"

echo "✅ Web App created: https://$APP_NAME.azurewebsites.net"
```

### 3. Get Credentials for GitHub
```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

az ad sp create-for-rbac \
  --name "skill-agent-gh-actions" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/skill-agent-rg \
  --sdk-auth
```

📋 **Copy the entire JSON output!**

### 4. Configure GitHub Secrets

Go to: `https://github.com/YOUR_USERNAME/skill-agent/settings/secrets/actions`

Add these secrets:

1. **AZURE_CREDENTIALS** → Paste the JSON from step 3
2. **AZURE_WEBAPP_NAME** → Your app name (from `echo $APP_NAME`)

### 5. Set Environment Variables in Azure
```bash
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group skill-agent-rg \
  --settings \
    ANTHROPIC_API_KEY="your-key-here" \
    OPENAI_API_KEY="your-key-here" \
    GOOGLE_API_KEY="your-key-here" \
    GITHUB_REPO_URL="https://github.com/yourusername/your-skills-repo"
```

### 6. Deploy!
```bash
# Push to main branch
git push origin main

# Or manually trigger from GitHub Actions tab
```

## Access Your App

- **App URL**: `https://$APP_NAME.azurewebsites.net`
- **API Docs**: `https://$APP_NAME.azurewebsites.net/docs`
- **Health Check**: `https://$APP_NAME.azurewebsites.net/`

## View Logs
```bash
az webapp log tail --name $APP_NAME --resource-group skill-agent-rg
```

## Delete Everything
```bash
az group delete --name skill-agent-rg --yes --no-wait
```

## Troubleshooting

**App not starting?**
```bash
# Check logs
az webapp log tail --name $APP_NAME --resource-group skill-agent-rg

# Restart app
az webapp restart --name $APP_NAME --resource-group skill-agent-rg
```

**GitHub Actions failing?**
- Verify `AZURE_CREDENTIALS` secret is valid JSON
- Check `AZURE_WEBAPP_NAME` matches your app name

## Next Steps

See [DEPLOYMENT.md](./DEPLOYMENT.md) for:
- Staging environments
- Custom domains
- Scaling
- Monitoring
- Advanced configuration

## Pricing

The B1 (Basic) plan used in this guide costs approximately **$13/month**.

**Free tier**: Change `--sku B1` to `--sku F1` for free hosting (limited features).

---

**Need help?** Check the full [deployment guide](./DEPLOYMENT.md) or Azure documentation.

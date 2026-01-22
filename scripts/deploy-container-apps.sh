#!/bin/bash
# Quick deployment script for Azure Container Apps
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Azure Container Apps Deployment Script ===${NC}\n"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI is not installed${NC}"
    echo "Install from: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-skill-agent-rg}"
LOCATION="${LOCATION:-eastus}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-skill-agent-app}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-skill-agent-env}"
CONTAINER_REGISTRY_NAME="skillagentreg$(echo $RANDOM | md5sum | head -c 6)"
IMAGE_NAME="skill-agent"

echo "Configuration:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  Container App: $CONTAINER_APP_NAME"
echo "  Environment: $ENVIRONMENT_NAME"
echo "  Registry: $CONTAINER_REGISTRY_NAME"
echo ""

# Login check
echo -e "${YELLOW}Checking Azure login...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Not logged in. Running 'az login'...${NC}"
    az login
fi

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo -e "${GREEN}Using subscription: $SUBSCRIPTION_ID${NC}\n"

# Create resource group
echo -e "${YELLOW}Creating resource group...${NC}"
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none

echo -e "${GREEN}✓ Resource group created${NC}\n"

# Create container registry
echo -e "${YELLOW}Creating container registry...${NC}"
az acr create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$CONTAINER_REGISTRY_NAME" \
    --sku Basic \
    --admin-enabled true \
    --output none

echo -e "${GREEN}✓ Container registry created${NC}\n"

# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show --name "$CONTAINER_REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "$CONTAINER_REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$CONTAINER_REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" --query passwords[0].value -o tsv)

echo "Registry details:"
echo "  Login Server: $ACR_LOGIN_SERVER"
echo "  Username: $ACR_USERNAME"
echo ""

# Build and push image
echo -e "${YELLOW}Building and pushing Docker image...${NC}"
echo "This may take a few minutes..."

# Login to ACR
echo "$ACR_PASSWORD" | docker login "$ACR_LOGIN_SERVER" --username "$ACR_USERNAME" --password-stdin

# Build image
docker build -t "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest" .

# Push image
docker push "$ACR_LOGIN_SERVER/$IMAGE_NAME:latest"

echo -e "${GREEN}✓ Image built and pushed${NC}\n"

# Deploy using Bicep
echo -e "${YELLOW}Deploying Azure Container Apps infrastructure...${NC}"

# Prompt for API keys (optional)
read -p "Enter Anthropic API Key (or press Enter to skip): " ANTHROPIC_KEY
read -p "Enter OpenAI API Key (or press Enter to skip): " OPENAI_KEY
read -p "Enter Google API Key (or press Enter to skip): " GOOGLE_KEY
read -p "Enter GitHub Repo URL for skills (or press Enter to skip): " GITHUB_REPO

# Deploy with Bicep
az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file infra/container-apps.bicep \
    --parameters \
        environmentName="$ENVIRONMENT_NAME" \
        containerAppName="$CONTAINER_APP_NAME" \
        containerRegistryName="$CONTAINER_REGISTRY_NAME" \
        location="$LOCATION" \
        containerImage="$IMAGE_NAME:latest" \
        anthropicApiKey="${ANTHROPIC_KEY:-}" \
        openaiApiKey="${OPENAI_KEY:-}" \
        googleApiKey="${GOOGLE_KEY:-}" \
        githubRepoUrl="${GITHUB_REPO:-}" \
    --output none

echo -e "${GREEN}✓ Container Apps infrastructure deployed${NC}\n"

# Get app URL
APP_URL=$(az containerapp show \
    --name "$CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn -o tsv)

echo -e "${GREEN}=================================${NC}"
echo -e "${GREEN}Deployment successful! 🚀${NC}"
echo -e "${GREEN}=================================${NC}"
echo ""
echo "Application URL: https://$APP_URL"
echo "API Documentation: https://$APP_URL/docs"
echo "Health Check: https://$APP_URL/health"
echo ""
echo "Registry:"
echo "  Server: $ACR_LOGIN_SERVER"
echo "  Username: $ACR_USERNAME"
echo ""
echo -e "${YELLOW}Save these credentials for GitHub Actions:${NC}"
echo ""
echo "GitHub Secret: ACR_PASSWORD"
echo "Value: $ACR_PASSWORD"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Add the ACR_PASSWORD to your GitHub repository secrets"
echo "2. Update .github/workflows/container-apps-deploy.yml with your resource names"
echo "3. Push to main branch to trigger automatic deployment"
echo ""
echo "To view logs:"
echo "  az containerapp logs show -n $CONTAINER_APP_NAME -g $RESOURCE_GROUP --follow"
echo ""
echo "To update environment variables:"
echo "  az containerapp update -n $CONTAINER_APP_NAME -g $RESOURCE_GROUP --set-env-vars KEY=VALUE"
echo ""

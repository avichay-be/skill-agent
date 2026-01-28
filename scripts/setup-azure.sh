#!/bin/bash
# Quick setup script for Azure CI/CD deployment
# Usage: ./scripts/setup-azure.sh

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="blackedge-data-ai"
LOCATION="eastus"
ACR_NAME="skillagent"
APP_SERVICE_NAME="skill-agent-app"

echo -e "${YELLOW}Skill Agent - Azure CI/CD Setup${NC}"
echo "=================================="

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI not installed${NC}"
    exit 1
fi

if ! az account show &> /dev/null; then
    echo -e "${RED}❌ Not logged in to Azure. Run: az login${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Azure CLI configured${NC}"

# Get subscription info
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
SUBSCRIPTION_NAME=$(az account show --query name --output tsv)
echo -e "${GREEN}✓ Using subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)${NC}"

# Create resource group
echo -e "\n${YELLOW}Creating resource group...${NC}"
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION \
  --tags project=skill-agent environment=prod

echo -e "${GREEN}✓ Resource group created${NC}"

# Create ACR
echo -e "\n${YELLOW}Creating Azure Container Registry...${NC}"
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Standard \
  --admin-enabled true

echo -e "${GREEN}✓ ACR created: $ACR_NAME${NC}"

# Get ACR credentials
echo -e "\n${YELLOW}Retrieving ACR credentials...${NC}"
ACR_LOGIN_SERVER=$(az acr show \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --query loginServer \
  --output tsv)

ACR_USERNAME=$(az acr credential show \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --query username \
  --output tsv)

ACR_PASSWORD=$(az acr credential show \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --query 'passwords[0].value' \
  --output tsv)

echo -e "${GREEN}✓ ACR Credentials retrieved${NC}"

# Create service principal
echo -e "\n${YELLOW}Creating service principal for CI/CD...${NC}"
SP_JSON=$(az ad sp create-for-rbac \
  --name "skill-agent-ci-cd" \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --json-auth)

echo -e "${GREEN}✓ Service principal created${NC}"

# Display GitHub Secrets needed
echo -e "\n${YELLOW}========== GITHUB SECRETS ===========${NC}"
echo -e "\nAdd the following to your GitHub repository secrets:"
echo ""
echo -e "${YELLOW}1. ACR_REGISTRY_URL${NC}"
echo "   Value: $ACR_LOGIN_SERVER"
echo ""
echo -e "${YELLOW}2. ACR_USERNAME${NC}"
echo "   Value: $ACR_USERNAME"
echo ""
echo -e "${YELLOW}3. ACR_PASSWORD${NC}"
echo "   Value: (shown below)"
echo ""
echo -e "${YELLOW}4. AZURE_CREDENTIALS${NC}"
echo "   Value: (shown below)"
echo ""
echo -e "${YELLOW}5. AZURE_APP_NAME${NC}"
echo "   Value: $APP_SERVICE_NAME"
echo ""

# Save credentials to temporary file
TEMP_CREDS="/tmp/azure-credentials-$RANDOM.json"
echo "$SP_JSON" > $TEMP_CREDS

echo -e "${YELLOW}Credentials saved to: $TEMP_CREDS${NC}"
echo -e "${RED}⚠️  Keep these credentials secure!${NC}"

# Deploy infrastructure with Bicep
echo -e "\n${YELLOW}Building Bicep template...${NC}"
if command -v az bicep &> /dev/null; then
    az bicep build --file infra/main.bicep
    echo -e "${GREEN}✓ Bicep template built${NC}"
else
    echo -e "${YELLOW}⚠️  Bicep CLI not found. Skipping build step.${NC}"
fi

# Show what-if for deployment
echo -e "\n${YELLOW}Previewing infrastructure deployment (Container App)...${NC}"
az deployment group what-if \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --parameters dockerImageUri="${ACR_LOGIN_SERVER}/skill-agent:latest"

read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Deploying infrastructure (Container App)...${NC}"
    az deployment group create \
      --resource-group $RESOURCE_GROUP \
      --template-file infra/main.bicep \
      --parameters infra/main.bicepparam \
      --parameters dockerImageUri="${ACR_LOGIN_SERVER}/skill-agent:latest"
    
    echo -e "${GREEN}✓ Infrastructure deployed${NC}"
else
    echo -e "${YELLOW}Deployment cancelled${NC}"
fi

# Summary
echo -e "\n${GREEN}========== SETUP COMPLETE ==========${NC}"
echo ""
echo "Next steps:"
echo "1. Add the secrets above to your GitHub repository"
echo "2. Push code to trigger CI/CD pipeline"
echo "3. Monitor deployment in GitHub Actions"
echo ""
echo "Resources created:"
echo "  - Resource Group: $RESOURCE_GROUP"
echo "  - Container Registry: $ACR_LOGIN_SERVER"
echo "  - Container App: $APP_SERVICE_NAME"
echo ""
echo "Documentation: See AZURE_DEPLOYMENT.md for detailed instructions"
echo ""
echo -e "${YELLOW}Credentials file: $TEMP_CREDS${NC}"
echo -e "${RED}Delete this file after adding secrets to GitHub!${NC}"

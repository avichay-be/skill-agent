#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:?RESOURCE_GROUP is required}"
LOCATION="${LOCATION:-eastus}"
AZURE_CONTAINER_APP_NAME="${AZURE_CONTAINER_APP_NAME:?AZURE_CONTAINER_APP_NAME is required}"
CONTAINERAPPS_ENVIRONMENT_NAME="${CONTAINERAPPS_ENVIRONMENT_NAME:-skill-agent-env}"
CONTAINER_REGISTRY_NAME="${CONTAINER_REGISTRY_NAME:?CONTAINER_REGISTRY_NAME is required}"
LOG_ANALYTICS_WORKSPACE_NAME="${LOG_ANALYTICS_WORKSPACE_NAME:-skill-agent-logs}"
IMAGE_NAME="${IMAGE_NAME:-skill-agent}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
TARGET_PORT="${TARGET_PORT:-8000}"
BOOTSTRAP_INFRA="${BOOTSTRAP_INFRA:-true}"
ENSURE_APP="${ENSURE_APP:-false}"
CPU_CORES="${CPU_CORES:-0.5}"
MEMORY_SIZE="${MEMORY_SIZE:-1.0Gi}"
MIN_REPLICAS="${MIN_REPLICAS:-1}"
MAX_REPLICAS="${MAX_REPLICAS:-3}"

say() {
    echo "[ensure-container-apps] $*"
}

ensure_provider() {
    local namespace="$1"
    local state

    state="$(az provider show --namespace "$namespace" --query registrationState -o tsv 2>/dev/null || true)"
    if [[ "$state" == "Registered" ]]; then
        say "Provider '$namespace' is already registered"
        return 0
    fi

    if az provider register --namespace "$namespace" --wait 1>/dev/null 2>&1; then
        say "Registered provider '$namespace'"
        return 0
    fi

    say "Could not register provider '$namespace'; continuing with existing subscription state"
}

require_existing() {
    local resource_name="$1"
    local guidance="$2"

    echo "::error::$resource_name does not exist and BOOTSTRAP_INFRA=false. $guidance"
    exit 1
}

write_output() {
    local key="$1"
    local value="$2"

    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
        printf '%s=%s\n' "$key" "$value" >> "$GITHUB_OUTPUT"
    fi
}

az extension add --name containerapp --upgrade --yes 1>/dev/null
ensure_provider Microsoft.App
ensure_provider Microsoft.ContainerRegistry
ensure_provider Microsoft.OperationalInsights

say "Ensuring resource group '$RESOURCE_GROUP'"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" 1>/dev/null

if az acr show --name "$CONTAINER_REGISTRY_NAME" --resource-group "$RESOURCE_GROUP" 1>/dev/null 2>&1; then
    say "ACR '$CONTAINER_REGISTRY_NAME' already exists"
else
    if [[ "$BOOTSTRAP_INFRA" != "true" ]]; then
        require_existing \
            "Azure Container Registry '$CONTAINER_REGISTRY_NAME'" \
            "Set BOOTSTRAP_INFRA=true or create the registry first."
    fi

    say "Creating ACR '$CONTAINER_REGISTRY_NAME'"
    az acr create \
        --name "$CONTAINER_REGISTRY_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku Basic \
        --admin-enabled true \
        1>/dev/null
fi

ACR_LOGIN_SERVER="$(az acr show \
    --name "$CONTAINER_REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query loginServer \
    -o tsv)"

write_output "acr_name" "$CONTAINER_REGISTRY_NAME"
write_output "acr_login_server" "$ACR_LOGIN_SERVER"
say "Using ACR login server '$ACR_LOGIN_SERVER'"

if az monitor log-analytics workspace show \
    --resource-group "$RESOURCE_GROUP" \
    --workspace-name "$LOG_ANALYTICS_WORKSPACE_NAME" 1>/dev/null 2>&1; then
    say "Log Analytics workspace '$LOG_ANALYTICS_WORKSPACE_NAME' already exists"
else
    if [[ "$BOOTSTRAP_INFRA" != "true" ]]; then
        require_existing \
            "Log Analytics workspace '$LOG_ANALYTICS_WORKSPACE_NAME'" \
            "Set BOOTSTRAP_INFRA=true or create the workspace first."
    fi

    say "Creating Log Analytics workspace '$LOG_ANALYTICS_WORKSPACE_NAME'"
    az monitor log-analytics workspace create \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$LOG_ANALYTICS_WORKSPACE_NAME" \
        --location "$LOCATION" \
        1>/dev/null
fi

if az containerapp env show \
    --name "$CONTAINERAPPS_ENVIRONMENT_NAME" \
    --resource-group "$RESOURCE_GROUP" 1>/dev/null 2>&1; then
    say "Container Apps environment '$CONTAINERAPPS_ENVIRONMENT_NAME' already exists"
else
    if [[ "$BOOTSTRAP_INFRA" != "true" ]]; then
        require_existing \
            "Container Apps environment '$CONTAINERAPPS_ENVIRONMENT_NAME'" \
            "Set BOOTSTRAP_INFRA=true or create the environment first."
    fi

    LOG_ANALYTICS_ID="$(az monitor log-analytics workspace show \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$LOG_ANALYTICS_WORKSPACE_NAME" \
        --query customerId \
        -o tsv)"
    LOG_ANALYTICS_KEY="$(az monitor log-analytics workspace get-shared-keys \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "$LOG_ANALYTICS_WORKSPACE_NAME" \
        --query primarySharedKey \
        -o tsv)"

    say "Creating Container Apps environment '$CONTAINERAPPS_ENVIRONMENT_NAME'"
    az containerapp env create \
        --name "$CONTAINERAPPS_ENVIRONMENT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --logs-workspace-id "$LOG_ANALYTICS_ID" \
        --logs-workspace-key "$LOG_ANALYTICS_KEY" \
        1>/dev/null
fi

if [[ "$ENSURE_APP" != "true" ]]; then
    say "Skipping Container App creation because ENSURE_APP=false"
    exit 0
fi

if az containerapp show \
    --name "$AZURE_CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" 1>/dev/null 2>&1; then
    say "Container App '$AZURE_CONTAINER_APP_NAME' already exists"
    APP_FQDN="$(az containerapp show \
        --name "$AZURE_CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query properties.configuration.ingress.fqdn \
        -o tsv)"
    write_output "container_app_fqdn" "$APP_FQDN"
    exit 0
fi

if [[ "$BOOTSTRAP_INFRA" != "true" ]]; then
    require_existing \
        "Container App '$AZURE_CONTAINER_APP_NAME'" \
        "Set BOOTSTRAP_INFRA=true or create the app first."
fi

ACR_USERNAME="$(az acr credential show \
    --name "$CONTAINER_REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query username \
    -o tsv)"
ACR_PASSWORD="$(az acr credential show \
    --name "$CONTAINER_REGISTRY_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query passwords[0].value \
    -o tsv)"

say "Creating Container App '$AZURE_CONTAINER_APP_NAME'"
az containerapp create \
    --name "$AZURE_CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$CONTAINERAPPS_ENVIRONMENT_NAME" \
    --image "$ACR_LOGIN_SERVER/$IMAGE_NAME:$IMAGE_TAG" \
    --target-port "$TARGET_PORT" \
    --ingress external \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_USERNAME" \
    --registry-password "$ACR_PASSWORD" \
    --cpu "$CPU_CORES" \
    --memory "$MEMORY_SIZE" \
    --min-replicas "$MIN_REPLICAS" \
    --max-replicas "$MAX_REPLICAS" \
    --env-vars \
        APP_NAME="Skill Agent" \
        ENVIRONMENT=production \
        LOG_LEVEL=INFO \
    1>/dev/null

APP_FQDN="$(az containerapp show \
    --name "$AZURE_CONTAINER_APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)"
write_output "container_app_fqdn" "$APP_FQDN"
say "Container App available at '$APP_FQDN'"

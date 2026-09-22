#!/usr/bin/env bash
# ============================================================
# deploy-backend.sh — Deploy Model Fusion backend to Azure
# Sources .env for config values, deploys Bicep, builds image
# in ACR, updates the Container App with the real image,
# and assigns the OpenAI role to the backend identity.
# ============================================================
set -euo pipefail

# ---------- Configuration ----------
SUBSCRIPTION="c5e2e3c4-7b5b-4b10-b8b2-bef972d4b0d4"
RESOURCE_GROUP="rg-modelfusion"
LOCATION="southcentralus"
APP_NAME="modelfusion"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ---------- Load .env ----------
# Reuses the same .env file the app uses for local development
ENV_FILE="$SCRIPT_DIR/../src/.env"
if [[ -f "$ENV_FILE" ]]; then
  echo "Loading environment from $ENV_FILE"
  set -a
  source "$ENV_FILE"
  set +a
else
  echo "WARNING: No .env file found at $ENV_FILE — using existing environment variables"
fi

# ---------- Verify required variables ----------
: "${AZURE_OPENAI_ENDPOINT:?Set AZURE_OPENAI_ENDPOINT in .env}"
: "${AZURE_OPENAI_DEPLOYMENT_GPT:?Set AZURE_OPENAI_DEPLOYMENT_GPT in .env}"
: "${AZURE_OPENAI_DEPLOYMENT_GROK:?Set AZURE_OPENAI_DEPLOYMENT_GROK in .env}"
: "${AZURE_OPENAI_DEPLOYMENT_DEEPSEEK:?Set AZURE_OPENAI_DEPLOYMENT_DEEPSEEK in .env}"
: "${GEMINI_API_KEY:?Set GEMINI_API_KEY in .env}"
: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY in .env}"
: "${AZURE_OPENAI_RESOURCE_ID:?Set AZURE_OPENAI_RESOURCE_ID in .env}"

# ---------- Verify Azure CLI login ----------
echo "=== Checking Azure CLI login ==="
az account show --output none 2>/dev/null || {
  echo "ERROR: Not logged in. Run 'az login' first."
  exit 1
}

# ---------- Set subscription ----------
echo "=== Setting subscription ==="
az account set --subscription "$SUBSCRIPTION"

# ---------- Create resource group ----------
echo "=== Creating resource group '$RESOURCE_GROUP' ==="
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

# ---------- Deploy Bicep infrastructure ----------
echo "=== Deploying Bicep template ==="
DEPLOY_OUTPUT=$(az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters \
    azureOpenAiEndpoint="$AZURE_OPENAI_ENDPOINT" \
    azureOpenAiDeploymentGpt="$AZURE_OPENAI_DEPLOYMENT_GPT" \
    azureOpenAiDeploymentGrok="$AZURE_OPENAI_DEPLOYMENT_GROK" \
    azureOpenAiDeploymentDeepseek="$AZURE_OPENAI_DEPLOYMENT_DEEPSEEK" \
    geminiApiKey="$GEMINI_API_KEY" \
    anthropicApiKey="$ANTHROPIC_API_KEY" \
    geminiModel="${GEMINI_MODEL:-gemini-3-pro-preview}" \
    anthropicModel="${ANTHROPIC_MODEL:-claude-3-5-sonnet-20241022}" \
    appInsightsConnectionString="${APPLICATIONINSIGHTS_CONNECTION_STRING:-}" \
  --query "properties.outputs" \
  --output json)

# ---------- Parse deployment outputs ----------
ACR_LOGIN_SERVER=$(echo "$DEPLOY_OUTPUT" | jq -r '.acrLoginServer.value')
ACR_NAME=$(echo "$ACR_LOGIN_SERVER" | cut -d. -f1)
BACKEND_FQDN=$(echo "$DEPLOY_OUTPUT" | jq -r '.backendFqdn.value')
BACKEND_PRINCIPAL_ID=$(echo "$DEPLOY_OUTPUT" | jq -r '.backendPrincipalId.value')

echo "ACR: $ACR_LOGIN_SERVER"
echo "Backend FQDN: $BACKEND_FQDN"

# ---------- Build backend image in ACR ----------
echo "=== Building backend image in ACR ==="
az acr build \
  --registry "$ACR_NAME" \
  --image "${APP_NAME}-backend:latest" \
  --file "$SCRIPT_DIR/../src/Dockerfile.backend" \
  "$SCRIPT_DIR/../src"

# ---------- Update container app with real image ----------
echo "=== Updating backend container app ==="
az containerapp update \
  --name "${APP_NAME}-backend" \
  --resource-group "$RESOURCE_GROUP" \
  --image "${ACR_LOGIN_SERVER}/${APP_NAME}-backend:latest"

# ---------- Assign OpenAI role to backend identity ----------
echo "=== Assigning Cognitive Services OpenAI User role ==="
az role assignment create \
  --assignee "$BACKEND_PRINCIPAL_ID" \
  --role "Cognitive Services OpenAI User" \
  --scope "$AZURE_OPENAI_RESOURCE_ID"

# ---------- Done ----------
echo ""
echo "=== Deployment Complete ==="
echo "Backend URL: https://${BACKEND_FQDN}"
echo "Swagger UI:  https://${BACKEND_FQDN}/docs"
echo "Health:      https://${BACKEND_FQDN}/health"

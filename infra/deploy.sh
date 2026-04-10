#!/usr/bin/env bash
set -euo pipefail

# Configuration (override via env vars or args)
RESOURCE_GROUP="${RESOURCE_GROUP:-stt-comparison-rg}"
LOCATION="${LOCATION:-swedencentral}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-stt-comparison}"
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-greenfield}"

# Step 1: Create resource group
echo "📦 Creating resource group $RESOURCE_GROUP..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

# Step 2: Deploy Bicep infrastructure
echo "🏗️ Deploying infrastructure (mode: $DEPLOYMENT_MODE)..."
DEPLOY_OUTPUT=$(az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --parameters environmentName="$ENVIRONMENT_NAME" \
  --parameters deploymentMode="$DEPLOYMENT_MODE" \
  --query 'properties.outputs' \
  --output json)

# Extract outputs
ACR_NAME=$(echo "$DEPLOY_OUTPUT" | jq -r '.acrName.value')
ACR_LOGIN_SERVER=$(echo "$DEPLOY_OUTPUT" | jq -r '.acrLoginServer.value')
APP_NAME=$(echo "$DEPLOY_OUTPUT" | jq -r '.containerAppName.value')
APP_FQDN=$(echo "$DEPLOY_OUTPUT" | jq -r '.containerAppFqdn.value')

# Step 3: Build and push Docker image
echo "🐳 Building and pushing Docker image..."
az acr build \
  --registry "$ACR_NAME" \
  --image stt-comparison:latest \
  --file Dockerfile \
  .

# Step 4: Update Container App with the image
echo "🚀 Updating Container App..."
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --image "${ACR_LOGIN_SERVER}/stt-comparison:latest" \
  --output none

echo ""
echo "✅ Deployment complete!"
echo "🌐 App URL: https://${APP_FQDN}"

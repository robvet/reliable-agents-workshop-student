// ============================================================
// main.bicep — Infrastructure for Model Fusion Playground
// Deploys: ACR, Container Apps Environment, Backend Container App
// with system-assigned managed identity and AcrPull role.
// ============================================================

// ---------- Parameters ----------

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Base name prefix for all resources (lowercase, no special chars)')
param appName string = 'modelfusion'

@description('Azure OpenAI endpoint URL')
param azureOpenAiEndpoint string

@description('Azure OpenAI GPT deployment name')
param azureOpenAiDeploymentGpt string

@description('Azure OpenAI Grok deployment name')
param azureOpenAiDeploymentGrok string

@description('Azure OpenAI DeepSeek deployment name')
param azureOpenAiDeploymentDeepseek string

@secure()
@description('Gemini API key (third-party secret)')
param geminiApiKey string

@description('Gemini model name')
param geminiModel string = 'gemini-3-pro-preview'

@secure()
@description('Anthropic API key (third-party secret)')
param anthropicApiKey string

@description('Anthropic model name')
param anthropicModel string = 'claude-3-5-sonnet-20241022'

@secure()
@description('Application Insights connection string (optional)')
param appInsightsConnectionString string = ''

// ---------- Variables ----------

// ACR names: alphanumeric only, 5-50 chars. uniqueString avoids naming collisions.
var acrName = '${appName}acr${uniqueString(resourceGroup().id)}'
var envName = '${appName}-env'
var backendAppName = '${appName}-backend'

// Built-in role definition ID for AcrPull
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

// ---------- Azure Container Registry ----------

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

// ---------- Container Apps Environment ----------

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {}
}

// ---------- Backend Container App ----------

resource backendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: backendAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8010
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: 'system'
        }
      ]
      secrets: [
        { name: 'gemini-api-key', value: geminiApiKey }
        { name: 'anthropic-api-key', value: anthropicApiKey }
        { name: 'appinsights-cs', value: appInsightsConnectionString }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          // Placeholder image — deploy script replaces with real image after ACR build
          image: 'mcr.microsoft.com/k8se/quickstart:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT_GPT', value: azureOpenAiDeploymentGpt }
            { name: 'AZURE_OPENAI_DEPLOYMENT_GROK', value: azureOpenAiDeploymentGrok }
            { name: 'AZURE_OPENAI_DEPLOYMENT_DEEPSEEK', value: azureOpenAiDeploymentDeepseek }
            { name: 'GEMINI_API_KEY', secretRef: 'gemini-api-key' }
            { name: 'GEMINI_MODEL', value: geminiModel }
            { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' }
            { name: 'ANTHROPIC_MODEL', value: anthropicModel }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-cs' }
            { name: 'APP_ENVIRONMENT', value: 'production' }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
}

// ---------- Role Assignment: AcrPull ----------
// Allows the backend's managed identity to pull images from ACR

resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, backendApp.id, acrPullRoleId)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: backendApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------- Outputs ----------

output acrLoginServer string = acr.properties.loginServer
output backendFqdn string = backendApp.properties.configuration.ingress.fqdn
output backendPrincipalId string = backendApp.identity.principalId

// STT Comparison Tool — Azure Infrastructure
// Deploys Container Apps with managed identity auth to Azure AI services
// Supports greenfield (create all resources) and brownfield (use existing) modes

targetScope = 'resourceGroup'

// ─── Core Parameters ─────────────────────────────────────────────────────────

@description('Azure region for resource deployment')
param location string = resourceGroup().location

@description('Environment name used as prefix for all resources')
param environmentName string

@description('Deployment mode: greenfield creates all resources, brownfield uses existing ones')
@allowed(['greenfield', 'brownfield'])
param deploymentMode string = 'greenfield'

// ─── Brownfield Parameters (existing resource IDs) ───────────────────────────

@description('Resource ID of an existing Azure Speech resource (brownfield only)')
param existingSpeechResourceId string = ''

@description('Resource ID of an existing MAI Speech resource (brownfield only)')
param existingMaiSpeechResourceId string = ''

@description('Resource ID of an existing Azure OpenAI resource (brownfield only)')
param existingOpenAiResourceId string = ''

@description('Resource ID of an existing Storage Account (brownfield only)')
param existingStorageAccountId string = ''

// ─── Service Configuration ───────────────────────────────────────────────────

@description('Azure region for the Speech resource')
param speechRegion string = 'swedencentral'

@description('Azure region for the MAI Speech resource')
param maiSpeechRegion string = 'eastus'

@description('Azure OpenAI model deployment name for gpt-4o-transcribe')
param openAiDeploymentName string = 'gpt-4o-transcribe'

@description('Azure OpenAI model deployment name for Whisper')
param whisperDeploymentName string = 'whisper'

@description('Container image to deploy (leave empty for placeholder)')
param containerImage string = ''

@description('Port the container listens on')
param containerPort int = 8000

// ─── Derived Names ───────────────────────────────────────────────────────────

var acrName = replace('${environmentName}acr', '-', '')
var envName = '${environmentName}-env'
var appName = '${environmentName}-app'
var speechName = '${environmentName}-speech'
var maiSpeechName = '${environmentName}-mai-speech'
var openAiName = '${environmentName}-openai'
var storageName = replace('${environmentName}stor', '-', '')

// ─── Always-Created Resources ────────────────────────────────────────────────

module acr 'modules/container-registry.bicep' = {
  name: 'container-registry'
  params: {
    location: location
    name: acrName
  }
}

module containerAppEnv 'modules/container-app-env.bicep' = {
  name: 'container-app-env'
  params: {
    location: location
    name: envName
  }
}

// ─── Greenfield Resources (conditional) ──────────────────────────────────────

module speech 'modules/speech.bicep' = if (deploymentMode == 'greenfield') {
  name: 'speech'
  params: {
    location: speechRegion
    name: speechName
  }
}

module maiSpeech 'modules/mai-speech.bicep' = if (deploymentMode == 'greenfield') {
  name: 'mai-speech'
  params: {
    location: maiSpeechRegion
    name: maiSpeechName
  }
}

module openAi 'modules/openai.bicep' = if (deploymentMode == 'greenfield') {
  name: 'openai'
  params: {
    location: location
    name: openAiName
    gpt4oTranscribeDeploymentName: openAiDeploymentName
    whisperDeploymentName: whisperDeploymentName
  }
}

module storage 'modules/storage.bicep' = if (deploymentMode == 'greenfield') {
  name: 'storage'
  params: {
    location: location
    name: storageName
  }
}

// ─── Resolve Resource IDs and Endpoints ──────────────────────────────────────

var speechResourceId = deploymentMode == 'greenfield' ? speech.outputs.id : existingSpeechResourceId
var maiSpeechResourceId = deploymentMode == 'greenfield' ? maiSpeech.outputs.id : existingMaiSpeechResourceId
var openAiResourceId = deploymentMode == 'greenfield' ? openAi.outputs.id : existingOpenAiResourceId
var storageResourceId = deploymentMode == 'greenfield' ? storage.outputs.id : existingStorageAccountId

var speechEndpoint = deploymentMode == 'greenfield' ? speech.outputs.endpoint : ''
var maiSpeechEndpoint = deploymentMode == 'greenfield' ? maiSpeech.outputs.endpoint : ''
var openAiEndpoint = deploymentMode == 'greenfield' ? openAi.outputs.endpoint : ''
var storageAccountName = deploymentMode == 'greenfield' ? storage.outputs.name : last(split(existingStorageAccountId, '/'))

// ─── Container App ───────────────────────────────────────────────────────────

module containerApp 'modules/container-app.bicep' = {
  name: 'container-app'
  params: {
    location: location
    name: appName
    containerAppEnvId: containerAppEnv.outputs.id
    containerImage: containerImage
    containerPort: containerPort
    acrLoginServer: acr.outputs.loginServer
    speechEndpoint: speechEndpoint
    speechRegion: speechRegion
    maiSpeechEndpoint: maiSpeechEndpoint
    maiSpeechRegion: maiSpeechRegion
    storageAccountName: storageAccountName
    storageContainerName: 'transcription-audio'
    openAiEndpoint: openAiEndpoint
    openAiDeploymentName: openAiDeploymentName
    whisperDeploymentName: whisperDeploymentName
  }
}

// ─── Role Assignments ────────────────────────────────────────────────────────

module roleAssignments 'modules/role-assignments.bicep' = {
  name: 'role-assignments'
  params: {
    principalId: containerApp.outputs.principalId
    speechResourceId: speechResourceId
    maiSpeechResourceId: maiSpeechResourceId
    openAiResourceId: openAiResourceId
    storageResourceId: storageResourceId
    acrResourceId: acr.outputs.id
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

@description('Container App FQDN')
output appFqdn string = containerApp.outputs.fqdn

@description('Container App URL')
output appUrl string = 'https://${containerApp.outputs.fqdn}'

@description('Container Registry login server')
output acrLoginServer string = acr.outputs.loginServer

@description('Container App managed identity principal ID')
output appPrincipalId string = containerApp.outputs.principalId

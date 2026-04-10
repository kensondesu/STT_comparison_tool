@description('Principal ID of the Container App managed identity')
param principalId string

@description('Resource ID of the Azure Speech resource')
param speechResourceId string

@description('Resource ID of the MAI Speech resource')
param maiSpeechResourceId string

@description('Resource ID of the Azure OpenAI resource')
param openAiResourceId string

@description('Resource ID of the Storage Account')
param storageResourceId string

@description('Resource ID of the Container Registry')
param acrResourceId string

// Built-in role definition IDs
var cognitiveServicesUserId = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var cognitiveServicesOpenAiUserId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var storageBlobDataContributorId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var storageBlobDelegatorId = 'db58b8e5-c6ad-4a2a-8342-4190687cbf4a'
var acrPullId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

// Reference existing resources by ID
resource speechResource 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(speechResourceId, '/'))
}

resource maiSpeechResource 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(maiSpeechResourceId, '/'))
}

resource openAiResource 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(openAiResourceId, '/'))
}

resource storageResource 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: last(split(storageResourceId, '/'))
}

resource acrResource 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: last(split(acrResourceId, '/'))
}

// 1. Cognitive Services User on Speech → STT Fast/Batch
resource speechRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(speechResource.id, principalId, cognitiveServicesUserId)
  scope: speechResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// 2. Cognitive Services User on MAI Speech → MAI-Transcribe + LLM Speech
resource maiSpeechRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(maiSpeechResource.id, principalId, cognitiveServicesUserId)
  scope: maiSpeechResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// 3. Cognitive Services OpenAI User on OpenAI → gpt-4o-transcribe + Whisper
resource openAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiResource.id, principalId, cognitiveServicesOpenAiUserId)
  scope: openAiResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUserId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// 4. Storage Blob Data Contributor on Storage → batch upload
resource storageBlobContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageResource.id, principalId, storageBlobDataContributorId)
  scope: storageResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// 5. Storage Blob Delegator on Storage → user delegation SAS
resource storageBlobDelegatorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageResource.id, principalId, storageBlobDelegatorId)
  scope: storageResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDelegatorId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// 6. AcrPull on ACR → container image pull
resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrResource.id, principalId, acrPullId)
  scope: acrResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

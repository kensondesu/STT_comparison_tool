@description('Azure region for the OpenAI resource')
param location string

@description('Name of the OpenAI resource')
param name string

@description('Deployment name for gpt-4o-transcribe model')
param gpt4oTranscribeDeploymentName string

@description('Deployment name for Whisper model')
param whisperDeploymentName string

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
  }
}

resource gpt4oTranscribeDeploy 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: gpt4oTranscribeDeploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: 1
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-transcribe'
      version: '2025-03-20'
    }
  }
}

resource whisperDeploy 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: whisperDeploymentName
  dependsOn: [gpt4oTranscribeDeploy]
  sku: {
    name: 'Standard'
    capacity: 1
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'whisper'
      version: '001'
    }
  }
}

@description('Resource ID of the OpenAI resource')
output id string = openAi.id

@description('Endpoint URL of the OpenAI resource')
output endpoint string = openAi.properties.endpoint

@description('Name of the OpenAI resource')
output name string = openAi.name

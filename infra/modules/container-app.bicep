@description('Azure region for the Container App')
param location string

@description('Name of the Container App')
param name string

@description('Resource ID of the Container Apps Environment')
param containerAppEnvId string

@description('Container image to deploy (e.g. myacr.azurecr.io/app:latest)')
param containerImage string

@description('Target port the container listens on')
param containerPort int

@description('ACR login server URL')
param acrLoginServer string

@description('Azure Speech endpoint URL')
param speechEndpoint string

@description('Azure Speech region')
param speechRegion string

@description('MAI Speech endpoint URL')
param maiSpeechEndpoint string

@description('MAI Speech region')
param maiSpeechRegion string

@description('Azure Storage account name')
param storageAccountName string

@description('Azure Storage container name for audio blobs')
param storageContainerName string

@description('Azure OpenAI endpoint URL')
param openAiEndpoint string

@description('Azure OpenAI deployment name for gpt-4o-transcribe')
param openAiDeploymentName string

@description('Azure OpenAI deployment name for Whisper')
param whisperDeploymentName string

var effectiveImage = !empty(containerImage) ? containerImage : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppEnvId
    configuration: {
      ingress: {
        external: true
        targetPort: containerPort
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: name
          image: effectiveImage
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'AZURE_SPEECH_ENDPOINT', value: speechEndpoint }
            { name: 'AZURE_SPEECH_REGION', value: speechRegion }
            { name: 'MAI_SPEECH_ENDPOINT', value: maiSpeechEndpoint }
            { name: 'MAI_SPEECH_REGION', value: maiSpeechRegion }
            { name: 'AZURE_STORAGE_ACCOUNT_NAME', value: storageAccountName }
            { name: 'AZURE_STORAGE_CONTAINER_NAME', value: storageContainerName }
            { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT_NAME', value: openAiDeploymentName }
            { name: 'AZURE_WHISPER_DEPLOYMENT_NAME', value: whisperDeploymentName }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

@description('Resource ID of the Container App')
output id string = containerApp.id

@description('Name of the Container App')
output name string = containerApp.name

@description('Fully qualified domain name of the Container App')
output fqdn string = containerApp.properties.configuration.ingress.fqdn

@description('Principal ID of the system-assigned managed identity')
output principalId string = containerApp.identity.principalId

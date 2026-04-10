@description('Azure region for the Storage Account')
param location string

@description('Name of the Storage Account')
param name string

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource audioContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'transcription-audio'
  properties: {
    publicAccess: 'None'
  }
}

@description('Resource ID of the Storage Account')
output id string = storageAccount.id

@description('Name of the Storage Account')
output name string = storageAccount.name

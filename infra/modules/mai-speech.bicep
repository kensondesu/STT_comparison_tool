@description('Azure region for the MAI Speech resource')
param location string

@description('Name of the MAI Speech resource')
param name string

resource maiSpeech 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  kind: 'SpeechServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
  }
}

@description('Resource ID of the MAI Speech resource')
output id string = maiSpeech.id

@description('Endpoint URL of the MAI Speech resource')
output endpoint string = maiSpeech.properties.endpoint

@description('Name of the MAI Speech resource')
output name string = maiSpeech.name

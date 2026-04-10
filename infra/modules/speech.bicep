@description('Azure region for the Speech resource')
param location string

@description('Name of the Speech resource')
param name string

resource speech 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
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

@description('Resource ID of the Speech resource')
output id string = speech.id

@description('Endpoint URL of the Speech resource')
output endpoint string = speech.properties.endpoint

@description('Name of the Speech resource')
output name string = speech.name

@description('Azure region for the Container Registry')
param location string

@description('Name of the Container Registry')
param name string

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

@description('Resource ID of the Container Registry')
output id string = acr.id

@description('Name of the Container Registry')
output name string = acr.name

@description('Login server URL for the Container Registry')
output loginServer string = acr.properties.loginServer

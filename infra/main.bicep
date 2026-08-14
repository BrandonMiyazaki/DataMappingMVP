@description('Name of the environment (for example dev, test, prod).')
param environmentName string = 'dev'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Globally unique storage account name.')
param storageAccountName string = 'st${uniqueString(resourceGroup().id)}'

@description('Function App name.')
param functionAppName string = 'func-data-mapping-${environmentName}-${uniqueString(resourceGroup().id)}'

@description('Application Insights name.')
param appInsightsName string = 'appi-data-mapping-${environmentName}-${uniqueString(resourceGroup().id)}'

var commonTags = {
  environment: environmentName
  application: 'data-mapping-mvp'
  managedBy: 'bicep'
}

var functionAppTags = union(commonTags, {
  'azd-service-name': 'func'
})

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: commonTags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: commonTags
  properties: {
    Application_Type: 'web'
    Flow_Type: 'Bluefield'
    Request_Source: 'rest'
  }
}

resource hostingPlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${functionAppName}-plan'
  location: location
  kind: 'functionapp'
  tags: commonTags
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  tags: functionAppTags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: hostingPlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.12'
      minTlsVersion: '1.2'
      appSettings: [
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${listKeys(storageAccount.id, storageAccount.apiVersion).keys[0].value}'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
      ]
    }
  }
}

resource rawContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/raw'
  properties: {
    publicAccess: 'None'
  }
}

resource processedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/processed'
  properties: {
    publicAccess: 'None'
  }
}

resource failedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/failed'
  properties: {
    publicAccess: 'None'
  }
}

resource archiveContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/archive'
  properties: {
    publicAccess: 'None'
  }
}

resource stateContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/state'
  properties: {
    publicAccess: 'None'
  }
}

resource deadLetterContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/eventgrid-deadletter'
  properties: {
    publicAccess: 'None'
  }
}

output storageAccountName string = storageAccount.name
output functionAppName string = functionApp.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output functionAppPrincipalId string = functionApp.identity.principalId

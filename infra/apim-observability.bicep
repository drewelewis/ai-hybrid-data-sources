@description('Azure location for observability resources and the private endpoint.')
param location string

@description('Tags applied to observability resources.')
param tags object

@description('Short unique token used to name resources.')
param resourceToken string

@description('Existing APIM service name.')
param apimName string

@description('Existing hub VNet name.')
param vnetName string

@description('Existing private-endpoint subnet name.')
param privateEndpointSubnetName string

@description('Existing blob private DNS zone name to reuse for Azure Monitor.')
param blobPrivateDnsZoneName string

@allowed([
  30
  60
  90
  120
  180
  270
  365
])
@description('Log Analytics retention in days.')
param logRetentionDays int = 30

@minValue(0)
@maxValue(100)
@description('Percentage of successful APIM requests sent to Application Insights. Errors are always logged.')
param telemetrySamplingPercentage int = 100

var monitoringMetricsPublisherRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '3913510d-42f4-4e42-8a64-420c390055eb'
)

resource apim 'Microsoft.ApiManagement/service@2025-09-01-preview' existing = {
  name: apimName
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: vnetName
}

resource blobPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: blobPrivateDnsZoneName
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'law-${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: logRetentionDays
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Enabled'
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${resourceToken}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    // Not yet represented by the Bicep type registry: https://github.com/Azure/bicep-types-az/issues/2048
    #disable-next-line BCP037
    CustomMetricsOptedInType: 'WithDimensions'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
    DisableLocalAuth: true
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource monitorPrivateLinkScope 'Microsoft.Insights/privateLinkScopes@2023-06-01-preview' = {
  name: 'ampls-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    accessModeSettings: {
      ingestionAccessMode: 'PrivateOnly'
      queryAccessMode: 'Open'
    }
  }
}

resource monitorWorkspaceScope 'Microsoft.Insights/privateLinkScopes/scopedResources@2023-06-01-preview' = {
  parent: monitorPrivateLinkScope
  name: 'log-analytics'
  properties: {
    kind: 'resource'
    linkedResourceId: logAnalytics.id
  }
}

resource monitorAppInsightsScope 'Microsoft.Insights/privateLinkScopes/scopedResources@2023-06-01-preview' = {
  parent: monitorPrivateLinkScope
  name: 'application-insights'
  properties: {
    kind: 'resource'
    linkedResourceId: appInsights.id
  }
}

resource monitorPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.monitor.azure.com'
  location: 'global'
  tags: tags
}

resource omsPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.oms.opinsights.azure.com'
  location: 'global'
  tags: tags
}

resource odsPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.ods.opinsights.azure.com'
  location: 'global'
  tags: tags
}

resource automationPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.agentsvc.azure-automation.net'
  location: 'global'
  tags: tags
}

resource monitorPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: monitorPrivateDnsZone
  name: 'link-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource omsPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: omsPrivateDnsZone
  name: 'link-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource odsPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: odsPrivateDnsZone
  name: 'link-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource automationPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: automationPrivateDnsZone
  name: 'link-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource monitorPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = {
  name: 'pep-ampls-${resourceToken}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/${privateEndpointSubnetName}'
    }
    privateLinkServiceConnections: [
      {
        name: 'azure-monitor'
        properties: {
          privateLinkServiceId: monitorPrivateLinkScope.id
          groupIds: [
            'azuremonitor'
          ]
        }
      }
    ]
  }
  dependsOn: [
    monitorWorkspaceScope
    monitorAppInsightsScope
  ]
}

resource monitorPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = {
  parent: monitorPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'azure-monitor'
        properties: {
          privateDnsZoneId: monitorPrivateDnsZone.id
        }
      }
      {
        name: 'log-analytics-oms'
        properties: {
          privateDnsZoneId: omsPrivateDnsZone.id
        }
      }
      {
        name: 'log-analytics-ods'
        properties: {
          privateDnsZoneId: odsPrivateDnsZone.id
        }
      }
      {
        name: 'azure-automation-agent'
        properties: {
          privateDnsZoneId: automationPrivateDnsZone.id
        }
      }
      {
        name: 'azure-monitor-blob'
        properties: {
          privateDnsZoneId: blobPrivateDnsZone.id
        }
      }
    ]
  }
  dependsOn: [
    monitorPrivateDnsLink
    omsPrivateDnsLink
    odsPrivateDnsLink
    automationPrivateDnsLink
  ]
}

resource telemetryPublisherRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsights.id, apim.id, monitoringMetricsPublisherRoleId)
  scope: appInsights
  properties: {
    principalId: apim.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: monitoringMetricsPublisherRoleId
  }
}

resource appInsightsLogger 'Microsoft.ApiManagement/service/loggers@2024-05-01' = {
  parent: apim
  name: 'application-insights'
  properties: {
    loggerType: 'applicationInsights'
    description: 'Managed-identity APIM telemetry logger'
    credentials: {
      connectionString: appInsights.properties.ConnectionString
      identityClientId: 'SystemAssigned'
    }
    isBuffered: true
    resourceId: appInsights.id
  }
  dependsOn: [
    telemetryPublisherRole
    monitorPrivateDnsZoneGroup
  ]
}

resource appInsightsDiagnostic 'Microsoft.ApiManagement/service/diagnostics@2024-05-01' = {
  parent: apim
  name: 'applicationinsights'
  properties: {
    loggerId: appInsightsLogger.id
    alwaysLog: 'allErrors'
    sampling: {
      samplingType: 'fixed'
      percentage: telemetrySamplingPercentage
    }
    verbosity: 'information'
    httpCorrelationProtocol: 'W3C'
    operationNameFormat: 'Name'
    frontend: {
      request: {
        headers: []
        body: {
          bytes: 0
        }
      }
      response: {
        headers: [
          'apim-request-id'
          'x-llmmgmt-model-ratelimit-limit'
          'x-llmmgmt-ratelimit-limit'
          'x-llmmgmt-model-ratelimit-consumed'
          'x-llmmgmt-model-ratelimit-remaining'
          'x-llmmgmt-sku-ratelimit-limit'
          'x-llmmgmt-sku-ratelimit-consumed'
          'x-llmmgmt-sku-ratelimit-remaining'
          'x-llmmgmt-ratelimit-limit-calls'
          'x-llmmgmt-ratelimit-remaining-calls'
          'x-llmmgmt-retry-after'
          'x-llmmgmt-product-ratelimit-consumed'
          'x-llmmgmt-product-ratelimit-remaining'
        ]
        body: {
          bytes: 0
        }
      }
    }
    backend: {
      request: {
        headers: []
        body: {
          bytes: 0
        }
      }
      response: {
        headers: []
        body: {
          bytes: 0
        }
      }
    }
  }
}

resource gatewayDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'apim-gateway-logs'
  scope: apim
  properties: {
    workspaceId: logAnalytics.id
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        category: 'GatewayLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

output logAnalyticsWorkspaceName string = logAnalytics.name
output applicationInsightsName string = appInsights.name
output monitorPrivateLinkScopeName string = monitorPrivateLinkScope.name
output monitorPrivateEndpointIp string = !empty(monitorPrivateEndpoint.properties.customDnsConfigs)
  ? monitorPrivateEndpoint.properties.customDnsConfigs[0].ipAddresses[0]
  : ''

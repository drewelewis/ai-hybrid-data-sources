@description('Azure location for all resources.')
param location string

@description('Tags applied to all resources.')
param tags object

@description('Short unique token used to name resources.')
param resourceToken string

@description('On-prem private address space(s) advertised to Azure.')
param onPremAddressPrefixes array

@description('DDNS FQDN of the on-prem VPN device (takes precedence over onPremGatewayIp).')
param onPremGatewayFqdn string

@description('Public IP of the on-prem VPN device (used when FQDN is empty).')
param onPremGatewayIp string

@secure()
@description('IPsec pre-shared key.')
param sharedKey string

@description('Publisher email for the API Management instance (owner notifications).')
param apimPublisherEmail string

@description('Publisher/organization name for the API Management instance.')
param apimPublisherName string

@allowed([
  'premiumV2Injection'
  'standardV2PrivateLink'
])
@description('APIM networking profile.')
param apimNetworkProfile string = 'premiumV2Injection'

@description('Scale-out units for the selected API Management v2 tier.')
param apimCapacity int = 1

@description('APIM private IP inside the injection subnet (Premium v2 Internal mode returns null, so it is supplied statically). First usable address in the /24 apim subnet.')
param apimPrivateIp string = '10.100.1.4'

@description('App Service Plan SKU for the VNet-integrated front-end proxy (Basic tier or higher).')
param appServiceSkuName string = 'B1'

@description('Azure location for the App Service plan and its regional VNet integration spoke.')
param appServiceLocation string = 'canadaeast'

@allowed([
  30
  60
  90
  120
  180
  270
  365
])
@description('Log Analytics retention in days for APIM observability.')
param apimLogRetentionDays int = 30

@minValue(0)
@maxValue(100)
@description('Percentage of successful APIM requests sent to Application Insights. Errors are always logged.')
param apimTelemetrySamplingPercentage int = 100

// ---- Addressing (clear of on-prem 192.168.50.0/24 and WAN 192.168.1.0/24) ----
var vnetAddressPrefix = '10.100.0.0/16'
var gatewaySubnetPrefix = '10.100.0.0/27'
var apimSubnetPrefix = '10.100.1.0/24'
var apimPrivateEndpointSubnetPrefix = '10.100.2.0/27'
var appServiceVnetAddressPrefix = '10.101.0.0/16'
var appServiceSubnetPrefix = '10.101.0.0/27'
var usePremiumV2Injection = apimNetworkProfile == 'premiumV2Injection'
var apimSkuName = usePremiumV2Injection ? 'PremiumV2' : 'StandardV2'
var apimDnsZoneName = usePremiumV2Injection ? 'azure-api.net' : 'privatelink.azure-api.net'
var apimSubnetName = usePremiumV2Injection ? 'apim' : 'snet-apim-outbound'
var privateEndpointSubnetName = 'snet-apim-private-endpoint'

// Both v2 networking models require outbound 443 to Key Vault on their delegated subnet.
resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-apim-${resourceToken}'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'Allow-KeyVault-outbound'
        properties: {
          priority: 1000
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'AzureKeyVault'
          destinationPortRange: '443'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'vnet-${resourceToken}'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [ vnetAddressPrefix ]
    }
    subnets: [
      {
        name: 'GatewaySubnet'
        properties: {
          addressPrefix: gatewaySubnetPrefix
        }
      }
      {
        name: apimSubnetName
        properties: {
          addressPrefix: apimSubnetPrefix
          networkSecurityGroup: {
            id: nsg.id
          }
          delegations: [
            {
              name: 'apim-delegation'
              properties: {
                serviceName: usePremiumV2Injection ? 'Microsoft.Web/hostingEnvironments' : 'Microsoft.Web/serverFarms'
              }
            }
          ]
        }
      }
      {
        name: privateEndpointSubnetName
        properties: {
          addressPrefix: apimPrivateEndpointSubnetPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

// APIM is the final live capacity probe. Every remaining deployment root depends on it so
// an APIM rejection stops the deployment before VPN, App Service, and DNS provisioning.
// App Service regional VNet integration requires the app and integration subnet to be in
// the same region. This spoke can therefore use App Service quota outside the hub region.
resource appServiceVnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'vnet-app-${resourceToken}'
  location: appServiceLocation
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [ appServiceVnetAddressPrefix ]
    }
    subnets: [
      {
        name: 'snet-appservice-integration'
        properties: {
          addressPrefix: appServiceSubnetPrefix
          delegations: [
            {
              name: 'appservice-delegation'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
        }
      }
    ]
  }
  dependsOn: [
    apim
  ]
}

resource hubToAppServicePeering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-05-01' = {
  parent: vnet
  name: 'hub-to-app-${resourceToken}'
  properties: {
    remoteVirtualNetwork: {
      id: appServiceVnet.id
    }
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: false
    allowGatewayTransit: true
    useRemoteGateways: false
  }
}

resource appServiceToHubPeering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-05-01' = {
  parent: appServiceVnet
  name: 'app-to-hub-${resourceToken}'
  properties: {
    remoteVirtualNetwork: {
      id: vnet.id
    }
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: false
    allowGatewayTransit: false
    useRemoteGateways: true
  }
  dependsOn: [
    hubToAppServicePeering
    vpnGateway
  ]
}

resource vpnGatewayPip 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: 'pip-vng-${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  // AZ VPN gateway SKUs require a zone-redundant public IP.
  zones: [ '1', '2', '3' ]
  properties: {
    publicIPAllocationMethod: 'Static'
  }
  dependsOn: [
    apim
  ]
}

resource vpnGateway 'Microsoft.Network/virtualNetworkGateways@2024-05-01' = {
  name: 'vng-${resourceToken}'
  location: location
  tags: tags
  properties: {
    gatewayType: 'Vpn'
    vpnType: 'RouteBased'
    enableBgp: false
    activeActive: false
    // Non-AZ VpnGw SKUs are retired; only the zone-redundant *AZ SKUs can be created.
    sku: {
      name: 'VpnGw1AZ'
      tier: 'VpnGw1AZ'
    }
    ipConfigurations: [
      {
        name: 'default'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: '${vnet.id}/subnets/GatewaySubnet'
          }
          publicIPAddress: {
            id: vpnGatewayPip.id
          }
        }
      }
    ]
  }
}

resource localGateway 'Microsoft.Network/localNetworkGateways@2024-05-01' = {
  name: 'lng-${resourceToken}'
  location: location
  tags: tags
  properties: {
    localNetworkAddressSpace: {
      addressPrefixes: onPremAddressPrefixes
    }
    gatewayIpAddress: empty(onPremGatewayFqdn) ? onPremGatewayIp : null
    fqdn: empty(onPremGatewayFqdn) ? null : onPremGatewayFqdn
  }
  dependsOn: [
    apim
  ]
}

resource connection 'Microsoft.Network/connections@2024-05-01' = {
  name: 'cn-${resourceToken}'
  location: location
  tags: tags
  properties: {
    connectionType: 'IPsec'
    connectionProtocol: 'IKEv2'
    virtualNetworkGateway1: {
      id: vpnGateway.id
    }
    localNetworkGateway2: {
      id: localGateway.id
    }
    sharedKey: sharedKey
    enableBgp: false
    usePolicyBasedTrafficSelectors: false
    dpdTimeoutSeconds: 45
    // Deterministic IKEv2 policy so the on-prem strongSwan proposal matches exactly.
    ipsecPolicies: [
      {
        saLifeTimeSeconds: 3600
        saDataSizeKilobytes: 102400000
        ipsecEncryption: 'AES256'
        ipsecIntegrity: 'SHA256'
        ikeEncryption: 'AES256'
        ikeIntegrity: 'SHA256'
        dhGroup: 'DHGroup14'
        pfsGroup: 'None'
      }
    ]
  }
}

// Premium v2 is injected; Standard v2 uses outbound integration and gains private inbound
// connectivity through the private endpoint below.
resource apim 'Microsoft.ApiManagement/service@2025-09-01-preview' = {
  name: 'apim-${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: apimSkuName
    capacity: apimCapacity
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: apimPublisherEmail
    publisherName: apimPublisherName
    customProperties: {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Protocols.Server.Http2': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Ssl30': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls11': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TripleDes168': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Ssl30': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'False'
    }
    developerPortalStatus: 'Disabled'
    legacyPortalStatus: 'Disabled'
    ...(!usePremiumV2Injection ? {
      natGatewayState: 'Enabled'
    } : {})
    publicNetworkAccess: 'Enabled'
    virtualNetworkType: usePremiumV2Injection ? 'Internal' : 'External'
    virtualNetworkConfiguration: {
      subnetResourceId: '${vnet.id}/subnets/${apimSubnetName}'
    }
  }
}

resource apimPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = if (!usePremiumV2Injection) {
  name: 'pep-apim-${resourceToken}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: '${vnet.id}/subnets/${privateEndpointSubnetName}'
    }
    privateLinkServiceConnections: [
      {
        name: 'apim-gateway'
        properties: {
          privateLinkServiceId: apim.id
          groupIds: [
            'Gateway'
          ]
        }
      }
    ]
  }
}

resource apimPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: apimDnsZoneName
  location: 'global'
  tags: tags
  dependsOn: [
    apim
  ]
}

resource apimPrivateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: apimPrivateDnsZone
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

resource apimPrivateDnsAppServiceLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: apimPrivateDnsZone
  name: 'link-app-${resourceToken}'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: appServiceVnet.id
    }
  }
}

resource apimPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (!usePremiumV2Injection) {
  parent: apimPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'apim-gateway'
        properties: {
          privateDnsZoneId: apimPrivateDnsZone.id
        }
      }
    ]
  }
}

resource apimGatewayARecord 'Microsoft.Network/privateDnsZones/A@2020-06-01' = if (usePremiumV2Injection) {
  parent: apimPrivateDnsZone
  name: apim.name
  properties: {
    ttl: 3600
    aRecords: [
      {
        ipv4Address: apimPrivateIp
      }
    ]
  }
}

module mappingStorage 'mapping-storage.bicep' = {
  name: 'mapping-storage-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    apimName: apim.name
    vnetName: vnet.name
    privateEndpointSubnetName: privateEndpointSubnetName
  }
}

module apimObservability 'apim-observability.bicep' = {
  name: 'apim-observability-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    apimName: apim.name
    vnetName: vnet.name
    privateEndpointSubnetName: privateEndpointSubnetName
    blobPrivateDnsZoneName: mappingStorage.outputs.blobPrivateDnsZoneName
    logRetentionDays: apimLogRetentionDays
    telemetrySamplingPercentage: apimTelemetrySamplingPercentage
  }
}

module observabilityWorkbook 'observability-workbook.bicep' = {
  name: 'observability-workbook-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    workspaceResourceId: resourceId(
      'Microsoft.OperationalInsights/workspaces',
      apimObservability.outputs.logAnalyticsWorkspaceName
    )
    appInsightsResourceId: resourceId(
      'Microsoft.Insights/components',
      apimObservability.outputs.applicationInsightsName
    )
    apimResourceId: apim.id
  }
}

module aiGatewayUsageWorkbook 'ai-gateway-usage-workbook.bicep' = {
  name: 'ai-gateway-usage-workbook-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    workspaceResourceId: resourceId(
      'Microsoft.OperationalInsights/workspaces',
      apimObservability.outputs.logAnalyticsWorkspaceName
    )
    appInsightsResourceId: resourceId(
      'Microsoft.Insights/components',
      apimObservability.outputs.applicationInsightsName
    )
    apimResourceId: apim.id
  }
}

module aiGatewayDimensionValuesWorkbook 'ai-gateway-dimension-values-workbook.bicep' = {
  name: 'ai-gateway-dimension-values-workbook-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    workspaceResourceId: resourceId(
      'Microsoft.OperationalInsights/workspaces',
      apimObservability.outputs.logAnalyticsWorkspaceName
    )
    apimResourceId: apim.id
  }
}

module apimLimitDebugWorkbook 'apim-limit-debug-workbook.bicep' = {
  name: 'apim-limit-debug-workbook-${resourceToken}'
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    workspaceResourceId: resourceId(
      'Microsoft.OperationalInsights/workspaces',
      apimObservability.outputs.logAnalyticsWorkspaceName
    )
    appInsightsResourceId: resourceId(
      'Microsoft.Insights/components',
      apimObservability.outputs.applicationInsightsName
    )
    apimResourceId: apim.id
  }
}

// ---- Front-end App Service (Linux) that serves the SPA and proxies /ai to APIM ----
resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'plan-${resourceToken}'
  location: appServiceLocation
  tags: tags
  sku: {
    name: appServiceSkuName
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
  dependsOn: [
    apim
  ]
}

resource appService 'Microsoft.Web/sites@2024-04-01' = {
  name: 'app-${resourceToken}'
  location: appServiceLocation
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    // Regional VNet integration into the dedicated delegated subnet.
    virtualNetworkSubnetId: '${appServiceVnet.id}/subnets/snet-appservice-integration'
    siteConfig: {
      linuxFxVersion: 'NODE|20-lts'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      // Route all outbound traffic through the VNet so private DNS resolves the APIM host.
      vnetRouteAllEnabled: true
    }
  }
  dependsOn: [
    appServiceToHubPeering
    hubToAppServicePeering
    apimPrivateDnsAppServiceLink
  ]
}

// Preserve settings managed outside this template, including the APIM subscription key.
module appServiceSettings 'app-service-settings.bicep' = {
  name: 'app-service-settings-${resourceToken}'
  params: {
    appServiceName: appService.name
    // Constructed instead of using gatewayUrl, which is empty in Premium v2 Internal mode.
    apimOrigin: 'https://${apim.name}.azure-api.net'
    currentAppSettings: list('${appService.id}/config/appsettings', '2024-04-01').properties
  }
}

output vpnGatewayPublicIp string = vpnGatewayPip.properties.ipAddress
output vnetAddressSpace string = vnetAddressPrefix
output vpnConnectionName string = connection.name
output apimName string = apim.name
output apimGatewayUrl string = 'https://${apim.name}.azure-api.net'
output apimPrivateIp string = usePremiumV2Injection
  ? apimPrivateIp
  : (!empty(apimPrivateEndpoint!.properties.customDnsConfigs)
      ? apimPrivateEndpoint!.properties.customDnsConfigs[0].ipAddresses[0]
      : '')
output apimPrivateDnsZoneName string = apimDnsZoneName
output mappingStorageAccountName string = mappingStorage.outputs.storageAccountName
output mappingContainerName string = mappingStorage.outputs.containerName
output mappingBlobName string = mappingStorage.outputs.blobName
output mappingBlobUrl string = mappingStorage.outputs.blobUrl
output mappingStoragePrivateIp string = mappingStorage.outputs.storagePrivateIp
output logAnalyticsWorkspaceName string = apimObservability.outputs.logAnalyticsWorkspaceName
output applicationInsightsName string = apimObservability.outputs.applicationInsightsName
output monitorPrivateLinkScopeName string = apimObservability.outputs.monitorPrivateLinkScopeName
output monitorPrivateEndpointIp string = apimObservability.outputs.monitorPrivateEndpointIp
output observabilityWorkbookId string = observabilityWorkbook.outputs.workbookId
output observabilityWorkbookName string = observabilityWorkbook.outputs.workbookName
output aiGatewayUsageWorkbookId string = aiGatewayUsageWorkbook.outputs.workbookId
output aiGatewayUsageWorkbookName string = aiGatewayUsageWorkbook.outputs.workbookName
output aiGatewayDimensionValuesWorkbookId string = aiGatewayDimensionValuesWorkbook.outputs.workbookId
output aiGatewayDimensionValuesWorkbookName string = aiGatewayDimensionValuesWorkbook.outputs.workbookName
output apimLimitDebugWorkbookId string = apimLimitDebugWorkbook.outputs.workbookId
output apimLimitDebugWorkbookName string = apimLimitDebugWorkbook.outputs.workbookName
output appServiceName string = appService.name
output appServiceDefaultHostName string = 'https://${appService.properties.defaultHostName}'
output appServiceLocation string = appServiceLocation

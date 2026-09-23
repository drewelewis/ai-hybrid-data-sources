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

@description('Scale-out units for API Management Premium v2.')
param apimCapacity int = 1

@description('APIM private IP inside the injection subnet (Premium v2 Internal mode returns null, so it is supplied statically). First usable address in the /24 apim subnet.')
param apimPrivateIp string = '10.100.1.4'

@description('App Service Plan SKU for the VNet-integrated front-end proxy (Basic tier or higher).')
param appServiceSkuName string = 'B1'

@description('Azure location for the App Service plan and its regional VNet integration spoke.')
param appServiceLocation string = 'canadaeast'

// ---- Addressing (clear of on-prem 192.168.50.0/24 and WAN 192.168.1.0/24) ----
var vnetAddressPrefix = '10.100.0.0/16'
var gatewaySubnetPrefix = '10.100.0.0/27'
var apimSubnetPrefix = '10.100.1.0/24'
var appServiceVnetAddressPrefix = '10.101.0.0/16'
var appServiceSubnetPrefix = '10.101.0.0/27'

// NSG required on the API Management injection subnet. Premium v2 simplified injection
// only mandates outbound 443 to Azure Key Vault; platform defaults cover the rest.
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
        name: 'apim'
        properties: {
          addressPrefix: apimSubnetPrefix
          networkSecurityGroup: {
            id: nsg.id
          }
          delegations: [
            {
              name: 'apim-delegation'
              properties: {
                serviceName: 'Microsoft.Web/hostingEnvironments'
              }
            }
          ]
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

// ---- API Management (Premium v2), VNet-injected for private ingress/egress ----
// Injected in Internal mode: the gateway is reachable only via a private IP inside the
// VNet, giving the private-only, no-public-endpoint posture the Option B pattern requires.
resource apim 'Microsoft.ApiManagement/service@2025-09-01-preview' = {
  name: 'apim-${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'PremiumV2'
    capacity: apimCapacity
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: apimPublisherEmail
    publisherName: apimPublisherName
    virtualNetworkType: 'Internal'
    virtualNetworkConfiguration: {
      subnetResourceId: '${vnet.id}/subnets/apim'
    }
  }
}

// ---- Private DNS so the VNet can resolve the Internal-mode APIM gateway host ----
// Internal APIM uses the real azure-api.net domain (not privatelink.azure-api.net).
resource apimPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'azure-api.net'
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

resource apimGatewayARecord 'Microsoft.Network/privateDnsZones/A@2020-06-01' = {
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
      appSettings: [
        {
          // APIM gateway origin only; the SPA builds the /openai/... operation path and
          // calls it same-origin under /ai, which the Node proxy forwards to this origin.
          // Constructed (not apim.properties.gatewayUrl, which is empty in Internal mode)
          // so it always matches the azure-api.net private DNS A record above.
          name: 'APIM_ORIGIN'
          value: 'https://${apim.name}.azure-api.net'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'false'
        }
      ]
    }
  }
  dependsOn: [
    appServiceToHubPeering
    hubToAppServicePeering
    apimPrivateDnsAppServiceLink
  ]
}

output vpnGatewayPublicIp string = vpnGatewayPip.properties.ipAddress
output vnetAddressSpace string = vnetAddressPrefix
output vpnConnectionName string = connection.name
output apimName string = apim.name
output apimGatewayUrl string = apim.properties.gatewayUrl
output appServiceName string = appService.name
output appServiceDefaultHostName string = 'https://${appService.properties.defaultHostName}'
output appServiceLocation string = appServiceLocation

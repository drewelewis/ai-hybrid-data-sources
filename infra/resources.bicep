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

// ---- Addressing (clear of on-prem 192.168.50.0/24 and WAN 192.168.1.0/24) ----
var vnetAddressPrefix = '10.100.0.0/16'
var gatewaySubnetPrefix = '10.100.0.0/27'
var apimSubnetPrefix = '10.100.1.0/24'

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

output vpnGatewayPublicIp string = vpnGatewayPip.properties.ipAddress
output vnetAddressSpace string = vnetAddressPrefix
output vpnConnectionName string = connection.name
output apimName string = apim.name
output apimGatewayUrl string = apim.properties.gatewayUrl

// Glue that connects a spoke VNet (e.g. a private Foundry) to this repo's hub:
//   - VNet peering both directions
//   - a private DNS zone so the spoke resolves the Internal APIM hostname to its private IP
// Run AFTER the spoke VNet exists. Deploy at subscription scope:
//   az deployment sub create -l <region> --template-file peering/peering.bicep --parameters ...
targetScope = 'subscription'

@description('Resource group of the hub VNet (APIM + VPN gateway).')
param hubResourceGroup string

@description('Hub VNet name.')
param hubVnetName string

@description('Resource group of the spoke VNet (e.g. the Foundry spoke).')
param spokeResourceGroup string

@description('Spoke VNet name.')
param spokeVnetName string

@description('APIM instance name — the hostname label under azure-api.net for the DNS A record.')
param apimName string

@description('APIM private IP. Premium v2 assigns this dynamically; update the record if it changes.')
param apimPrivateIp string

@description('Only enable if the spoke needs DIRECT on-prem private-IP access via the hub VPN gateway. Not needed for the APIM path.')
param enableGatewayTransit bool = false

var hubVnetId = resourceId(hubResourceGroup, 'Microsoft.Network/virtualNetworks', hubVnetName)
var spokeVnetId = resourceId(spokeResourceGroup, 'Microsoft.Network/virtualNetworks', spokeVnetName)

module hubToSpoke 'modules/peering-link.bicep' = {
  name: 'peer-hub-to-spoke'
  scope: resourceGroup(hubResourceGroup)
  params: {
    localVnetName: hubVnetName
    peeringName: 'hub-to-${spokeVnetName}'
    remoteVnetId: spokeVnetId
    allowGatewayTransit: enableGatewayTransit
    useRemoteGateways: false
  }
}

module spokeToHub 'modules/peering-link.bicep' = {
  name: 'peer-spoke-to-hub'
  scope: resourceGroup(spokeResourceGroup)
  params: {
    localVnetName: spokeVnetName
    peeringName: 'spoke-to-${hubVnetName}'
    remoteVnetId: hubVnetId
    allowGatewayTransit: false
    useRemoteGateways: enableGatewayTransit
  }
}

module apimDns 'modules/apim-private-dns.bicep' = {
  name: 'apim-private-dns'
  scope: resourceGroup(spokeResourceGroup)
  params: {
    apimName: apimName
    apimPrivateIp: apimPrivateIp
    spokeVnetId: spokeVnetId
  }
}

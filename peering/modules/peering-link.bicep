// One directional VNet peering, created on the local VNet (RG-scoped).
@description('Name of the local VNet this peering is created on.')
param localVnetName string

@description('Name for the peering resource.')
param peeringName string

@description('Resource ID of the remote VNet to peer with.')
param remoteVnetId string

@description('Share this VNet gateway with the peer.')
param allowGatewayTransit bool

@description('Use the remote VNet gateway (the peer must allow gateway transit).')
param useRemoteGateways bool

resource localVnet 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: localVnetName
}

resource peering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-05-01' = {
  parent: localVnet
  name: peeringName
  properties: {
    remoteVirtualNetwork: {
      id: remoteVnetId
    }
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: true
    allowGatewayTransit: allowGatewayTransit
    useRemoteGateways: useRemoteGateways
  }
}

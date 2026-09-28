// Private DNS so a spoke resolves the selected APIM private gateway path.
@description('APIM instance name (the hostname label under azure-api.net).')
param apimName string

@description('APIM private IP.')
param apimPrivateIp string

@allowed([
  'azure-api.net'
  'privatelink.azure-api.net'
])
@description('Private DNS zone used by the APIM networking profile.')
param privateDnsZoneName string

@description('Resource ID of the spoke VNet to link the zone to.')
param spokeVnetId string

resource zone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneName
  location: 'global'
}

resource aRecord 'Microsoft.Network/privateDnsZones/A@2020-06-01' = {
  parent: zone
  name: apimName
  properties: {
    ttl: 300
    aRecords: [
      {
        ipv4Address: apimPrivateIp
      }
    ]
  }
}

resource link 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: zone
  name: 'link-${last(split(spokeVnetId, '/'))}'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: spokeVnetId
    }
  }
}

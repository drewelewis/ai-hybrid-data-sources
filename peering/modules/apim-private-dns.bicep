// Private DNS so a spoke resolves the Internal APIM gateway hostname to its private IP.
// NOTE: linking the azure-api.net zone to the spoke shadows ALL *.azure-api.net names there;
// acceptable for a spoke dedicated to reaching this APIM.
@description('APIM instance name (the hostname label under azure-api.net).')
param apimName string

@description('APIM private IP.')
param apimPrivateIp string

@description('Resource ID of the spoke VNet to link the zone to.')
param spokeVnetId string

resource zone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'azure-api.net'
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

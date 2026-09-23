// Links the Foundry private-endpoint DNS zones (created in the spoke by template 19) to the HUB
// VNet, so APIM — which lives in the hub — resolves the Foundry inference FQDN to its private IP.
// Runs in the spoke/Foundry resource group where the zones already exist.
@description('Resource ID of the hub VNet to link the Foundry private DNS zones to.')
param hubVnetId string

@description('Foundry privatelink zone names to link to the hub.')
param zoneNames array = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.services.ai.azure.com'
]

resource hubLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [for z in zoneNames: {
  name: '${z}/hub-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: hubVnetId
    }
  }
}]

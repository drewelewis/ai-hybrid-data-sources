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

@description('Also publish the Foundry model deployment as an APIM backend (hub DNS link + backend/API + RBAC).')
param wireFoundryBackend bool = false

@description('Foundry (AIServices) resource group. Required when wireFoundryBackend=true.')
param foundryResourceGroup string = ''

@description('Foundry account name. Required when wireFoundryBackend=true.')
param foundryAccountName string = ''

@description('Foundry inference endpoint, e.g. https://acct.cognitiveservices.azure.com/. Required when wireFoundryBackend=true.')
param foundryEndpoint string = ''

@description('Foundry model deployment name (for the sample call URL).')
param foundryDeploymentName string = ''

@description('Entra tenant id whose tokens the Foundry API accepts. Required when wireFoundryBackend=true.')
param entraTenantId string = ''

@description('Accepted JWT audience (API app registration App ID URI or client id). Required when wireFoundryBackend=true.')
param jwtAudience string = ''

@description('Browser origins allowed to call the Foundry API (SPA dev/prod origins).')
param allowedCorsOrigins array = [ 'http://localhost:5173' ]

var hubVnetId = resourceId(subscription().subscriptionId, hubResourceGroup, 'Microsoft.Network/virtualNetworks', hubVnetName)
var spokeVnetId = resourceId(subscription().subscriptionId, spokeResourceGroup, 'Microsoft.Network/virtualNetworks', spokeVnetName)

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

// --- Optional: publish the Foundry model as an APIM backend (repeatable, no CLI patches) ---

// Link the Foundry private DNS zones to the hub so APIM resolves the model's private endpoint.
module foundryDnsHubLink 'modules/foundry-dns-hub-link.bicep' = if (wireFoundryBackend) {
  name: 'foundry-dns-hub-link'
  scope: resourceGroup(foundryResourceGroup)
  params: {
    hubVnetId: hubVnetId
  }
}

// Create the APIM backend + Azure OpenAI API with managed-identity auth to the Foundry endpoint.
module apimFoundryApi 'modules/apim-foundry-api.bicep' = if (wireFoundryBackend) {
  name: 'apim-foundry-api'
  scope: resourceGroup(hubResourceGroup)
  params: {
    apimName: apimName
    foundryEndpoint: foundryEndpoint
    entraTenantId: entraTenantId
    jwtAudience: jwtAudience
    allowedCorsOrigins: allowedCorsOrigins
  }
}

// Grant APIM's managed identity access to the Foundry model deployment.
module foundryRbac 'modules/foundry-role-assignment.bicep' = if (wireFoundryBackend) {
  name: 'foundry-rbac'
  scope: resourceGroup(foundryResourceGroup)
  params: {
    foundryAccountName: foundryAccountName
    principalId: apimFoundryApi!.outputs.apimPrincipalId
  }
}

@description('Sample call URL for the Foundry model through APIM (empty unless wired).')
output foundryCallExample string = wireFoundryBackend ? 'https://${apimName}.azure-api.net/openai/deployments/${foundryDeploymentName}/chat/completions?api-version=2024-02-01' : ''

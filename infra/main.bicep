targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the azd environment; used to derive resource names and the resource group.')
param environmentName string

@minLength(1)
@description('Primary Azure location for all resources.')
param location string

@description('On-prem private address space(s) advertised to Azure over the tunnel.')
param onPremAddressPrefixes array = [ '192.168.50.0/24' ]

@description('DDNS FQDN of the on-prem VPN device. Leave empty to use onPremGatewayIp instead.')
param onPremGatewayFqdn string = ''

@description('Public IP of the on-prem VPN device. Used only when onPremGatewayFqdn is empty.')
param onPremGatewayIp string = ''

@secure()
@description('IPsec pre-shared key (PSK) shared with the on-prem device.')
param sharedKey string

@description('Publisher email for the API Management instance (owner notifications).')
param apimPublisherEmail string

@description('Publisher/organization name for the API Management instance.')
param apimPublisherName string = 'Contoso'

@description('Scale-out units for API Management Premium v2.')
param apimCapacity int = 1

var tags = { 'azd-env-name': environmentName }
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    onPremAddressPrefixes: onPremAddressPrefixes
    onPremGatewayFqdn: onPremGatewayFqdn
    onPremGatewayIp: onPremGatewayIp
    sharedKey: sharedKey
    apimPublisherEmail: apimPublisherEmail
    apimPublisherName: apimPublisherName
    apimCapacity: apimCapacity
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output VPN_GATEWAY_PUBLIC_IP string = resources.outputs.vpnGatewayPublicIp
output VNET_ADDRESS_SPACE string = resources.outputs.vnetAddressSpace
output VPN_CONNECTION_NAME string = resources.outputs.vpnConnectionName
output APIM_NAME string = resources.outputs.apimName
output APIM_GATEWAY_URL string = resources.outputs.apimGatewayUrl

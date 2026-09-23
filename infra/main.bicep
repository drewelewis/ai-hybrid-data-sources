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

@description('Public IP of your on-prem VPN device (the local network gateway address). Used when onPremGatewayFqdn is empty.')
param onPremGatewayIp string

@secure()
@description('IPsec pre-shared key (PSK) shared with the on-prem device.')
param sharedKey string

@description('Publisher email for the API Management instance (owner notifications).')
param apimPublisherEmail string

@description('Publisher/organization name shown on the API Management instance.')
param apimPublisherName string

@description('Scale-out units for API Management Premium v2.')
param apimCapacity int = 1

@description('APIM private IP inside the injection subnet (supplied statically because Premium v2 Internal mode returns null).')
param apimPrivateIp string = '10.100.1.4'

@description('App Service Plan SKU for the VNet-integrated front-end proxy (Basic tier or higher).')
param appServiceSkuName string = 'B1'

@description('Azure location for the App Service plan and its regional VNet integration spoke.')
param appServiceLocation string = 'canadaeast'

var tags = { 'azd-env-name': environmentName }
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module identity 'identity.bicep' = {
  name: 'identity-${resourceToken}'
  params: {
    deploymentSuffix: resourceToken
    environmentName: environmentName
    productionOrigin: 'https://app-${resourceToken}.azurewebsites.net'
  }
  dependsOn: [
    resources
  ]
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
    apimPrivateIp: apimPrivateIp
    appServiceSkuName: appServiceSkuName
    appServiceLocation: appServiceLocation
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output VPN_GATEWAY_PUBLIC_IP string = resources.outputs.vpnGatewayPublicIp
output VNET_ADDRESS_SPACE string = resources.outputs.vnetAddressSpace
output VPN_CONNECTION_NAME string = resources.outputs.vpnConnectionName
output APIM_NAME string = resources.outputs.apimName
output APIM_GATEWAY_URL string = resources.outputs.apimGatewayUrl
output APP_SERVICE_NAME string = resources.outputs.appServiceName
output APP_SERVICE_URL string = resources.outputs.appServiceDefaultHostName
output APP_SERVICE_LOCATION string = resources.outputs.appServiceLocation
output ENTRA_TENANT_ID string = identity.outputs.tenantId
output ENTRA_API_CLIENT_ID string = identity.outputs.apiClientId
output ENTRA_API_AUDIENCE string = identity.outputs.apiAudience
output ENTRA_API_SCOPE string = identity.outputs.apiScope
output ENTRA_DEV_SPA_CLIENT_ID string = identity.outputs.devSpaClientId
output ENTRA_PROD_SPA_CLIENT_ID string = identity.outputs.prodSpaClientId

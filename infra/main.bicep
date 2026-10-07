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

@allowed([
  'premiumV2Injection'
  'standardV2PrivateLink'
])
@description('APIM networking profile. Premium v2 uses full VNet injection; Standard v2 uses Private Link plus outbound VNet integration.')
param apimNetworkProfile string = 'premiumV2Injection'

@description('Scale-out units for the selected API Management v2 tier.')
param apimCapacity int = 1

@description('APIM private IP inside the injection subnet (supplied statically because Premium v2 Internal mode returns null).')
param apimPrivateIp string = '10.100.1.4'

@description('App Service Plan SKU for the VNet-integrated front-end proxy (Basic tier or higher).')
param appServiceSkuName string = 'B1'

@description('Azure location for the App Service plan and its regional VNet integration spoke.')
param appServiceLocation string = 'canadaeast'

@allowed([
  30
  60
  90
  120
  180
  270
  365
])
@description('Log Analytics retention in days for APIM observability.')
param apimLogRetentionDays int = 30

@minValue(0)
@maxValue(100)
@description('Percentage of successful APIM requests sent to Application Insights. Errors are always logged.')
param apimTelemetrySamplingPercentage int = 100

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
    apimNetworkProfile: apimNetworkProfile
    apimCapacity: apimCapacity
    apimPrivateIp: apimPrivateIp
    appServiceSkuName: appServiceSkuName
    appServiceLocation: appServiceLocation
    apimLogRetentionDays: apimLogRetentionDays
    apimTelemetrySamplingPercentage: apimTelemetrySamplingPercentage
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output VPN_GATEWAY_PUBLIC_IP string = resources.outputs.vpnGatewayPublicIp
output VNET_ADDRESS_SPACE string = resources.outputs.vnetAddressSpace
output VPN_CONNECTION_NAME string = resources.outputs.vpnConnectionName
output APIM_NAME string = resources.outputs.apimName
output APIM_GATEWAY_URL string = resources.outputs.apimGatewayUrl
output APIM_PRIVATE_IP string = resources.outputs.apimPrivateIp
output APIM_NETWORK_PROFILE string = apimNetworkProfile
output APIM_PRIVATE_DNS_ZONE string = resources.outputs.apimPrivateDnsZoneName
output MAPPING_STORAGE_ACCOUNT string = resources.outputs.mappingStorageAccountName
output MAPPING_CONTAINER string = resources.outputs.mappingContainerName
output MAPPING_BLOB_NAME string = resources.outputs.mappingBlobName
output MAPPING_BLOB_URL string = resources.outputs.mappingBlobUrl
output MAPPING_STORAGE_PRIVATE_IP string = resources.outputs.mappingStoragePrivateIp
output LOG_ANALYTICS_WORKSPACE string = resources.outputs.logAnalyticsWorkspaceName
output APPLICATION_INSIGHTS_NAME string = resources.outputs.applicationInsightsName
output MONITOR_PRIVATE_LINK_SCOPE string = resources.outputs.monitorPrivateLinkScopeName
output MONITOR_PRIVATE_ENDPOINT_IP string = resources.outputs.monitorPrivateEndpointIp
output OBSERVABILITY_WORKBOOK_ID string = resources.outputs.observabilityWorkbookId
output OBSERVABILITY_WORKBOOK_NAME string = resources.outputs.observabilityWorkbookName
output AI_GATEWAY_USAGE_WORKBOOK_ID string = resources.outputs.aiGatewayUsageWorkbookId
output AI_GATEWAY_USAGE_WORKBOOK_NAME string = resources.outputs.aiGatewayUsageWorkbookName
output AI_GATEWAY_DIMENSION_VALUES_WORKBOOK_ID string = resources.outputs.aiGatewayDimensionValuesWorkbookId
output AI_GATEWAY_DIMENSION_VALUES_WORKBOOK_NAME string = resources.outputs.aiGatewayDimensionValuesWorkbookName
output APIM_LIMIT_DEBUG_WORKBOOK_ID string = resources.outputs.apimLimitDebugWorkbookId
output APIM_LIMIT_DEBUG_WORKBOOK_NAME string = resources.outputs.apimLimitDebugWorkbookName
output APP_SERVICE_NAME string = resources.outputs.appServiceName
output APP_SERVICE_URL string = resources.outputs.appServiceDefaultHostName
output APP_SERVICE_LOCATION string = resources.outputs.appServiceLocation
output ENTRA_TENANT_ID string = identity.outputs.tenantId
output ENTRA_API_CLIENT_ID string = identity.outputs.apiClientId
output ENTRA_API_AUDIENCE string = identity.outputs.apiAudience
output ENTRA_API_SCOPE string = identity.outputs.apiScope
output ENTRA_DEV_SPA_CLIENT_ID string = identity.outputs.devSpaClientId
output ENTRA_PROD_SPA_CLIENT_ID string = identity.outputs.prodSpaClientId

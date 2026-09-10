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

@description('Deploy a small Linux test VM in Azure to validate reachability to on-prem.')
param deployTestVm bool = true

@description('Admin username for the test VM.')
param vmAdminUsername string = 'azureuser'

@secure()
@description('Admin password for the test VM (12-72 chars, 3 of: lower/upper/digit/symbol).')
param vmAdminPassword string = ''

@description('Source IP allowed to SSH to the test VM (your public IP). Empty disables SSH inbound.')
param allowedSshSourceIp string = ''

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
    deployTestVm: deployTestVm
    vmAdminUsername: vmAdminUsername
    vmAdminPassword: vmAdminPassword
    allowedSshSourceIp: allowedSshSourceIp
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output VPN_GATEWAY_PUBLIC_IP string = resources.outputs.vpnGatewayPublicIp
output VNET_ADDRESS_SPACE string = resources.outputs.vnetAddressSpace
output TEST_VM_PRIVATE_IP string = resources.outputs.testVmPrivateIp
output TEST_VM_PUBLIC_IP string = resources.outputs.testVmPublicIp

@description('Azure location for all resources.')
param location string

@description('Tags applied to all resources.')
param tags object

@description('Short unique token used to name resources.')
param resourceToken string

@description('On-prem private address space(s) advertised to Azure.')
param onPremAddressPrefixes array

@description('DDNS FQDN of the on-prem VPN device (takes precedence over onPremGatewayIp).')
param onPremGatewayFqdn string

@description('Public IP of the on-prem VPN device (used when FQDN is empty).')
param onPremGatewayIp string

@secure()
@description('IPsec pre-shared key.')
param sharedKey string

@description('Deploy a small Linux test VM to validate on-prem reachability.')
param deployTestVm bool

@description('Admin username for the test VM.')
param vmAdminUsername string

@secure()
@description('Admin password for the test VM.')
param vmAdminPassword string

@description('Source IP allowed to SSH to the test VM. Empty disables inbound SSH.')
param allowedSshSourceIp string

// ---- Addressing (clear of on-prem 192.168.50.0/24 and WAN 192.168.1.0/24) ----
var vnetAddressPrefix = '10.100.0.0/16'
var gatewaySubnetPrefix = '10.100.0.0/27'
var workloadSubnetPrefix = '10.100.1.0/24'

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-${resourceToken}'
  location: location
  tags: tags
  properties: {
    securityRules: empty(allowedSshSourceIp) ? [] : [
      {
        name: 'Allow-SSH-inbound'
        properties: {
          priority: 1000
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: allowedSshSourceIp
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '22'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'vnet-${resourceToken}'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [ vnetAddressPrefix ]
    }
    subnets: [
      {
        name: 'GatewaySubnet'
        properties: {
          addressPrefix: gatewaySubnetPrefix
        }
      }
      {
        name: 'workload'
        properties: {
          addressPrefix: workloadSubnetPrefix
          networkSecurityGroup: {
            id: nsg.id
          }
        }
      }
    ]
  }
}

resource vpnGatewayPip 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: 'pip-vng-${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource vpnGateway 'Microsoft.Network/virtualNetworkGateways@2024-05-01' = {
  name: 'vng-${resourceToken}'
  location: location
  tags: tags
  properties: {
    gatewayType: 'Vpn'
    vpnType: 'RouteBased'
    enableBgp: false
    activeActive: false
    sku: {
      name: 'VpnGw1'
      tier: 'VpnGw1'
    }
    ipConfigurations: [
      {
        name: 'default'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: '${vnet.id}/subnets/GatewaySubnet'
          }
          publicIPAddress: {
            id: vpnGatewayPip.id
          }
        }
      }
    ]
  }
}

resource localGateway 'Microsoft.Network/localNetworkGateways@2024-05-01' = {
  name: 'lng-${resourceToken}'
  location: location
  tags: tags
  properties: {
    localNetworkAddressSpace: {
      addressPrefixes: onPremAddressPrefixes
    }
    gatewayIpAddress: empty(onPremGatewayFqdn) ? onPremGatewayIp : null
    fqdn: empty(onPremGatewayFqdn) ? null : onPremGatewayFqdn
  }
}

resource connection 'Microsoft.Network/connections@2024-05-01' = {
  name: 'cn-${resourceToken}'
  location: location
  tags: tags
  properties: {
    connectionType: 'IPsec'
    connectionProtocol: 'IKEv2'
    virtualNetworkGateway1: {
      id: vpnGateway.id
    }
    localNetworkGateway2: {
      id: localGateway.id
    }
    sharedKey: sharedKey
    enableBgp: false
    usePolicyBasedTrafficSelectors: false
    dpdTimeoutSeconds: 45
    // Deterministic IKEv2 policy so the on-prem strongSwan proposal matches exactly.
    ipsecPolicies: [
      {
        saLifeTimeSeconds: 3600
        saDataSizeKilobytes: 102400000
        ipsecEncryption: 'AES256'
        ipsecIntegrity: 'SHA256'
        ikeEncryption: 'AES256'
        ikeIntegrity: 'SHA256'
        dhGroup: 'DHGroup14'
        pfsGroup: 'None'
      }
    ]
  }
}

// ---- Optional test VM (lean validation) ----
resource vmPip 'Microsoft.Network/publicIPAddresses@2024-05-01' = if (deployTestVm) {
  name: 'pip-vm-${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2024-05-01' = if (deployTestVm) {
  name: 'nic-${resourceToken}'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: '${vnet.id}/subnets/workload'
          }
          publicIPAddress: {
            id: vmPip.id
          }
        }
      }
    ]
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-07-01' = if (deployTestVm) {
  name: 'vm-${resourceToken}'
  location: location
  tags: tags
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_B1s'
    }
    osProfile: {
      computerName: 'testvm'
      adminUsername: vmAdminUsername
      adminPassword: vmAdminPassword
      linuxConfiguration: {
        disablePasswordAuthentication: false
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: '0001-com-ubuntu-server-jammy'
        sku: '22_04-lts-gen2'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
  }
}

output vpnGatewayPublicIp string = vpnGatewayPip.properties.ipAddress
output vnetAddressSpace string = vnetAddressPrefix
output testVmPrivateIp string = deployTestVm ? nic.properties.ipConfigurations[0].properties.privateIPAddress : ''
output testVmPublicIp string = deployTestVm ? vmPip.properties.ipAddress : ''

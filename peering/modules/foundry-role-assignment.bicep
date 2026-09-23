// Grants APIM's system-assigned managed identity least-privilege access to call the Foundry
// model deployment (Cognitive Services OpenAI User). Runs in the Foundry resource group.
@description('Foundry (AIServices/Cognitive Services) account name.')
param foundryAccountName string

@description('Principal ID of the APIM system-assigned managed identity.')
param principalId string

// Cognitive Services OpenAI User
var roleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}

resource ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: account
  name: guid(account.id, principalId, roleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

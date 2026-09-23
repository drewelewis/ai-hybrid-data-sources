targetScope = 'subscription'

extension 'br:mcr.microsoft.com/bicep/extensions/microsoftgraph/v1.0:1.0.0'

param uniqueName string
param displayName string
param apiClientId string
param chatInvokeScopeId string
param environmentName string
param authorizedSpaClientIds array

var apiAudience = 'api://${apiClientId}'

resource apiRegistration 'Microsoft.Graph/applications@v1.0' = {
  uniqueName: uniqueName
  displayName: displayName
  description: 'Shared protected API registration for local development and production App Service clients.'
  signInAudience: 'AzureADMyOrg'
  identifierUris: [
    apiAudience
  ]
  api: {
    requestedAccessTokenVersion: 2
    oauth2PermissionScopes: [
      {
        id: chatInvokeScopeId
        value: 'Chat.Invoke'
        type: 'Admin'
        isEnabled: true
        adminConsentDisplayName: 'Invoke the AI chat API'
        adminConsentDescription: 'Allows this application to send AI chat requests on behalf of the signed-in user.'
      }
    ]
    preAuthorizedApplications: map(authorizedSpaClientIds, clientId => {
      appId: clientId
      delegatedPermissionIds: [
        chatInvokeScopeId
      ]
    })
  }
  tags: [
    'azd-env-name:${environmentName}'
    'ai-hybrid-data-sources'
  ]
}

output apiAudience string = apiAudience
output apiScope string = '${apiAudience}/Chat.Invoke'

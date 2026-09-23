targetScope = 'subscription'

extension 'br:mcr.microsoft.com/bicep/extensions/microsoftgraph/v1.0:1.0.0'

@description('azd environment name used to isolate app registrations in the tenant.')
param environmentName string

@description('Stable environment and region suffix for nested deployment names.')
param deploymentSuffix string

@description('Production App Service origin registered for SPA authentication redirects.')
param productionOrigin string

var registrationPrefix = 'ai-hybrid-data-sources-${environmentName}'
// Preserve the existing scope ID when importing the current manually created API.
var chatInvokeScopeId = '60ecce06-4082-4341-91e6-62ede7549d91'

resource apiRegistration 'Microsoft.Graph/applications@v1.0' = {
  uniqueName: '${registrationPrefix}-api'
  displayName: '${registrationPrefix}-api'
  description: 'Shared protected API registration for local development and production App Service clients.'
  signInAudience: 'AzureADMyOrg'
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
  }
  tags: [
    'azd-env-name:${environmentName}'
    'ai-hybrid-data-sources'
  ]
}

resource apiServicePrincipal 'Microsoft.Graph/servicePrincipals@v1.0' = {
  appId: apiRegistration.appId
  displayName: apiRegistration.displayName
  tags: [
    'WindowsAzureActiveDirectoryIntegratedApp'
  ]
}

// appId is assigned by Entra, so configure the conventional api://<appId> identifier in a
// second deployment after the application exists.
module apiIdentifier 'identity-api-identifier.bicep' = {
  name: 'identity-api-identifier-${deploymentSuffix}'
  params: {
    uniqueName: apiRegistration.uniqueName
    displayName: apiRegistration.displayName
    apiClientId: apiRegistration.appId
    chatInvokeScopeId: chatInvokeScopeId
    environmentName: environmentName
    authorizedSpaClientIds: [
      devSpaRegistration.appId
      prodSpaRegistration.appId
    ]
  }
  dependsOn: [
    apiServicePrincipal
  ]
}

resource devSpaRegistration 'Microsoft.Graph/applications@v1.0' = {
  uniqueName: '${registrationPrefix}-spa-dev'
  displayName: '${registrationPrefix}-spa-dev'
  description: 'Public SPA client for local Vite development.'
  signInAudience: 'AzureADMyOrg'
  spa: {
    redirectUris: [
      'http://localhost:5173'
      'http://localhost:5173/blank.html'
    ]
  }
  requiredResourceAccess: [
    {
      resourceAppId: apiRegistration.appId
      resourceAccess: [
        {
          id: chatInvokeScopeId
          type: 'Scope'
        }
      ]
    }
  ]
  tags: [
    'azd-env-name:${environmentName}'
    'ai-hybrid-data-sources'
    'environment:development'
  ]
}

resource devSpaServicePrincipal 'Microsoft.Graph/servicePrincipals@v1.0' = {
  appId: devSpaRegistration.appId
  displayName: devSpaRegistration.displayName
  tags: [
    'WindowsAzureActiveDirectoryIntegratedApp'
  ]
}

resource prodSpaRegistration 'Microsoft.Graph/applications@v1.0' = {
  uniqueName: '${registrationPrefix}-spa-prod'
  displayName: '${registrationPrefix}-spa-prod'
  description: 'Public SPA client for the production App Service deployment.'
  signInAudience: 'AzureADMyOrg'
  spa: {
    redirectUris: [
      productionOrigin
    ]
  }
  requiredResourceAccess: [
    {
      resourceAppId: apiRegistration.appId
      resourceAccess: [
        {
          id: chatInvokeScopeId
          type: 'Scope'
        }
      ]
    }
  ]
  tags: [
    'azd-env-name:${environmentName}'
    'ai-hybrid-data-sources'
    'environment:production'
  ]
}

resource prodSpaServicePrincipal 'Microsoft.Graph/servicePrincipals@v1.0' = {
  appId: prodSpaRegistration.appId
  displayName: prodSpaRegistration.displayName
  tags: [
    'WindowsAzureActiveDirectoryIntegratedApp'
  ]
}

output tenantId string = tenant().tenantId
output apiClientId string = apiRegistration.appId
output apiAudience string = apiIdentifier.outputs.apiAudience
output apiScope string = apiIdentifier.outputs.apiScope
output devSpaClientId string = devSpaRegistration.appId
output prodSpaClientId string = prodSpaRegistration.appId

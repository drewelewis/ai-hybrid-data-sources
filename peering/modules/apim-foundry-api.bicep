// Publishes the private Foundry model deployment as a governed APIM API:
//   - a backend pointing at the Foundry /openai inference endpoint (reached over peering + private DNS)
//   - an Azure OpenAI-shaped API (chat completions) with managed-identity auth to the backend (no keys)
// Runs in the hub resource group where APIM lives.
@description('APIM instance name (hub).')
param apimName string

@description('Foundry inference endpoint, e.g. https://acct.cognitiveservices.azure.com/ (trailing slash ok).')
param foundryEndpoint string

@description('APIM backend id to create for the Foundry endpoint.')
param backendId string = 'foundry-openai'

@description('APIM API id.')
param apiId string = 'foundry-openai'

@description('APIM API path (callers hit https://<apim>.azure-api.net/<path>/deployments/...).')
param apiPath string = 'openai'

@description('Entra tenant id whose tokens the API accepts (from the SPA app registration).')
param entraTenantId string

@description('Accepted JWT audience — the API app registration App ID URI or client id, e.g. api://<guid>.')
param jwtAudience string

@description('Browser origins allowed to call the API (SPA dev/prod origins).')
param allowedCorsOrigins array = [ 'http://localhost:5173' ]

var corsOriginsXml = join(map(allowedCorsOrigins, origin => '<origin>${origin}</origin>'), '')

// Enable Entra token auth only when both tenant and audience are provided; otherwise
// keep the subscription-key model (safe default — never an open API).
var jwtEnabled = !empty(entraTenantId) && !empty(jwtAudience)
// Accept both v2 token audience shapes: the App ID URI (api://<guid>) and the bare <guid>.
var jwtAudienceBare = replace(jwtAudience, 'api://', '')
var audiencesXml = '<audience>${jwtAudience}</audience><audience>${jwtAudienceBare}</audience>'
var validateJwtXml = jwtEnabled ? '<validate-jwt header-name="Authorization" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized" require-scheme="Bearer"><openid-config url="https://login.microsoftonline.com/${entraTenantId}/v2.0/.well-known/openid-configuration" /><audiences>${audiencesXml}</audiences><issuers><issuer>https://login.microsoftonline.com/${entraTenantId}/v2.0</issuer></issuers></validate-jwt>' : ''

resource apim 'Microsoft.ApiManagement/service@2024-05-01' existing = {
  name: apimName
}

resource backend 'Microsoft.ApiManagement/service/backends@2024-05-01' = {
  parent: apim
  name: backendId
  properties: {
    protocol: 'http'
    url: '${foundryEndpoint}openai'
  }
}

resource api 'Microsoft.ApiManagement/service/apis@2024-05-01' = {
  parent: apim
  name: apiId
  properties: {
    displayName: 'Foundry OpenAI'
    path: apiPath
    protocols: [ 'https' ]
    subscriptionRequired: !jwtEnabled
  }
}

resource chatCompletions 'Microsoft.ApiManagement/service/apis/operations@2024-05-01' = {
  parent: api
  name: 'chat-completions'
  properties: {
    displayName: 'Chat Completions'
    method: 'POST'
    urlTemplate: '/deployments/{deployment-id}/chat/completions'
    templateParameters: [
      {
        name: 'deployment-id'
        type: 'string'
        required: true
      }
    ]
  }
}

// API-level policy: CORS + Entra JWT validation on the client side, then route to the
// Foundry backend with APIM's managed identity (keyless end to end).
resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: api
  name: 'policy'
  dependsOn: [ backend ]
  properties: {
    format: 'rawxml'
    value: '<policies><inbound><base /><cors allow-credentials="false"><allowed-origins>${corsOriginsXml}</allowed-origins><allowed-methods><method>OPTIONS</method><method>POST</method></allowed-methods><allowed-headers><header>Authorization</header><header>Content-Type</header></allowed-headers></cors>${validateJwtXml}<set-backend-service backend-id="${backendId}" /><authentication-managed-identity resource="https://cognitiveservices.azure.com" /></inbound><backend><base /></backend><outbound><base /></outbound><on-error><base /></on-error></policies>'
  }
}

@description('APIM system-assigned managed identity principalId (for the Foundry role assignment).')
output apimPrincipalId string = apim.identity.principalId

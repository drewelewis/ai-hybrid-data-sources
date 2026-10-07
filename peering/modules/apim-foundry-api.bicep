// Publishes the private Foundry model deployment as a governed APIM API:
//   - a backend pointing at the Foundry /openai inference endpoint (reached over peering + private DNS)
//   - an Azure OpenAI-shaped API (chat completions) with managed-identity auth to the backend (no keys)
// Runs in the hub resource group where APIM lives.
@description('APIM instance name (hub).')
param apimName string

@description('Foundry inference endpoint, e.g. https://acct.cognitiveservices.azure.com/ (trailing slash ok).')
param foundryEndpoint string

@description('APIM backend id to create for the Foundry endpoint.')
param backendId string = 'v2-prod-backendpool-ai-hybrid-data-sources-exp'

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

@description('Private blob URL containing the APIM product-to-model mapping.')
param mappingBlobUrl string

@description('Enables temporary, subscription-scoped APIM branch traces. Keep disabled outside an approved test window.')
param debugTracingEnabled bool = false

@description('APIM subscription ID allowed to emit temporary branch traces.')
param debugTracingSubscriptionId string = ''

@description('UTC expiry for temporary branch tracing. Use an ISO 8601 value.')
param debugTracingExpiryUtc string = '1970-01-01T00:00:00Z'

@description('APIM product ID represented by the mapping root key.')
param productId string = 'openai-ai-hybrid-data-sources-lob-oai-small-v2'

@description('Display name for the APIM product.')
param productDisplayName string = 'AI Hybrid Data Sources LOB OpenAI Small v2'

var corsOriginsXml = join(map(allowedCorsOrigins, origin => '<origin>${origin}</origin>'), '')

// Enable Entra token auth only when both tenant and audience are provided; otherwise
// keep the subscription-key model (safe default — never an open API).
var jwtEnabled = !empty(entraTenantId) && !empty(jwtAudience)
// Accept both v2 token audience shapes: the App ID URI (api://<guid>) and the bare <guid>.
var jwtAudienceBare = replace(jwtAudience, 'api://', '')
var audiencesXml = '<audience>${jwtAudience}</audience><audience>${jwtAudienceBare}</audience>'
// Browser delegated tokens use the v2 issuer. Managed identities can use the tenant's
// v1 issuer for the same API audience, so accept both issuer forms for this tenant.
var entraLoginEndpoint = environment().authentication.loginEndpoint
var issuersXml = '<issuer>${entraLoginEndpoint}${entraTenantId}/v2.0</issuer><issuer>https://sts.windows.net/${entraTenantId}/</issuer>'
var validateJwtXml = jwtEnabled ? '<validate-jwt header-name="Authorization" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized" require-scheme="Bearer"><openid-config url="${entraLoginEndpoint}${entraTenantId}/v2.0/.well-known/openid-configuration" /><audiences>${audiencesXml}</audiences><issuers>${issuersXml}</issuers></validate-jwt>' : ''
var policyTemplate = loadTextContent('apim-foundry-policy.xml')
var policyWithCors = replace(policyTemplate, '__CORS_ORIGINS__', corsOriginsXml)
var policyWithJwt = replace(policyWithCors, '__VALIDATE_JWT__', validateJwtXml)
var policyWithMapping = replace(policyWithJwt, '__MAPPING_BLOB_URL__', mappingBlobUrl)
var policyWithDebugEnabled = replace(policyWithMapping, '__DEBUG_TRACING_ENABLED__', string(debugTracingEnabled))
var policyWithDebugSubscription = replace(policyWithDebugEnabled, '__DEBUG_TRACING_SUBSCRIPTION_ID__', debugTracingSubscriptionId)
var policyWithDebugExpiry = replace(policyWithDebugSubscription, '__DEBUG_TRACING_EXPIRY_UTC__', debugTracingExpiryUtc)
var policyXml = replace(policyWithDebugExpiry, '__DEBUG_TRACING_API_ID__', apiId)

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
    subscriptionRequired: true
  }
}

resource product 'Microsoft.ApiManagement/service/products@2024-05-01' = {
  parent: apim
  name: productId
  properties: {
    displayName: productDisplayName
    approvalRequired: false
    state: 'published'
    subscriptionRequired: true
  }
}

resource productApi 'Microsoft.ApiManagement/service/products/apis@2024-05-01' = {
  parent: product
  name: apiId
  dependsOn: [ api ]
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

// API-level policy: require both the product subscription and Entra JWT, resolve the
// requested model from the private mapping, then use managed identity for Foundry.
resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: api
  name: 'policy'
  dependsOn: [ backend ]
  properties: {
    format: 'rawxml'
    value: policyXml
  }
}

@description('APIM system-assigned managed identity principalId (for the Foundry role assignment).')
output apimPrincipalId string = apim.identity.principalId

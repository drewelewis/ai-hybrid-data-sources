@description('Azure location for the workbook resource.')
param location string

@description('Tags applied to the workbook resource.')
param tags object = {}

@description('Short unique token used to create a stable workbook resource name.')
param resourceToken string

@description('Resource ID of the Log Analytics workspace queried by the workbook.')
param workspaceResourceId string

@description('Resource ID of the workspace-based Application Insights component.')
param appInsightsResourceId string

@description('Resource ID of the API Management service.')
param apimResourceId string

@description('Friendly workbook name shown in the Azure portal.')
param workbookDisplayName string = 'AI Gateway Usage Dimensions'

var workbookName = guid(resourceGroup().id, 'ai-gateway-usage-${resourceToken}')

var workbookDefinition = {
  version: 'Notebook/1.0'
  items: [
    {
      type: 1
      name: 'overview'
      content: {
        json: '''# AI Gateway usage dimensions

Focused view of the four bounded dimensions emitted by the APIM `llm-emit-token-metric` policy:

- **Product ID**
- **Subscription ID**
- **Backend ID**
- **Deployment**

The primary panels correlate `AppRequests` token headers with unsampled `ApiManagementGatewayLogs` by gateway request ID. This makes current values visible even when native `AI-Gateway` custom metric records are delayed or absent. With the default 100% Application Insights sampling, token totals are exact for captured responses; lowering sampling makes token totals sampled estimates.'''
      }
    }
    {
      type: 9
      name: 'parameters'
      content: {
        version: 'KqlParameterItem/1.0'
        parameters: [
          {
            id: 'time-range'
            version: 'KqlParameterItem/1.0'
            name: 'TimeRange'
            label: 'Time range'
            type: 4
            isRequired: true
            value: {
              durationMs: 604800000
            }
            typeSettings: {
              selectableValues: [
                {
                  durationMs: 3600000
                }
                {
                  durationMs: 14400000
                }
                {
                  durationMs: 43200000
                }
                {
                  durationMs: 86400000
                }
                {
                  durationMs: 172800000
                }
                {
                  durationMs: 604800000
                }
                {
                  durationMs: 2592000000
                }
              ]
              allowCustom: true
            }
          }
        ]
        style: 'pills'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
      }
    }
    {
      type: 1
      name: 'summary-heading'
      content: {
        json: '## Usage summary'
      }
    }
    {
      type: 3
      name: 'usage-kpis'
      content: {
        version: 'KqlItem/1.0'
        title: 'Requests, tokens, and active dimensions'
        query: '''
let requestUsage =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        TokensConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"])
    | project GatewayCorrelationId, TokensConsumed;
let gateway =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
    | project
        GatewayCorrelationId = CorrelationId,
        ProductId,
        SubscriptionId = ApimSubscriptionId,
        BackendId,
        Deployment,
        IsRequestSuccess;
requestUsage
| join kind=inner gateway on GatewayCorrelationId
| summarize
    Requests = count(),
    Successful = countif(IsRequestSuccess == true),
    Failures = countif(IsRequestSuccess == false),
    TokensConsumed = sum(TokensConsumed),
    Products = dcountif(ProductId, isnotempty(ProductId)),
    Subscriptions = dcountif(SubscriptionId, isnotempty(SubscriptionId)),
    Backends = dcountif(BackendId, isnotempty(BackendId)),
    Deployments = dcountif(Deployment, isnotempty(Deployment))
'''
        size: 1
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'tiles'
      }
    }
    {
      type: 3
      name: 'dimension-inventory'
      content: {
        version: 'KqlItem/1.0'
        title: 'Dimension value inventory'
        query: '''
let requestUsage =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        TokensConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"])
    | project RequestTime = TimeGenerated, GatewayCorrelationId, TokensConsumed;
let gateway =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
    | project
        GatewayCorrelationId = CorrelationId,
        ProductId,
        SubscriptionId = ApimSubscriptionId,
        BackendId,
        Deployment,
        IsRequestSuccess,
        TotalTime;
requestUsage
| join kind=inner gateway on GatewayCorrelationId
| summarize
    Requests = count(),
    Successful = countif(IsRequestSuccess == true),
    Failures = countif(IsRequestSuccess == false),
    TokensConsumed = sum(TokensConsumed),
    P95Ms = percentile(todouble(TotalTime), 95),
    LastSeen = max(RequestTime)
  by ProductId, SubscriptionId, BackendId, Deployment
| order by TokensConsumed desc, Requests desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'token-trend'
      content: {
        version: 'KqlItem/1.0'
        title: 'Consumed tokens over time by deployment'
        query: '''
let requestUsage =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        TokensConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"])
    | project RequestTime = TimeGenerated, GatewayCorrelationId, TokensConsumed;
let gateway =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
    | project GatewayCorrelationId = CorrelationId, Deployment;
requestUsage
| join kind=inner gateway on GatewayCorrelationId
| where isnotnull(TokensConsumed)
| summarize TokensConsumed = sum(TokensConsumed) by bin(RequestTime, 15m), Deployment
| order by RequestTime asc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'timechart'
      }
    }
    {
      type: 1
      name: 'governance-heading'
      content: {
        json: '## Product and subscription governance'
      }
    }
    {
      type: 3
      name: 'product-subscription-usage'
      content: {
        version: 'KqlItem/1.0'
        title: 'Usage by product and subscription'
        query: '''
let requestUsage =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        TokensConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"]),
        ProductRemaining = tolong(Properties["Response-x-llmmgmt-product-ratelimit-remaining"])
    | project RequestTime = TimeGenerated, GatewayCorrelationId, TokensConsumed, ProductRemaining;
let gateway =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | project
        GatewayCorrelationId = CorrelationId,
        ProductId,
        SubscriptionId = ApimSubscriptionId,
        IsRequestSuccess,
        ResponseCode;
requestUsage
| join kind=inner gateway on GatewayCorrelationId
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false),
    TokensConsumed = sum(TokensConsumed),
    MinimumProductRemaining = min(ProductRemaining),
    LastSeen = max(RequestTime)
  by ProductId, SubscriptionId
| order by TokensConsumed desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'product-token-share'
      content: {
        version: 'KqlItem/1.0'
        title: 'Token share by product'
        query: '''
let requestUsage =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        TokensConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"])
    | project GatewayCorrelationId, TokensConsumed;
let gateway =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | project GatewayCorrelationId = CorrelationId, ProductId;
requestUsage
| join kind=inner gateway on GatewayCorrelationId
| where isnotnull(TokensConsumed)
| summarize TokensConsumed = sum(TokensConsumed) by ProductId
| order by TokensConsumed desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'piechart'
      }
    }
    {
      type: 1
      name: 'routing-heading'
      content: {
        json: '## Backend and deployment routing'
      }
    }
    {
      type: 3
      name: 'backend-deployment-usage'
      content: {
        version: 'KqlItem/1.0'
        title: 'Usage by backend and deployment'
        query: '''
let requestUsage =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        TokensConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"]),
        ModelLimit = tolong(Properties["Response-x-llmmgmt-model-ratelimit-limit"]),
        ModelRemaining = tolong(Properties["Response-x-llmmgmt-model-ratelimit-remaining"]),
        SkuLimit = tolong(Properties["Response-x-llmmgmt-sku-ratelimit-limit"]),
        SkuRemaining = coalesce(
            tolong(Properties["Response-x-llmmgmt-sku-ratelimit-remaining"]),
            tolong(Properties["Response-x-llmmgmt-product-ratelimit-remaining"])),
        RpmLimit = tolong(Properties["Response-x-llmmgmt-ratelimit-limit-calls"]),
        RpmRemaining = tolong(Properties["Response-x-llmmgmt-ratelimit-remaining-calls"])
    | project RequestTime = TimeGenerated, GatewayCorrelationId, TokensConsumed, ModelLimit, ModelRemaining, SkuLimit, SkuRemaining, RpmLimit, RpmRemaining;
let gateway =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
    | project
        GatewayCorrelationId = CorrelationId,
        BackendId,
        Deployment,
        IsRequestSuccess,
        BackendResponseCode,
        BackendTime;
requestUsage
| join kind=inner gateway on GatewayCorrelationId
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false),
    BackendFailures = countif(toint(BackendResponseCode) >= 400),
    ModelLimit = max(ModelLimit),
    TokensConsumed = sum(TokensConsumed),
    MinimumModelRemaining = min(ModelRemaining),
    SkuLimit = max(SkuLimit),
    MinimumSkuRemaining = min(SkuRemaining),
    RpmLimit = max(RpmLimit),
    MinimumRpmRemaining = min(RpmRemaining),
    P95BackendMs = percentile(todouble(BackendTime), 95),
    LastSeen = max(RequestTime)
  by BackendId, Deployment
| order by TokensConsumed desc, Requests desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'deployment-token-share'
      content: {
        version: 'KqlItem/1.0'
        title: 'Token consumption by deployment'
        query: '''
let requestUsage =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        TokensConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"])
    | project GatewayCorrelationId, TokensConsumed;
let gateway =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
    | project GatewayCorrelationId = CorrelationId, Deployment;
requestUsage
| join kind=inner gateway on GatewayCorrelationId
| where isnotnull(TokensConsumed)
| summarize TokensConsumed = sum(TokensConsumed) by Deployment
| order by TokensConsumed desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'barchart'
      }
    }
    {
      type: 1
      name: 'request-heading'
      content: {
        json: '## Request-level detail'
      }
    }
    {
      type: 3
      name: 'recent-request-usage'
      content: {
        version: 'KqlItem/1.0'
        title: 'Recent requests with all four dimensions'
        query: '''
let requestUsage =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        TokensConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"]),
        ModelLimit = tolong(Properties["Response-x-llmmgmt-model-ratelimit-limit"]),
        ModelRemaining = tolong(Properties["Response-x-llmmgmt-model-ratelimit-remaining"]),
        SkuLimit = tolong(Properties["Response-x-llmmgmt-sku-ratelimit-limit"]),
        SkuConsumed = coalesce(
            tolong(Properties["Response-x-llmmgmt-sku-ratelimit-consumed"]),
            tolong(Properties["Response-x-llmmgmt-product-ratelimit-consumed"])),
        SkuRemaining = coalesce(
            tolong(Properties["Response-x-llmmgmt-sku-ratelimit-remaining"]),
            tolong(Properties["Response-x-llmmgmt-product-ratelimit-remaining"])),
        RpmLimit = tolong(Properties["Response-x-llmmgmt-ratelimit-limit-calls"]),
        RpmRemaining = tolong(Properties["Response-x-llmmgmt-ratelimit-remaining-calls"]),
        RetryAfterSeconds = tolong(Properties["Response-x-llmmgmt-retry-after"])
    | project
        RequestTime = TimeGenerated,
        GatewayCorrelationId,
        TokensConsumed,
        ModelLimit,
        ModelRemaining,
        SkuLimit,
        SkuConsumed,
        SkuRemaining,
        RpmLimit,
        RpmRemaining,
        RetryAfterSeconds;
let gateway =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
    | project
        GatewayCorrelationId = CorrelationId,
        ProductId,
        SubscriptionId = ApimSubscriptionId,
        BackendId,
        Deployment,
        ResponseCode,
        BackendResponseCode,
        TotalTime;
requestUsage
| join kind=inner gateway on GatewayCorrelationId
| project
    RequestTime,
    GatewayCorrelationId,
    ProductId,
    SubscriptionId,
    BackendId,
    Deployment,
    ModelLimit,
    TokensConsumed,
    ModelRemaining,
    SkuLimit,
    SkuConsumed,
    SkuRemaining,
    RpmLimit,
    RpmRemaining,
    RetryAfterSeconds,
    ResponseCode,
    BackendResponseCode,
    TotalTime
| top 200 by RequestTime desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 1
      name: 'native-heading'
      content: {
        json: '''## Native AI-Gateway custom metrics

The policy also targets Application Insights custom metrics. When records are available, this panel shows the native metric names and dimensions. You can inspect the same stream in **Application Insights > Metrics**, then select the **AI-Gateway** custom namespace and split by Product ID, Subscription ID, Backend ID, or Deployment.'''
      }
    }
    {
      type: 3
      name: 'native-token-metrics'
      content: {
        version: 'KqlItem/1.0'
        title: 'Native token metric records'
        query: '''
AppMetrics
| where TimeGenerated {TimeRange}
| where Name startswith "AI-Gateway"
    or Name has "Total Tokens"
    or Name has "Prompt Tokens"
    or Name has "Completion Tokens"
    or Name has "Cached Tokens"
    or Name has "Reasoning Tokens"
| extend
    ProductId = tostring(Properties["Product ID"]),
    SubscriptionId = tostring(Properties["Subscription ID"]),
    BackendId = tostring(Properties["Backend ID"]),
    Deployment = tostring(Properties["Deployment"])
| summarize
    Tokens = sum(Sum),
    Samples = sum(ItemCount),
    LastSeen = max(TimeGenerated)
  by Name, ProductId, SubscriptionId, BackendId, Deployment
| order by Tokens desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 1
      name: 'guidance'
      content: {
        json: '''## How to interpret the dimensions

- **Product ID** identifies the APIM product that packages access and policy.
- **Subscription ID** identifies the APIM subscription used by the caller, not an Azure subscription GUID.
- **Backend ID** identifies the APIM backend or backend pool selected by policy. It can be empty when a request fails before backend selection.
- **Deployment** is parsed from the OpenAI-compatible `/deployments/{name}` route.

Token totals come from the model-level `tokens-consumed` response header captured by Application Insights. Prompts and completions are not collected.'''
      }
    }
  ]
  isLocked: false
  fallbackResourceIds: [
    workspaceResourceId
    appInsightsResourceId
    apimResourceId
  ]
}

resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: workbookName
  location: location
  kind: 'shared'
  tags: union(tags, {
    'hidden-title': workbookDisplayName
  })
  properties: {
    displayName: workbookDisplayName
    description: 'Focused Product ID, Subscription ID, Backend ID, Deployment, and token usage analysis for the APIM AI gateway.'
    serializedData: string(workbookDefinition)
    version: 'Notebook/1.0'
    sourceId: workspaceResourceId
    category: 'workbook'
  }
}

output workbookId string = workbook.id
output workbookName string = workbook.name
output workbookDisplayName string = workbook.properties.displayName

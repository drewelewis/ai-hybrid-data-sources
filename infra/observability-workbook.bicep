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
param workbookDisplayName string = 'APIM Observability'

var workbookName = guid(resourceGroup().id, 'apim-observability-${resourceToken}')

var workbookDefinition = {
  version: 'Notebook/1.0'
  items: [
    {
      type: 1
      name: 'overview'
      content: {
        json: '''# APIM Observability

Operational view of gateway traffic, failures, latency, dependencies, governed consumers, LLM usage, and platform health.

- **Exact traffic and failures:** unsampled `ApiManagementGatewayLogs`
- **Transactions and dependencies:** `AppRequests` and `AppDependencies`
- **Platform health:** `AzureMetrics`
- **Token telemetry:** `AppMetrics` from the `AI-Gateway` policy

Change the time range below to update every panel. Empty token panels normally mean no supported usage payload was emitted in the selected period.'''
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
              durationMs: 86400000
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
      name: 'health-heading'
      content: {
        json: '## Health overview'
      }
    }
    {
      type: 3
      name: 'health-kpis'
      content: {
        version: 'KqlItem/1.0'
        title: 'Gateway health'
        query: '''
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| summarize
    Requests = count(),
    Successful = countif(IsRequestSuccess == true),
    Failures = countif(IsRequestSuccess == false),
    SuccessRatePct = round(100.0 * countif(IsRequestSuccess == true) / count(), 2),
    P50Ms = percentile(todouble(TotalTime), 50),
    P95Ms = percentile(todouble(TotalTime), 95),
    P99Ms = percentile(todouble(TotalTime), 99)
'''
        size: 1
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'tiles'
      }
    }
    {
      type: 3
      name: 'traffic-trend'
      content: {
        version: 'KqlItem/1.0'
        title: 'Requests and failures over time'
        query: '''
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false)
  by bin(TimeGenerated, 5m)
| order by TimeGenerated asc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'timechart'
      }
    }
    {
      type: 3
      name: 'status-distribution'
      content: {
        version: 'KqlItem/1.0'
        title: 'Response code distribution'
        query: '''
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| summarize Requests = count() by ResponseCode
| order by Requests desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'piechart'
      }
    }
    {
      type: 3
      name: 'telemetry-freshness'
      content: {
        version: 'KqlItem/1.0'
        title: 'Telemetry freshness'
        query: '''
union
    (ApiManagementGatewayLogs | summarize LastRecord = max(TimeGenerated) | extend Stream = "Gateway logs"),
    (AppRequests | summarize LastRecord = max(TimeGenerated) | extend Stream = "Application Insights requests"),
    (AppDependencies | summarize LastRecord = max(TimeGenerated) | extend Stream = "Application Insights dependencies"),
    (AzureMetrics | where ResourceProvider =~ "MICROSOFT.APIMANAGEMENT" | summarize LastRecord = max(TimeGenerated) | extend Stream = "APIM platform metrics")
| extend AgeMinutes = datetime_diff("minute", now(), LastRecord)
| project Stream, LastRecord, AgeMinutes
| order by AgeMinutes desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 1
      name: 'failures-heading'
      content: {
        json: '## Failures and diagnosis'
      }
    }
    {
      type: 3
      name: 'failure-causes'
      content: {
        version: 'KqlItem/1.0'
        title: 'Top gateway failure causes'
        query: '''
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| where IsRequestSuccess == false or toint(ResponseCode) >= 400
| summarize
    Failures = count(),
    SampleMessage = take_any(LastErrorMessage),
    Latest = max(TimeGenerated)
  by ResponseCode, LastErrorSource, LastErrorSection, LastErrorReason
| top 20 by Failures desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'recent-failures'
      content: {
        version: 'KqlItem/1.0'
        title: 'Recent failed requests'
        query: '''
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| where IsRequestSuccess == false or toint(ResponseCode) >= 400
| project
    TimeGenerated,
    CorrelationId,
    ResponseCode,
    BackendResponseCode,
    ApiId,
    OperationId,
    ProductId,
    ApimSubscriptionId,
    BackendId,
    TotalTime,
    LastErrorSource,
    LastErrorReason,
    LastErrorMessage
| top 100 by TimeGenerated desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 1
      name: 'performance-heading'
      content: {
        json: '## Performance and dependencies'
      }
    }
    {
      type: 3
      name: 'latency-trend'
      content: {
        version: 'KqlItem/1.0'
        title: 'Gateway and backend latency'
        query: '''
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| summarize
    P50TotalMs = percentile(todouble(TotalTime), 50),
    P95TotalMs = percentile(todouble(TotalTime), 95),
    P95BackendMs = percentile(todouble(BackendTime), 95)
  by bin(TimeGenerated, 5m)
| order by TimeGenerated asc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'timechart'
      }
    }
    {
      type: 3
      name: 'operation-performance'
      content: {
        version: 'KqlItem/1.0'
        title: 'Performance by operation and backend'
        query: '''
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false),
    AvgTotalMs = round(avg(todouble(TotalTime)), 1),
    P50TotalMs = percentile(todouble(TotalTime), 50),
    P95TotalMs = percentile(todouble(TotalTime), 95),
    P99TotalMs = percentile(todouble(TotalTime), 99),
    P95BackendMs = percentile(todouble(BackendTime), 95)
  by ApiId, OperationId, BackendId
| order by P95TotalMs desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'dependency-health'
      content: {
        version: 'KqlItem/1.0'
        title: 'Dependency health'
        query: '''
AppDependencies
| where TimeGenerated {TimeRange}
| summarize
    Calls = sum(ItemCount),
    Failures = sumif(ItemCount, Success == false),
    FailureRatePct = round(100.0 * sumif(ItemCount, Success == false) / sum(ItemCount), 2),
    AvgMs = round(avg(DurationMs), 1),
    P95Ms = percentile(DurationMs, 95)
  by Target, Name, DependencyType
| order by Failures desc, P95Ms desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 1
      name: 'usage-heading'
      content: {
        json: '## Usage, governance, and LLM consumption'
      }
    }
    {
      type: 3
      name: 'consumer-usage'
      content: {
        version: 'KqlItem/1.0'
        title: 'Traffic by product and subscription'
        query: '''
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false),
    RequestBytes = sum(tolong(RequestSize)),
    ResponseBytes = sum(tolong(ResponseSize)),
    P95Ms = percentile(todouble(TotalTime), 95)
  by ProductId, ApimSubscriptionId
| order by Requests desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'deployment-usage'
      content: {
        version: 'KqlItem/1.0'
        title: 'Traffic by model deployment'
        query: '''
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false),
    P95Ms = percentile(todouble(TotalTime), 95)
  by Deployment, BackendId
| order by Requests desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'rate-limit-pressure'
      content: {
        version: 'KqlItem/1.0'
        title: 'Minimum remaining model and product limits'
        query: '''
AppRequests
| where TimeGenerated {TimeRange}
| extend
    Product = tostring(Properties["Product Name"]),
    Subscription = tostring(Properties["Subscription Name"]),
    ModelRemaining = tolong(Properties["Response-x-llmmgmt-model-ratelimit-remaining"]),
    ProductRemaining = tolong(Properties["Response-x-llmmgmt-product-ratelimit-remaining"])
| where isnotnull(ModelRemaining) or isnotnull(ProductRemaining)
| summarize
    MinimumModelRemaining = min(ModelRemaining),
    MinimumProductRemaining = min(ProductRemaining),
    Latest = max(TimeGenerated)
  by Product, Subscription
| order by MinimumModelRemaining asc, MinimumProductRemaining asc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'token-metrics'
      content: {
        version: 'KqlItem/1.0'
        title: 'Correlated token consumption by usage dimensions'
        query: '''
let requestUsage =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        ModelLimit = tolong(Properties["Response-x-llmmgmt-model-ratelimit-limit"]),
        TokensConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"]),
        SkuLimit = tolong(Properties["Response-x-llmmgmt-sku-ratelimit-limit"]),
        SkuTokensConsumed = coalesce(
            tolong(Properties["Response-x-llmmgmt-sku-ratelimit-consumed"]),
            tolong(Properties["Response-x-llmmgmt-product-ratelimit-consumed"])),
        RpmLimit = tolong(Properties["Response-x-llmmgmt-ratelimit-limit-calls"])
    | project GatewayCorrelationId, ModelLimit, TokensConsumed, SkuLimit, SkuTokensConsumed, RpmLimit;
let gateway =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
    | project
        GatewayCorrelationId = CorrelationId,
        ProductId,
        SubscriptionId = ApimSubscriptionId,
        BackendId,
        Deployment;
requestUsage
| join kind=inner gateway on GatewayCorrelationId
| where isnotnull(TokensConsumed)
| summarize
    ModelLimit = max(ModelLimit),
    TokensConsumed = sum(TokensConsumed),
    SkuLimit = max(SkuLimit),
    SkuTokensConsumed = sum(SkuTokensConsumed),
    RpmLimit = max(RpmLimit),
    Requests = count()
  by ProductId, SubscriptionId, BackendId, Deployment
| order by TokensConsumed desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 1
      name: 'platform-heading'
      content: {
        json: '## APIM platform health'
      }
    }
    {
      type: 3
      name: 'platform-metrics'
      content: {
        version: 'KqlItem/1.0'
        title: 'APIM platform metrics'
        query: '''
AzureMetrics
| where TimeGenerated {TimeRange}
| where ResourceProvider =~ "MICROSOFT.APIMANAGEMENT"
| summarize
    Average = avg(Average),
    Maximum = max(Maximum),
    Total = sum(Total)
  by MetricName, UnitName, bin(TimeGenerated, 5m)
| order by TimeGenerated asc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'timechart'
      }
    }
    {
      type: 3
      name: 'platform-metric-inventory'
      content: {
        version: 'KqlItem/1.0'
        title: 'Available APIM metric series'
        query: '''
AzureMetrics
| where TimeGenerated {TimeRange}
| where ResourceProvider =~ "MICROSOFT.APIMANAGEMENT"
| summarize Samples = count(), Latest = max(TimeGenerated) by MetricName, UnitName
| order by MetricName asc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 1
      name: 'investigation-guidance'
      content: {
        json: '''## Investigation guidance

1. Use **Gateway health** and **Requests and failures over time** to identify when the change began.
2. Use **Top gateway failure causes** to separate authentication, policy, routing, throttling, and backend failures.
3. Copy `CorrelationId` from **Recent failed requests**. In Application Insights, match it to the request property `Request Id`, then use `OperationId` to inspect dependencies.
4. Compare total and backend latency to decide whether to investigate APIM/policies or the model backend.
5. Use product, subscription, deployment, and rate-limit panels for governed-consumer impact.

See the repository's `observability_user_guide.md` for detailed workflows and additional KQL.'''
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
    description: 'APIM traffic, failures, latency, dependencies, governed usage, LLM telemetry, and platform health.'
    serializedData: string(workbookDefinition)
    version: 'Notebook/1.0'
    sourceId: workspaceResourceId
    category: 'workbook'
  }
}

output workbookId string = workbook.id
output workbookName string = workbook.name
output workbookDisplayName string = workbook.properties.displayName

@description('Azure location for the workbook resource.')
param location string

@description('Tags applied to the workbook resource.')
param tags object = {}

@description('Short unique token used to preserve the stable workbook resource name.')
param resourceToken string

@description('Resource ID of the Log Analytics workspace queried by the workbook.')
param workspaceResourceId string

@description('Resource ID of the API Management service.')
param apimResourceId string

@description('Friendly workbook name shown in the Azure portal.')
param workbookDisplayName string = 'AI Gateway Dimension Values'

// Keep the original seed so simplifying the workbook updates the deployed resource in place.
var workbookName = guid(resourceGroup().id, 'ai-gateway-request-detail-${resourceToken}')

var workbookDefinition = {
  version: 'Notebook/1.0'
  items: [
    {
      type: 1
      name: 'heading'
      content: {
        json: '# AI Gateway requests, dimensions, and rate-limit values'
      }
    }
    {
      type: 3
      name: 'dimension-values'
      content: {
        version: 'KqlItem/1.0'
        query: '''
let requestTelemetry =
    AppRequests
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        ['RPM Limit'] = tolong(Properties["Response-x-llmmgmt-ratelimit-limit-calls"]),
        ['RPM Remaining'] = tolong(Properties["Response-x-llmmgmt-ratelimit-remaining-calls"]),
        ['Retry After Seconds'] = tolong(Properties["Response-x-llmmgmt-retry-after"]),
        ['Model TPM Limit'] = coalesce(
            tolong(Properties["Response-x-llmmgmt-model-ratelimit-limit"]),
            tolong(Properties["Response-x-llmmgmt-ratelimit-limit"])),
        ['Model Tokens Consumed'] = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"]),
        ['Model Tokens Remaining'] = tolong(Properties["Response-x-llmmgmt-model-ratelimit-remaining"]),
        ['SKU TPM Limit'] = tolong(Properties["Response-x-llmmgmt-sku-ratelimit-limit"]),
        ['SKU Tokens Consumed'] = coalesce(
            tolong(Properties["Response-x-llmmgmt-sku-ratelimit-consumed"]),
            tolong(Properties["Response-x-llmmgmt-product-ratelimit-consumed"])),
        ['SKU Tokens Remaining'] = coalesce(
            tolong(Properties["Response-x-llmmgmt-sku-ratelimit-remaining"]),
            tolong(Properties["Response-x-llmmgmt-product-ratelimit-remaining"]))
    | summarize arg_max(TimeGenerated, *) by GatewayCorrelationId
    | project
        GatewayCorrelationId,
        ['RPM Limit'],
        ['RPM Remaining'],
        ['Retry After Seconds'],
        ['Model TPM Limit'],
        ['Model Tokens Consumed'],
        ['Model Tokens Remaining'],
        ['SKU TPM Limit'],
        ['SKU Tokens Consumed'],
        ['SKU Tokens Remaining'];
ApiManagementGatewayLogs
| extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
| project
    GatewayCorrelationId = CorrelationId,
    ['Request Time'] = TimeGenerated,
    ['Product ID'] = ProductId,
    ['Subscription ID'] = ApimSubscriptionId,
    ['Backend ID'] = BackendId,
    Deployment,
    ['Response Code'] = ResponseCode
| join kind=leftouter requestTelemetry on GatewayCorrelationId
| project
    ['Request Time'],
    ['Product ID'],
    ['Subscription ID'],
    ['Backend ID'],
    Deployment,
    ['Response Code'],
    ['RPM Limit'],
    ['RPM Remaining'],
    ['Retry After Seconds'],
    ['Model TPM Limit'],
    ['Model Tokens Consumed'],
    ['Model Tokens Remaining'],
    ['SKU TPM Limit'],
    ['SKU Tokens Consumed'],
    ['SKU Tokens Remaining']
| order by ['Request Time'] desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
  ]
  isLocked: false
  fallbackResourceIds: [
    workspaceResourceId
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
    description: 'Full-page APIM request list with routing dimensions and emitted RPM, model TPM, and SKU TPM values.'
    serializedData: string(workbookDefinition)
    version: 'Notebook/1.0'
    sourceId: workspaceResourceId
    category: 'workbook'
  }
}

output workbookId string = workbook.id
output workbookName string = workbook.name
output workbookDisplayName string = workbook.properties.displayName

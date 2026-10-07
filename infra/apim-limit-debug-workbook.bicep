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
param workbookDisplayName string = 'APIM RPM-TPM Threshold Debug'

var workbookName = guid(resourceGroup().id, 'apim-limit-debug-${resourceToken}')

var workbookDefinition = {
  version: 'Notebook/1.0'
  items: [
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
            label: 'Time period'
            type: 4
            isRequired: true
            value: {
              durationMs: 86400000
            }
            typeSettings: {
              selectableValues: [
                {
                  durationMs: 900000
                }
                {
                  durationMs: 3600000
                }
                {
                  durationMs: 14400000
                }
                {
                  durationMs: 86400000
                }
              ]
              allowCustom: true
            }
          }
          {
            id: 'subscription-id'
            version: 'KqlParameterItem/1.0'
            name: 'SubscriptionId'
            label: 'APIM subscription ID'
            type: 1
            isRequired: false
            value: 'ai-hybrid-data-sources-lob-oai-small-v2-sub'
          }
          {
            id: 'model'
            version: 'KqlParameterItem/1.0'
            name: 'Model'
            label: 'Model/deployment'
            type: 1
            isRequired: false
            value: ''
          }
          {
            id: 'backend-id'
            version: 'KqlParameterItem/1.0'
            name: 'BackendId'
            label: 'Backend ID'
            type: 1
            isRequired: false
            value: ''
          }
          {
            id: 'gateway'
            version: 'KqlParameterItem/1.0'
            name: 'Gateway'
            label: 'Gateway/region'
            type: 1
            isRequired: false
            value: ''
          }
          {
            id: 'sku-rpm-threshold'
            version: 'KqlParameterItem/1.0'
            name: 'SkuRpmThreshold'
            label: 'Temporary SKU RPM threshold'
            type: 1
            isRequired: true
            value: '20'
          }
          {
            id: 'sku-tpm-threshold'
            version: 'KqlParameterItem/1.0'
            name: 'SkuTpmThreshold'
            label: 'Temporary subscriber SKU TPM threshold'
            type: 1
            isRequired: true
            value: '300'
          }
          {
            id: 'model-tpm-threshold'
            version: 'KqlParameterItem/1.0'
            name: 'ModelTpmThreshold'
            label: 'Temporary subscriber + model TPM threshold'
            type: 1
            isRequired: true
            value: '250'
          }
          {
            id: 'backend-tpm'
            version: 'KqlParameterItem/1.0'
            name: 'BackendDeploymentTpm'
            label: 'Native backend deployment TPM (context only; not charted)'
            type: 1
            isRequired: true
            value: '30000'
          }
          {
            id: 'warning-percent'
            version: 'KqlParameterItem/1.0'
            name: 'WarningPercentage'
            label: 'Warning percentage'
            type: 1
            isRequired: true
            value: '80'
          }
        ]
        style: 'pills'
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
      }
    }
    {
      type: 1
      name: 'overview'
      content: {
        json: '''# APIM RPM/TPM threshold debug

Use the **Time period** picker above to focus every chart and evidence table on the same test window. The workbook correlates unsampled APIM gateway logs with Application Insights request, dependency, metric, and guarded branch-trace telemetry.

> **Window warning:** Clock-aligned one-minute bins are observational aids. They do not reproduce APIM sliding-window or v2 token-bucket state exactly. Confirm suspected breaches with request-level remaining counters and correlated request/trace IDs.

`UNKNOWN` means required telemetry or a threshold is missing. It never means zero or healthy. A `BREACH` label is evidence to inspect, not proof by itself.

The TPM charts are intentionally separate. The subscription-global chart counts each request once across all models. The per-model chart partitions those same requests by deployment. TPM limits are chart reference lines, not numeric result columns, so the legend cannot sum repeated limit values into a misleading total.'''
      }
    }
    {
      type: 3
      name: 'breach-status'
      content: {
        version: 'KqlItem/1.0'
        title: 'Threshold status (BREACH requires request-level confirmation)'
        query: '''
let subscriptionFilter = "{SubscriptionId}";
let modelFilter = "{Model}";
let backendFilter = "{BackendId}";
let gatewayFilter = "{Gateway}";
let rpmThreshold = tolong("{SkuRpmThreshold}");
let skuTpmThreshold = tolong("{SkuTpmThreshold}");
let modelTpmThreshold = tolong("{ModelTpmThreshold}");
let warningRatio = todouble("{WarningPercentage}") / 100.0;
let requestTelemetry =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        SkuTokens = tolong(coalesce(
            Properties["Response-x-llmmgmt-sku-ratelimit-consumed"],
            Properties["Response-x-llmmgmt-product-ratelimit-consumed"])),
        ModelTokens = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"])
    | summarize arg_max(TimeGenerated, *) by GatewayCorrelationId
    | project GatewayCorrelationId, SkuTokens, ModelTokens;
let observedByModel =
    ApiManagementGatewayLogs
    | where TimeGenerated {TimeRange}
    | extend
        Model = extract(@"/deployments/([^/?]+)", 1, Url),
        Gateway = coalesce(
            tostring(column_ifexists("GatewayId", "")),
            tostring(column_ifexists("Region", "")),
            "unknown")
    | where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter
    | where isempty(backendFilter) or BackendId == backendFilter
    | where isempty(gatewayFilter) or Gateway == gatewayFilter
    | project Minute = bin(TimeGenerated, 1m), GatewayCorrelationId = CorrelationId, Model, ResponseCode
    | join kind=leftouter requestTelemetry on GatewayCorrelationId
    | summarize
        AcceptedRequests = countif(toint(ResponseCode) < 400),
        Rejected429 = countif(toint(ResponseCode) == 429),
        SkuTokens = sum(SkuTokens),
        ModelTokens = sum(ModelTokens)
      by Minute, Model;
let observed =
    observedByModel
    | summarize
        AcceptedRequests = sum(AcceptedRequests),
        Rejected429 = sum(Rejected429),
        SkuTokens = sum(SkuTokens),
        PeakModelTokens = maxif(ModelTokens, isempty(modelFilter) or Model == modelFilter)
      by Minute;
let peaks =
    observed
    | summarize
        PeakRpm = max(AcceptedRequests),
        PeakSkuTpm = max(SkuTokens),
        PeakModelTpm = max(PeakModelTokens),
        Total429 = sum(Rejected429);
peaks
| extend
    RpmRatio = iff(rpmThreshold > 0, todouble(PeakRpm) / rpmThreshold, real(null)),
    SkuTpmRatio = iff(skuTpmThreshold > 0, todouble(PeakSkuTpm) / skuTpmThreshold, real(null)),
    ModelTpmRatio = iff(modelTpmThreshold > 0, todouble(PeakModelTpm) / modelTpmThreshold, real(null))
| project
    RPM = PeakRpm,
    RPMStatus = case(isnull(RpmRatio), "UNKNOWN", RpmRatio > 1.0, "BREACH", RpmRatio >= warningRatio, "WARNING", "OK"),
    SkuTPM = PeakSkuTpm,
    SkuTPMStatus = case(isnull(SkuTpmRatio), "UNKNOWN", SkuTpmRatio > 1.0, "BREACH", SkuTpmRatio >= warningRatio, "WARNING", "OK"),
    ModelTPM = PeakModelTpm,
    ModelTPMStatus = case(isnull(ModelTpmRatio), "UNKNOWN", ModelTpmRatio > 1.0, "BREACH", ModelTpmRatio >= warningRatio, "WARNING", "OK"),
    APIM429 = Total429
'''
        size: 1
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'tiles'
      }
    }
    {
      type: 3
      name: 'sku-token-threshold'
      content: {
        version: 'KqlItem/1.0'
        title: '1a. TPM - Subscription-global actual tokens per minute (each request counted once)'
        query: '''
let subscriptionFilter = "{SubscriptionId}";
let requestTelemetry =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        ApimSubscriptionId = tostring(Properties["Subscription Name"]),
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        SkuTokens = tolong(coalesce(
            Properties["Response-x-llmmgmt-sku-ratelimit-consumed"],
            Properties["Response-x-llmmgmt-product-ratelimit-consumed"]))
    | where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter
    | summarize arg_max(TimeGenerated, *) by GatewayCorrelationId
    | project GatewayCorrelationId, SkuTokens;
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter
| project TimeGenerated, GatewayCorrelationId = CorrelationId
| join kind=leftouter requestTelemetry on GatewayCorrelationId
| summarize SubscriptionGlobalTokens = sum(SkuTokens) by TimeGenerated = bin(TimeGenerated, 1m)
| order by TimeGenerated asc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'timechart'
        chartSettings: {
          showThresholdLine: true
          thresholdValue: '{SkuTpmThreshold}'
        }
      }
    }
    {
      type: 3
      name: 'model-token-threshold'
      content: {
        version: 'KqlItem/1.0'
        title: '1b. TPM - Per-model actual tokens per minute (partitioned, not added to global)'
        query: '''
let subscriptionFilter = "{SubscriptionId}";
let modelFilter = "{Model}";
let requestTelemetry =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        ApimSubscriptionId = tostring(Properties["Subscription Name"]),
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        ModelTokens = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"])
    | where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter
    | summarize arg_max(TimeGenerated, *) by GatewayCorrelationId
    | project GatewayCorrelationId, ModelTokens;
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| extend Model = extract(@"/deployments/([^/?]+)", 1, Url)
| where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter
| where isempty(modelFilter) or Model == modelFilter
| project TimeGenerated, GatewayCorrelationId = CorrelationId, Model
| join kind=leftouter requestTelemetry on GatewayCorrelationId
| summarize
    MiniRequests = countif(Model == "gpt-5.4-mini"),
    MiniTokens = sumif(ModelTokens, Model == "gpt-5.4-mini"),
    NanoRequests = countif(Model == "gpt-5.4-nano"),
    NanoTokens = sumif(ModelTokens, Model == "gpt-5.4-nano")
  by TimeGenerated = bin(TimeGenerated, 1m)
| extend
    MiniTokens = iff(MiniRequests > 0, MiniTokens, long(null)),
    NanoTokens = iff(NanoRequests > 0, NanoTokens, long(null))
| project TimeGenerated, MiniTokens, NanoTokens
| order by TimeGenerated asc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'timechart'
        chartSettings: {
          showThresholdLine: true
          thresholdValue: '{ModelTpmThreshold}'
        }
      }
    }
    {
      type: 3
      name: 'rpm-threshold'
      content: {
        version: 'KqlItem/1.0'
        title: '2. RPM - Aggregate accepted calls per minute vs mapped SKU-global limit'
        query: '''
let subscriptionFilter = "{SubscriptionId}";
let backendFilter = "{BackendId}";
let rpmThreshold = tolong("{SkuRpmThreshold}");
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| extend Model = extract(@"/deployments/([^/?]+)", 1, Url)
| where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter
| where isempty(backendFilter) or BackendId == backendFilter
| summarize
    Accepted = countif(toint(ResponseCode) < 400),
    Rejected429 = countif(toint(ResponseCode) == 429)
  by bin(TimeGenerated, 1m)
| extend Threshold = rpmThreshold, Breach = iff(rpmThreshold > 0 and Accepted > rpmThreshold, Accepted, long(null))
| project TimeGenerated, Accepted, Rejected429, Threshold, Breach
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
      name: 'remaining-counters'
      content: {
        version: 'KqlItem/1.0'
        title: '3. Diagnostic only - Remaining counters per request (not an overage calculation)'
        query: '''
let subscriptionFilter = "{SubscriptionId}";
let modelFilter = "{Model}";
let requestTelemetry =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        RpmRemaining = tolong(Properties["Response-x-llmmgmt-ratelimit-remaining-calls"]),
        ModelTpmRemaining = tolong(Properties["Response-x-llmmgmt-model-ratelimit-remaining"]),
        SkuTpmRemaining = tolong(coalesce(
            Properties["Response-x-llmmgmt-sku-ratelimit-remaining"],
            Properties["Response-x-llmmgmt-product-ratelimit-remaining"]))
    | summarize arg_max(TimeGenerated, *) by GatewayCorrelationId
    | project GatewayCorrelationId, RpmRemaining, ModelTpmRemaining, SkuTpmRemaining;
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| extend Model = extract(@"/deployments/([^/?]+)", 1, Url)
| where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter
| where isempty(modelFilter) or Model == modelFilter
| project TimeGenerated, GatewayCorrelationId = CorrelationId
| join kind=leftouter requestTelemetry on GatewayCorrelationId
| project TimeGenerated, RpmRemaining, ModelTpmRemaining, SkuTpmRemaining, Zero = 0
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
      name: 'retry-amplification'
      content: {
        version: 'KqlItem/1.0'
        title: 'Backend retry amplification'
        query: '''
let dependencies =
    AppDependencies
    | where TimeGenerated {TimeRange}
    | summarize BackendAttempts = count(), BackendCodes = make_set(ResultCode, 10) by OperationId;
AppRequests
| where TimeGenerated {TimeRange}
| extend GatewayCorrelationId = tostring(Properties["Request Id"])
| project TimeGenerated, OperationId, GatewayCorrelationId, RequestSuccess = Success, RequestResultCode = ResultCode
| join kind=leftouter dependencies on OperationId
| extend BackendAttempts = coalesce(BackendAttempts, 0)
| summarize
    APIMRequests = count(),
    BackendAttempts = sum(BackendAttempts),
    RetryAmplificationRatio = iff(count() > 0, round(todouble(sum(BackendAttempts)) / count(), 2), real(null)),
    RequestsWithRetries = countif(BackendAttempts > 1)
'''
        size: 1
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'tiles'
      }
    }
    {
      type: 3
      name: 'gateway-model-split'
      content: {
        version: 'KqlItem/1.0'
        title: 'Cross-model RPM proof - aggregate exceeds limit while model buckets do not'
        query: '''
let subscriptionFilter = "{SubscriptionId}";
let rpmThreshold = tolong("{SkuRpmThreshold}");
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| extend
    Model = extract(@"/deployments/([^/?]+)", 1, Url),
    Gateway = coalesce(
        tostring(column_ifexists("GatewayId", "")),
        tostring(column_ifexists("Region", "")),
        "unknown")
| where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter
| summarize Requests = count(), Accepted = countif(toint(ResponseCode) < 400), Rejected429 = countif(toint(ResponseCode) == 429)
  by Minute = bin(TimeGenerated, 1m), Gateway, Model
| as perModel
| join kind=leftouter (
    perModel
    | summarize AggregateAccepted = sum(Accepted), Aggregate429 = sum(Rejected429), PeakModelAccepted = max(Accepted)
      by Minute
  ) on Minute
| extend
    Threshold = rpmThreshold,
    ModelBucketStatus = case(rpmThreshold <= 0, "UNKNOWN", Accepted > rpmThreshold, "BREACH", "OK"),
    AggregateStatus = case(rpmThreshold <= 0, "UNKNOWN", AggregateAccepted > rpmThreshold, "BREACH", "OK"),
    PartitionEvidence = case(
        rpmThreshold <= 0, "UNKNOWN",
        AggregateAccepted > rpmThreshold and PeakModelAccepted <= rpmThreshold, "GLOBAL_NAME_BUT_MODEL_PARTITIONED",
        "NOT_PROVEN")
| order by Minute desc, Gateway asc, Model asc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'request-evidence'
      content: {
        version: 'KqlItem/1.0'
        title: 'Correlated request-level evidence'
        query: '''
let subscriptionFilter = "{SubscriptionId}";
let modelFilter = "{Model}";
let rpmThreshold = tolong("{SkuRpmThreshold}");
let skuThreshold = tolong("{SkuTpmThreshold}");
let modelThreshold = tolong("{ModelTpmThreshold}");
let requestTelemetry =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        RpmRemaining = tolong(Properties["Response-x-llmmgmt-ratelimit-remaining-calls"]),
        RetryAfter = tolong(Properties["Response-x-llmmgmt-retry-after"]),
        ModelLimit = tolong(coalesce(
            Properties["Response-x-llmmgmt-model-ratelimit-limit"],
            Properties["Response-x-llmmgmt-ratelimit-limit"])),
        ModelConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"]),
        ModelRemaining = tolong(Properties["Response-x-llmmgmt-model-ratelimit-remaining"]),
        SkuLimit = tolong(Properties["Response-x-llmmgmt-sku-ratelimit-limit"]),
        SkuConsumed = tolong(coalesce(
            Properties["Response-x-llmmgmt-sku-ratelimit-consumed"],
            Properties["Response-x-llmmgmt-product-ratelimit-consumed"])),
        SkuRemaining = tolong(coalesce(
            Properties["Response-x-llmmgmt-sku-ratelimit-remaining"],
            Properties["Response-x-llmmgmt-product-ratelimit-remaining"]))
    | summarize arg_max(TimeGenerated, *) by GatewayCorrelationId
    | project OperationId, GatewayCorrelationId, RpmRemaining, RetryAfter, ModelLimit, ModelConsumed, ModelRemaining, SkuLimit, SkuConsumed, SkuRemaining;
let dependencies =
    AppDependencies
    | where TimeGenerated {TimeRange}
    | summarize BackendAttempts = count() by OperationId;
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| extend
    Model = extract(@"/deployments/([^/?]+)", 1, Url),
    Gateway = coalesce(
        tostring(column_ifexists("GatewayId", "")),
        tostring(column_ifexists("Region", "")),
        "unknown")
| where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter
| where isempty(modelFilter) or Model == modelFilter
| project
    RequestTime = TimeGenerated,
    GatewayCorrelationId = CorrelationId,
    ProductId,
    SubscriptionId = ApimSubscriptionId,
    Model,
    BackendId,
    Gateway,
    ApimStatus = ResponseCode,
    BackendStatus = BackendResponseCode
| join kind=leftouter requestTelemetry on GatewayCorrelationId
| join kind=leftouter dependencies on OperationId
| extend
    RpmThreshold = rpmThreshold,
    SkuTpmThreshold = skuThreshold,
    ModelTpmThreshold = modelThreshold,
    EvidenceStatus = case(
        isnull(RpmRemaining) or isnull(SkuRemaining) or isnull(ModelRemaining), "UNKNOWN",
        RpmRemaining <= 0 or SkuRemaining <= 0 or ModelRemaining <= 0, "THRESHOLD",
        "OK")
| project RequestTime, GatewayCorrelationId, OperationId, ProductId, SubscriptionId, Model, BackendId, Gateway,
    ApimStatus, BackendStatus, BackendAttempts, RpmThreshold, RpmRemaining, RetryAfter,
    ModelTpmThreshold, ModelLimit, ModelConsumed, ModelRemaining,
    SkuTpmThreshold, SkuLimit, SkuConsumed, SkuRemaining, EvidenceStatus
| top 250 by RequestTime desc
'''
        size: 0
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'table'
      }
    }
    {
      type: 3
      name: 'data-quality'
      content: {
        version: 'KqlItem/1.0'
        title: 'Data quality (missing is UNKNOWN, never healthy)'
        query: '''
let requests =
    AppRequests
    | where TimeGenerated {TimeRange}
    | extend
        GatewayCorrelationId = tostring(Properties["Request Id"]),
        Tokens = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"]),
        Threshold = tolong(Properties["Response-x-llmmgmt-model-ratelimit-limit"])
    | summarize arg_max(TimeGenerated, *) by GatewayCorrelationId
    | project GatewayCorrelationId, Tokens, Threshold;
ApiManagementGatewayLogs
| where TimeGenerated {TimeRange}
| extend Model = extract(@"/deployments/([^/?]+)", 1, Url)
| project GatewayCorrelationId = CorrelationId, Model
| join kind=leftouter requests on GatewayCorrelationId
| summarize
    GatewayRows = count(),
    MissingRequestJoin = countif(isempty(GatewayCorrelationId1)),
    MissingTokenUsage = countif(isnull(Tokens)),
    MissingModel = countif(isempty(Model)),
    MissingThreshold = countif(isnull(Threshold))
| extend Status = iff(MissingRequestJoin + MissingTokenUsage + MissingModel + MissingThreshold > 0, "UNKNOWN DATA PRESENT", "COMPLETE FOR SELECTED WINDOW")
'''
        size: 1
        queryType: 0
        resourceType: 'microsoft.operationalinsights/workspaces'
        visualization: 'tiles'
      }
    }
    {
      type: 3
      name: 'branch-timeline'
      content: {
        version: 'KqlItem/1.0'
        title: 'Guarded branch-decision timeline'
        query: '''
AppTraces
| where TimeGenerated {TimeRange}
| extend
    Event = tostring(Properties["event"]),
    RequestId = tostring(Properties["requestId"]),
    ApiId = tostring(Properties["apiId"]),
    OperationId = tostring(Properties["operationId"]),
    ProductId = tostring(Properties["productId"]),
    SubscriptionId = tostring(Properties["subscriptionId"]),
    Model = tostring(Properties["model"]),
    ConfiguredLimit = tostring(Properties["configuredLimit"]),
    Attempt = tostring(coalesce(Properties["attempt"], Properties["backendAttempt"])),
    StatusCode = tostring(Properties["statusCode"])
| where Event in (
    "mapping.cache.hit", "mapping.cache.miss", "mapping.fetch.success", "mapping.fetch.failure",
    "config.found", "config.not-found", "rpm.configured", "rpm.fallback-20000",
    "model-tpm.multipart", "model-tpm.streaming", "model-tpm.nonstreaming", "model-tpm.disabled",
    "sku-tpm.multipart", "sku-tpm.streaming", "sku-tpm.nonstreaming", "sku-tpm.disabled",
    "backend.attempt", "outbound.summary")
| project TimeGenerated, RequestId, Event, ApiId, OperationId, ProductId, SubscriptionId, Model, ConfiguredLimit, Attempt, StatusCode
| order by RequestId asc, TimeGenerated asc
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
    description: 'Controlled-test workbook for APIM RPM/TPM threshold breaches, retries, branch decisions, and request evidence.'
    serializedData: string(workbookDefinition)
    version: 'Notebook/1.0'
    sourceId: workspaceResourceId
    category: 'workbook'
  }
}

output workbookId string = workbook.id
output workbookName string = workbook.name
output workbookDisplayName string = workbook.properties.displayName

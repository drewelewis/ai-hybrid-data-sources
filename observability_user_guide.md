# Observability user guide

This guide shows application owners and operators how to gather intelligence from the APIM
observability stack deployed by this repository. It covers where to start in the Azure
portal, when to use Application Insights versus Log Analytics, investigation workflows, KQL
queries, visualizations, and alerting.

For the resource design, networking, security posture, and deployment settings, see
[Observability architecture and setup](./observability.md).

## What this stack can tell you

The deployed stack answers gateway-level questions:

- How much traffic is the application receiving?
- Which APIs, operations, products, subscriptions, model deployments, and backends are used?
- What is the success rate and status-code distribution?
- Are failures caused by authentication, APIM policy, routing, throttling, or a backend?
- Where is latency spent?
- Which dependencies are slow or failing?
- How many LLM tokens are consumed, and by which bounded business dimensions?
- Is APIM approaching a capacity or throttling concern?

It does not automatically expose internal front-end or backend code behavior. If a gateway
request succeeds but the application produces a semantically wrong answer, add
application-level instrumentation and domain-specific quality evaluation.

## Before investigating

You need:

- access to the deployed Azure subscription and resource group;
- `Log Analytics Reader` or equivalent data-query permission on the workspace;
- `Monitoring Reader` if you also need resource metrics and monitoring configuration; and
- a known investigation time window in UTC, if possible.

Get the current environment's resource names:

```powershell
azd env get-value AZURE_RESOURCE_GROUP
azd env get-value APIM_NAME
azd env get-value LOG_ANALYTICS_WORKSPACE
azd env get-value APPLICATION_INSIGHTS_NAME
```

In the Azure portal, set the time picker before interpreting any chart. Portal blades and log
queries can retain different time ranges.

## Application Insights or Log Analytics?

Application Insights is workspace-based, so both experiences ultimately query the same Log
Analytics workspace. Choose the experience based on the question:

| Question | Start here | Why |
| --- | --- | --- |
| Exact request count or complete traffic inventory | **Log Analytics** > `ApiManagementGatewayLogs` | Gateway logs are unsampled |
| Status codes, APIM policy errors, backend codes, product/subscription usage | **Log Analytics** | Gateway-specific fields are richest here |
| Broad application health and visual triage | **Application Insights > Overview** | Fast rates, failures, and response-time charts |
| Which operations fail most? | **Application Insights > Failures** | Built-in failure grouping and drill-down |
| Which operations are slow? | **Application Insights > Performance** | Built-in percentile and operation views |
| Trace one request and its dependencies | **Application Insights > Transaction search** | W3C-correlated request/dependency timeline |
| Dependency map and health | **Application Insights > Application map** | Visual service/dependency relationships |
| Custom analysis across multiple tables | **Log Analytics > Logs** | Full KQL, joins, trends, and exports |
| APIM CPU, capacity, duration, and platform metrics | **APIM > Metrics** or `AzureMetrics` | Native resource metrics |
| LLM token consumption | **Application Insights > Metrics** | `AI-Gateway` custom token metric namespace |
| Durable operations dashboard | **Azure Monitor > Workbooks > APIM Observability** | Predeployed operational view combining logs, metrics, parameters, and investigation guidance |
| Product, subscription, backend, deployment, and token usage | **Azure Monitor > Workbooks > AI Gateway Usage Dimensions** | Dedicated governed-usage and dimension analysis |
| Request time plus product, subscription, backend, and deployment | **Azure Monitor > Workbooks > AI Gateway Dimension Values** | Minimal full-page request and dimension report |
| Notifications and automation | **Azure Monitor > Alerts** | Metric or KQL-based alert rules and action groups |

**Rule of thumb:** use Application Insights to discover and drill into a transaction; use
Log Analytics to prove, count, compare, correlate, and report.

## Where to go for common questions

### Overall traffic

For a quick visual:

1. Open the deployed Application Insights resource.
2. Select **Overview**.
3. Review **Failed requests**, **Server response time**, and **Server requests**.

For exact totals:

1. Open the Log Analytics workspace.
2. Select **Logs**.
3. Query `ApiManagementGatewayLogs`.

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(24h)
| summarize
    Requests = count(),
    Successful = countif(IsRequestSuccess == true),
    Failed = countif(IsRequestSuccess == false),
    SuccessRate = round(100.0 * countif(IsRequestSuccess == true) / count(), 2),
    P50Ms = percentile(todouble(TotalTime), 50),
    P95Ms = percentile(todouble(TotalTime), 95),
    P99Ms = percentile(todouble(TotalTime), 99)
```

Traffic over time:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(24h)
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false)
  by bin(TimeGenerated, 5m)
| render timechart
```

Use gateway logs for exact counts. Application Insights requests can be sampled. If you do
count `AppRequests`, use `sum(ItemCount)` rather than `count()`:

```kusto
AppRequests
| where TimeGenerated > ago(24h)
| summarize
    EstimatedRequests = sum(ItemCount),
    EstimatedFailures = sumif(ItemCount, Success == false)
  by bin(TimeGenerated, 5m)
| render timechart
```

### Errors and failed requests

For visual triage:

1. Open Application Insights.
2. Select **Investigate > Failures**.
3. Choose **Operations**, then sort or filter by failed request count.
4. Select an operation and then a sample request to open transaction details.

For APIM root-cause fields, use Log Analytics:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(24h)
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
    LastErrorSection,
    LastErrorReason,
    LastErrorMessage
| order by TimeGenerated desc
```

Group failures to find the dominant issue:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(24h)
| where IsRequestSuccess == false or toint(ResponseCode) >= 400
| summarize
    Failures = count(),
    SampleMessage = take_any(LastErrorMessage)
  by ResponseCode, LastErrorSource, LastErrorSection, LastErrorReason
| order by Failures desc
```

Interpretation:

| Pattern | Likely owner/action |
| --- | --- |
| `401` with `validate-jwt`, `TokenNotPresent`, or token validation reason | Client identity/configuration; inspect token presence, issuer, audience, scope, and expiry |
| `403` | Authorization, product/subscription state, policy, or backend access |
| `404` with APIM policy message | Requested model deployment is not mapped for the selected product |
| `429` generated before a backend call | APIM token/rate limit; review model and product limits |
| `429` with backend response `429` | Foundry/model quota or backend throttling |
| `503` with mapping-related message | Private mapping storage lookup, managed identity, DNS, or cached configuration |
| Frontend `5xx`, backend code empty | APIM policy, routing, networking, or gateway execution |
| Frontend `5xx`, backend code also `5xx` | Backend service or model deployment |
| Gateway success but user-visible failure | Front-end behavior or response interpretation; gateway telemetry alone may be insufficient |

### Authentication failures

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(24h)
| where LastErrorSource == "validate-jwt" or ResponseCode in ("401", "403")
| summarize
    Failures = count(),
    FirstSeen = min(TimeGenerated),
    LastSeen = max(TimeGenerated)
  by LastErrorReason, LastErrorMessage, ProductId, OperationId
| order by Failures desc
```

Do not expect raw bearer tokens or authorization headers; the stack intentionally does not
collect them.

### Slow requests and latency

For visual triage:

1. Open Application Insights.
2. Select **Investigate > Performance**.
3. Sort by duration or select a slow operation.
4. Open a sample and inspect its transaction timeline.

For exact gateway latency:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(24h)
| summarize
    Requests = count(),
    AvgTotalMs = round(avg(todouble(TotalTime)), 1),
    P50TotalMs = percentile(todouble(TotalTime), 50),
    P95TotalMs = percentile(todouble(TotalTime), 95),
    P99TotalMs = percentile(todouble(TotalTime), 99),
    P95BackendMs = percentile(todouble(BackendTime), 95)
  by ApiId, OperationId, BackendId
| order by P95TotalMs desc
```

Find individual outliers:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(24h)
| extend
    TotalMs = todouble(TotalTime),
    BackendMs = todouble(BackendTime),
    CacheMs = todouble(CacheTime),
    ClientMs = todouble(ClientTime)
| extend GatewayAndTransferMs =
    TotalMs - coalesce(BackendMs, 0.0) - coalesce(CacheMs, 0.0) - coalesce(ClientMs, 0.0)
| top 50 by TotalMs desc
| project
    TimeGenerated,
    CorrelationId,
    OperationId,
    BackendId,
    ResponseCode,
    TotalMs,
    BackendMs,
    CacheMs,
    ClientMs,
    GatewayAndTransferMs
```

Interpret carefully:

- High `BackendTime` points to model/backend processing or backend network latency.
- Low `BackendTime` but high `TotalTime` points toward APIM policy work, retries, streaming,
  gateway queuing, or transfer time.
- Streaming responses make a single duration less representative of time-to-first-token.
  Add application-level measurements if that distinction matters.
- The policy retries `408`, `429`, and `5xx` backend responses up to three times, so one
  client request can legitimately have a long duration.

### Dependencies

Open **Application Insights > Application map** for a visual overview. APIM dependencies can
include the model backend, Microsoft Entra endpoints, and private mapping storage.

Query dependency health:

```kusto
AppDependencies
| where TimeGenerated > ago(24h)
| summarize
    Calls = sum(ItemCount),
    Failures = sumif(ItemCount, Success == false),
    FailureRate = round(100.0 * sumif(ItemCount, Success == false) / sum(ItemCount), 2),
    AvgMs = round(avg(DurationMs), 1),
    P95Ms = percentile(DurationMs, 95)
  by Target, Name, DependencyType
| order by Failures desc, P95Ms desc
```

Recent failed dependencies:

```kusto
AppDependencies
| where TimeGenerated > ago(24h)
| where Success == false
| project
    TimeGenerated,
    OperationId,
    ParentId,
    Target,
    Name,
    ResultCode,
    DurationMs,
    Properties
| order by TimeGenerated desc
```

### Traffic by API, model, product, subscription, and backend

By API operation:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(7d)
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false),
    P95Ms = percentile(todouble(TotalTime), 95)
  by ApiId, OperationId
| order by Requests desc
```

By deployment parsed from the OpenAI-compatible URL:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(7d)
| extend Deployment = extract(@"/deployments/([^/?]+)", 1, Url)
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false),
    P95Ms = percentile(todouble(TotalTime), 95)
  by Deployment
| order by Requests desc
```

By governed consumer:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(7d)
| summarize
    Requests = count(),
    Failures = countif(IsRequestSuccess == false),
    RequestBytes = sum(tolong(RequestSize)),
    ResponseBytes = sum(tolong(ResponseSize))
  by ProductId, ApimSubscriptionId
| order by Requests desc
```

Prefer `ProductId` and `ApimSubscriptionId` over `CallerIpAddress` for consumer attribution.
The caller address can be a proxy, App Service integration address, or NAT address.

By backend:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(7d)
| summarize
    Requests = count(),
    GatewayFailures = countif(IsRequestSuccess == false),
    BackendFailures = countif(toint(BackendResponseCode) >= 400),
    P95BackendMs = percentile(todouble(BackendTime), 95)
  by BackendId, BackendUrl
| order by Requests desc
```

### Rate limits and quota pressure

APIM stores the allow-listed rate-limit response headers in `AppRequests.Properties`:

```kusto
AppRequests
| where TimeGenerated > ago(24h)
| extend
    Product = tostring(Properties["Product Name"]),
    Subscription = tostring(Properties["Subscription Name"]),
    ModelLimit = tolong(Properties["Response-x-llmmgmt-model-ratelimit-limit"]),
    ModelConsumed = tolong(Properties["Response-x-llmmgmt-model-ratelimit-consumed"]),
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
    RetryAfterSeconds = tolong(Properties["Response-x-llmmgmt-retry-after"]),
    GatewayRequestId = tostring(Properties["Request Id"])
| where isnotnull(ModelConsumed) or isnotnull(SkuConsumed) or isnotnull(RpmRemaining)
| project
    TimeGenerated,
    GatewayRequestId,
    Name,
    ResultCode,
    Product,
    Subscription,
    ModelLimit,
    ModelConsumed,
    ModelRemaining,
    SkuLimit,
    SkuConsumed,
    SkuRemaining,
    RpmLimit,
    RpmRemaining,
    RetryAfterSeconds
| order by TimeGenerated desc
```

Find callers approaching either configured limit:

```kusto
AppRequests
| where TimeGenerated > ago(24h)
| extend
    Product = tostring(Properties["Product Name"]),
    Subscription = tostring(Properties["Subscription Name"]),
    ModelRemaining = tolong(Properties["Response-x-llmmgmt-model-ratelimit-remaining"]),
    SkuRemaining = coalesce(
        tolong(Properties["Response-x-llmmgmt-sku-ratelimit-remaining"]),
        tolong(Properties["Response-x-llmmgmt-product-ratelimit-remaining"])),
    RpmRemaining = tolong(Properties["Response-x-llmmgmt-ratelimit-remaining-calls"])
| where isnotnull(ModelRemaining) or isnotnull(SkuRemaining) or isnotnull(RpmRemaining)
| summarize
    MinimumModelRemaining = min(ModelRemaining),
    MinimumSkuRemaining = min(SkuRemaining),
    MinimumRpmRemaining = min(RpmRemaining)
  by Product, Subscription
| order by MinimumModelRemaining asc, MinimumProductRemaining asc
```

These are per-request enforcement values, not a replacement for the token metrics described
next.

### LLM token consumption

1. Open the deployed Application Insights resource.
2. Select **Monitoring > Metrics**.
3. Choose the custom metric namespace **AI-Gateway**.
4. Select the available total, prompt, completion, cached, reasoning, or provider-specific
   token metric.
5. Split or filter by **Product ID**, **Subscription ID**, **Backend ID**, or **Deployment**.
6. Use **Sum** aggregation for consumption over the selected period.

If token metrics are absent:

- confirm requests are sent through the API carrying the token-metric policy;
- confirm the model/endpoint returns usage in a supported schema;
- for streaming Chat Completions, send `stream_options.include_usage: true`;
- allow time for metric ingestion;
- confirm the Application Insights logger and managed-identity role assignment are healthy;
- confirm custom metrics with dimensions remain enabled; and
- check that dimension/time-series cardinality limits have not been reached.

Do not enable `GatewayLlmLogs` merely to obtain token totals; that category can contain prompt
and response content and is intentionally disabled.

### APIM platform health and capacity

For a quick chart:

1. Open APIM.
2. Select **Monitoring > Metrics**.
3. Inspect capacity, requests, duration, CPU, and gateway-specific metrics available for the
   selected APIM tier.
4. Split by gateway location or status-code dimension where supported.

The diagnostic setting also sends metrics to `AzureMetrics`:

```kusto
AzureMetrics
| where TimeGenerated > ago(24h)
| where ResourceProvider =~ "MICROSOFT.APIMANAGEMENT"
| summarize
    Average = avg(Average),
    Maximum = max(Maximum),
    Total = sum(Total)
  by MetricName, UnitName, bin(TimeGenerated, 5m)
| render timechart
```

List the metric names that are actually arriving before building an alert:

```kusto
AzureMetrics
| where TimeGenerated > ago(24h)
| where ResourceProvider =~ "MICROSOFT.APIMANAGEMENT"
| summarize Samples = count(), Latest = max(TimeGenerated) by MetricName, UnitName
| order by MetricName asc
```

Use the native Metrics experience for low-latency metric alerts. Use `AzureMetrics` when you
need KQL joins, long-window analysis, or a workbook that already uses workspace data.

## Trace one request end to end

The gateway `CorrelationId` equals the Application Insights request property `Request Id`.
Application Insights then uses `OperationId` to correlate the request with dependencies.

### Portal workflow

1. Obtain an `apim-request-id` or approximate UTC time from the client.
2. In Application Insights, open **Transaction search**.
3. Set the time range and filter to **Request** telemetry.
4. Search by operation, result code, or request property.
5. Open the request and inspect the transaction timeline and dependencies.
6. If APIM-specific detail is needed, copy the request's `Request Id` property and query the
   gateway table by `CorrelationId`.

### KQL workflow

Set the ID from `ApiManagementGatewayLogs.CorrelationId` or
`AppRequests.Properties["Request Id"]`:

```kusto
let gatewayRequestId = "PASTE-CORRELATION-ID";
let request =
    AppRequests
    | where tostring(Properties["Request Id"]) == gatewayRequestId
    | project
        TimeGenerated,
        OperationId,
        RequestName = Name,
        RequestSuccess = Success,
        RequestResult = ResultCode,
        RequestDurationMs = DurationMs,
        RequestProperties = Properties;
let dependencies =
    AppDependencies
    | join kind=inner (request | project OperationId) on OperationId
    | project
        TimeGenerated,
        OperationId,
        DependencyName = Name,
        Target,
        DependencySuccess = Success,
        DependencyResult = ResultCode,
        DependencyDurationMs = DurationMs,
        DependencyProperties = Properties;
union
    (request | extend TelemetryType = "Request"),
    (dependencies | extend TelemetryType = "Dependency")
| order by TimeGenerated asc
```

Gateway details for the same ID:

```kusto
let gatewayRequestId = "PASTE-CORRELATION-ID";
ApiManagementGatewayLogs
| where CorrelationId == gatewayRequestId
| project
    TimeGenerated,
    CorrelationId,
    ApiId,
    OperationId,
    ProductId,
    ApimSubscriptionId,
    BackendId,
    ResponseCode,
    BackendResponseCode,
    TotalTime,
    BackendTime,
    LastErrorSource,
    LastErrorReason,
    LastErrorMessage
```

## Build a daily operational review

Use a consistent sequence:

1. **Check availability and request volume.** Compare today with the same weekday or a known
   baseline.
2. **Check failure rate and dominant status codes.** Separate client/authentication errors
   from APIM and backend errors.
3. **Check p50, p95, and p99 latency.** Determine whether backend time explains the change.
4. **Check dependency health.** Look for Microsoft Entra, storage, or model-backend failures.
5. **Check throttling and remaining limits.** Review `429` responses and rate-limit headers.
6. **Check token usage.** Split by product, subscription, deployment, and backend.
7. **Check APIM capacity.** Look for sustained rather than isolated spikes.
8. **Record the time window and correlation IDs** for anomalies before data ages out.

Avoid judging health from averages alone. Always include traffic volume, error rate, and high
percentiles.

## Use the deployed workbook

The infrastructure deploys two shared workbooks:

- **APIM Observability** for overall traffic, failures, latency, dependencies, usage, and
  platform health.
- **AI Gateway Usage Dimensions** for Product ID, Subscription ID, Backend ID, Deployment,
  token consumption, and remaining-limit analysis.
- **AI Gateway Dimension Values** for a minimal full-page table with one row per APIM request
  containing request time, Product ID, Subscription ID, Backend ID, and Deployment.

1. Open **Azure Monitor > Workbooks**.
2. Select the workbook for the investigation. If needed, filter to the current resource
   group.
3. Set the global time range.
4. Start with **Health overview**, then use the failure, performance, usage, token, and
   platform sections to narrow the investigation.
5. Copy a gateway `CorrelationId` from **Recent failed requests** when an individual
   transaction needs deeper investigation in Application Insights.

The workbooks are defined in
[`infra/observability-workbook.bicep`](./infra/observability-workbook.bicep) and
[`infra/ai-gateway-usage-workbook.bicep`](./infra/ai-gateway-usage-workbook.bicep), and
[`infra/ai-gateway-dimension-values-workbook.bicep`](./infra/ai-gateway-dimension-values-workbook.bicep).
They are updated by `azd up`. Make shared changes in Bicep rather than editing deployed
workbooks in place; an infrastructure deployment replaces portal-only edits. Users can
clone them to personal workbooks for temporary experiments.

The workbook intentionally excludes prompt, completion, token, key, and authorization
values. Do not add them to parameters, queries, or exported results.

## Create alerts

This baseline does not create alerts or action groups. Build alerts only after observing
normal traffic so thresholds reflect the application.

Recommended starting alerts:

| Signal | Suggested approach | Notes |
| --- | --- | --- |
| No gateway traffic when traffic is expected | Log search alert | Suppress during known idle windows |
| Elevated gateway failure rate | Log search alert | Require a minimum request count to avoid noisy percentages |
| Repeated `401`/`403` spike | Log search alert | Can indicate a client release or identity configuration issue |
| Repeated `429` | Log search alert | Separate APIM-generated from backend-generated throttling |
| Backend `5xx` | Log search alert | Group by backend/deployment |
| High p95 latency | Log search or metric alert | Use a sustained window and minimum volume |
| APIM capacity | Native metric alert | Prefer native metrics for faster evaluation |
| Dependency failures | Log search alert on `AppDependencies` | Group by target |
| Token consumption anomaly | Custom metric alert | Split only on bounded dimensions |
| Telemetry silence | Separate checks for gateway and App Insights streams | Detect collection failures, not only application failures |

Example failure-rate query for an alert:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(10m)
| summarize Requests = count(), Failures = countif(IsRequestSuccess == false)
| extend FailureRate = 100.0 * Failures / Requests
| where Requests >= 20 and FailureRate >= 5.0
```

Example backend-error alert:

```kusto
ApiManagementGatewayLogs
| where TimeGenerated > ago(10m)
| where toint(BackendResponseCode) >= 500
| summarize Failures = count() by BackendId, bin(TimeGenerated, 5m)
| where Failures >= 3
```

Attach an Azure Monitor action group for email, chat, incident management, or automation.
Include the environment, time window, affected backend/operation, and a portal query link in
the notification.

## Export and share results safely

- Prefer workbook links or saved queries over CSV exports.
- Remove caller addresses and subscription identifiers unless the recipient needs them.
- Never add body or authorization-header capture to make an investigation easier.
- Treat URLs, product IDs, deployment names, and backend names as operationally sensitive.
- Use UTC timestamps and state the query window.
- Include both the numerator and denominator when reporting percentages.
- Note whether counts come from unsampled gateway logs or sampled Application Insights data.

## Troubleshooting the observability stack

### Gateway logs are empty

1. Confirm the request reached the expected APIM environment.
2. Widen the query time range and wait several minutes.
3. Check APIM **Monitoring > Diagnostic settings** for `apim-gateway-logs`.
4. Confirm `GatewayLogs` is enabled and targets the expected workspace.
5. Verify your RBAC access to workspace data.
6. Query without resource filters:

   ```kusto
   ApiManagementGatewayLogs
   | take 10
   ```

### Application Insights requests are empty

1. Confirm APIM has an Application Insights logger named `application-insights`.
2. Confirm the APIM API diagnostic named `applicationinsights` is enabled.
3. Check that APIM's managed identity has `Monitoring Metrics Publisher` on Application
   Insights.
4. Confirm the Azure Monitor Private Link Scope contains both Application Insights and the
   workspace.
5. Check the monitor private endpoint connection and private DNS zone group.
6. Compare with gateway logs. If gateway logs exist but `AppRequests` does not, focus on the
   APIM logger/private-ingestion path.

### Gateway logs exist but dependencies do not

- Ensure the selected transaction actually performed a backend or policy dependency call.
- Search `AppDependencies` by the request's Application Insights `OperationId`, not the APIM
  gateway `CorrelationId`.
- Consider sampling and ingestion delay.

### Counts disagree

Expected causes include:

- Application Insights sampling;
- different portal time ranges;
- ingestion delay;
- `count()` used instead of `sum(ItemCount)` in Application Insights;
- filters scoped to a different resource; or
- all errors retained while successful Application Insights requests are sampled.

Use `ApiManagementGatewayLogs` as the exact traffic source.

### A query reports an unknown column or table

Azure schemas evolve and empty tables can be unavailable until their first record. Confirm
the live schema:

```kusto
ApiManagementGatewayLogs
| getschema
```

Then compare it with the Microsoft table reference linked below.

## Query efficiency

- Always constrain `TimeGenerated` early.
- Project only needed columns before joins.
- Summarize before joining high-volume tables when transaction-level detail is unnecessary.
- Use gateway logs for exact counts rather than joining every request to Application
  Insights.
- Avoid unbounded `search *`.
- Save reviewed queries in a query pack or workbook rather than maintaining divergent local
  copies.

## Microsoft references

- [Application Insights investigation tools](https://learn.microsoft.com/azure/azure-monitor/app/failures-performance-transactions)
- [Application map](https://learn.microsoft.com/azure/azure-monitor/app/app-map)
- [Log queries in Azure Monitor](https://learn.microsoft.com/azure/azure-monitor/logs/log-query-overview)
- [`ApiManagementGatewayLogs` reference](https://learn.microsoft.com/azure/azure-monitor/reference/tables/apimanagementgatewaylogs)
- [Sample APIM gateway queries](https://learn.microsoft.com/azure/azure-monitor/reference/queries/apimanagementgatewaylogs)
- [`AppRequests` reference](https://learn.microsoft.com/azure/azure-monitor/reference/tables/apprequests)
- [`AppDependencies` reference](https://learn.microsoft.com/azure/azure-monitor/reference/tables/appdependencies)
- [Azure Monitor Workbooks](https://learn.microsoft.com/azure/azure-monitor/visualize/workbooks-overview)
- [Create log search alerts](https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-create-log-alert-rule)
- [APIM token metrics](https://learn.microsoft.com/azure/api-management/llm-emit-token-metric-policy)

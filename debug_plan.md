# APIM RPM/TPM Debug Plan

## Objective

Prove, with APIM traces and correlated request data, why traffic can appear to exceed:

- `skuGlobalMaxCallsPerMinute` (RPM)
- `skuGlobalMaxTokensPerMinute` (TPM)

Do not change the APIM policy logic until the evidence has identified which hypothesis is
responsible. Use the existing APIM subscription, existing product/config mapping, and existing
model deployments. No new subscription or model is required.

## Safety and cost controls

1. Run during a controlled test window because the existing counters and mapping are shared with
   normal traffic.
2. Use the one existing APIM subscription key to generate test traffic and obtain approval from
   its owner and the product owner.
3. Record the current mapping values and mapping blob ETag before changing any test values.
4. Keep these three limits distinct:
   - **Subscriber SKU TPM**: `skuGlobalMaxTokensPerMinute`, keyed by APIM subscription.
   - **Subscriber + model TPM ceiling**: `maxTokensPerMinute`, keyed by APIM subscription and
     model. Despite its name, this policy counter is not global across all subscribers using the
     deployment.
   - **Backend model deployment TPM**: the native shared Azure AI Foundry/Azure OpenAI deployment
     capacity across all subscribers. Do not change this capacity for the test.
5. Target a 10x reduction for the selected mapping while preserving the intended hierarchy:
   - `testRPM = max(1, floor(current skuGlobalMaxCallsPerMinute / 10))`
   - `calibratedRequestTokens = actual total tokens from the one-request smoke calibration`
   - choose `testModelTPM` above one calibrated request;
   - choose `testSkuTPM` above `testModelTPM` but below the combined calibrated usage of one
     request to each model.
   This preserves the intended `testModelTPM < testSkuTPM` hierarchy while allowing a cross-model
   test in which neither model bucket breaches independently but their shared subscriber SKU
   counter does. If prompt size prevents a full 10x reduction, record the smaller reduction rather
   than using an unexecutable threshold.
6. If the 10x RPM result is still expensive (for example, the `20000` fallback becomes `2000`),
   cap the temporary test RPM at `20`.
7. If the 10x TPM results are still expensive, lower both values while keeping one calibrated
   request below the model limit and the model limit below the subscriber SKU limit. Never raise
   either test value merely to reach the backend deployment capacity.
8. Use the existing lowest-cost suitable deployment, short prompts, `temperature: 0`, and a
   response cap of 8 tokens where the operation supports it.
9. Stop immediately if unrelated production traffic receives a 429 or if Foundry cost/usage
   rises outside the expected test envelope.
10. Restore the original mapping values and verify the mapping blob ETag/content after every test
   session.

The calibrated cross-model TPM profile for the current two-tab UI test is:

- `skuGlobalMaxCallsPerMinute`: `20`, so RPM does not mask the TPM result.
- `skuGlobalMaxTokensPerMinute`: `300`.
- `maxTokensPerMinute`: `250` for both mapped models.
- Calibration prompt: `Write exactly 120 words explaining why rate limiting matters. Do not use headings or lists.`
- Observed totals before lowering the limits: `158` tokens for `gpt-5.4-mini` and `168` tokens
  for `gpt-5.4-nano`, or `326` combined.

The controlled cross-model TPM reproduction on 2026-10-05 produced:

- At `13:52:05Z`, concurrent requests to `gpt-5.4-mini` and `gpt-5.4-nano` were both
  accepted with HTTP 200.
- Mini consumed `162` tokens and nano consumed `172`; both stayed below their independent
  `250` model TPM limits, but their combined `334` tokens exceeded the shared `300` subscriber
  SKU TPM limit.
- Four subsequent 14-token mini requests were also accepted, bringing directly observed usage
  to `390` tokens in the same test interval.
- The reported subscriber SKU remaining values were non-monotonic (`18`, `61`, `253`, `61`)
  rather than converging consistently toward zero.
- This proves that concurrent requests can be admitted before shared SKU token usage propagates
  across APIM gateway workers. The shared key has the intended subscription scope, but the
  distributed token counter is not a strict, strongly consistent hard cap.

After splitting the workbook's combined TPM visualization into independent subscription-global
and per-model charts, a clean sequential cross-model rerun at `18:54:05Z` produced:

- `gpt-5.4-mini`: HTTP 200, `162` tokens, `88` model tokens remaining, and `138` subscriber SKU
  tokens remaining.
- `gpt-5.4-nano`: HTTP 200, `175` tokens, `75` model tokens remaining, and `125` subscriber SKU
  tokens remaining.
- Each request remained below its `250` model TPM limit, while their unique combined usage was
  `337` tokens against the shared `300` subscriber SKU TPM limit.
- Correlation IDs: `bf1e5284-b63c-4915-9ac5-be457e38db46` for mini and
  `69cafa7d-dff1-4989-bc2f-564a4bde7ed4` for nano.

The corrected global chart sums the SKU token header once per gateway request. The corrected model
chart shows mini and nano as separate numeric series. Mapped limits are chart reference lines, not
query-result columns, so the workbook no longer sums repeated limits or adds the global and model
views into one token total.

Changing mapping values for the controlled test is allowed. Changing the APIM policy logic is not
part of the reproduction phase. The workbook, custom-agent profile, and bounded Playwright routine
are diagnostic test artifacts; implementing them does not authorize a policy change. Temporary
guarded `trace` policies may be added after the unchanged baseline is captured, but they must not
change branch conditions, policy order, counter keys, thresholds, request bodies, or backend
selection.

## Hard preconditions and no-go gates

All gates in this section must pass before changing mapping values or generating paid test traffic.

### Single-subscription scope and mapping blast radius

The mapping is selected by APIM product ID, not by APIM subscription ID. Changing a product/model
mapping therefore affects every subscription using that product/model even though each runtime
counter includes the subscription ID.

1. Verify that the selected product currently has exactly one APIM subscription.
2. Record that subscription's current request rate during the proposed test window.
3. Obtain approval from the subscription owner and product owner for the temporary limits.
4. Require a quiet window with no unrelated traffic for the selected product/model.
5. Abort if another subscription is discovered or unrelated traffic cannot be stopped.

Do not describe the mapping update as subscription-isolated. It is only the counters that are
partitioned by subscription. Multi-subscription testing is explicitly out of scope for this plan.

### Telemetry readiness

Run one smoke request and prove that the existing environment supplies each data source before
building queries or starting load:

- unsampled `ApiManagementGatewayLogs`;
- `AppRequests` with the gateway request ID used for correlation;
- captured safe `x-llmmgmt-*` response headers needed by the workbook;
- model/deployment, product, APIM subscription, backend, status, and gateway/region dimensions;
- native AI Gateway token metrics or another verified source of actual token totals;
- `AppDependencies` only if a smoke trace proves retry attempts are emitted as separate records.
- `AppTraces` or the configured resource-log field containing guarded `llmmgmt-branch-debug`
  events.

If retry attempts are not individually represented in `AppDependencies`, use APIM debug traces for
the retry analysis and label workbook retry amplification as unavailable. Missing telemetry must
render as unknown, never zero or healthy.

### Correlation readiness

APIM debug tracing requires `Apim-Debug-Authorization` on the request. The normal customer UI is
not assumed to send that header, and the UI agent must not inject it.

Use two evidence paths:

1. **Direct traced control calls** use a time-limited APIM debug credential and produce
   `Apim-Trace-Id`.
2. **UI exercise calls** must expose an existing outgoing W3C `traceparent` or a safe response
   correlation ID that can be joined to `AppRequests` and `ApiManagementGatewayLogs`.

The agent must capture the existing browser-visible correlation value without modifying the
request. If neither correlation mechanism exists, UI load may demonstrate visible throttling but
cannot prove an exact request-to-trace chain; report `BLOCKED_CORRELATION` and do not infer identity
from timestamp alone.

### Counter and cache readiness

1. The mapping cache has a one-hour TTL and can be local to serving gateway instances/regions.
2. After updating the mapping, verify the temporary values on every serving gateway/region using
   an existing routing path and traced control request where possible.
3. After all serving paths show the temporary values, require at least one full 60-second counter
   interval with zero unrelated traffic before the first measurement.
4. Repeat the same per-gateway verification after restoring the original mapping.
5. Keep the test window open until rollback is confirmed everywhere; do not treat the blob ETag
   alone as proof that all gateways are using the restored values.

### Agent runtime and deterministic bounds

The custom agent must target VS Code because the external customer UI and Azure portal workbook
cannot be exercised by GitHub cloud agent's localhost-only Playwright service.

The agent may decide which scenario to run and interpret results, but one bounded Playwright
routine must enforce:

- approved UI and workbook host names;
- UTC start and stop times;
- attempt count;
- concurrency;
- calibrated token budget;
- allowed scenarios;
- stop conditions.

The routine must validate all bounds before its first UI action and maintain counters in code.
Natural-language instructions alone are not an acceptable cost or safety control.

## What the current effective policy indicates

These are hypotheses to prove, not conclusions to use as a substitute for traces.

| ID | Hypothesis | Policy evidence | Expected observation |
|---|---|---|---|
| H1 | The RPM limit is per subscription **and model**, not SKU-global. | The RPM key is `context.Subscription.Id + llmmgmt-model`. | Each model gets an independent RPM bucket. Calls across two existing models can sum above `skuGlobalMaxCallsPerMinute` without either bucket returning 429. |
| H2 | Override-routed requests bypass both RPM and TPM policies. | The `OVERRIDE_BACKEND_SERVICE_URL` branch sets the backend and exits the branch before all limit policies. | A trace for an override-routed request contains no `rate-limit-by-key` or token-limit execution. |
| H3 | Backend retries make Foundry call counts exceed accepted APIM request counts. | The backend retries 408, 429, 500, 502, and 503 up to three times. Inbound limits execute once, while the backend can be attempted multiple times. | One APIM request ID correlates with two or more backend attempts/Foundry requests. |
| H4 | TPM temporarily overshoots under concurrency. | Most non-streaming branches use `estimate-prompt-tokens="false"`, so actual tokens are learned from the response. | Several concurrent requests are admitted before earlier responses update the token counter; later requests receive 429. |
| H5 | Token counters are separate per APIM gateway/region. | APIM token counters do not aggregate across regional gateways. | Requests split across gateways exceed the configured aggregate while each gateway remains near or below its local limit. |
| H6 | Call counters are approximate and separate per APIM gateway/region. | APIM documents distributed rate limits as approximate and call data as local to each regional gateway. | Small RPM overshoot occurs during a burst, or aggregate multi-region traffic exceeds the limit without a single gateway doing so. |
| H7 | Different model configurations apply different TPM values to the same SKU counter key. | SKU TPM is keyed only by `context.Subscription.Id`, but its limit value is read from the selected model configuration. | Existing models with different `skuGlobalMaxTokensPerMinute` values use one counter key with inconsistent limits, producing unpredictable v2-tier behavior. |
| H8 | Missing/nonpositive RPM configuration silently enables the `20000` calls/min fallback. | The `otherwise` branch applies `calls="20000"`. | Trace/config shows no positive configured RPM, and response behavior follows the fallback rather than the expected SKU value. |
| H10 | Monitoring compares different one-minute windows or different token measures. | APIM limits use gateway counter windows; dashboards may use clock-aligned bins and Foundry actual usage. | The apparent excess disappears when events are correlated by timestamp, gateway, subscription, model, and request ID instead of a dashboard one-minute bin. |

### Future multi-subscription architecture note (not tested)

The shared deployment can conceptually support several subscriber allocations, such as five
subscribers at 200 TPM against a 1,000 TPM deployment. This plan does not create, simulate, or test
those additional subscriptions. It exercises only the one existing APIM subscription. The native
backend deployment limit remains the final shared ceiling if more subscriptions are added later.

## Measurements to keep separate

Capture all four values. Do not compare one as if it were another.

1. **Client attempts**: every request emitted by the test driver.
2. **APIM accepted requests**: client responses that passed inbound policy and reached the backend.
3. **Backend attempts**: every `forward-request`, including retries.
4. **Foundry usage**: backend request count and actual prompt/completion/total tokens.

An APIM RPM policy limits inbound client requests. It does not directly limit retry attempts made
inside the backend section.

## Evidence to capture for every request

Use a unique W3C `traceparent` for each client request and retain:

- UTC send and receive timestamps with millisecond precision
- APIM subscription ID (never store the subscription key)
- APIM product ID
- operation and URL template
- requested model/deployment
- request body fields that affect token use (`stream`, response-token cap)
- HTTP status
- `Apim-Trace-Id`
- APIM/context request ID and the supplied trace ID
- gateway/region identifier, if present in diagnostics
- backend attempt number and backend status
- `x-llmmgmt-ratelimit-remaining-calls`
- `x-llmmgmt-retry-after`
- `x-llmmgmt-model-ratelimit-remaining`
- `x-llmmgmt-model-ratelimit-consumed`
- `x-llmmgmt-sku-ratelimit-remaining`
- `x-llmmgmt-sku-ratelimit-consumed`
- Foundry prompt, completion, and total token usage

Sanitize authorization headers, APIM subscription keys, managed-identity tokens, prompts containing
customer data, and backend URLs before sharing traces.

## Phase 1: Snapshot, baseline, and branch instrumentation

### Baseline without policy changes

1. Export and save privately:
   - the current effective policy;
   - the current mapping document and ETag;
   - APIM tier and whether the instance is multi-region;
   - all gateways/regions that can serve the API;
   - the selected subscription/product's values for all three policy limits;
   - the existing backend model deployment's native TPM capacity.
2. Confirm whether `OVERRIDE_BACKEND_SERVICE_URL` is defined at global, product, API, operation, or
   request scope for the tested route.
3. Confirm whether the observed dashboard combines:
   - multiple models;
   - multiple APIM regions/gateways;
   - APIM client requests and Foundry backend attempts.
4. Validate the capacity allocation before changing values:
   - `subscriber + model TPM ceiling < subscriber SKU TPM`;
   - both subscriber policy limits are below the backend model deployment TPM.
   Do not mistake a backend deployment 429 for an APIM subscriber limit failure.
   During the controlled debug cycle, cache `llmmgmt-mapping` for 60 seconds so promoted mapping
   values become effective predictably without an ad hoc cache-invalidation path.
5. Complete every hard precondition and record a pass/fail result.
6. Send one non-streaming request through the normal route with APIM tracing enabled.
7. Send one streaming request through the normal route with tracing enabled.
8. If an existing override-routed operation is available, send one low-token request through it.
9. For each request, verify from the trace:
   - the resolved `llmmgmt-model`;
   - the resolved `llmmgmt-config`;
   - the selected branch;
   - whether RPM, model TPM, and SKU TPM policies executed;
   - how many backend attempts occurred.

### Temporary structured branch traces

Add temporary `trace` policies because the nested `choose` structure otherwise makes the semantic
decision path difficult to compare across requests. Apply the same trace event names to the
customer effective policy and the comparison `apim-foundry-policy` wherever equivalent branches
exist.

Do not trace every policy statement. Emit one event only when a meaningful branch decision or
backend attempt occurs.

#### Trace guard

All custom traces must be gated by:

- an explicit debug-enabled named value;
- the one selected APIM subscription ID;
- an absolute UTC expiry time;
- the approved API ID.

Use explicit names such as `llmmgmt-debug-tracing-enabled`,
`llmmgmt-debug-tracing-subscription-id`, `llmmgmt-debug-tracing-expiry-utc`, and
`llmmgmt-debug-tracing-api-id`. These values are configuration, not secrets, but must still be
removed or disabled after the test.

Set one Boolean variable near the beginning of inbound processing and wrap every custom trace with
that guard. Default the named value to disabled. The UTC expiry must cause tracing to stop even if
an operator forgets to disable the flag.

The APIM `trace` policy is not affected by Application Insights sampling, so an unguarded trace can
create substantial telemetry volume. Use `information` for branch decisions and `error` only for
mapping/config failures. Confirm the diagnostic verbosity accepts the selected severity.

#### Trace schema

Use a single literal source such as `llmmgmt-branch-debug` and structured metadata:

- `event`: stable branch event name;
- `requestId`: `context.RequestId`;
- `apiId`;
- `operationId`;
- `productId`;
- `subscriptionId`;
- `model`;
- `backendId`, when selected;
- `configuredLimit`, only for nonsecret numeric RPM/TPM values;
- `estimatePromptTokens`, when applicable;
- `backendAttempt`, when applicable;
- `previousBackendStatus`, when applicable.

Never emit authorization headers, subscription keys, managed-identity tokens, JWT claims, request
or response bodies, prompts, mapping blob contents, complete `llmmgmt-config`, or backend URLs.

#### Required branch events

| Event | Emit when | Purpose |
|---|---|---|
| `mapping.cache.hit` | Cached mapping is present after lookup. | Proves which mapping path ran. |
| `mapping.cache.miss` | Cached mapping is empty and blob retrieval starts. | Separates cache behavior from rate-limit behavior. |
| `mapping.fetch.success` | Blob response is valid and mapping is stored. | Confirms fresh configuration was loaded. |
| `mapping.fetch.failure` | Fetch/parse fails or mapping remains empty. | Explains 503/config failures. |
| `config.found` | Product/model configuration resolves. | Records safe model/backend/limit metadata. |
| `config.not-found` | Product/model configuration is null. | Explains the deployment-not-found path. |
| `backend.override` | Existing override branch is selected. | Proves the effective-policy bypass path; omit where no override exists. |
| `rpm.configured` | Positive `skuGlobalMaxCallsPerMinute` is used. | Distinguishes configured RPM from fallback. |
| `rpm.fallback-20000` | Missing/nonpositive RPM uses the fallback. | Proves H8 directly. |
| `model-tpm.multipart` | Multipart model TPM branch runs. | Records `estimatePromptTokens=false`. |
| `model-tpm.streaming` | Streaming model TPM branch runs. | Records `estimatePromptTokens=true`. |
| `model-tpm.nonstreaming` | JSON/nonstreaming model TPM branch runs. | Records `estimatePromptTokens=false`. |
| `model-tpm.disabled` | Model TPM value is absent/nonpositive. | Makes a skipped limiter explicit. |
| `sku-tpm.multipart` | Multipart SKU TPM branch runs. | Records the subscription-scoped limiter path. |
| `sku-tpm.streaming` | Streaming SKU TPM branch runs. | Records `estimatePromptTokens=true`. |
| `sku-tpm.nonstreaming` | JSON/nonstreaming SKU TPM branch runs. | Records `estimatePromptTokens=false`. |
| `sku-tpm.disabled` | SKU TPM value is absent/nonpositive. | Makes a skipped limiter explicit. |
| `backend.attempt` | Immediately before each `forward-request` execution. | Counts original and retry attempts. |
| `outbound.summary` | Outbound processing begins. | Records response status, attempt count, and available consumed/remaining counters. |

To produce `backend.attempt`, initialize a request-scoped integer before backend execution and
increment it inside the retry block immediately before `forward-request`. Because the retry policy
re-executes its child policies, this gives a deterministic backend-attempt count. The increment and
trace must not alter the retry condition or response.

Do not depend on a custom trace inside `on-error`. Use the native APIM error trace plus
`context.LastError` information already present in the retrieved debug trace, because the custom
`trace` policy's documented sections are inbound, backend, and outbound.

#### Instrumentation validation and rollback

1. Save the unchanged effective policy and its revision/ETag.
2. Add only guarded trace statements and the backend-attempt diagnostic variable.
3. Validate policy syntax before activating the debug flag.
4. With the flag disabled, send one smoke request and confirm no custom branch events appear.
5. Enable the flag with a short UTC expiry and send one traced nonstreaming request.
6. Confirm exactly one applicable event appears for mapping, config, RPM, model TPM, SKU TPM, and
   each backend attempt.
7. Confirm no prohibited data appears in request tracing, Application Insights, or resource logs.
8. Run the controlled tests.
9. Disable the flag immediately after testing.
10. Remove the temporary trace statements and diagnostic counter, restore the prior policy, and
    verify the effective policy matches the saved baseline.

### Enabling APIM request tracing

Do not use the retired `Ocp-Apim-Trace` mechanism. Use a time-limited API debug credential:

1. Call `listDebugCredentials` for the existing API and managed gateway.
2. Send the returned token in `Apim-Debug-Authorization`.
3. Save `Apim-Trace-Id` from the response.
4. Call `listTrace` with that trace ID.

Management endpoints:

```text
POST https://management.azure.com/subscriptions/{azureSubscriptionId}/resourceGroups/{resourceGroup}/providers/Microsoft.ApiManagement/service/{apimName}/gateways/managed/listDebugCredentials?api-version=2023-05-01-preview

POST https://management.azure.com/subscriptions/{azureSubscriptionId}/resourceGroups/{resourceGroup}/providers/Microsoft.ApiManagement/service/{apimName}/gateways/managed/listTrace?api-version=2024-06-01-preview
```

Debug credential body:

```json
{
  "credentialsExpireAfter": "PT1H",
  "apiId": "/subscriptions/{azureSubscriptionId}/resourceGroups/{resourceGroup}/providers/Microsoft.ApiManagement/service/{apimName}/apis/{apiId}",
  "purposes": ["tracing"]
}
```

Trace retrieval body:

```json
{
  "traceId": "{Apim-Trace-Id}"
}
```

## Phase 2: Apply temporary low-cost mapping values

After the unchanged baseline and guarded branch instrumentation validation are complete:

Prepare a local candidate only after the smoke request supplies actual token usage and the native
backend deployment TPM is known:

```powershell
.\scripts\prepare-apim-limit-test-mapping.ps1 `
  -MappingFile .\untracked\new_v2-mapping.json `
  -ProductName ai-hybrid-data-sources-lob-oai-small-v2 `
  -CalibratedRequestTokens <actual-total-tokens> `
  -BackendDeploymentTpm <native-deployment-tpm>
```

The preparer does not contact Azure or publish the mapping. It writes an ignored candidate mapping
and safety manifest under `untracked/`, preserves all model and backend assignments, treats a
missing/nonpositive RPM as the policy's `20000` fallback, caps the temporary RPM at `20`, and
refuses a calculated model TPM that is not below the supplied native deployment TPM. The manifest
always records `publishAuthorized: false`; completing the following gates is still required before
using the separate publisher.

1. Update only the selected existing product/model mapping used for the controlled test, after
   confirming that exactly one APIM subscription is attached.
2. Keep all existing model deployments and backend assignments unchanged.
3. Apply the calculated/capped RPM and TPM values from **Safety and cost controls**.
4. Record the new mapping ETag and exact UTC update time.
5. Account for the policy's internal mapping cache:
   - wait for the cache TTL, or use the team's existing safe cache-refresh procedure;
   - do not assume the blob update is active immediately.
6. Send traced control requests through every existing serving gateway/region and confirm the
   resolved `llmmgmt-config` contains the temporary values.
7. Verify zero unrelated traffic for the affected product/model, then wait at least 75 seconds to
   clear prior one-minute counter activity.
8. Do not begin load tests until every serving path shows the temporary values and the quiet
   interval has completed.

## Phase 3: Add the threshold-debug workbook

Create a new Azure Monitor Workbook before running the reproduction tests. The workbook is a test
deliverable and does not require a new Log Analytics workspace, Application Insights component,
APIM subscription, model, or backend.

### Planned implementation

Follow the existing workbook-as-Bicep pattern:

- Add `infra/ai-gateway-threshold-debug-workbook.bicep`.
- Deploy it as a new module from `infra/resources.bicep`.
- Use the existing Log Analytics workspace, Application Insights component, and APIM resource IDs.
- Use `Microsoft.Insights/workbooks@2023-06-01`, `kind: 'shared'`, and a stable
  `guid(resourceGroup().id, 'ai-gateway-threshold-debug-${resourceToken}')` name.
- Add workbook ID, name, and display-name outputs following the existing workbook modules.
- Update the existing observability documentation when the workbook is implemented.

Keep this as a separate debug workbook rather than overloading the existing usage workbook. It can
be retained after the investigation if operators find it useful.

### Workbook parameters

Add these filters and controls:

- `TimeRange`, default 4 hours, with 30-minute, 1-hour, 4-hour, 12-hour, and custom options.
- APIM product ID.
- APIM subscription ID.
- deployment/model.
- backend ID.
- gateway/region.
- test start and end UTC timestamps.
- `SkuRpmThreshold`.
- `SkuTpmThreshold`.
- `ModelTpmThreshold`.
- `BackendDeploymentTpm`.
- warning percentage, default `80`.

Populate the three threshold parameters with the temporary values used in Phase 2. Use manual
parameters for the first reproduction so the visualization does not depend on adding policy
headers or changing policy logic. If the existing response headers provide reliable limit values,
show those as observed values but do not silently replace the explicit test thresholds.

### Data sources and correlation

Reuse the telemetry paths already provisioned by this repository:

- `ApiManagementGatewayLogs` for unsampled APIM request totals, response codes, subscription,
  product, backend, URL/deployment, latency, and gateway/region where available.
- `AppRequests` for the captured `x-llmmgmt-*` response headers.
- `AppDependencies` for backend dependency attempts only after telemetry readiness proves retry
  attempts are emitted separately.
- `AppMetrics` for native AI Gateway prompt, completion, and total-token metrics where available.
- `AppTraces` or resource logs for guarded branch decisions and backend-attempt events.

Join `ApiManagementGatewayLogs.CorrelationId` to `AppRequests.Properties["Request Id"]`. Use the
Application Insights operation ID to correlate requests and backend dependencies. Preserve
unmatched rows in a diagnostic table instead of dropping them silently.

### Required visualizations

1. **Breach status tiles**
   - current/peak observed RPM;
   - current/peak SKU TPM;
   - current/peak model TPM;
   - count of RPM breach intervals;
   - count of TPM breach intervals;
   - APIM 429 count;
   - retry amplification ratio (`backend attempts / APIM accepted requests`).
   - Color rules: green below warning percentage, amber from warning percentage through 100%,
     and red above 100%.

2. **RPM versus threshold time chart**
   - accepted APIM requests per interval;
   - rejected 429 requests;
   - backend dependency attempts;
   - `SkuRpmThreshold` as a constant reference line;
   - red breach points/columns where observed RPM exceeds the threshold.

3. **SKU TPM versus threshold time chart**
   - actual total tokens grouped by APIM subscription across all selected models;
   - `SkuTpmThreshold` as a constant reference line;
   - breach ratio (`observed / threshold`);
   - red breach points/columns above 100%.

4. **Model TPM versus threshold time chart**
   - actual total tokens split by subscription and model;
   - `ModelTpmThreshold` reference line;
   - label this as the **subscriber + model policy ceiling**, not backend deployment capacity;
   - separate series for each existing model selected by the filter.

5. **Shared backend deployment capacity chart**
   - actual tokens from the one selected APIM subscription routed to the deployment;
   - `BackendDeploymentTpm` as a constant reference line;
   - clearly state that this single-subscription view does not represent future aggregate use;
   - highlight native deployment-capacity responses separately from APIM policy breaches.

6. **Remaining-counter chart**
   - RPM remaining;
   - model TPM remaining;
   - SKU TPM remaining;
   - a zero reference line;
   - highlight negative, zero, missing, and reset values distinctly.

7. **Retries and backend amplification**
   - APIM accepted requests versus backend dependency attempts;
   - requests grouped by backend response code;
   - table of request/operation IDs with more than one backend attempt.

8. **Gateway/region split**
   - RPM and TPM by gateway/region;
   - aggregate total alongside each gateway-local total;
   - red aggregate breaches even when every individual gateway remains below its local limit.

9. **Cross-model RPM partition**
   - requests by model and subscription;
   - aggregate requests across models;
   - make it visually obvious when each model is under the RPM limit but the aggregate is over it.

10. **Request-level evidence table**
   - UTC timestamp;
   - APIM request/correlation ID;
   - Application Insights operation ID;
   - product, subscription, model, backend, and gateway/region;
   - APIM and backend status;
   - token consumed/remaining/limit fields;
   - calls remaining and retry-after;
   - backend attempt count;
   - calculated breach type and breach ratio.
   - Apply red conditional formatting to confirmed breaches and amber formatting to missing limit
     telemetry.

11. **Data-quality tiles**
    - gateway rows without a matching `AppRequests` row;
    - requests without token usage;
    - requests without model/deployment;
    - requests without threshold values;
    - sampling notice based on available telemetry.

12. **Branch-decision timeline**
    - branch events ordered by timestamp and grouped by APIM request ID;
    - mapping source, config resolution, RPM branch, model TPM branch, SKU TPM branch, backend
      attempts, and outbound summary;
    - highlight requests missing an expected branch event;
    - allow drill-through from a breach row to its full branch sequence.

### Window-semantics warning

Display this warning at the top of the workbook:

> Workbook one-minute bins are an observational aid. They do not reproduce APIM's internal
> sliding-window or v2 token-bucket state exactly. Use remaining-counter headers and request traces
> to confirm a policy breach.

Provide both:

- clock-aligned one-minute charts for comparison with existing dashboards; and
- request-level remaining-counter views for policy-focused evidence.

Do not label a clock-aligned telemetry-bin excess as a confirmed APIM enforcement failure by
itself.

### Workbook validation

Before load testing:

1. Compile the Bicep workbook and parent template.
2. Open the workbook with the existing APIM/product/subscription/model filters selected.
3. Send one minimal traced request and wait for ingestion.
4. Confirm the request appears in the evidence table with the same correlation/operation IDs.
5. Confirm the configured temporary RPM/TPM reference lines equal the Phase 2 values.
6. Use a deliberately low workbook-only threshold parameter to verify red/amber/green formatting
   without consuming extra model tokens.
7. Reset the workbook threshold parameters to the real temporary test values.
8. Confirm empty/missing telemetry renders as unknown, not zero or healthy.

Capture workbook screenshots or exported query results at each proven breach and record the
corresponding APIM trace IDs. The raw trace and query results remain the authoritative evidence.

## Phase 4: Add the UI limit-exercise custom agent

Implement a user-invocable GitHub Copilot custom agent at:

```text
.github/agents/apim-limit-ui-tester.agent.md
```

The agent exists to exercise the customer's existing UI and deliberately cross the temporary test
RPM/TPM thresholds by a small, bounded amount. It must not create a subscription, model, backend,
gateway, or any other Azure resource.

### Agent profile

The `.agent.md` file must contain YAML frontmatter and Markdown instructions following GitHub's
custom-agent format. Use a descriptive profile similar to:

```yaml
---
name: APIM Limit UI Tester
description: Exercises the existing customer UI to reproduce bounded APIM RPM/TPM breaches and capture correlated evidence.
target: vscode
user-invocable: true
disable-model-invocation: true
tools:
  - <browser navigation and page-reading tool>
  - <Playwright execution tool>
  - <screenshot tool>
  - <read-only workspace search/read tools>
---
```

Resolve the exact installed browser tool IDs when implementing the agent. Grant only browser
automation, screenshots, and read-only workspace access. Do not grant file editing, shell, Azure
resource mutation, deployment, or secret-management tools. If the required browser tools are not
available, the agent must stop rather than silently switch to direct API load generation.

Setting `disable-model-invocation: true` prevents Copilot from selecting this cost-generating agent
automatically. A human must explicitly invoke it. `target: vscode` prevents the profile from being
treated as a GitHub cloud-agent workload that cannot reach the external customer UI.

### Deterministic Playwright routine

The agent must run one bounded Playwright routine for each scenario. The complete run manifest must
be passed to that routine before the first browser action. The routine must:

- reject unknown scenarios and unapproved hosts;
- parse and validate UTC start/end times;
- clamp attempts and concurrency to the lower of operator values and plan limits;
- maintain attempt, accepted-response, 429, and token counters in code;
- cancel outstanding work when a stop condition is reached;
- reject direct `fetch`, `XMLHttpRequest`, or HTTP-client load generation;
- return a structured result to the agent.

The agent must not implement the load loop as repeated free-form tool decisions. If the browser
tool cannot execute the bounded routine atomically, report `BLOCKED_DETERMINISTIC_RUNNER`.

### Required operator inputs

The agent must require and echo a sanitized run manifest before sending traffic:

- existing UI URL;
- test start/end UTC window;
- selected scenario;
- existing model/deployment name;
- second existing model only when running the cross-model scenario;
- `testRPM`, `testSkuTPM`, and `testModelTPM`;
- existing backend model deployment TPM;
- response-token cap;
- calibrated request-token count from the one-request smoke calibration;
- maximum request attempts;
- maximum concurrency;
- workbook URL;
- whether APIM tracing has already been enabled for the run.
- approved UI and workbook host names;
- existing browser-visible correlation mechanism (`traceparent` or response correlation header).

Never place credentials, APIM subscription keys, tokens, or customer prompts in the agent file,
run manifest, screenshots, console output, or committed artifacts. Reuse an already authenticated
browser session. If authentication is required, pause for the operator; never attempt to bypass
authentication or scrape credentials.

### Agent safety contract

The agent must enforce all of these controls:

1. Refuse to run unless the operator confirms the Phase 2 temporary limits are active and visible
   in traced control calls from every serving gateway/region.
2. Refuse to run unless `testModelTPM > testSkuTPM` and both are below the existing backend model
   deployment TPM.
3. Refuse to run outside the declared UTC test window.
4. Use only synthetic, non-sensitive prompts.
5. Set the smallest response-token cap supported by the UI, targeting 8 tokens.
6. Start with concurrency 1; increase to 2 and then at most 4 only for the concurrency scenario.
7. Never exceed the lower of:
   - the operator-provided maximum request attempts;
   - `testRPM + 2` for serial RPM testing;
   - the request count needed to target 1.25x `testSkuTPM` for TPM testing.
8. Stop immediately after the first conclusive threshold result:
   - HTTP 429;
   - visible UI throttling error;
   - a remaining counter at or below zero;
   - observed token usage above the temporary threshold;
   - the workbook showing a red breach backed by correlated request IDs.
9. Stop on unexpected 401, 403, repeated 5xx, navigation away from the approved hosts, missing
   model controls, or any indication that unrelated users are being throttled.
10. Never retry a 429 automatically. Record `Retry-After`, wait only when the selected scenario
   explicitly tests recovery, and perform at most one recovery request.
11. Never change policies, mapping values, workbook thresholds, application settings, or Azure
    resources.
12. Refuse UI load with `BLOCKED_CORRELATION` if no existing browser-visible correlation value can
    be joined to APIM telemetry.

### UI discovery and interaction rules

The customer UI is deployed separately from this infrastructure repository, so selectors are not
available here. At runtime the agent must:

1. inspect the rendered page and identify controls by accessible role, label, or test ID;
2. identify the existing model selector, prompt input, response-token control if exposed, send
   control, response area, and error notification;
3. verify the selected model immediately before each scenario; when the UI is fixed-model and has
   no selector, verify `/deployments/{model}/` from every passively observed UI request and do not
   run `cross-model-rpm`;
4. use normal UI interactions for every generated request;
5. use multiple browser pages/contexts for controlled concurrency rather than calling APIM or
   Foundry directly;
6. observe browser network responses without modifying request destinations or injecting
   credentials;
7. stop and report `BLOCKED_SELECTOR_AMBIGUITY` if any required control cannot be identified
   unambiguously.

The agent may use Playwright evaluation for synchronization, network observation, and bounded
parallel page interaction. It must not use `fetch`, `XMLHttpRequest`, or a direct HTTP client to
bypass the UI.

### Agent scenarios

The agent must expose these named scenarios:

1. **`smoke`**
   - Submit one minimal prompt.
   - Confirm the UI renders a response and capture the request/response correlation evidence.

2. **`rpm-serial`**
   - Submit one request at a time through the UI.
   - Stop at the first 429/UI throttle indication or after `testRPM + 2` attempts.
   - Capture remaining-call and retry-after headers when visible in network responses.

3. **`rpm-concurrent`**
   - Use two browser pages, increasing to four only if no result is obtained.
   - Send synchronized minimal prompts through normal UI actions.
   - Stop immediately when the bounded breach condition is met.

4. **`tpm-serial`**
   - Submit minimal deterministic prompts one at a time with the configured response-token cap.
   - Accumulate actual token values from observed responses/telemetry.
   - Stop after the first conclusive TPM throttle or threshold result.

5. **`tpm-concurrent`**
   - Use two pages initially and target only 1.25x the temporary SKU TPM.
   - Increase to at most four pages only when required to reproduce the concurrency overshoot.

6. **`cross-model-rpm`**
   - Run only when two existing UI-selectable models are already available.
   - Send bounded traffic to each model in the same window.
   - Demonstrate whether per-model buckets allow aggregate RPM above the SKU threshold.

7. **`recovery-after-429`**
   - Run only after another scenario records a 429 and `Retry-After`.
   - Wait for the indicated period and submit exactly one additional UI request.
   - Record whether service recovers as expected.

8. **`workbook-visual-check`**
   - Open the existing threshold-debug workbook after telemetry ingestion.
   - Apply the same test-window, subscription, model, backend, and gateway filters.
   - Capture the red threshold visualization and request-level evidence rows.
   - Do not alter workbook threshold parameters during this scenario.

### Agent evidence bundle

For each invocation, the agent must produce a sanitized run summary in the session artifacts, not
commit it automatically. Include:

- run ID and scenario;
- UTC start/end time;
- UI and workbook host names only;
- temporary thresholds and safety caps;
- selected existing model(s);
- whether the UI uses a selector or a fixed model verified from the observed deployment request
  path;
- attempts, accepted responses, 429s, and UI errors;
- observed token totals and remaining counters;
- retry-after value;
- browser-visible `traceparent` or response correlation IDs for UI calls;
- `Apim-Trace-Id` values from the separate direct traced control calls;
- backend attempt count when available from the workbook;
- final stop reason;
- screenshots before load, at the first breach, and in the workbook;
- a redacted browser-network summary containing status, timing, safe rate-limit headers, and
  correlation IDs;
- verdict: `PROVEN`, `NOT_REPRODUCED`, `BLOCKED`, or `ABORTED_SAFETY`.

The agent must not claim `PROVEN` from a screenshot alone. The breach screenshot must correlate to
raw telemetry and at least one APIM request/trace ID.

### Agent acceptance tests

Before allowing the agent to run a paid limit test:

1. Validate the `.agent.md` frontmatter and confirm it is discoverable as a custom agent.
2. Confirm `target: vscode` and verify the installed browser tools can reach the approved external
   UI and workbook hosts.
3. Validate the deterministic routine rejects unknown hosts, invalid UTC windows, excessive
   attempts, and excessive concurrency before any browser action.
4. Run `smoke` with one request and prove its browser-visible correlation value joins to the
   expected APIM telemetry row.
5. Confirm no secrets appear in screenshots, logs, network summaries, or session artifacts.
6. Set a workbook-only threshold below the smoke request's observed value and run
   `workbook-visual-check` to validate red highlighting without extra token consumption.
7. Verify an intentionally tiny `maximum request attempts` value causes the routine to stop at that
   exact bound.
8. Verify an out-of-window run is refused without sending a request.
9. Verify a simulated ambiguous selector returns `BLOCKED_SELECTOR_AMBIGUITY`.
10. Verify a missing correlation mechanism returns `BLOCKED_CORRELATION`.
11. Reset the workbook threshold parameters to the real temporary test values.

## Phase 5: Reproduction tests

Run tests sequentially. Wait at least 75 seconds between tests so a prior one-minute counter window
does not contaminate the next result. Use a unique existing browser correlation value for every UI
request and a new APIM debug trace ID for every separate direct control request. Run the
UI-generated portions through the custom agent:

| Reproduction test | Agent scenario |
|---|---|
| Test A serial pass | `rpm-serial` |
| Test A concurrent pass | `rpm-concurrent` |
| Test B | `cross-model-rpm` |
| Test C | `tpm-serial` |
| Test D | `tpm-concurrent` |
| Post-test workbook proof | `workbook-visual-check` |

Tests E, F, G, and H remain trace/telemetry analyses unless an existing UI route naturally covers
them. Do not extend the agent to create failures, override routes, regions, gateways, or model
configurations.

### Test A: Single-model RPM control

Purpose: establish normal RPM enforcement for one existing model.

1. Send requests serially at a steady rate until `testRPM + 2` attempts have been made.
2. Keep prompts and responses minimal.
3. Expected result:
   - no more than approximately `testRPM` requests are accepted in the window;
   - excess requests return 429;
   - remaining-call headers trend toward zero.
4. Repeat as a short concurrent burst to measure documented distributed-rate-limit variance.
5. Record exact accepted count; do not require mathematical precision from `rate-limit-by-key`.

### Test B: Cross-model RPM partition

Run only if the existing mapping already exposes at least two models. Do not deploy a new model.

1. Send up to `testRPM` minimal requests to existing model A.
2. In the same window, send up to `testRPM` minimal requests to existing model B.
3. Expected result if H1 is true:
   - each model has its own remaining-call progression;
   - accepted aggregate calls approach `2 * testRPM`;
   - aggregate calls exceed `skuGlobalMaxCallsPerMinute` without the expected SKU-global 429.
4. If only one model is currently available, mark H1 as proven by static key analysis but not
   dynamically reproduced; do not create another deployment solely for this test.

### Test C: SKU TPM, non-streaming, serial

Purpose: establish that the lower subscriber + model control protects before the higher
subscriber SKU control under low concurrency.

1. Use one existing model.
2. Confirm `testModelTPM < testSkuTPM` and the backend deployment TPM is higher than both.
3. Set a small fixed response-token cap.
4. Send requests one at a time and wait for each response.
5. Sum actual total tokens from backend responses.
6. Expected result:
   - consumed/remaining headers update after responses;
   - after actual usage reaches the temporary model TPM, a subsequent request is blocked before
     the SKU-global limit is reached.

### Test D: SKU TPM concurrency overshoot

Purpose: prove or reject H4 for both the lower model counter and higher SKU-global counter.

1. Use the same request as Test C.
2. Start a burst whose estimated aggregate actual tokens are 1.25x to 1.5x `testSkuTPM`.
3. Keep the burst small; start with concurrency 2, then 4 only if necessary.
4. Expected result if H4 is true:
   - concurrent requests pass inbound before preceding responses update either counter;
   - actual Foundry tokens temporarily exceed `testModelTPM` and may exceed `testSkuTPM`;
   - later requests return 429 until the counter recovers.
5. Compare non-streaming and streaming behavior. Streaming token usage is estimated by APIM and may
   differ from Foundry actual token usage.

### Test E: Retry amplification

Purpose: determine whether backend retries explain API-call excess.

1. First search existing diagnostics for naturally occurring 408/429/5xx responses during the
   test period; do not intentionally destabilize a production backend.
2. Select traced requests whose first backend attempt returned a retryable status.
3. Count backend attempts associated with the same APIM request/trace ID.
4. Expected result if H3 is true:
   - inbound RPM decrements once;
   - the backend section records multiple `forward-request` attempts;
   - Foundry/backend request count is greater than APIM accepted request count.
5. Do not force failures unless the team already has a safe, existing test mechanism.

### Test F: Override branch

Run only if an existing route already sets `OVERRIDE_BACKEND_SERVICE_URL`.

1. Send the same minimal traced request through the normal and override routes.
2. Expected result if H2 is true:
   - normal route trace executes RPM and both TPM controls;
   - override route trace reaches `set-backend-service` without those controls;
   - limit headers are absent or show defaults on the override response.
3. Do not add an override solely to reproduce this hypothesis.

### Test G: Regional/gateway split

Run only if the existing service already uses multiple regional or workspace gateways.

1. Group existing request telemetry by gateway/region.
2. Repeat a small burst through the currently available routing paths.
3. Expected result if H5/H6 is true:
   - each gateway enforces a local counter;
   - aggregate accepted calls/tokens can exceed the configured value.
4. Do not add a region or gateway for this test.

### Test H: Counter-value consistency

1. Compare `skuGlobalMaxTokensPerMinute` for every existing model under the selected mapping.
2. The SKU TPM counter key is only the APIM subscription ID.
3. If values differ, trace one request to each existing model in alternating order.
4. Record the applied value and remaining-token behavior.
5. On APIM v2 tiers, treat differing limits for the same counter key as a confirmed configuration
   defect even if a short test does not visibly fail.

## Result table

Populate this table from the evidence:

| Test | Agent run ID/scenario | UTC window | Gateway/region | Model | Client attempts | APIM accepted | APIM 429 | Backend attempts | Actual tokens | Result |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|
| A | | | | | | | | | | |
| B | | | | | | | | | | |
| C | | | | | | | | | | |
| D | | | | | | | | | | |
| E | N/A | | | | | | | | | |
| F | N/A | | | | | | | | | |
| G | N/A | | | | | | | | | |
| H | N/A | | | | | | | | | |

## Proof criteria

A hypothesis is proven only when:

- request timestamps and trace IDs correlate APIM and Foundry records;
- the effective policy branch and resolved counter key are known;
- retries are counted separately from client requests;
- results are grouped by APIM subscription, model, and gateway/region;
- APIM estimated tokens are not presented as Foundry actual tokens;
- the temporary mapping values are visible in a trace;
- the guarded branch-event sequence identifies the mapping, config, RPM, model TPM, SKU TPM, and
  backend-attempt paths for each direct control request;
- every workbook breach links back to raw query results and one or more request/trace IDs;
- the agent stayed within its machine-enforced request, concurrency, token, host, and UTC-window
  bounds;
- no result includes traffic from unrelated callers in the affected product/model window.

## Decision gate before policy changes

Do not modify policy logic until the team has:

1. passed and recorded every hard precondition;
2. completed Tests A, C, and D;
3. completed every conditional test applicable to the existing topology;
4. passed the custom agent acceptance tests and retained its sanitized evidence bundle;
5. validated the threshold-debug workbook and captured the applicable breach views;
6. identified which hypotheses are proven;
7. restored the original mapping values and verified them on every serving gateway/region;
8. disabled and removed temporary branch instrumentation and verified the effective policy matches
   the saved baseline;
9. verified normal traffic after rollback;
10. confirmed that this test's “SKU global” scope means the one existing APIM subscription across
   its selected models.

That scope decision determines the correct counter keys and cannot be inferred from the variable
names alone.

## Likely remediation candidates after proof

These are intentionally deferred until the decision gate:

- Remove the model from the RPM counter key if RPM is intended to aggregate across models.
- Add explicit delimiters and scope prefixes to counter keys.
- Apply the same controls to the override branch or remove that bypass.
- Make `skuGlobalMaxTokensPerMinute` identical wherever the same counter key is used.
- Reconsider retry count/statuses or separately cap backend attempts.
- Use prompt estimation where stricter pre-backend TPM enforcement is worth the performance and
  estimation tradeoff.
- Replace the permissive `20000` RPM fallback with fail-closed behavior if a missing configuration
  must never grant a high limit.
- Treat documented distributed/concurrent overshoot as a design tolerance, and set configured
  limits below the hard business ceiling by an evidence-based safety margin.

## Microsoft references

- [rate-limit-by-key policy](https://learn.microsoft.com/azure/api-management/rate-limit-by-key-policy)
- [LLM token limit policy](https://learn.microsoft.com/azure/api-management/llm-token-limit-policy)
- [APIM request tracing](https://learn.microsoft.com/azure/api-management/api-management-howto-api-inspector)
- [APIM trace policy](https://learn.microsoft.com/azure/api-management/trace-policy)
- [Azure Monitor Workbooks](https://learn.microsoft.com/azure/azure-monitor/visualize/workbooks-overview)
- [GitHub Copilot custom agents configuration](https://docs.github.com/copilot/reference/custom-agents-configuration)

Relevant documented behavior:

- Distributed call-rate limiting is not completely precise.
- Call and token counters are tracked independently at each regional/workspace gateway.
- Without prompt estimation, token excess is detected after the backend response.
- Concurrent requests can temporarily exceed a token limit.
- Streaming prompt and completion token counts are estimated.
- APIM v2 tiers require a consistent limit value when the same counter key is used by multiple
  policy instances.

[CmdletBinding()]
param(
  [string] $WorkbookPath = 'infra\apim-limit-debug-workbook.bicep'
)

$ErrorActionPreference = 'Stop'

$raw = Get-Content -LiteralPath $WorkbookPath -Raw
$requiredPanels = @(
  'breach-status'
  'rpm-threshold'
  'sku-token-threshold'
  'model-token-threshold'
  'remaining-counters'
  'retry-amplification'
  'gateway-model-split'
  'request-evidence'
  'data-quality'
  'branch-timeline'
)
$requiredParameters = @(
  'TimeRange'
  'SubscriptionId'
  'Model'
  'BackendId'
  'Gateway'
  'SkuRpmThreshold'
  'SkuTpmThreshold'
  'ModelTpmThreshold'
  'BackendDeploymentTpm'
  'WarningPercentage'
)
$requiredEvidence = @(
  'ApiManagementGatewayLogs'
  'AppRequests'
  'AppDependencies'
  'AppTraces'
  'GatewayCorrelationId'
  'OperationId'
  'BackendAttempts'
  'BREACH'
  'UNKNOWN'
  'rpm.fallback-20000'
  'outbound.summary'
)

$failures = [System.Collections.Generic.List[string]]::new()
foreach ($panel in $requiredPanels) {
  if (-not $raw.Contains("name: '$panel'")) {
    $failures.Add("Missing workbook panel '$panel'.")
  }
}
foreach ($parameter in $requiredParameters) {
  if (-not $raw.Contains("name: '$parameter'")) {
    $failures.Add("Missing workbook parameter '$parameter'.")
  }
}
foreach ($evidence in $requiredEvidence) {
  if (-not $raw.Contains($evidence)) {
    $failures.Add("Missing workbook evidence marker '$evidence'.")
  }
}

if (-not $raw.Contains('Clock-aligned one-minute bins are observational aids')) {
  $failures.Add('Missing APIM window-semantics warning.')
}
$parameterPanelIndex = $raw.IndexOf("name: 'parameters'")
$overviewPanelIndex = $raw.IndexOf("name: 'overview'")
if ($parameterPanelIndex -lt 0 -or
    $overviewPanelIndex -le $parameterPanelIndex) {
  $failures.Add('The parameter bar, including the Time period picker, must be the first workbook item.')
}
if (-not $raw.Contains("label: 'Time period'") -or
    -not $raw.Contains('allowCustom: true')) {
  $failures.Add('Missing top-level Time period picker with custom-range support.')
}
$skuTokenPanelIndex = $raw.IndexOf("name: 'sku-token-threshold'")
$modelTokenPanelIndex = $raw.IndexOf("name: 'model-token-threshold'")
$rpmPanelIndex = $raw.IndexOf("name: 'rpm-threshold'")
$remainingPanelIndex = $raw.IndexOf("name: 'remaining-counters'")
if ($skuTokenPanelIndex -lt 0 -or
    $modelTokenPanelIndex -le $skuTokenPanelIndex -or
    $rpmPanelIndex -le $modelTokenPanelIndex -or
    $remainingPanelIndex -le $rpmPanelIndex) {
  $failures.Add('Primary panels must be ordered global TPM, per-model TPM, RPM, then request-level diagnostics.')
}
foreach ($title in @(
    '1a. TPM - Subscription-global actual tokens per minute (each request counted once)'
    '1b. TPM - Per-model actual tokens per minute (partitioned, not added to global)'
    '2. RPM - Aggregate accepted calls per minute vs mapped SKU-global limit'
    '3. Diagnostic only - Remaining counters per request'
    'Cross-model RPM proof - aggregate exceeds limit while model buckets do not'
  )) {
  if (-not $raw.Contains($title)) {
    $failures.Add("Missing clear workbook panel title '$title'.")
  }
}
foreach ($proofMarker in @(
    'SubscriptionGlobalTokens = sum(SkuTokens)'
    'MiniTokens = sumif(ModelTokens, Model == "gpt-5.4-mini")'
    'NanoTokens = sumif(ModelTokens, Model == "gpt-5.4-nano")'
    "thresholdValue: '{SkuTpmThreshold}'"
    "thresholdValue: '{ModelTpmThreshold}'"
    'AggregateAccepted'
    'PeakModelAccepted'
    'GLOBAL_NAME_BUT_MODEL_PARTITIONED'
  )) {
  if (-not $raw.Contains($proofMarker)) {
    $failures.Add("Missing mapped-limit proof marker '$proofMarker'.")
  }
}
if (-not $raw.Contains("name: 'Model'") -or -not $raw.Contains("value: ''")) {
  $failures.Add('The optional model filter must default to empty so subscription-global charts include every model.')
}
if ($raw.Contains('MappedLimit = skuThreshold') -or
    $raw.Contains('MappedLimit = modelThreshold') -or
    $raw.Contains('| project TimeGenerated, Series, ActualTokens, MappedLimit, Breach')) {
  $failures.Add('TPM charts must not emit repeated mapped limits as summable query-result columns.')
}
if (-not $raw.Contains('ApimSubscriptionId = tostring(Properties["Subscription Name"])') -or
    -not $raw.Contains('| where isempty(subscriptionFilter) or ApimSubscriptionId == subscriptionFilter')) {
  $failures.Add('The TPM panel must scope both request and gateway telemetry to the selected APIM subscription.')
}
foreach ($backendCapacityMarker in @(
    'BackendThreshold'
    'let backendThreshold'
  )) {
  if ($raw.Contains($backendCapacityMarker)) {
    $failures.Add("The controlled-limit workbook must not report or chart native backend capacity ('$backendCapacityMarker').")
  }
}
if (-not $raw.Contains('Native backend deployment TPM (context only; not charted)')) {
  $failures.Add('The native backend capacity parameter must be retained and labeled as context only.')
}
if ($raw.Contains('Microsoft.OperationalInsights/workspaces@') -or
    $raw.Contains('Microsoft.Insights/components@')) {
  $failures.Add('The workbook must reuse existing telemetry resources.')
}
if ($raw.Contains('UNKNOWN", 0') -or $raw.Contains('coalesce(Tokens, 0)')) {
  $failures.Add('Missing telemetry must not be rendered as zero.')
}

if ($failures.Count -gt 0) {
  throw ($failures -join [Environment]::NewLine)
}

Write-Output 'Validated APIM RPM/TPM threshold-debug workbook structure.'

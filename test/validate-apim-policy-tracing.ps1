[CmdletBinding()]
param(
    [string[]] $PolicyPaths = @(
        'peering\modules\apim-foundry-policy.xml'
    )
)

$ErrorActionPreference = 'Stop'

$requiredEvents = @(
    'mapping.cache.hit',
    'mapping.cache.miss',
    'mapping.fetch.success',
    'mapping.fetch.failure',
    'config.found',
    'config.not-found',
    'rpm.configured',
    'rpm.fallback-20000',
    'model-tpm.multipart',
    'model-tpm.streaming',
    'model-tpm.nonstreaming',
    'model-tpm.disabled',
    'sku-tpm.multipart',
    'sku-tpm.streaming',
    'sku-tpm.nonstreaming',
    'sku-tpm.disabled',
    'backend.attempt',
    'outbound.summary'
)

$requiredPlaceholders = @(
    '__DEBUG_TRACING_ENABLED__',
    '__DEBUG_TRACING_SUBSCRIPTION_ID__',
    '__DEBUG_TRACING_EXPIRY_UTC__',
    '__DEBUG_TRACING_API_ID__'
)

$failures = [System.Collections.Generic.List[string]]::new()
$resolvedPolicies = [System.Collections.Generic.List[string]]::new()

foreach ($policyPath in $PolicyPaths) {
    $resolvedPath = (Resolve-Path -LiteralPath $policyPath).Path
    $resolvedPolicies.Add($resolvedPath)
    $raw = Get-Content -Raw -LiteralPath $resolvedPath

    try {
        [xml] $xml = $raw
    }
    catch {
        $failures.Add("${policyPath}: invalid XML: $($_.Exception.Message)")
        continue
    }

    foreach ($placeholder in $requiredPlaceholders) {
        if (-not $raw.Contains($placeholder)) {
            $failures.Add("${policyPath}: missing trace guard placeholder $placeholder")
        }
    }

    $guardVariables = @($xml.SelectNodes('//set-variable[@name="llmmgmt-debug-tracing-enabled"]'))
    if ($guardVariables.Count -ne 1) {
        $failures.Add("${policyPath}: expected one llmmgmt-debug-tracing-enabled variable, found $($guardVariables.Count)")
    }

    $branchTraces = @($xml.SelectNodes('//trace[@source="llmmgmt-branch-debug"]'))
    $actualEvents = @(
        $branchTraces |
            ForEach-Object { $_.SelectSingleNode('./metadata[@name="event"]') } |
            Where-Object { $null -ne $_ } |
            ForEach-Object { $_.GetAttribute('value') }
    )

    foreach ($eventName in $requiredEvents) {
        $count = @($actualEvents | Where-Object { $_ -eq $eventName }).Count
        if ($count -ne 1) {
            $failures.Add("${policyPath}: expected one '$eventName' trace event, found $count")
        }
    }

    foreach ($trace in $branchTraces) {
        $guard = $trace.ParentNode
        if ($guard.Name -ne 'when' -or
            -not $guard.GetAttribute('condition').Contains('llmmgmt-debug-tracing-enabled')) {
            $eventNode = $trace.SelectSingleNode('./metadata[@name="event"]')
            $eventName = if ($null -eq $eventNode) { '<missing>' } else { $eventNode.GetAttribute('value') }
            $failures.Add("${policyPath}: '$eventName' trace is not directly guarded")
        }

        $traceXml = $trace.OuterXml
        foreach ($forbidden in @(
            'Authorization',
            'context.Request.Body',
            'context.Response.Body',
            'api-key',
            'msi-access-token',
            'llmmgmt-mapping'
        )) {
            if ($traceXml.Contains($forbidden)) {
                $failures.Add("${policyPath}: trace contains forbidden data reference '$forbidden'")
            }
        }
    }

    $rateLimits = @($xml.SelectNodes('//rate-limit-by-key'))
    if ($rateLimits.Count -ne 2) {
        $failures.Add("${policyPath}: rate-limit-by-key count changed from 2 to $($rateLimits.Count)")
    }

    $tokenLimits = @($xml.SelectNodes('//azure-openai-token-limit'))
    if ($tokenLimits.Count -ne 6) {
        $failures.Add("${policyPath}: azure-openai-token-limit count changed from 6 to $($tokenLimits.Count)")
    }

    $requestIdHeaders = @($xml.SelectNodes('//set-header[@name="x-llmmgmt-request-id"]'))
    if ($requestIdHeaders.Count -ne 2) {
        $failures.Add("${policyPath}: expected request correlation headers in outbound and on-error")
    }

    $mappingCacheStores = @($xml.SelectNodes('//cache-store-value[@key="llmmgmt-mapping"]'))
    if ($mappingCacheStores.Count -ne 1 -or $mappingCacheStores[0].GetAttribute('duration') -ne '60') {
        $failures.Add("${policyPath}: mapping cache TTL must be 60 seconds for bounded debug promotion")
    }

    $retry = $xml.SelectSingleNode('/policies/backend/retry')
    if ($null -eq $retry -or $retry.GetAttribute('count') -ne '3') {
        $failures.Add("${policyPath}: backend retry count must remain 3")
    }

    $forwardRequests = @($xml.SelectNodes('/policies/backend/retry/forward-request'))
    if ($forwardRequests.Count -ne 1) {
        $failures.Add("${policyPath}: expected one forward-request inside retry, found $($forwardRequests.Count)")
    }

    $attemptVariables = @($xml.SelectNodes('/policies/backend/retry/set-variable[@name="llmmgmt-backend-attempt"]'))
    if ($attemptVariables.Count -ne 1) {
        $failures.Add("${policyPath}: expected one backend-attempt increment inside retry")
    }
    elseif ($null -ne $forwardRequests[0]) {
        $attemptPosition = 0
        $forwardPosition = 0
        $position = 0
        foreach ($child in $retry.ChildNodes) {
            if ($child.NodeType -ne [System.Xml.XmlNodeType]::Element) {
                continue
            }

            $position++
            if ($child.LocalName -eq 'set-variable' -and
                $child.GetAttribute('name') -eq 'llmmgmt-backend-attempt') {
                $attemptPosition = $position
            }
            elseif ($child.LocalName -eq 'forward-request') {
                $forwardPosition = $position
            }
        }

        if ($attemptPosition -eq 0 -or $forwardPosition -eq 0 -or $attemptPosition -gt $forwardPosition) {
            $failures.Add("${policyPath}: backend-attempt increment must precede forward-request")
        }
    }
}

$apiModulePath = 'peering\modules\apim-foundry-api.bicep'
$apiModule = Get-Content -Raw -LiteralPath $apiModulePath
foreach ($issuer in @(
    'environment().authentication.loginEndpoint'
    'https://sts.windows.net/${entraTenantId}/'
)) {
    if (-not $apiModule.Contains($issuer)) {
        $failures.Add("${apiModulePath}: missing supported APIM JWT issuer '$issuer'")
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Output "Validated guarded APIM branch tracing in $($resolvedPolicies.Count) policy files."

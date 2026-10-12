[CmdletBinding()]
param(
    [Parameter()]
    [string] $Query = @'
let agentIdToFind = "7f2edbcc-8375-4d1d-a430-93c14e8db94e";
CloudAppEvents
| where Timestamp > ago(1h)
| where ActionType in (
    "InvokeAgent",
    "InferenceCall",
    "ExecuteToolBySDK",
    "ExecuteToolByGateway",
    "ExecuteToolByMCPServer")
| extend data = parse_json(tostring(RawEventData))
| extend AgentId = tostring(data.AgentId)
| extend TargetAgentId = tostring(data.TargetAgentId)
| extend PlatformTargetAgentId = tostring(data.PlatformTargetAgentId)
| where AgentId == agentIdToFind
    or TargetAgentId == agentIdToFind
    or PlatformTargetAgentId == agentIdToFind
| project Timestamp, ActionType, AgentId, TargetAgentId,
    PlatformTargetAgentId, data
| order by Timestamp desc
'@,

    [Parameter()]
    [switch] $IncludeSchema
)

$ErrorActionPreference = 'Stop'
$tenantId = '00648bab-6c91-4292-9a2a-2297df511222'
$clientId = '9a65a06f-b725-4769-92e9-e262f763d3e4'
$endpoint = 'https://graph.microsoft.com/v1.0/security/runHuntingQuery'
$scope = 'https://graph.microsoft.com/ThreatHunting.Read.All'
$tokenEndpoint = "https://login.microsoftonline.com/$tenantId/oauth2/v2.0/token"
$deviceCodeEndpoint = (
    "https://login.microsoftonline.com/$tenantId/oauth2/v2.0/devicecode"
)

if (
    -not $global:A365DefenderHuntingToken -or
    $global:A365DefenderHuntingToken.ExpiresOn -le [DateTimeOffset]::UtcNow.AddMinutes(1)
) {
    $deviceCode = Invoke-RestMethod `
        -Method POST `
        -Uri $deviceCodeEndpoint `
        -ContentType 'application/x-www-form-urlencoded' `
        -Body @{
            client_id = $clientId
            scope = $scope
        }

    Write-Host $deviceCode.message
    $pollInterval = [int] $deviceCode.interval
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds(
        [int] $deviceCode.expires_in
    )
    $token = $null

    while (-not $token -and [DateTimeOffset]::UtcNow -lt $deadline) {
        Start-Sleep -Seconds $pollInterval
        try {
            $token = Invoke-RestMethod `
                -Method POST `
                -Uri $tokenEndpoint `
                -ContentType 'application/x-www-form-urlencoded' `
                -Body @{
                    grant_type = (
                        'urn:ietf:params:oauth:grant-type:device_code'
                    )
                    client_id = $clientId
                    device_code = $deviceCode.device_code
                }
        }
        catch {
            $oauthError = $_.ErrorDetails.Message | ConvertFrom-Json
            if ($oauthError.error -eq 'authorization_pending') {
                continue
            }
            if ($oauthError.error -eq 'slow_down') {
                $pollInterval += 5
                continue
            }
            throw
        }
    }

    if (-not $token) {
        throw 'Device-code authentication expired before sign-in completed.'
    }

    $global:A365DefenderHuntingToken = [pscustomobject] @{
        AccessToken = $token.access_token
        ExpiresOn = [DateTimeOffset]::UtcNow.AddSeconds(
            [int] $token.expires_in
        )
    }
}

$body = @{ Query = $Query } | ConvertTo-Json -Compress
$response = Invoke-RestMethod `
    -Method POST `
    -Uri $endpoint `
    -Body $body `
    -ContentType 'application/json' `
    -Headers @{
        Authorization = (
            "Bearer $($global:A365DefenderHuntingToken.AccessToken)"
        )
    }

if ($IncludeSchema) {
    $response.schema |
        ForEach-Object {
            [pscustomobject] @{
                Name = $_['name']
                Type = $_['type']
            }
        } |
        Format-Table Name, Type -AutoSize
}

if (-not $response.results -or $response.results.Count -eq 0) {
    Write-Host 'Query completed successfully with no matching rows.'
    return
}

$response.results | ConvertTo-Json -Depth 20

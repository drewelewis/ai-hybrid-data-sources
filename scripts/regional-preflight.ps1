#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [string]$SubscriptionId,
  [string[]]$HubRegions = @('canadacentral', 'centralus', 'eastus2', 'westus3', 'westus2', 'swedencentral', 'uksouth', 'northeurope', 'westeurope'),
  [string[]]$AppRegions = @('canadaeast', 'canadacentral', 'centralus', 'eastus2', 'northeurope', 'swedencentral'),
  [string[]]$FoundryRegions = @('swedencentral', 'centralus', 'eastus2', 'canadacentral', 'northeurope'),
  [string]$AppServiceSku = 'B1',
  [ValidateSet('AnySmall', 'Exact')]
  [string]$ModelSelection = 'AnySmall',
  [string[]]$SmallModelPreference = @(
    'gpt-5.4-mini',
    'gpt-5.4-nano',
    'gpt-5-mini',
    'gpt-5-nano',
    'gpt-4.1-mini',
    'gpt-4.1-nano',
    'gpt-4o-mini'
  ),
  [string]$ModelName = 'gpt-5.4-mini',
  [string]$ModelVersion = '2026-03-17',
  [string]$ModelSku = 'GlobalStandard',
  [int]$ModelCapacity = 30,
  [string]$OutputPath = '.azure\preflight\regional-preflight.json',
  [switch]$InvokedByPicker
)

$ErrorActionPreference = 'Stop'

function Invoke-AzJson {
  param(
    [Parameter(Mandatory)]
    [string[]]$Arguments
  )

  $raw = @(& az @Arguments --only-show-errors --output json 2>&1)
  $exitCode = $LASTEXITCODE
  $text = ($raw | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine

  if ($exitCode -ne 0) {
    return [pscustomobject]@{
      Succeeded = $false
      Data = $null
      Error = $text.Trim()
    }
  }

  if (-not $text.Trim()) {
    return [pscustomobject]@{
      Succeeded = $true
      Data = $null
      Error = $null
    }
  }

  try {
    $data = $text | ConvertFrom-Json
  }
  catch {
    throw "Azure CLI returned invalid JSON for 'az $($Arguments -join ' ')': $text"
  }

  return [pscustomobject]@{
    Succeeded = $true
    Data = $data
    Error = $null
  }
}

function Get-DisplayName {
  param(
    [Parameter(Mandatory)]
    [string]$Region
  )

  $displayName = $script:LocationNames[$Region.ToLowerInvariant()]
  if (-not $displayName) {
    throw "Azure region '$Region' was not returned by az account list-locations."
  }
  return $displayName
}

function Get-ProviderLocations {
  param(
    [Parameter(Mandatory)]
    [string]$Namespace,
    [Parameter(Mandatory)]
    [string]$ResourceType
  )

  $cacheKey = "$Namespace/$ResourceType"
  if ($script:ProviderLocationCache.ContainsKey($cacheKey)) {
    return $script:ProviderLocationCache[$cacheKey]
  }

  $response = Invoke-AzJson -Arguments @(
    'provider', 'show',
    '--subscription', $SubscriptionId,
    '--namespace', $Namespace,
    '--query', "resourceTypes[?resourceType=='$ResourceType'].locations | [0]"
  )
  if (-not $response.Succeeded) {
    throw "Unable to query regional support for $cacheKey. $($response.Error)"
  }

  $locations = @($response.Data)
  $script:ProviderLocationCache[$cacheKey] = $locations
  return $locations
}

function Test-ProviderRegion {
  param(
    [Parameter(Mandatory)]
    [string]$Namespace,
    [Parameter(Mandatory)]
    [string]$ResourceType,
    [Parameter(Mandatory)]
    [string]$Region,
    [Parameter(Mandatory)]
    [string]$Name,
    [string]$SupportedStatus = 'PASS',
    [string]$SupportedDetail = 'Resource type is advertised in this region.'
  )

  $displayName = Get-DisplayName -Region $Region
  $supported = (Get-ProviderLocations -Namespace $Namespace -ResourceType $ResourceType) -contains $displayName
  if ($supported) {
    return [pscustomobject]@{
      Name = $Name
      Status = $SupportedStatus
      Detail = $SupportedDetail
    }
  }

  return [pscustomobject]@{
    Name = $Name
    Status = 'FAIL'
    Detail = "Resource type is not advertised in $displayName."
  }
}

function Get-OverallStatus {
  param(
    [Parameter(Mandatory)]
    [object[]]$Checks
  )

  if (@($Checks | Where-Object Status -eq 'FAIL').Count -gt 0) {
    return 'FAIL'
  }
  if (@($Checks | Where-Object Status -in @('CONDITIONAL', 'UNKNOWN')).Count -gt 0) {
    return 'CONDITIONAL'
  }
  return 'PASS'
}

function Test-ApimPremiumV2Region {
  param(
    [Parameter(Mandatory)]
    [string]$Region,
    [Parameter(Mandatory)]
    [object]$SkuResponse
  )

  if (-not $SkuResponse.Succeeded) {
    return [pscustomobject]@{
      Name = 'APIM Premium v2 subscription SKU'
      Status = 'UNKNOWN'
      Detail = "The APIM subscription SKU API could not be queried: $($SkuResponse.Error)"
    }
  }

  $regionSkus = @($SkuResponse.Data.value | Where-Object {
      $_.name -eq 'PremiumV2' -and @($_.locations) -contains $Region
    })
  if ($regionSkus.Count -eq 0) {
    return [pscustomobject]@{
      Name = 'APIM Premium v2 subscription SKU'
      Status = 'FAIL'
      Detail = "The subscription-scoped APIM SKU API does not list PremiumV2 in $(Get-DisplayName -Region $Region)."
    }
  }

  $unrestrictedSkus = @($regionSkus | Where-Object { @($_.restrictions).Count -eq 0 })
  if ($unrestrictedSkus.Count -eq 0) {
    $reasons = @(
      $regionSkus.restrictions |
        ForEach-Object { $_.reasonCode } |
        Where-Object { $_ } |
        Sort-Object -Unique
    )
    $reasonText = if ($reasons.Count -gt 0) { $reasons -join ', ' } else { 'unspecified restriction' }
    return [pscustomobject]@{
      Name = 'APIM Premium v2 subscription SKU'
      Status = 'FAIL'
      Detail = "The subscription-scoped APIM SKU API restricts PremiumV2 in $(Get-DisplayName -Region $Region): $reasonText."
    }
  }

  return [pscustomobject]@{
    Name = 'APIM Premium v2 subscription SKU'
    Status = 'CONDITIONAL'
    Detail = "The subscription-scoped APIM SKU API lists PremiumV2 in $(Get-DisplayName -Region $Region) without a formal restriction. Azure does not expose transient physical capacity through this API, so the staged APIM create is the decisive probe."
  }
}

if (-not $SubscriptionId) {
  $accountResponse = Invoke-AzJson -Arguments @('account', 'show')
  if (-not $accountResponse.Succeeded) {
    throw "Azure CLI is not authenticated. Run az login first. $($accountResponse.Error)"
  }
  $SubscriptionId = $accountResponse.Data.id
}

$accountResponse = Invoke-AzJson -Arguments @('account', 'show')
if (-not $accountResponse.Succeeded) {
  throw "Azure CLI is not authenticated. Run az login first. $($accountResponse.Error)"
}
if ($accountResponse.Data.id -ne $SubscriptionId) {
  throw "Azure CLI targets subscription '$($accountResponse.Data.id)', but preflight requested '$SubscriptionId'. Run az account set --subscription $SubscriptionId."
}

$quotaExtensionResponse = Invoke-AzJson -Arguments @('extension', 'show', '--name', 'quota')
if (-not $quotaExtensionResponse.Succeeded) {
  throw "Azure CLI quota extension is required. Install it with: az extension add --name quota"
}

$locationsResponse = Invoke-AzJson -Arguments @(
  'account', 'list-locations',
  '--query', '[].{name:name,displayName:displayName}'
)
if (-not $locationsResponse.Succeeded) {
  throw "Unable to list Azure regions. $($locationsResponse.Error)"
}

$script:LocationNames = @{}
foreach ($location in @($locationsResponse.Data)) {
  $script:LocationNames[$location.name.ToLowerInvariant()] = $location.displayName
}
$script:ProviderLocationCache = @{}

$apimSkuResponse = Invoke-AzJson -Arguments @(
  'rest',
  '--method', 'get',
  '--url', "https://management.azure.com/subscriptions/$SubscriptionId/providers/Microsoft.ApiManagement/skus?api-version=2025-09-01-preview"
)

$appLocationsResponse = Invoke-AzJson -Arguments @(
  'appservice', 'list-locations',
  '--subscription', $SubscriptionId,
  '--sku', $AppServiceSku,
  '--linux-workers-enabled'
)
if (-not $appLocationsResponse.Succeeded) {
  throw "Unable to list App Service regions for SKU '$AppServiceSku'. $($appLocationsResponse.Error)"
}
$appLocationNames = @($appLocationsResponse.Data | ForEach-Object { $_.name })

$results = [System.Collections.Generic.List[object]]::new()

foreach ($region in $HubRegions) {
  $checks = @(
    Test-ApimPremiumV2Region -Region $region -SkuResponse $apimSkuResponse
    Test-ProviderRegion `
      -Namespace 'Microsoft.Network' `
      -ResourceType 'virtualNetworkGateways' `
      -Region $region `
      -Name 'VpnGw1AZ' `
      -SupportedStatus 'CONDITIONAL' `
      -SupportedDetail 'VPN gateways are advertised in this region, but VpnGw1AZ capacity requires ARM validation or deployment.'
  )

  $results.Add([pscustomobject]@{
    Area = 'Hub'
    Region = $region
    Result = Get-OverallStatus -Checks $checks
    Checks = $checks
  })
}

foreach ($region in $AppRegions) {
  $displayName = Get-DisplayName -Region $region
  $supported = $appLocationNames -contains $displayName
  $checks = @(
    [pscustomobject]@{
      Name = "Linux App Service $AppServiceSku"
      Status = if ($supported) { 'PASS' } else { 'FAIL' }
      Detail = if ($supported) {
        "SKU $AppServiceSku is listed for Linux workers in $displayName."
      }
      else {
        "SKU $AppServiceSku is not listed for Linux workers in $displayName."
      }
    }
  )

  $results.Add([pscustomobject]@{
    Area = 'Application'
    Region = $region
    Result = Get-OverallStatus -Checks $checks
    Checks = $checks
  })
}

foreach ($region in $FoundryRegions) {
  $checks = [System.Collections.Generic.List[object]]::new()
  $checks.Add((Test-ProviderRegion -Namespace 'Microsoft.CognitiveServices' -ResourceType 'accounts' -Region $region -Name 'Azure AI Foundry account'))
  $checks.Add((Test-ProviderRegion -Namespace 'Microsoft.Search' -ResourceType 'searchServices' -Region $region -Name 'AI Search'))
  $checks.Add((Test-ProviderRegion -Namespace 'Microsoft.DocumentDB' -ResourceType 'databaseAccounts' -Region $region -Name 'Cosmos DB'))
  $checks.Add((Test-ProviderRegion -Namespace 'Microsoft.ContainerRegistry' -ResourceType 'registries' -Region $region -Name 'Container Registry'))

  $modelQuery = if ($ModelSelection -eq 'Exact') {
    "[?model.name=='$ModelName' && model.version=='$ModelVersion']"
  }
  else {
    "[?model.capabilities.chatCompletion=='true' && (contains(model.name, 'mini') || contains(model.name, 'nano'))]"
  }
  $modelResponse = Invoke-AzJson -Arguments @(
    'cognitiveservices', 'model', 'list',
    '--subscription', $SubscriptionId,
    '--location', $region,
    '--query', $modelQuery
  )
  $recommendedModel = $null
  $eligibleModels = [System.Collections.Generic.List[object]]::new()
  if (-not $modelResponse.Succeeded) {
    $checks.Add([pscustomobject]@{
      Name = if ($ModelSelection -eq 'Exact') { "$ModelName $ModelVersion $ModelSku" } else { "Any small chat model $ModelSku" }
      Status = 'FAIL'
      Detail = "Model availability query failed. $($modelResponse.Error)"
    })
  }
  elseif (@($modelResponse.Data).Count -eq 0) {
    $checks.Add([pscustomobject]@{
      Name = if ($ModelSelection -eq 'Exact') { "$ModelName $ModelVersion $ModelSku" } else { "Any small chat model $ModelSku" }
      Status = 'FAIL'
      Detail = if ($ModelSelection -eq 'Exact') {
        'The exact model and version were not returned for this region.'
      }
      else {
        'No small chat models were returned for this region.'
      }
    })
  }
  else {
    $selectedModel = $null
    if ($ModelSelection -eq 'Exact') {
      $selectedModel = @($modelResponse.Data | Select-Object -First 1)
    }
    else {
      foreach ($candidateName in $SmallModelPreference) {
        $candidate = @(
          $modelResponse.Data |
            Where-Object {
              $_.model.name -eq $candidateName -and
              $_.model.lifecycleStatus -eq 'GenerallyAvailable' -and
              @($_.model.skus | Where-Object name -eq $ModelSku).Count -gt 0
            } |
            Sort-Object `
              @{ Expression = { $_.model.isDefaultVersion }; Descending = $true },
              @{ Expression = { $_.model.version }; Descending = $true } |
            Select-Object -First 1
        )
        if ($candidate.Count -gt 0) {
          $candidateRecord = $candidate[0]
          $eligibleModels.Add([pscustomobject]@{
            Name = $candidateRecord.model.name
            Version = $candidateRecord.model.version
            Sku = $ModelSku
            Capacity = $ModelCapacity
          })
          if (-not $selectedModel) {
            $selectedModel = $candidate
          }
        }
      }
    }

    $selectedModelRecord = @($selectedModel | Select-Object -First 1)
    if ($selectedModelRecord.Count -eq 0) {
      $checks.Add([pscustomobject]@{
        Name = if ($ModelSelection -eq 'Exact') { "$ModelName $ModelVersion $ModelSku" } else { "Any small chat model $ModelSku" }
        Status = 'FAIL'
        Detail = if ($ModelSelection -eq 'Exact') {
          "The model is available, but deployment SKU $ModelSku is not."
        }
        else {
          "No preferred generally available small chat model supports deployment SKU $ModelSku."
        }
      })
    }
    else {
      $selectedModelRecord = $selectedModelRecord[0]
      $sku = @($selectedModelRecord.model.skus | Where-Object name -eq $ModelSku | Select-Object -First 1)
      $lifecycleStatus = $selectedModelRecord.model.lifecycleStatus
      $deprecationDate = if ($sku[0].deprecationDate -is [datetime]) {
        $sku[0].deprecationDate.ToUniversalTime().ToString('o')
      }
      else {
        $sku[0].deprecationDate
      }
      $status = if ($lifecycleStatus -eq 'GenerallyAvailable') { 'PASS' } else { 'CONDITIONAL' }
      $recommendedModel = [pscustomobject]@{
        Name = $selectedModelRecord.model.name
        Version = $selectedModelRecord.model.version
        Sku = $ModelSku
        Capacity = $ModelCapacity
      }
      if ($ModelSelection -eq 'Exact') {
        $eligibleModels.Add($recommendedModel)
      }
      $checks.Add([pscustomobject]@{
        Name = "$($recommendedModel.Name) $($recommendedModel.Version) $ModelSku"
        Status = $status
        Detail = "Model is available; lifecycle=$lifecycleStatus; SKU deprecation=$deprecationDate; requested capacity=$ModelCapacity."
      })
    }
  }

  $quotaModelName = if ($recommendedModel) { $recommendedModel.Name } else { $ModelName }
  $quotaScope = "/subscriptions/$SubscriptionId/providers/Microsoft.CognitiveServices/locations/$region"
  $quotaResponse = Invoke-AzJson -Arguments @(
    'quota', 'list',
    '--subscription', $SubscriptionId,
    '--scope', $quotaScope,
    '--query', "[?contains(properties.name.localizedValue, '$quotaModelName')]"
  )
  if (-not $quotaResponse.Succeeded) {
    $checks.Add([pscustomobject]@{
      Name = 'Model quota'
      Status = 'UNKNOWN'
      Detail = "Microsoft.Quota did not return usable data: $($quotaResponse.Error)"
    })
  }
  elseif (@($quotaResponse.Data).Count -eq 0) {
    $checks.Add([pscustomobject]@{
      Name = 'Model quota'
      Status = 'UNKNOWN'
      Detail = 'Microsoft.Quota returned no matching model quota. This does not mean unlimited capacity.'
    })
  }
  else {
    $limits = @($quotaResponse.Data | ForEach-Object { $_.properties.limit.value })
    $checks.Add([pscustomobject]@{
      Name = 'Model quota'
      Status = 'CONDITIONAL'
      Detail = "Quota records were returned with limits: $($limits -join ', '). Usage still requires provider-specific verification."
    })
  }

  $checksArray = @($checks)
  $results.Add([pscustomobject]@{
    Area = 'Foundry'
    Region = $region
    Result = Get-OverallStatus -Checks $checksArray
    RecommendedModel = $recommendedModel
    EligibleModels = @($eligibleModels)
    Checks = $checksArray
  })
}

$report = [ordered]@{
  schemaVersion = '1.0'
  checkedAt = (Get-Date).ToUniversalTime().ToString('o')
  subscription = [ordered]@{
    id = $SubscriptionId
    name = $accountResponse.Data.name
    tenantId = $accountResponse.Data.tenantId
  }
  configuration = [ordered]@{
    appServiceSku = $AppServiceSku
    modelSelection = $ModelSelection
    smallModelPreference = $SmallModelPreference
    modelName = $ModelName
    modelVersion = $ModelVersion
    modelSku = $ModelSku
    modelCapacity = $ModelCapacity
  }
  results = @($results)
}

$resolvedOutputPath = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
  $OutputPath
}
else {
  Join-Path (Get-Location) $OutputPath
}
$outputDirectory = Split-Path $resolvedOutputPath -Parent
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
$report | ConvertTo-Json -Depth 10 | Set-Content -Path $resolvedOutputPath -Encoding utf8

$results |
  Select-Object Area, Region, Result, @{
    Name = 'Details'
    Expression = {
      ($_.Checks | ForEach-Object { "$($_.Name)=$($_.Status)" }) -join '; '
    }
  } |
  Format-Table -AutoSize

Write-Host ""
Write-Host "Regional preflight report: $resolvedOutputPath" -ForegroundColor Green
Write-Host 'CONDITIONAL or UNKNOWN means Azure does not expose enough evidence to guarantee deploy-time capacity.' -ForegroundColor Yellow

$resultCode = if (@($results | Where-Object Result -eq 'FAIL').Count -gt 0) { 2 } else { 0 }
if ($InvokedByPicker) {
  $global:LASTEXITCODE = $resultCode
  return
}
exit $resultCode

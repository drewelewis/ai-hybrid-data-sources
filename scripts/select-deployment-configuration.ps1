#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'

function Get-AzdValue {
  param(
    [Parameter(Mandatory)]
    [string]$Name
  )

  $value = @(& azd env get-value $Name 2>$null)
  if ($LASTEXITCODE -ne 0) {
    return $null
  }
  return (($value | ForEach-Object { $_.ToString() }) -join '').Trim()
}

function Select-Option {
  param(
    [Parameter(Mandatory)]
    [string]$Label,
    [Parameter(Mandatory)]
    [string[]]$Options,
    [Parameter(Mandatory)]
    [string]$DefaultValue
  )

  $defaultIndex = [Array]::IndexOf($Options, $DefaultValue)
  if ($defaultIndex -lt 0) {
    $defaultIndex = 0
  }

  Write-Host ""
  Write-Host $Label -ForegroundColor Cyan
  for ($index = 0; $index -lt $Options.Count; $index++) {
    $suffix = if ($index -eq $defaultIndex) { ' (default)' } else { '' }
    Write-Host "  $($index + 1). $($Options[$index])$suffix"
  }

  $answer = Read-Host "Select 1-$($Options.Count) [$($defaultIndex + 1)]"
  if (-not $answer) {
    return $Options[$defaultIndex]
  }

  $selection = 0
  if (-not [int]::TryParse($answer, [ref]$selection) -or $selection -lt 1 -or $selection -gt $Options.Count) {
    throw "Invalid selection '$answer' for $Label."
  }
  return $Options[$selection - 1]
}

function Set-AzdValue {
  param(
    [Parameter(Mandatory)]
    [string]$Name,
    [Parameter(Mandatory)]
    [string]$Value
  )

  if ($env:REGION_PICKER_DRY_RUN -eq 'true') {
    Write-Host "DRY RUN: azd env set $Name $Value"
    return
  }

  & azd env set $Name $Value
  if ($LASTEXITCODE -ne 0) {
    throw "Unable to persist azd environment value '$Name'."
  }
}

function Get-ModelOptions {
  param(
    [Parameter(Mandatory)]
    [object]$Report,
    [Parameter(Mandatory)]
    [string]$Region
  )

  $foundryResult = @($Report.results | Where-Object { $_.Area -eq 'Foundry' -and $_.Region -eq $Region } | Select-Object -First 1)
  if ($foundryResult.Count -eq 0 -or @($foundryResult[0].EligibleModels).Count -eq 0) {
    throw "Preflight returned no eligible small models for Foundry region '$Region'."
  }
  return @($foundryResult[0].EligibleModels | ForEach-Object { "$($_.Name)|$($_.Version)" })
}

$azAccountRaw = @(& az account show --output json --only-show-errors 2>&1)
if ($LASTEXITCODE -ne 0) {
  throw "Azure CLI is not authenticated. Run az login, select the intended subscription, and run azd up again."
}
$azAccount = (($azAccountRaw | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine) | ConvertFrom-Json

$azdStatusRaw = @(& azd auth status 2>&1)
if ($LASTEXITCODE -ne 0) {
  throw "Azure Developer CLI is not authenticated. Run: azd auth login --tenant-id $($azAccount.tenantId)"
}
$azdStatus = ($azdStatusRaw | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
$azdIdentityMatch = [regex]::Match($azdStatus, 'Logged in to Azure as (?<identity>[^\r\n]+)')
if (-not $azdIdentityMatch.Success) {
  throw "Unable to determine the Azure Developer CLI identity. Run: azd auth login --tenant-id $($azAccount.tenantId)"
}
$azdIdentity = $azdIdentityMatch.Groups['identity'].Value.Trim()
$azIdentity = $azAccount.user.name
if ($azIdentity -and $azdIdentity -ne $azIdentity) {
  throw @"
Azure CLI and Azure Developer CLI are authenticated as different identities.
az:  $azIdentity (tenant $($azAccount.tenantId), subscription $($azAccount.id))
azd: $azdIdentity

Cancel this deployment context and run:
  azd auth logout
  azd auth login --tenant-id $($azAccount.tenantId)
  azd up
"@
}

Set-AzdValue -Name 'AZURE_SUBSCRIPTION_ID' -Value $azAccount.id
Set-AzdValue -Name 'AZURE_TENANT_ID' -Value $azAccount.tenantId

Write-Host ""
Write-Host 'Azure deployment context verified and bound to the azd environment:' -ForegroundColor Green
Write-Host "  Subscription: $($azAccount.name) ($($azAccount.id))"
Write-Host "  Tenant:       $($azAccount.tenantId)"
Write-Host "  Identity:     $azIdentity"

Write-Host ""
Write-Host 'Checking advertised regional services, subscription SKU restrictions, models, and quotas...' -ForegroundColor Cyan
Write-Host 'APIM Premium v2 has no read-only physical-capacity API. The final APIM resource is staged first as the decisive live probe.' -ForegroundColor Yellow

$preflightScript = Join-Path $PSScriptRoot 'regional-preflight.ps1'
& $preflightScript -InvokedByPicker
$preflightExitCode = $LASTEXITCODE
if ($preflightExitCode -notin @(0, 2)) {
  throw "Regional preflight failed with exit code $preflightExitCode. Provisioning was stopped."
}

$preflightPath = Join-Path (Get-Location) '.azure\preflight\regional-preflight.json'
if (-not (Test-Path -LiteralPath $preflightPath)) {
  throw "Regional preflight did not produce '$preflightPath'. Provisioning was stopped."
}
$preflightReport = Get-Content -LiteralPath $preflightPath -Raw | ConvertFrom-Json
$hubRegions = @($preflightReport.results | Where-Object { $_.Area -eq 'Hub' -and $_.Result -ne 'FAIL' } | ForEach-Object Region)
$appRegions = @($preflightReport.results | Where-Object { $_.Area -eq 'Application' -and $_.Result -ne 'FAIL' } | ForEach-Object Region)
$foundryRegions = @($preflightReport.results | Where-Object { $_.Area -eq 'Foundry' -and $_.Result -ne 'FAIL' } | ForEach-Object Region)
if ($hubRegions.Count -eq 0 -or $appRegions.Count -eq 0 -or $foundryRegions.Count -eq 0) {
  throw 'Regional preflight returned no viable placement for one or more layers. Provisioning was stopped.'
}

Write-Host ""
Write-Host "Fresh regional preflight completed at $($preflightReport.checkedAt)." -ForegroundColor Green
Write-Host 'Unsupported or formally restricted candidates have been removed from the placement pickers.' -ForegroundColor Green
Write-Host 'A listed hub region is eligible for an APIM create attempt, not capacity-approved.' -ForegroundColor Yellow

$currentHub = Get-AzdValue -Name 'AZURE_LOCATION'
$currentApp = Get-AzdValue -Name 'APP_SERVICE_LOCATION'
$currentFoundry = Get-AzdValue -Name 'FOUNDRY_REGION'
$currentModel = Get-AzdValue -Name 'FOUNDRY_MODEL'
$currentModelVersion = Get-AzdValue -Name 'FOUNDRY_MODEL_VERSION'

$hubRegion = if ($currentHub -in $hubRegions) { $currentHub } else { $hubRegions[0] }
$appRegion = if ($currentApp -in $appRegions) { $currentApp } else { $appRegions[0] }
$foundryRegion = if ($currentFoundry -in $foundryRegions) { $currentFoundry } else { $foundryRegions[0] }
$modelOptions = Get-ModelOptions -Report $preflightReport -Region $foundryRegion
$currentModelOption = "$currentModel|$currentModelVersion"
$selectedModelOption = if ($currentModelOption -in $modelOptions) { $currentModelOption } else { $modelOptions[0] }
$modelName, $modelVersion = $selectedModelOption.Split('|', 2)

$nonInteractive = $env:CI -eq 'true' -or $env:AZD_NON_INTERACTIVE -in @('true', '1')
$allConfigured = (
  $currentHub -eq $hubRegion -and
  $currentApp -eq $appRegion -and
  $currentFoundry -eq $foundryRegion -and
  $currentModelOption -eq $selectedModelOption
)

if (-not $nonInteractive -and $env:AZD_SKIP_REGION_PICKER -ne 'true') {
  $reuse = $false
  if ($allConfigured) {
    Write-Host ""
    Write-Host "Saved deployment placement:" -ForegroundColor Cyan
    Write-Host "  Hub:         $hubRegion (APIM live probe pending)"
    Write-Host "  Application: $appRegion"
    Write-Host "  Foundry:     $foundryRegion"
    Write-Host "  Model:       $modelName $modelVersion"
    $answer = Read-Host 'Reuse these values? [Y/n]'
    $reuse = $answer -notmatch '^(n|no)$'
  }

  if (-not $reuse) {
    $hubRegion = Select-Option -Label 'Hub / VPN / APIM region' -Options $hubRegions -DefaultValue $hubRegion
    $appRegion = Select-Option -Label 'Application App Service region' -Options $appRegions -DefaultValue $appRegion
    $foundryRegion = Select-Option -Label 'Foundry spoke region' -Options $foundryRegions -DefaultValue $foundryRegion

    $modelOptions = Get-ModelOptions -Report $preflightReport -Region $foundryRegion
    $currentModelOption = "$modelName|$modelVersion"
    $selectedModel = Select-Option -Label 'Foundry small chat model' -Options $modelOptions -DefaultValue $currentModelOption
    $modelName, $modelVersion = $selectedModel.Split('|', 2)
  }
}

Set-AzdValue -Name 'AZURE_LOCATION' -Value $hubRegion
Set-AzdValue -Name 'APP_SERVICE_LOCATION' -Value $appRegion
Set-AzdValue -Name 'FOUNDRY_REGION' -Value $foundryRegion
Set-AzdValue -Name 'FOUNDRY_MODEL' -Value $modelName
Set-AzdValue -Name 'FOUNDRY_MODEL_VERSION' -Value $modelVersion

Write-Host ""
Write-Host 'Deployment placement saved to the azd environment:' -ForegroundColor Green
Write-Host "  Hub:         $hubRegion (APIM live probe pending)"
Write-Host "  Application: $appRegion"
Write-Host "  Foundry:     $foundryRegion"
Write-Host "  Model:       $modelName $modelVersion (GlobalStandard)"

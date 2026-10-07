#!/usr/bin/env pwsh
[CmdletBinding()]
param(
  [Parameter(Mandatory)]
  [string] $MappingFile,

  [Parameter(Mandatory)]
  [string] $ProductName,

  [Parameter(Mandatory)]
  [ValidateRange(1, 1000000)]
  [int] $CalibratedRequestTokens,

  [Parameter(Mandatory)]
  [ValidateRange(1, 1000000000)]
  [int] $BackendDeploymentTpm,

  [string] $OutputFile = 'untracked\apim-limit-test-mapping.json',

  [string] $ManifestFile = 'untracked\apim-limit-test-manifest.json',

  [ValidateRange(1, 20)]
  [int] $MaximumTestRpm = 20,

  [switch] $Force
)

$ErrorActionPreference = 'Stop'

function Resolve-OutputPath {
  param([Parameter(Mandatory)][string] $Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }

  return [System.IO.Path]::GetFullPath((Join-Path (Split-Path $PSScriptRoot -Parent) $Path))
}

function Assert-WritableOutput {
  param(
    [Parameter(Mandatory)][string] $Path,
    [Parameter(Mandatory)][bool] $AllowOverwrite
  )

  if ((Test-Path -LiteralPath $Path) -and -not $AllowOverwrite) {
    throw "Output '$Path' already exists. Use -Force to replace it."
  }

  $parent = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
}

$resolvedMappingFile = (Resolve-Path -LiteralPath $MappingFile -ErrorAction Stop).Path
$resolvedOutputFile = Resolve-OutputPath $OutputFile
$resolvedManifestFile = Resolve-OutputPath $ManifestFile

if ($resolvedOutputFile -eq $resolvedMappingFile -or $resolvedManifestFile -eq $resolvedMappingFile) {
  throw 'The candidate mapping and manifest must not overwrite the source mapping.'
}
if ($resolvedOutputFile -eq $resolvedManifestFile) {
  throw 'The candidate mapping and manifest paths must be different.'
}

Assert-WritableOutput -Path $resolvedOutputFile -AllowOverwrite $Force.IsPresent
Assert-WritableOutput -Path $resolvedManifestFile -AllowOverwrite $Force.IsPresent

$sourceJson = Get-Content -LiteralPath $resolvedMappingFile -Raw
$mapping = $sourceJson | ConvertFrom-Json -Depth 100
$productProperty = $mapping.PSObject.Properties[$ProductName]
if ($null -eq $productProperty) {
  throw "Product '$ProductName' was not found in '$resolvedMappingFile'."
}

$product = $productProperty.Value
$deployments = @($product.deployments)
if ($deployments.Count -eq 0) {
  throw "Product '$ProductName' has no deployments."
}
if ($product.skuGlobalMaxTokensPerMinute -le 0) {
  throw "Product '$ProductName' must have a positive skuGlobalMaxTokensPerMinute."
}

$rpmProperty = $product.PSObject.Properties['skuGlobalMaxCallsPerMinute']
$currentRpm = if ($null -ne $rpmProperty -and $rpmProperty.Value -gt 0) {
  [int]$rpmProperty.Value
}
else {
  20000
}
$rpmSource = if ($null -ne $rpmProperty -and $rpmProperty.Value -gt 0) {
  'configured'
}
else {
  'policy-fallback-20000'
}

$testRpm = [Math]::Min(
  $MaximumTestRpm,
  [Math]::Max(1, [Math]::Floor($currentRpm / 10))
)
$currentSkuTpm = [int]$product.skuGlobalMaxTokensPerMinute
$testSkuTpm = [Math]::Max(
  2 * $CalibratedRequestTokens,
  [Math]::Floor($currentSkuTpm / 10)
)

$deploymentChanges = [System.Collections.Generic.List[object]]::new()
foreach ($deployment in $deployments) {
  if ([string]::IsNullOrWhiteSpace($deployment.name) -or
      [string]::IsNullOrWhiteSpace($deployment.backendID) -or
      $deployment.maxTokensPerMinute -le 0) {
    throw "Product '$ProductName' contains an invalid deployment mapping."
  }

  $currentModelTpm = [int]$deployment.maxTokensPerMinute
  $testModelTpm = [Math]::Min(
    $testSkuTpm - $CalibratedRequestTokens,
    [Math]::Max(1, [Math]::Floor($currentModelTpm / 10))
  )
  if ($testModelTpm -ge $testSkuTpm) {
    throw "Calculated model TPM $testModelTpm for '$($deployment.name)' must be below SKU-global TPM $testSkuTpm."
  }
  if ($testModelTpm -ge $BackendDeploymentTpm) {
    throw "Calculated model TPM $testModelTpm for '$($deployment.name)' must be below backend deployment TPM $BackendDeploymentTpm."
  }

  $deployment.maxTokensPerMinute = [int]$testModelTpm
  $deploymentChanges.Add([ordered]@{
      name = $deployment.name
      backendID = $deployment.backendID
      originalMaxTokensPerMinute = $currentModelTpm
      testMaxTokensPerMinute = [int]$testModelTpm
    })
}

if ($null -eq $rpmProperty) {
  $product | Add-Member -NotePropertyName 'skuGlobalMaxCallsPerMinute' -NotePropertyValue ([int]$testRpm)
}
else {
  $product.skuGlobalMaxCallsPerMinute = [int]$testRpm
}
$product.skuGlobalMaxTokensPerMinute = [int]$testSkuTpm

$candidateJson = $mapping | ConvertTo-Json -Depth 100
$sourceHash = (Get-FileHash -LiteralPath $resolvedMappingFile -Algorithm SHA256).Hash
$candidateBytes = [Text.Encoding]::UTF8.GetBytes($candidateJson)
$candidateHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($candidateBytes))
$generatedAtUtc = [DateTime]::UtcNow.ToString('o')

$manifest = [ordered]@{
  generatedAtUtc = $generatedAtUtc
  publishAuthorized = $false
  source = [ordered]@{
    path = $resolvedMappingFile
    sha256 = $sourceHash
  }
  candidate = [ordered]@{
    path = $resolvedOutputFile
    sha256 = $candidateHash
  }
  product = $ProductName
  calibration = [ordered]@{
    calibratedRequestTokens = $CalibratedRequestTokens
    backendDeploymentTpm = $BackendDeploymentTpm
    maximumTestRpm = $MaximumTestRpm
  }
  limits = [ordered]@{
    rpmSource = $rpmSource
    originalSkuGlobalMaxCallsPerMinute = $currentRpm
    testSkuGlobalMaxCallsPerMinute = [int]$testRpm
    originalSkuGlobalMaxTokensPerMinute = $currentSkuTpm
    testSkuGlobalMaxTokensPerMinute = [int]$testSkuTpm
    deployments = @($deploymentChanges)
  }
  requiredBeforePublish = @(
    'Record the current mapping blob ETag and exact UTC time.'
    'Confirm exactly one APIM subscription is attached to the selected product.'
    'Obtain subscription-owner and product-owner approval for the quiet test window.'
    'Confirm zero unrelated traffic for the selected product and models.'
    'Verify the calibrated request token count with a traced smoke request.'
    'Verify every calculated policy TPM is below the native backend deployment TPM.'
  )
}

$candidateTempFile = [System.IO.Path]::GetTempFileName()
$manifestTempFile = [System.IO.Path]::GetTempFileName()
try {
  [System.IO.File]::WriteAllText(
    $candidateTempFile,
    $candidateJson,
    [System.Text.UTF8Encoding]::new($false)
  )
  [System.IO.File]::WriteAllText(
    $manifestTempFile,
    ($manifest | ConvertTo-Json -Depth 100),
    [System.Text.UTF8Encoding]::new($false)
  )
  Move-Item -LiteralPath $candidateTempFile -Destination $resolvedOutputFile -Force:$Force.IsPresent
  Move-Item -LiteralPath $manifestTempFile -Destination $resolvedManifestFile -Force:$Force.IsPresent
}
finally {
  Remove-Item -LiteralPath $candidateTempFile -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $manifestTempFile -Force -ErrorAction SilentlyContinue
}

Write-Output "Prepared a non-publishing test mapping at '$resolvedOutputFile'."
Write-Output "Review the safety manifest at '$resolvedManifestFile' before any publish action."

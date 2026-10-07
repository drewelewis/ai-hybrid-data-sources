[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path $PSScriptRoot -Parent
$preparer = Join-Path $repositoryRoot 'scripts\prepare-apim-limit-test-mapping.ps1'
$testDirectory = Join-Path ([System.IO.Path]::GetTempPath()) "apim-limit-mapping-$([guid]::NewGuid())"
$sourceFile = Join-Path $testDirectory 'source.json'
$candidateFile = Join-Path $testDirectory 'candidate.json'
$manifestFile = Join-Path $testDirectory 'manifest.json'

try {
  New-Item -ItemType Directory -Path $testDirectory | Out-Null
  @'
{
  "test-product": {
    "skuGlobalMaxTokensPerMinute": 4000,
    "deployments": [
      {
        "name": "model-a",
        "maxTokensPerMinute": 5000,
        "backendID": "existing-backend"
      },
      {
        "name": "model-b",
        "maxTokensPerMinute": 6000,
        "backendID": "existing-backend"
      }
    ]
  }
}
'@ | Set-Content -LiteralPath $sourceFile -Encoding utf8NoBOM

  $sourceHashBefore = (Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash
  & $preparer `
    -MappingFile $sourceFile `
    -ProductName 'test-product' `
    -CalibratedRequestTokens 100 `
    -BackendDeploymentTpm 1000 `
    -OutputFile $candidateFile `
    -ManifestFile $manifestFile

  $candidate = Get-Content -LiteralPath $candidateFile -Raw | ConvertFrom-Json -Depth 100
  $manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json -Depth 100
  $sourceHashAfter = (Get-FileHash -LiteralPath $sourceFile -Algorithm SHA256).Hash

  if ($sourceHashAfter -ne $sourceHashBefore) {
    throw 'The source mapping was modified.'
  }
  if ($candidate.'test-product'.skuGlobalMaxCallsPerMinute -ne 20) {
    throw 'The fallback RPM was not reduced and capped at 20.'
  }
  if ($candidate.'test-product'.skuGlobalMaxTokensPerMinute -ne 400) {
    throw 'The SKU TPM was not reduced to 400.'
  }
  if ($candidate.'test-product'.deployments[0].maxTokensPerMinute -ne 300 -or
      $candidate.'test-product'.deployments[1].maxTokensPerMinute -ne 300) {
    throw 'The model TPM values were not reduced and capped below SKU-global TPM.'
  }
  if (@($candidate.'test-product'.deployments | Select-Object -ExpandProperty backendID -Unique) -ne 'existing-backend') {
    throw 'The existing backend assignment changed.'
  }
  if ($manifest.publishAuthorized -ne $false -or
      $manifest.limits.rpmSource -ne 'policy-fallback-20000') {
    throw 'The safety manifest does not identify the non-publishing fallback-RPM calculation.'
  }
  if ((Get-FileHash -LiteralPath $candidateFile -Algorithm SHA256).Hash -ne $manifest.candidate.sha256) {
    throw 'The candidate SHA-256 does not match the exact file bytes.'
  }

  $unsafeAccepted = $false
  try {
    & $preparer `
      -MappingFile $sourceFile `
      -ProductName 'test-product' `
      -CalibratedRequestTokens 100 `
      -BackendDeploymentTpm 300 `
      -OutputFile (Join-Path $testDirectory 'unsafe.json') `
      -ManifestFile (Join-Path $testDirectory 'unsafe-manifest.json')
    $unsafeAccepted = $true
  }
  catch {
    if (-not $_.Exception.Message.Contains('must be below backend deployment TPM')) {
      throw
    }
  }

  if ($unsafeAccepted) {
    throw 'An unsafe model TPM was accepted.'
  }

  Write-Output 'Validated non-publishing APIM limit test mapping preparation.'
}
finally {
  Remove-Item -LiteralPath $testDirectory -Recurse -Force -ErrorAction SilentlyContinue
}

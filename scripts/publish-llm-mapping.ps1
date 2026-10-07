#!/usr/bin/env pwsh
param(
  [string] $MappingFile = ''
)

$ErrorActionPreference = 'Stop'

function Get-AzdValue {
  param([Parameter(Mandatory)][string] $Name)

  $value = (& azd env get-value $Name | ForEach-Object { $_.ToString() }) -join ''
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($value)) {
    throw "The active azd environment does not contain '$Name'. Run 'azd up' before publishing the mapping."
  }
  return $value.Trim()
}

if ([string]::IsNullOrWhiteSpace($MappingFile)) {
  $MappingFile = if ([string]::IsNullOrWhiteSpace($env:LLM_MAPPING_FILE)) {
    Join-Path (Split-Path $PSScriptRoot -Parent) 'untracked\new_v2-mapping.json'
  }
  else {
    $env:LLM_MAPPING_FILE
  }
}

$resolvedMappingFile = (Resolve-Path -LiteralPath $MappingFile -ErrorAction Stop).Path
$mapping = Get-Content -LiteralPath $resolvedMappingFile -Raw | ConvertFrom-Json -Depth 100
$products = @($mapping.PSObject.Properties)
if ($products.Count -eq 0) {
  throw "Mapping '$resolvedMappingFile' has no product mappings."
}
foreach ($product in $products) {
  $deployments = @($product.Value.deployments)
  if ($deployments.Count -eq 0) {
    throw "Product '$($product.Name)' has no deployments."
  }
  foreach ($deployment in $deployments) {
    if ([string]::IsNullOrWhiteSpace($deployment.name) -or
        [string]::IsNullOrWhiteSpace($deployment.backendID) -or
        $deployment.maxTokensPerMinute -le 0) {
      throw "Product '$($product.Name)' contains an invalid deployment mapping."
    }
  }
}

$subscriptionId = Get-AzdValue 'AZURE_SUBSCRIPTION_ID'
$resourceGroup = Get-AzdValue 'AZURE_RESOURCE_GROUP'
$storageAccount = Get-AzdValue 'MAPPING_STORAGE_ACCOUNT'
$container = Get-AzdValue 'MAPPING_CONTAINER'
$blobName = Get-AzdValue 'MAPPING_BLOB_NAME'
$privateIp = (& azd env get-value MAPPING_STORAGE_PRIVATE_IP 2>$null | ForEach-Object { $_.ToString() }) -join ''
$privateIp = $privateIp.Trim()

function Get-AzContextSuffix {
  $storageEndpoint = (& az cloud show --query suffixes.storageEndpoint --output tsv --only-show-errors).Trim()
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($storageEndpoint)) {
    throw 'Unable to determine the Azure Storage endpoint suffix.'
  }
  return $storageEndpoint.TrimStart('.')
}

$blobHost = "$storageAccount.blob.$(Get-AzContextSuffix)"
$blobUrl = "https://$blobHost/$container/$blobName"
$containerScope = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.Storage/storageAccounts/$storageAccount/blobServices/default/containers/$container"

& az account set --subscription $subscriptionId --only-show-errors
if ($LASTEXITCODE -ne 0) {
  throw "Unable to select subscription '$subscriptionId'."
}

if ([string]::IsNullOrWhiteSpace($privateIp)) {
  $privateEndpointName = "pep-$storageAccount"
  $networkInterfaceId = (& az network private-endpoint show `
    --resource-group $resourceGroup `
    --name $privateEndpointName `
    --query 'networkInterfaces[0].id' `
    --output tsv `
    --only-show-errors).Trim()
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($networkInterfaceId)) {
    throw "Unable to resolve the network interface for private endpoint '$privateEndpointName'."
  }
  $privateIp = (& az network nic show `
    --ids $networkInterfaceId `
    --query 'ipConfigurations[0].privateIPAddress' `
    --output tsv `
    --only-show-errors).Trim()
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($privateIp)) {
    throw "Unable to resolve the private IP for private endpoint '$privateEndpointName'."
  }
}

$account = (& az account show --output json --only-show-errors | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) {
  throw 'Unable to read the active Azure CLI identity.'
}
$identityToken = (& az account get-access-token `
  --resource 'https://management.azure.com/' `
  --query accessToken `
  --output tsv `
  --only-show-errors).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($identityToken)) {
  throw 'Unable to acquire an ARM token for the signed-in Azure CLI principal.'
}
$encodedClaims = $identityToken.Split('.')[1].Replace('-', '+').Replace('_', '/')
$encodedClaims += '=' * ((4 - ($encodedClaims.Length % 4)) % 4)
$claims = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encodedClaims)) | ConvertFrom-Json
$principalId = $claims.oid
$principalType = if ($account.user.type -eq 'user') { 'User' } else { 'ServicePrincipal' }
if ([string]::IsNullOrWhiteSpace($principalId)) {
  throw 'Unable to resolve the signed-in Azure CLI principal ID.'
}

$roleCount = (& az role assignment list `
  --assignee-object-id $principalId `
  --scope $containerScope `
  --query "[?roleDefinitionName=='Storage Blob Data Contributor'] | length(@)" `
  --output tsv `
  --only-show-errors).Trim()
if ($LASTEXITCODE -ne 0) {
  throw 'Unable to inspect mapping-container role assignments.'
}
if ($roleCount -eq '0') {
  Write-Host 'Granting the signed-in principal permission to publish the mapping blob...' -ForegroundColor Cyan
  & az role assignment create `
    --assignee-object-id $principalId `
    --assignee-principal-type $principalType `
    --role 'Storage Blob Data Contributor' `
    --scope $containerScope `
    --output none `
    --only-show-errors
  if ($LASTEXITCODE -ne 0) {
    throw 'Unable to grant Storage Blob Data Contributor on the mapping container.'
  }
}

$temporaryDownload = [System.IO.Path]::GetTempFileName()
try {
  $maxAttempts = 12
  for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    $accessToken = (& az account get-access-token `
      --resource 'https://storage.azure.com/' `
      --query accessToken `
      --output tsv `
      --only-show-errors).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($accessToken)) {
      throw 'Unable to acquire an Azure Storage access token.'
    }

    & curl.exe `
      --silent `
      --show-error `
      --fail-with-body `
      --request PUT `
      --resolve "${blobHost}:443:$privateIp" `
      --header "Authorization: Bearer $accessToken" `
      --header 'x-ms-version: 2023-11-03' `
      --header "x-ms-date: $([DateTime]::UtcNow.ToString('R'))" `
      --header 'x-ms-blob-type: BlockBlob' `
      --header 'Content-Type: application/json' `
      --upload-file $resolvedMappingFile `
      $blobUrl
    if ($LASTEXITCODE -eq 0) {
      break
    }
    if ($attempt -eq $maxAttempts) {
      throw "Unable to upload '$resolvedMappingFile'. Confirm the S2S VPN can route to $privateIp and RBAC propagation has completed."
    }
    Write-Host "Upload attempt $attempt failed; waiting for network or RBAC propagation..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
  }

  & curl.exe `
    --silent `
    --show-error `
    --fail-with-body `
    --resolve "${blobHost}:443:$privateIp" `
    --header "Authorization: Bearer $accessToken" `
    --header 'x-ms-version: 2023-11-03' `
    --header "x-ms-date: $([DateTime]::UtcNow.ToString('R'))" `
    --output $temporaryDownload `
    $blobUrl
  if ($LASTEXITCODE -ne 0) {
    throw 'The mapping uploaded, but downloading it for verification failed.'
  }

  $sourceHash = (Get-FileHash -LiteralPath $resolvedMappingFile -Algorithm SHA256).Hash
  $downloadHash = (Get-FileHash -LiteralPath $temporaryDownload -Algorithm SHA256).Hash
  if ($sourceHash -ne $downloadHash) {
    throw 'The uploaded mapping does not match the local file.'
  }
}
finally {
  Remove-Item -LiteralPath $temporaryDownload -Force -ErrorAction SilentlyContinue
}

Write-Host "Published and verified mapping: $blobUrl" -ForegroundColor Green

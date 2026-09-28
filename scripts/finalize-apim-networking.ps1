#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'

$networkProfile = (& azd env get-value APIM_NETWORK_PROFILE).Trim()
if ($networkProfile -ne 'standardV2PrivateLink') {
  Write-Host "APIM network profile '$networkProfile' requires no post-provision public-access change."
  exit 0
}

$subscriptionId = (& azd env get-value AZURE_SUBSCRIPTION_ID).Trim()
$resourceGroup = (& azd env get-value AZURE_RESOURCE_GROUP).Trim()
$apimName = (& azd env get-value APIM_NAME).Trim()
$resourceId = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.ApiManagement/service/$apimName"
$url = "https://management.azure.com${resourceId}?api-version=2025-09-01-preview"
$privateEndpointName = "pep-$apimName"
$maxAttempts = 20
$retryDelaySeconds = 30

$connectionStateOutput = @(& az network private-endpoint show `
  --subscription $subscriptionId `
  --resource-group $resourceGroup `
  --name $privateEndpointName `
  --query "privateLinkServiceConnections[0].privateLinkServiceConnectionState.status" `
  --output tsv `
  --only-show-errors)
if ($LASTEXITCODE -ne 0) {
  throw "Unable to read Standard v2 APIM private endpoint '$privateEndpointName'. Public network access was left enabled."
}
$connectionState = (($connectionStateOutput | ForEach-Object { $_.ToString() }) -join '').Trim()
if ($connectionState -ne 'Approved') {
  throw "Standard v2 APIM private endpoint '$privateEndpointName' is not approved. Current state: '$connectionState'. Public network access was left enabled."
}

$currentState = (& az rest --method get --url $url --query properties.publicNetworkAccess --output tsv --only-show-errors).Trim()
if ($LASTEXITCODE -ne 0) {
  throw "Unable to read public network access for Standard v2 APIM '$apimName'."
}
if ($currentState -eq 'Disabled') {
  Write-Host 'Standard v2 public gateway access is already disabled; Private Link is the inbound gateway path.' -ForegroundColor Green
  exit 0
}

Write-Host 'Disabling the Standard v2 public gateway after Private Link provisioning...' -ForegroundColor Cyan
& az rest `
  --method patch `
  --url $url `
  --headers 'Content-Type=application/json' `
  --body '{\"properties\":{\"publicNetworkAccess\":\"Disabled\"}}' `
  --output none `
  --only-show-errors
if ($LASTEXITCODE -ne 0) {
  throw "Failed to start the Standard v2 public-access update for '$apimName'."
}

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
  $statusOutput = @(& az rest `
    --method get `
    --url $url `
    --query '{provisioningState:properties.provisioningState,publicNetworkAccess:properties.publicNetworkAccess}' `
    --output json `
    --only-show-errors)
  if ($LASTEXITCODE -eq 0) {
    $status = (($statusOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine) | ConvertFrom-Json
    if ($status.provisioningState -eq 'Succeeded' -and $status.publicNetworkAccess -eq 'Disabled') {
      Write-Host 'Standard v2 public gateway access is disabled; Private Link is the inbound gateway path.' -ForegroundColor Green
      exit 0
    }
    Write-Host "APIM public-access update is still running (provisioning=$($status.provisioningState), publicAccess=$($status.publicNetworkAccess))." -ForegroundColor Yellow
  }
  else {
    Write-Host "Unable to read APIM update status on attempt $attempt of $maxAttempts." -ForegroundColor Yellow
  }
  if ($attempt -lt $maxAttempts) {
    Start-Sleep -Seconds $retryDelaySeconds
  }
}

throw "Standard v2 APIM public access did not reach Disabled/Succeeded after $maxAttempts checks. Inspect '$apimName' before using it."

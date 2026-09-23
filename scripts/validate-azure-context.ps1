#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'

$azdSubscriptionId = $env:AZURE_SUBSCRIPTION_ID
if (-not $azdSubscriptionId) {
  throw 'AZURE_SUBSCRIPTION_ID is not set. Select a subscription for the azd environment before provisioning.'
}

$azSubscriptionId = (az account show --query id --output tsv).Trim()
if ($LASTEXITCODE -ne 0 -or -not $azSubscriptionId) {
  throw 'Azure CLI is not authenticated. Run az login and select the intended subscription before azd up.'
}

if ($azSubscriptionId -ne $azdSubscriptionId) {
  throw @"
Azure subscription mismatch; provisioning was stopped before resources were created.
azd environment '$($env:AZURE_ENV_NAME)' targets: $azdSubscriptionId
Azure CLI currently targets:                  $azSubscriptionId
Select the same subscription in both az and azd, then run azd up again.
"@
}

$account = az account show --query '{name:name,tenantId:tenantId}' --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
  throw "Unable to read Azure CLI account details for subscription '$azSubscriptionId'."
}

$azdTenantId = $env:AZURE_TENANT_ID
if (-not $azdTenantId) {
  $azdTenantId = (azd env get-value AZURE_TENANT_ID 2>$null)
}
if (-not $azdTenantId -or $azdTenantId.Trim() -ne $account.tenantId) {
  throw "Azure tenant mismatch. azd targets '$azdTenantId', but Azure CLI targets '$($account.tenantId)'. Run azd auth login --tenant-id $($account.tenantId)."
}

Write-Host "Azure context verified: $($account.name) ($azSubscriptionId), tenant $($account.tenantId)." -ForegroundColor Green

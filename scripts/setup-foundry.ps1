#!/usr/bin/env pwsh
# azd `postup` hook. Runs at the end of `azd up` and, by DEFAULT, deploys a
# network-isolated Foundry spoke (foundry-samples template 19) and peers it to this hub
# so `azd up` provisions the whole solution. Opt out by answering 'n', setting
# AZD_SKIP_FOUNDRY=true, or running non-interactively (CI). Does NOTHING on teardown.
$ErrorActionPreference = 'Stop'

function Get-AzdOptionalValue {
  param(
    [Parameter(Mandatory)]
    [string]$Name
  )

  $value = @(& azd env get-value $Name 2>$null)
  if ($LASTEXITCODE -ne 0) {
    return ''
  }
  return (($value | ForEach-Object { $_.ToString() }) -join '').Trim()
}

function Get-AzCliText {
  param(
    [Parameter(Mandatory)]
    [string[]]$Arguments,
    [switch]$AllowFailure
  )

  $value = @(& az @Arguments)
  if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
    throw "Azure CLI command failed: az $($Arguments -join ' ')"
  }
  return (($value | ForEach-Object { $_.ToString() }) -join '').Trim()
}

# --- CI / non-interactive guard: never block or auto-build in pipelines ---
if ($env:AZD_SKIP_FOUNDRY -eq 'true') { Write-Host 'AZD_SKIP_FOUNDRY=true — skipping Foundry setup.'; exit 0 }

# --- Hub context from azd / az ---
$hubRg    = (azd env get-value AZURE_RESOURCE_GROUP).Trim()
$apimName = (azd env get-value APIM_NAME).Trim()
$envName  = (azd env get-value AZURE_ENV_NAME).Trim()
$subscriptionId = (azd env get-value AZURE_SUBSCRIPTION_ID).Trim()
$hubVnet  = (az network vnet list --subscription $subscriptionId -g $hubRg --query "[0].name" -o tsv).Trim()
$configuredFoundryRegion = Get-AzdOptionalValue -Name 'FOUNDRY_REGION'
$configuredFoundryModel = Get-AzdOptionalValue -Name 'FOUNDRY_MODEL'
$configuredFoundryModelVersion = Get-AzdOptionalValue -Name 'FOUNDRY_MODEL_VERSION'
$apimIp = Get-AzdOptionalValue -Name 'APIM_PRIVATE_IP'
$apimPrivateDnsZone = Get-AzdOptionalValue -Name 'APIM_PRIVATE_DNS_ZONE'
if (-not $apimIp -or -not $apimPrivateDnsZone) {
  throw 'APIM_PRIVATE_IP and APIM_PRIVATE_DNS_ZONE outputs are required. Run azd provision before Foundry setup.'
}

Write-Host ''
Write-Host 'Hub is deployed (VNet + VPN + APIM).' -ForegroundColor Green

# Reuse a Foundry VNet already connected to this hub unless FOUNDRY_RG explicitly selects
# another resource group. This keeps repeated azd up runs idempotent.
$reuseExisting = $false
if (-not $env:FOUNDRY_RG) {
  $existingFoundryVnetId = Get-AzCliText -Arguments @(
    'network', 'vnet', 'peering', 'list',
    '--subscription', $subscriptionId,
    '--resource-group', $hubRg,
    '--vnet-name', $hubVnet,
    '--query', "[?peeringState=='Connected' && contains(remoteVirtualNetwork.id, '/resourceGroups/rg-foundry-')].remoteVirtualNetwork.id | [0]",
    '--output', 'tsv',
    '--only-show-errors'
  )
  if ($existingFoundryVnetId) {
    $vnetIdParts = $existingFoundryVnetId.Split('/')
    $candidateRg = $vnetIdParts[4]
    $candidateAccount = Get-AzCliText -Arguments @(
      'cognitiveservices', 'account', 'list',
      '--subscription', $subscriptionId,
      '--resource-group', $candidateRg,
      '--query', '[0].name',
      '--output', 'tsv',
      '--only-show-errors'
    )
    if ($candidateAccount) {
      $reuseExisting = $true
      $spokeRg = $candidateRg
      $spokeVnet = $vnetIdParts[8]
      $region = (az network vnet show --subscription $subscriptionId -g $spokeRg -n $spokeVnet --query location -o tsv).Trim()
      Write-Host "Found connected Foundry spoke '$spokeVnet' in '$spokeRg'; reusing it." -ForegroundColor Green
    }
  }
}

# --- Spoke params (env overrides or defaults). 10.x is NOT allowed in Canada Central -> 172.16/16. ---
# West US 3 is the first region where this subscription completed all Foundry dependencies.
if (-not $reuseExisting) {
  Write-Host 'INCLUDED by default: deploy a network-isolated Foundry spoke (template 19) and peer it to the hub' -ForegroundColor Yellow
  Write-Host '  so a private agent can reach APIM (and on-prem data) over the peering.' -ForegroundColor Yellow
  Write-Host '  Adds Cosmos DB, AI Search (Basic), ACR (Premium), App Insights + a model,' -ForegroundColor Yellow
  Write-Host '  takes ~45-60 min (capability host ~30-35 min), and has ongoing cost.' -ForegroundColor Yellow
  try { $ans = Read-Host 'Set up Foundry + spoke VNet + peering now? [Y/n]' }
  catch { Write-Host 'Non-interactive — skipping.'; exit 0 }
  if ($ans -match '^(n|no)$') { Write-Host 'Declined. Re-run scripts/setup-foundry.ps1 anytime to do it.'; exit 0 }

  $region  = if ($env:FOUNDRY_REGION) { $env:FOUNDRY_REGION } elseif ($configuredFoundryRegion) { $configuredFoundryRegion } else { 'westus3' }
  $spokeRg = if ($env:FOUNDRY_RG) { $env:FOUNDRY_RG } else { "rg-foundry-$envName" }
}
$spokeCidr = if ($env:FOUNDRY_VNET_CIDR) { $env:FOUNDRY_VNET_CIDR } else { '172.16.0.0/16' }
$agentCidr = if ($env:FOUNDRY_AGENT_CIDR) { $env:FOUNDRY_AGENT_CIDR } else { '172.16.0.0/24' }
$peCidr    = if ($env:FOUNDRY_PE_CIDR) { $env:FOUNDRY_PE_CIDR } else { '172.16.1.0/24' }
$model     = if ($env:FOUNDRY_MODEL) { $env:FOUNDRY_MODEL } elseif ($configuredFoundryModel) { $configuredFoundryModel } else { 'gpt-5.4-mini' }
$modelVer  = if ($env:FOUNDRY_MODEL_VERSION) { $env:FOUNDRY_MODEL_VERSION } elseif ($configuredFoundryModelVersion) { $configuredFoundryModelVersion } else { '2026-03-17' }
# Entra auth for the Foundry API. Explicit environment variables override the app
# registrations provisioned by the main Bicep deployment.
$provisionedTenantId = (azd env get-value ENTRA_TENANT_ID 2>$null)
$provisionedAudience = (azd env get-value ENTRA_API_AUDIENCE 2>$null)
$entraTenantId = if ($env:ENTRA_TENANT_ID) { $env:ENTRA_TENANT_ID } else { $provisionedTenantId.Trim() }
$jwtAudience   = if ($env:JWT_AUDIENCE) { $env:JWT_AUDIENCE } else { $provisionedAudience.Trim() }
$corsOrigins   = if ($env:CORS_ORIGINS) { $env:CORS_ORIGINS } else { '["http://localhost:5173"]' }

Write-Host "Hub: rg=$hubRg vnet=$hubVnet apim=$apimName" -ForegroundColor Cyan
Write-Host "Spoke: rg=$spokeRg region=$region model=$model ($modelVer)" -ForegroundColor Cyan

if (-not $reuseExisting) {
  # --- Register providers required by template 19 (idempotent) ---
  foreach ($p in 'Microsoft.KeyVault','Microsoft.CognitiveServices','Microsoft.Storage','Microsoft.Search','Microsoft.Network','Microsoft.App','Microsoft.ContainerService','Microsoft.DocumentDB') {
    az provider register --subscription $subscriptionId --namespace $p --only-show-errors | Out-Null
  }

  # --- Vendored Foundry template (infra/foundry-spoke): Key Vault purge protection ON + model pinned ---
  $tpl = Join-Path (Split-Path $PSScriptRoot -Parent) 'infra/foundry-spoke'
  if (-not (Test-Path (Join-Path $tpl 'main.bicep'))) { throw "Vendored Foundry template not found at $tpl." }

  # --- Deploy Foundry spoke (long-running; ~45-60 min) ---
  az group create --subscription $subscriptionId -n $spokeRg -l $region --only-show-errors | Out-Null
  Write-Host 'Deploying Foundry (capability host step is ~30-35 min — do NOT cancel)...' -ForegroundColor Cyan
  az deployment group create --subscription $subscriptionId -g $spokeRg --template-file (Join-Path $tpl 'main.bicep') `
    --parameters location=$region modelName=$model modelFormat=OpenAI modelVersion=$modelVer `
                 vnetAddressPrefix=$spokeCidr agentSubnetPrefix=$agentCidr peSubnetPrefix=$peCidr `
    --only-show-errors
  if ($LASTEXITCODE -ne 0) { throw "Foundry deployment failed (exit $LASTEXITCODE). Review the errors above (common causes: model quota/version for '$model', or regional capacity), then re-run." }

  # --- Discover the spoke VNet the template created, then peer + DNS ---
  $spokeVnet = (az network vnet list --subscription $subscriptionId -g $spokeRg --query "[0].name" -o tsv).Trim()
  if (-not $spokeVnet) { throw "No VNet found in $spokeRg after the Foundry deploy." }
}

# --- Discover the Foundry account so peering.bicep can publish it as an APIM backend ---
$foundryAcct = Get-AzCliText -Arguments @(
  'cognitiveservices', 'account', 'list',
  '--subscription', $subscriptionId,
  '--resource-group', $spokeRg,
  '--query', '[0].name',
  '--output', 'tsv',
  '--only-show-errors'
)
if (-not $foundryAcct) {
  throw "No Azure AI Foundry account was found in resource group '$spokeRg'."
}
$foundryEndpoint = (az cognitiveservices account show --subscription $subscriptionId -g $spokeRg -n $foundryAcct --query "properties.endpoint" -o tsv).Trim()
$foundryDeployment = (az cognitiveservices account deployment list --subscription $subscriptionId -g $spokeRg -n $foundryAcct --query "[0].name" -o tsv).Trim()
$escapedCorsOrigins = $corsOrigins.Replace('"', '\"')

$repoRoot = Split-Path $PSScriptRoot -Parent
Write-Host "Peering $spokeVnet <-> $hubVnet, DNS, and publishing Foundry '$foundryAcct' as an APIM backend..." -ForegroundColor Cyan
az deployment sub create --name "peering-$envName-$region" --subscription $subscriptionId -l $region --template-file (Join-Path $repoRoot 'peering/peering.bicep') `
  --parameters hubResourceGroup=$hubRg hubVnetName=$hubVnet spokeResourceGroup=$spokeRg spokeVnetName=$spokeVnet `
               apimName=$apimName apimPrivateIp=$apimIp apimPrivateDnsZone=$apimPrivateDnsZone `
               wireFoundryBackend=true foundryResourceGroup=$spokeRg foundryAccountName=$foundryAcct `
               foundryEndpoint=$foundryEndpoint foundryDeploymentName=$foundryDeployment `
               entraTenantId=$entraTenantId jwtAudience=$jwtAudience allowedCorsOrigins=$escapedCorsOrigins `
  --only-show-errors
if ($LASTEXITCODE -ne 0) { throw "Peering/DNS deployment failed (exit $LASTEXITCODE). See errors above." }

Write-Host ''
Write-Host "Done. Foundry spoke deployed and peered. From the spoke: https://$apimName.azure-api.net/onprem/json" -ForegroundColor Green
Write-Host "Foundry model via APIM: https://$apimName.azure-api.net/openai/deployments/$foundryDeployment/chat/completions?api-version=2024-02-01" -ForegroundColor Green
Write-Host 'Teardown is MANUAL (Foundry capability-host purge order) — see peering/readme.md + template 19 cleanup.' -ForegroundColor Yellow

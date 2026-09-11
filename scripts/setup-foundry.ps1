#!/usr/bin/env pwsh
# azd `postup` hook. Runs at the end of `azd up`. Prompts whether to ALSO deploy a
# network-isolated Foundry spoke (foundry-samples template 19) and peer it to this hub.
# Safe to decline — the hub is already deployed. Does NOTHING on teardown (azd down untouched).
$ErrorActionPreference = 'Stop'

# --- CI / non-interactive guard: never block or auto-build in pipelines ---
if ($env:AZD_SKIP_FOUNDRY -eq 'true') { Write-Host 'AZD_SKIP_FOUNDRY=true — skipping Foundry setup.'; exit 0 }

Write-Host ''
Write-Host 'Hub is deployed (VNet + VPN + APIM).' -ForegroundColor Green
Write-Host 'OPTIONAL: deploy a network-isolated Foundry spoke (template 19) and peer it to the hub' -ForegroundColor Yellow
Write-Host '  so a private agent can reach APIM (and on-prem data) over the peering.' -ForegroundColor Yellow
Write-Host '  Adds Cosmos DB, AI Search (Standard), ACR (Premium), App Insights + a model,' -ForegroundColor Yellow
Write-Host '  takes ~45-60 min (capability host ~30-35 min), and has ongoing cost.' -ForegroundColor Yellow
try { $ans = Read-Host 'Set up Foundry + spoke VNet + peering now? [y/N]' }
catch { Write-Host 'Non-interactive — skipping.'; exit 0 }
if ($ans -notmatch '^(y|yes)$') { Write-Host 'Skipped. Re-run scripts/setup-foundry.ps1 anytime to do it.'; exit 0 }

# --- Hub context from azd / az ---
$hubRg    = (azd env get-value AZURE_RESOURCE_GROUP).Trim()
$apimName = (azd env get-value APIM_NAME).Trim()
$envName  = (azd env get-value AZURE_ENV_NAME).Trim()
$hubVnet  = (az network vnet list -g $hubRg --query "[0].name" -o tsv).Trim()

# --- Spoke params (env overrides or defaults). 10.x is NOT allowed in Canada Central -> 172.16/16. ---
$region    = if ($env:FOUNDRY_REGION) { $env:FOUNDRY_REGION } else { 'canadacentral' }
$spokeRg   = if ($env:FOUNDRY_RG) { $env:FOUNDRY_RG } else { "rg-foundry-$envName" }
$spokeCidr = if ($env:FOUNDRY_VNET_CIDR) { $env:FOUNDRY_VNET_CIDR } else { '172.16.0.0/16' }
$agentCidr = if ($env:FOUNDRY_AGENT_CIDR) { $env:FOUNDRY_AGENT_CIDR } else { '172.16.0.0/24' }
$peCidr    = if ($env:FOUNDRY_PE_CIDR) { $env:FOUNDRY_PE_CIDR } else { '172.16.1.0/24' }
$model     = if ($env:FOUNDRY_MODEL) { $env:FOUNDRY_MODEL } else { 'gpt-4o-mini' }
$modelVer  = if ($env:FOUNDRY_MODEL_VERSION) { $env:FOUNDRY_MODEL_VERSION } else { '2024-07-18' }
$apimIp    = if ($env:APIM_PRIVATE_IP) { $env:APIM_PRIVATE_IP } else { '10.100.1.4' }

Write-Host "Hub: rg=$hubRg vnet=$hubVnet apim=$apimName" -ForegroundColor Cyan
Write-Host "Spoke: rg=$spokeRg cidr=$spokeCidr region=$region model=$model ($modelVer)" -ForegroundColor Cyan
$newIp = Read-Host "APIM private IP for the DNS record is '$apimIp' (Premium v2 is dynamic). Enter to accept, or type a new IP"
if ($newIp) { $apimIp = $newIp.Trim() }

# --- Register providers required by template 19 (idempotent) ---
foreach ($p in 'Microsoft.KeyVault','Microsoft.CognitiveServices','Microsoft.Storage','Microsoft.Search','Microsoft.Network','Microsoft.App','Microsoft.ContainerService','Microsoft.DocumentDB') {
  az provider register --namespace $p --only-show-errors | Out-Null
}

# --- Fetch template 19 (not vendored — pulled fresh) ---
$work = Join-Path ([IO.Path]::GetTempPath()) "foundry-samples-$(Get-Random)"
git clone --depth 1 https://github.com/microsoft-foundry/foundry-samples.git $work
$tpl = Join-Path $work 'infrastructure/infrastructure-setup-bicep/19-private-network-agent-tools'
if (-not (Test-Path (Join-Path $tpl 'main.bicep'))) { throw "Template 19 main.bicep not found at $tpl — review the foundry-samples layout." }

# --- Deploy Foundry spoke (long-running; ~45-60 min) ---
az group create -n $spokeRg -l $region --only-show-errors | Out-Null
Write-Host 'Deploying Foundry (capability host step is ~30-35 min — do NOT cancel)...' -ForegroundColor Cyan
az deployment group create -g $spokeRg --template-file (Join-Path $tpl 'main.bicep') `
  --parameters location=$region modelName=$model modelFormat=OpenAI modelVersion=$modelVer `
               vnetAddressPrefix=$spokeCidr agentSubnetPrefix=$agentCidr peSubnetPrefix=$peCidr `
  --only-show-errors

# --- Discover the spoke VNet the template created, then peer + DNS ---
$spokeVnet = (az network vnet list -g $spokeRg --query "[0].name" -o tsv).Trim()
if (-not $spokeVnet) { throw "No VNet found in $spokeRg after the Foundry deploy." }

$repoRoot = Split-Path $PSScriptRoot -Parent
Write-Host "Peering $spokeVnet <-> $hubVnet and creating azure-api.net private DNS..." -ForegroundColor Cyan
az deployment sub create -l $region --template-file (Join-Path $repoRoot 'peering/peering.bicep') `
  --parameters hubResourceGroup=$hubRg hubVnetName=$hubVnet spokeResourceGroup=$spokeRg spokeVnetName=$spokeVnet `
               apimName=$apimName apimPrivateIp=$apimIp `
  --only-show-errors

Write-Host ''
Write-Host "Done. Foundry spoke deployed and peered. From the spoke: https://$apimName.azure-api.net/onprem/json" -ForegroundColor Green
Write-Host 'Teardown is MANUAL (Foundry capability-host purge order) — see peering/readme.md + template 19 cleanup.' -ForegroundColor Yellow

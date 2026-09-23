#!/usr/bin/env sh
# azd `postup` hook (POSIX). By DEFAULT deploys a network-isolated Foundry spoke (template 19)
# and peers it to this hub so `azd up` provisions the whole solution. Opt out by answering 'n',
# setting AZD_SKIP_FOUNDRY=true, or running non-interactively (CI). Does nothing on teardown.
set -e

get_azd_optional_value() {
  if value=$(azd env get-value "$1" 2>/dev/null); then
    printf '%s' "$value" | tr -d '[:space:]'
  fi
}

if [ "$AZD_SKIP_FOUNDRY" = "true" ]; then echo "AZD_SKIP_FOUNDRY=true — skipping Foundry setup."; exit 0; fi

hubRg=$(azd env get-value AZURE_RESOURCE_GROUP | tr -d '[:space:]')
apimName=$(azd env get-value APIM_NAME | tr -d '[:space:]')
envName=$(azd env get-value AZURE_ENV_NAME | tr -d '[:space:]')
subscriptionId=$(azd env get-value AZURE_SUBSCRIPTION_ID | tr -d '[:space:]')
hubVnet=$(az network vnet list --subscription "$subscriptionId" -g "$hubRg" --query "[0].name" -o tsv | tr -d '[:space:]')
configuredFoundryRegion=$(get_azd_optional_value FOUNDRY_REGION)
configuredFoundryModel=$(get_azd_optional_value FOUNDRY_MODEL)
configuredFoundryModelVersion=$(get_azd_optional_value FOUNDRY_MODEL_VERSION)

echo ""
echo "Hub is deployed (VNet + VPN + APIM)."

# Reuse a Foundry VNet already connected to this hub unless FOUNDRY_RG explicitly selects
# another resource group. This keeps repeated azd up runs idempotent.
reuseExisting=false
if [ -z "$FOUNDRY_RG" ]; then
  existingFoundryVnetId=$(az network vnet peering list --subscription "$subscriptionId" -g "$hubRg" --vnet-name "$hubVnet" \
    --query "[?peeringState=='Connected' && contains(remoteVirtualNetwork.id, '/resourceGroups/rg-foundry-')].remoteVirtualNetwork.id | [0]" \
    -o tsv 2>/dev/null | tr -d '\r\n')
  if [ -n "$existingFoundryVnetId" ]; then
    candidateRg=$(printf '%s' "$existingFoundryVnetId" | cut -d/ -f5)
    candidateAccount=$(az cognitiveservices account list --subscription "$subscriptionId" -g "$candidateRg" --query '[0].name' -o tsv | tr -d '[:space:]')
    if [ -n "$candidateAccount" ]; then
      reuseExisting=true
      spokeRg=$candidateRg
      spokeVnet=$(printf '%s' "$existingFoundryVnetId" | cut -d/ -f9)
      region=$(az network vnet show --subscription "$subscriptionId" -g "$spokeRg" -n "$spokeVnet" --query location -o tsv | tr -d '[:space:]')
      echo "Found connected Foundry spoke '$spokeVnet' in '$spokeRg'; reusing it."
    fi
  fi
fi

if [ "$reuseExisting" = false ]; then
  echo "INCLUDED by default: deploy a network-isolated Foundry spoke (template 19) + peer it to the hub."
  echo "  Adds Cosmos DB, AI Search (Basic), ACR (Premium), App Insights + a model,"
  echo "  takes ~45-60 min (capability host ~30-35 min), and has ongoing cost."
  if [ ! -t 0 ]; then echo "Non-interactive — skipping."; exit 0; fi
  printf "Set up Foundry + spoke VNet + peering now? [Y/n] "
  read ans
  case "$ans" in n|N|no|NO) echo "Declined. Re-run scripts/setup-foundry.sh anytime."; exit 0;; *) ;; esac

  region=${FOUNDRY_REGION:-${configuredFoundryRegion:-swedencentral}}   # CC/East US lacked Cosmos+AI Search capacity; peers cross-region to CC hub
  spokeRg=${FOUNDRY_RG:-rg-foundry-$envName}
fi
spokeCidr=${FOUNDRY_VNET_CIDR:-172.16.0.0/16}   # 10.x not allowed in Canada Central
agentCidr=${FOUNDRY_AGENT_CIDR:-172.16.0.0/24}
peCidr=${FOUNDRY_PE_CIDR:-172.16.1.0/24}
model=${FOUNDRY_MODEL:-${configuredFoundryModel:-gpt-5.4-mini}}
modelVer=${FOUNDRY_MODEL_VERSION:-${configuredFoundryModelVersion:-2026-03-17}}
apimIp=${APIM_PRIVATE_IP:-10.100.1.4}
# Entra auth for the Foundry API. Explicit environment variables override the app
# registrations provisioned by the main Bicep deployment.
provisionedTenantId=$(azd env get-value ENTRA_TENANT_ID 2>/dev/null || true)
provisionedAudience=$(azd env get-value ENTRA_API_AUDIENCE 2>/dev/null || true)
entraTenantId=${ENTRA_TENANT_ID:-$provisionedTenantId}
jwtAudience=${JWT_AUDIENCE:-$provisionedAudience}
corsOrigins=${CORS_ORIGINS:-'["http://localhost:5173"]'}

echo "Hub: rg=$hubRg vnet=$hubVnet apim=$apimName | Spoke: rg=$spokeRg region=$region model=$model"
printf "APIM private IP for DNS is '%s' (Premium v2 is dynamic). Enter to accept or type a new IP: " "$apimIp"
read newIp; [ -n "$newIp" ] && apimIp=$(echo "$newIp" | tr -d '[:space:]')

repoRoot=$(cd "$(dirname "$0")/.." && pwd)
if [ "$reuseExisting" = false ]; then
  for p in Microsoft.KeyVault Microsoft.CognitiveServices Microsoft.Storage Microsoft.Search Microsoft.Network Microsoft.App Microsoft.ContainerService Microsoft.DocumentDB; do
    az provider register --subscription "$subscriptionId" --namespace "$p" --only-show-errors >/dev/null
  done

  tpl="$repoRoot/infra/foundry-spoke"
  [ -f "$tpl/main.bicep" ] || { echo "Vendored Foundry template not found at $tpl"; exit 1; }

  az group create --subscription "$subscriptionId" -n "$spokeRg" -l "$region" --only-show-errors >/dev/null
  echo "Deploying Foundry (capability host ~30-35 min — do NOT cancel)..."
  az deployment group create --subscription "$subscriptionId" -g "$spokeRg" --template-file "$tpl/main.bicep" \
    --parameters location="$region" modelName="$model" modelFormat=OpenAI modelVersion="$modelVer" \
                 vnetAddressPrefix="$spokeCidr" agentSubnetPrefix="$agentCidr" peSubnetPrefix="$peCidr" \
    --only-show-errors || { echo "Foundry deployment failed. Review the errors above (common causes: model quota/version for '$model', or regional capacity), then re-run."; exit 1; }

  spokeVnet=$(az network vnet list --subscription "$subscriptionId" -g "$spokeRg" --query "[0].name" -o tsv | tr -d '[:space:]')
  [ -n "$spokeVnet" ] || { echo "No VNet found in $spokeRg after Foundry deploy."; exit 1; }
fi

# Discover the Foundry account so peering.bicep can publish it as an APIM backend
foundryAcct=$(az cognitiveservices account list --subscription "$subscriptionId" -g "$spokeRg" --query "[0].name" -o tsv | tr -d '[:space:]')
foundryEndpoint=$(az cognitiveservices account show --subscription "$subscriptionId" -g "$spokeRg" -n "$foundryAcct" --query "properties.endpoint" -o tsv | tr -d '[:space:]')
foundryDeployment=$(az cognitiveservices account deployment list --subscription "$subscriptionId" -g "$spokeRg" -n "$foundryAcct" --query "[0].name" -o tsv | tr -d '[:space:]')

repoRoot=$(cd "$(dirname "$0")/.." && pwd)
echo "Peering $spokeVnet <-> $hubVnet, DNS, and publishing Foundry '$foundryAcct' as an APIM backend..."
az deployment sub create --subscription "$subscriptionId" -l "$region" --template-file "$repoRoot/peering/peering.bicep" \
  --parameters hubResourceGroup="$hubRg" hubVnetName="$hubVnet" spokeResourceGroup="$spokeRg" spokeVnetName="$spokeVnet" \
               apimName="$apimName" apimPrivateIp="$apimIp" \
               wireFoundryBackend=true foundryResourceGroup="$spokeRg" foundryAccountName="$foundryAcct" \
               foundryEndpoint="$foundryEndpoint" foundryDeploymentName="$foundryDeployment" \
               entraTenantId="$entraTenantId" jwtAudience="$jwtAudience" allowedCorsOrigins="$corsOrigins" \
  --only-show-errors || { echo "Peering/DNS deployment failed. See errors above."; exit 1; }

echo ""
echo "Done. From the spoke: https://$apimName.azure-api.net/onprem/json"
echo "Foundry model via APIM: https://$apimName.azure-api.net/openai/deployments/$foundryDeployment/chat/completions?api-version=2024-02-01"
echo "Teardown is MANUAL (Foundry caphost purge order) — see peering/readme.md + template 19 cleanup."

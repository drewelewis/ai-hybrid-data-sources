#!/usr/bin/env sh
# azd `postup` hook (POSIX). Optionally deploy a network-isolated Foundry spoke (template 19)
# and peer it to this hub. Safe to decline. Does nothing on teardown.
set -e

if [ "$AZD_SKIP_FOUNDRY" = "true" ]; then echo "AZD_SKIP_FOUNDRY=true — skipping Foundry setup."; exit 0; fi

echo ""
echo "Hub is deployed (VNet + VPN + APIM)."
echo "OPTIONAL: deploy a network-isolated Foundry spoke (template 19) + peer it to the hub."
echo "  Adds Cosmos DB, AI Search (Standard), ACR (Premium), App Insights + a model,"
echo "  takes ~45-60 min (capability host ~30-35 min), and has ongoing cost."
if [ ! -t 0 ]; then echo "Non-interactive — skipping."; exit 0; fi
printf "Set up Foundry + spoke VNet + peering now? [y/N] "
read ans
case "$ans" in y|Y|yes|YES) ;; *) echo "Skipped. Re-run scripts/setup-foundry.sh anytime."; exit 0;; esac

hubRg=$(azd env get-value AZURE_RESOURCE_GROUP | tr -d '[:space:]')
apimName=$(azd env get-value APIM_NAME | tr -d '[:space:]')
envName=$(azd env get-value AZURE_ENV_NAME | tr -d '[:space:]')
hubVnet=$(az network vnet list -g "$hubRg" --query "[0].name" -o tsv | tr -d '[:space:]')

region=${FOUNDRY_REGION:-canadacentral}
spokeRg=${FOUNDRY_RG:-rg-foundry-$envName}
spokeCidr=${FOUNDRY_VNET_CIDR:-172.16.0.0/16}   # 10.x not allowed in Canada Central
agentCidr=${FOUNDRY_AGENT_CIDR:-172.16.0.0/24}
peCidr=${FOUNDRY_PE_CIDR:-172.16.1.0/24}
model=${FOUNDRY_MODEL:-gpt-4o-mini}
modelVer=${FOUNDRY_MODEL_VERSION:-2024-07-18}
apimIp=${APIM_PRIVATE_IP:-10.100.1.4}

echo "Hub: rg=$hubRg vnet=$hubVnet apim=$apimName | Spoke: rg=$spokeRg cidr=$spokeCidr region=$region model=$model"
printf "APIM private IP for DNS is '%s' (Premium v2 is dynamic). Enter to accept or type a new IP: " "$apimIp"
read newIp; [ -n "$newIp" ] && apimIp=$(echo "$newIp" | tr -d '[:space:]')

for p in Microsoft.KeyVault Microsoft.CognitiveServices Microsoft.Storage Microsoft.Search Microsoft.Network Microsoft.App Microsoft.ContainerService Microsoft.DocumentDB; do
  az provider register --namespace "$p" --only-show-errors >/dev/null
done

work=$(mktemp -d)
git clone --depth 1 https://github.com/microsoft-foundry/foundry-samples.git "$work"
tpl="$work/infrastructure/infrastructure-setup-bicep/19-private-network-agent-tools"
[ -f "$tpl/main.bicep" ] || { echo "Template 19 main.bicep not found at $tpl"; exit 1; }

az group create -n "$spokeRg" -l "$region" --only-show-errors >/dev/null
echo "Deploying Foundry (capability host ~30-35 min — do NOT cancel)..."
az deployment group create -g "$spokeRg" --template-file "$tpl/main.bicep" \
  --parameters location="$region" modelName="$model" modelFormat=OpenAI modelVersion="$modelVer" \
               vnetAddressPrefix="$spokeCidr" agentSubnetPrefix="$agentCidr" peSubnetPrefix="$peCidr" \
  --only-show-errors

spokeVnet=$(az network vnet list -g "$spokeRg" --query "[0].name" -o tsv | tr -d '[:space:]')
[ -n "$spokeVnet" ] || { echo "No VNet found in $spokeRg after Foundry deploy."; exit 1; }

repoRoot=$(cd "$(dirname "$0")/.." && pwd)
echo "Peering $spokeVnet <-> $hubVnet and creating azure-api.net private DNS..."
az deployment sub create -l "$region" --template-file "$repoRoot/peering/peering.bicep" \
  --parameters hubResourceGroup="$hubRg" hubVnetName="$hubVnet" spokeResourceGroup="$spokeRg" spokeVnetName="$spokeVnet" \
               apimName="$apimName" apimPrivateIp="$apimIp" \
  --only-show-errors

echo ""
echo "Done. From the spoke: https://$apimName.azure-api.net/onprem/json"
echo "Teardown is MANUAL (Foundry caphost purge order) — see peering/readme.md + template 19 cleanup."

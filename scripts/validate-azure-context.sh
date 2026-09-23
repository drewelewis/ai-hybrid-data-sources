#!/usr/bin/env sh
set -eu

azd_subscription_id=${AZURE_SUBSCRIPTION_ID:-}
if [ -z "$azd_subscription_id" ]; then
  echo "AZURE_SUBSCRIPTION_ID is not set. Select a subscription for the azd environment before provisioning." >&2
  exit 1
fi

if ! az_subscription_id=$(az account show --query id --output tsv 2>/dev/null | tr -d '\r\n'); then
  echo "Azure CLI is not authenticated. Run az login and select the intended subscription before azd up." >&2
  exit 1
fi
if [ -z "$az_subscription_id" ]; then
  echo "Azure CLI is not authenticated. Run az login and select the intended subscription before azd up." >&2
  exit 1
fi

if [ "$az_subscription_id" != "$azd_subscription_id" ]; then
  echo "Azure subscription mismatch; provisioning was stopped before resources were created." >&2
  echo "azd environment '${AZURE_ENV_NAME:-unknown}' targets: $azd_subscription_id" >&2
  echo "Azure CLI currently targets:                  $az_subscription_id" >&2
  echo "Select the same subscription in both az and azd, then run azd up again." >&2
  exit 1
fi

account_name=$(az account show --query name --output tsv | tr -d '\r\n')
tenant_id=$(az account show --query tenantId --output tsv | tr -d '\r\n')
azd_tenant_id=${AZURE_TENANT_ID:-}
if [ -z "$azd_tenant_id" ]; then
  if value=$(azd env get-value AZURE_TENANT_ID 2>/dev/null); then
    azd_tenant_id=$(printf '%s' "$value" | tr -d '\r\n')
  fi
fi
if [ "$azd_tenant_id" != "$tenant_id" ]; then
  echo "Azure tenant mismatch. azd targets '$azd_tenant_id', but Azure CLI targets '$tenant_id'." >&2
  echo "Run azd auth login --tenant-id $tenant_id." >&2
  exit 1
fi
echo "Azure context verified: $account_name ($az_subscription_id), tenant $tenant_id."

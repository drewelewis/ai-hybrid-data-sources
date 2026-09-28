#!/usr/bin/env sh
set -eu

network_profile=$(azd env get-value APIM_NETWORK_PROFILE | tr -d '[:space:]')
if [ "$network_profile" != "standardV2PrivateLink" ]; then
  echo "APIM network profile '$network_profile' requires no post-provision public-access change."
  exit 0
fi

subscription_id=$(azd env get-value AZURE_SUBSCRIPTION_ID | tr -d '[:space:]')
resource_group=$(azd env get-value AZURE_RESOURCE_GROUP | tr -d '[:space:]')
apim_name=$(azd env get-value APIM_NAME | tr -d '[:space:]')
resource_id="/subscriptions/$subscription_id/resourceGroups/$resource_group/providers/Microsoft.ApiManagement/service/$apim_name"
url="https://management.azure.com$resource_id?api-version=2025-09-01-preview"
private_endpoint_name="pep-$apim_name"
max_attempts=20
retry_delay_seconds=30

if ! connection_state=$(az network private-endpoint show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$private_endpoint_name" \
    --query 'privateLinkServiceConnections[0].privateLinkServiceConnectionState.status' \
    --output tsv \
    --only-show-errors); then
  echo "Unable to read Standard v2 APIM private endpoint '$private_endpoint_name'. Public network access was left enabled." >&2
  exit 1
fi
connection_state=$(printf '%s' "$connection_state" | tr -d '[:space:]')
if [ "$connection_state" != "Approved" ]; then
  echo "Standard v2 APIM private endpoint '$private_endpoint_name' is not approved. Current state: '$connection_state'. Public network access was left enabled." >&2
  exit 1
fi

current_state=$(az rest --method get --url "$url" \
  --query properties.publicNetworkAccess \
  --output tsv \
  --only-show-errors | tr -d '[:space:]')
if [ "$current_state" = "Disabled" ]; then
  echo "Standard v2 public gateway access is already disabled; Private Link is the inbound gateway path."
  exit 0
fi

echo "Disabling the Standard v2 public gateway after Private Link provisioning..."
if ! az rest --method patch --url "$url" \
    --headers 'Content-Type=application/json' \
    --body '{"properties":{"publicNetworkAccess":"Disabled"}}' \
    --output none \
    --only-show-errors; then
  echo "Failed to start the Standard v2 public-access update for '$apim_name'." >&2
  exit 1
fi

attempt=1
while [ "$attempt" -le "$max_attempts" ]; do
  if status=$(az rest --method get --url "$url" \
      --query "join('|', [properties.provisioningState, properties.publicNetworkAccess])" \
      --output tsv \
      --only-show-errors); then
    provisioning_state=${status%%|*}
    public_network_access=${status#*|}
    if [ "$provisioning_state" = "Succeeded" ] && [ "$public_network_access" = "Disabled" ]; then
      echo "Standard v2 public gateway access is disabled; Private Link is the inbound gateway path."
      exit 0
    fi
    echo "APIM public-access update is still running (provisioning=$provisioning_state, publicAccess=$public_network_access)." >&2
  else
    echo "Unable to read APIM update status on attempt $attempt of $max_attempts." >&2
  fi
  if [ "$attempt" -lt "$max_attempts" ]; then
    sleep "$retry_delay_seconds"
  fi
  attempt=$((attempt + 1))
done

echo "Standard v2 APIM public access did not reach Disabled/Succeeded after $max_attempts checks. Inspect '$apim_name' before using it." >&2
exit 1

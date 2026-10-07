#!/usr/bin/env sh
set -eu

get_azd_value() {
  value=$(azd env get-value "$1" 2>/dev/null | tr -d '\r')
  if [ -z "$value" ]; then
    echo "The active azd environment does not contain '$1'. Run 'azd up' before publishing the mapping." >&2
    exit 1
  fi
  printf '%s' "$value"
}

mapping_file=${1:-${LLM_MAPPING_FILE:-untracked/new_v2-mapping.json}}
if [ ! -f "$mapping_file" ]; then
  echo "Mapping file '$mapping_file' does not exist." >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  python_cmd=python3
elif command -v python >/dev/null 2>&1; then
  python_cmd=python
else
  echo 'Python 3 is required to validate the mapping JSON before upload.' >&2
  exit 1
fi

"$python_cmd" -c '
import json, sys
with open(sys.argv[1], encoding="utf-8-sig") as stream:
    mapping = json.load(stream)
if not isinstance(mapping, dict) or not mapping:
    raise SystemExit("Mapping has no product mappings.")
for product, config in mapping.items():
    deployments = config.get("deployments", [])
    if not deployments:
        raise SystemExit(f"Product {product!r} has no deployments.")
    for deployment in deployments:
        if (not deployment.get("name")
                or not deployment.get("backendID")
                or deployment.get("maxTokensPerMinute", 0) <= 0):
            raise SystemExit(f"Product {product!r} contains an invalid deployment mapping.")
' "$mapping_file"

subscription_id=$(get_azd_value AZURE_SUBSCRIPTION_ID)
resource_group=$(get_azd_value AZURE_RESOURCE_GROUP)
storage_account=$(get_azd_value MAPPING_STORAGE_ACCOUNT)
container=$(get_azd_value MAPPING_CONTAINER)
blob_name=$(get_azd_value MAPPING_BLOB_NAME)
private_ip=$(azd env get-value MAPPING_STORAGE_PRIVATE_IP 2>/dev/null | tr -d '\r' || true)
storage_suffix=$(az cloud show --query suffixes.storageEndpoint --output tsv --only-show-errors | sed 's/^\.//')
blob_host="$storage_account.blob.$storage_suffix"
blob_url="https://$blob_host/$container/$blob_name"
container_scope="/subscriptions/$subscription_id/resourceGroups/$resource_group/providers/Microsoft.Storage/storageAccounts/$storage_account/blobServices/default/containers/$container"

az account set --subscription "$subscription_id" --only-show-errors
if [ -z "$private_ip" ]; then
  private_endpoint_name="pep-$storage_account"
  network_interface_id=$(az network private-endpoint show \
    --resource-group "$resource_group" \
    --name "$private_endpoint_name" \
    --query 'networkInterfaces[0].id' \
    --output tsv \
    --only-show-errors)
  if [ -z "$network_interface_id" ]; then
    echo "Unable to resolve the network interface for private endpoint '$private_endpoint_name'." >&2
    exit 1
  fi
  private_ip=$(az network nic show \
    --ids "$network_interface_id" \
    --query 'ipConfigurations[0].privateIPAddress' \
    --output tsv \
    --only-show-errors)
  if [ -z "$private_ip" ]; then
    echo "Unable to resolve the private IP for private endpoint '$private_endpoint_name'." >&2
    exit 1
  fi
fi
account_type=$(az account show --query user.type --output tsv --only-show-errors)
identity_token=$(az account get-access-token \
  --resource 'https://management.azure.com/' \
  --query accessToken \
  --output tsv \
  --only-show-errors)
principal_id=$("$python_cmd" -c '
import base64, json, sys
payload = sys.argv[1].split(".")[1]
payload += "=" * (-len(payload) % 4)
print(json.loads(base64.urlsafe_b64decode(payload))["oid"])
' "$identity_token")
if [ "$account_type" = "user" ]; then
  principal_type=User
else
  principal_type=ServicePrincipal
fi

role_count=$(az role assignment list \
  --assignee-object-id "$principal_id" \
  --scope "$container_scope" \
  --query "[?roleDefinitionName=='Storage Blob Data Contributor'] | length(@)" \
  --output tsv \
  --only-show-errors)
if [ "$role_count" = "0" ]; then
  echo 'Granting the signed-in principal permission to publish the mapping blob...'
  az role assignment create \
    --assignee-object-id "$principal_id" \
    --assignee-principal-type "$principal_type" \
    --role 'Storage Blob Data Contributor' \
    --scope "$container_scope" \
    --output none \
    --only-show-errors
fi

temporary_download=$(mktemp)
trap 'rm -f "$temporary_download"' EXIT

attempt=1
max_attempts=12
while [ "$attempt" -le "$max_attempts" ]; do
  access_token=$(az account get-access-token \
    --resource 'https://storage.azure.com/' \
    --query accessToken \
    --output tsv \
    --only-show-errors)
  if curl \
      --silent \
      --show-error \
      --fail-with-body \
      --request PUT \
      --resolve "$blob_host:443:$private_ip" \
      --header "Authorization: Bearer $access_token" \
      --header 'x-ms-version: 2023-11-03' \
      --header "x-ms-date: $(LC_ALL=C date -u '+%a, %d %b %Y %H:%M:%S GMT')" \
      --header 'x-ms-blob-type: BlockBlob' \
      --header 'Content-Type: application/json' \
      --upload-file "$mapping_file" \
      "$blob_url"; then
    break
  fi
  if [ "$attempt" -eq "$max_attempts" ]; then
    echo "Unable to upload '$mapping_file'. Confirm the S2S VPN can route to $private_ip and RBAC propagation has completed." >&2
    exit 1
  fi
  echo "Upload attempt $attempt failed; waiting for network or RBAC propagation..." >&2
  sleep 15
  attempt=$((attempt + 1))
done

curl \
  --silent \
  --show-error \
  --fail-with-body \
  --resolve "$blob_host:443:$private_ip" \
  --header "Authorization: Bearer $access_token" \
  --header 'x-ms-version: 2023-11-03' \
  --header "x-ms-date: $(LC_ALL=C date -u '+%a, %d %b %Y %H:%M:%S GMT')" \
  --output "$temporary_download" \
  "$blob_url"

source_hash=$("$python_cmd" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$mapping_file")
download_hash=$("$python_cmd" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$temporary_download")
if [ "$source_hash" != "$download_hash" ]; then
  echo 'The uploaded mapping does not match the local file.' >&2
  exit 1
fi

echo "Published and verified mapping: $blob_url"

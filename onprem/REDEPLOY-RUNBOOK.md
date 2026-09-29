# Redeploy runbook — tear down / bring up without breaking on-prem

This repo's baseline is meant to be **torn down when idle and brought back up on demand**
(both selectable APIM tiers and the VPN are always-on resources). This runbook lists exactly
what to reconfigure on each `azd up`, and how to keep on-prem churn to a minimum so the
tunnel comes back with the least effort.

> **"The tunnel stays up" caveat.** `azd down` deletes the resource group, which **destroys
> the Azure VPN gateway** — so the tunnel physically drops every cycle. What you *can* keep
> stable is the **on-prem side config**: if you follow the rules below, the only value that
> changes on-prem between cycles is the **Azure gateway public IP** (and only if you don't
> pin it — see [Appendix](#appendix--pin-the-gateway-ip-for-zero-on-prem-churn)).

---

## Core principle — what rotates vs. what stays stable

Resource **names** are derived from
`resourceToken = uniqueString(subscription, environmentName, location)`, so they are
**deterministic**: reuse the same azd environment, subscription, and region and every
resource comes back with the **same name**.

| Value | Stable across redeploy? | Condition / note |
| --- | --- | --- |
| Resource names (`vnet-…`, `apim-…`, `vng-…`, `cn-…`) | ✅ Stable | Same azd env name + subscription + region |
| VNet space `10.100.0.0/16`, on-prem LAN `192.168.50.0/24` | ✅ Stable | Hard-coded in Bicep / on-prem config |
| IKE/ESP proposals (`AES256/SHA256/DHGroup14/no PFS`) | ✅ Stable | Hard-coded on both ends |
| APIM gateway FQDN (`apim-<token>.azure-api.net`) | ✅ Stable | Token-derived name |
| **VPN gateway public IP** (`VPN_GATEWAY_PUBLIC_IP`) | ❌ **Rotates** | New IP on every recreate → **update on-prem** |
| **APIM private IP** | ⚠️ May change | Premium v2 uses `10.100.1.x`; Standard v2 Private Link uses `10.100.2.x`. The hooks reconcile Foundry DNS. |
| APIM network profile | ✅ Stable | Saved as `APIM_NETWORK_PROFILE`; use a separate azd environment to change profiles |
| **IPsec PSK** (`sharedKey`) | ⚠️ Prompted | Re-enter the **same** value to avoid on-prem edits |
| Foundry spoke (Cosmos/Search/ACR/model) | ❌ Manual | `azd down` does **not** remove it; teardown is manual |

**Bottom line:** keep the azd environment name, subscription, region, and PSK the same, and
the *only* thing you touch on-prem each cycle is the **gateway public IP**.

---

## Before you start — pin these so names don't drift

Reuse the **same azd environment** every cycle (this preserves `resourceToken`, so hub names,
subnets, and the APIM FQDN all stay identical):

```bash
azd env list                       # confirm the environment you want
azd env select <your-env-name>     # e.g. dev4-standardv2
```

Do **not** change the subscription or `AZURE_LOCATION` (the hub region) between cycles —
either one changes the token and every hub resource name, including the APIM FQDN the
Foundry spoke resolves. `FOUNDRY_REGION` is independent because the Foundry spoke has its
own resource group.

---

## Bring-up steps

### 1. Provision

```bash
az login
az account set --subscription <subscription-id>
azd auth login --tenant-id <tenant-id>
azd up
```

At the prompt, re-enter the **same** IPsec `sharedKey` and `apimPublisherEmail` you used
before. Reusing the PSK means the on-prem secret does **not** need editing.

> The `postup` hook detects an existing Foundry spoke connected to the hub and reuses it
> automatically; it only reconciles peering, DNS, APIM, and RBAC. It prompts before the
> 45–60 minute Foundry deployment only when no connected spoke exists. Use
> `AZD_SKIP_FOUNDRY=true` only when you intentionally want to skip reconciliation.

### 2. Capture the new outputs

```bash
azd env get-value VPN_GATEWAY_PUBLIC_IP    # <-- the value that changed; update on-prem
azd env get-value VPN_CONNECTION_NAME
azd env get-value APIM_NAME
azd env get-value APIM_NETWORK_PROFILE
azd env get-value APIM_PRIVATE_IP
azd env get-value APIM_PRIVATE_DNS_ZONE
azd env get-value AZURE_RESOURCE_GROUP
```

### 3. Update the on-prem gateway IP (the only routine on-prem change)

On strongSwan 6, the Azure gateway public IP appears in **three** places: the connection's
`remote_addrs`, its remote identity, and the PSK entry's peer identity. The legacy
strongSwan 5 configuration in this repo stores it only as `right` and `rightid`; its generic
`: PSK` entry contains no IP. Update the applicable fields to `VPN_GATEWAY_PUBLIC_IP`; the
PSK **value** stays unchanged.

First detect the installed toolchain:

```sh
command -v apk opkg
swanctl --version 2>/dev/null || ipsec version
```

**OpenWrt 25.x+ / strongSwan 6 (`swanctl`)**:

```sh
cp /etc/swanctl/conf.d/azure.conf /etc/swanctl/conf.d/azure.conf.bak
OLD_IP="$(awk '$1 == "remote_addrs" { print $3; exit }' /etc/swanctl/conf.d/azure.conf)"
NEW_IP="<paste VPN_GATEWAY_PUBLIC_IP>"
test -n "$OLD_IP" || { echo "Could not find remote_addrs"; exit 1; }
sed -i "s/${OLD_IP}/${NEW_IP}/g" /etc/swanctl/conf.d/azure.conf
grep -E 'remote_addrs|id[[:space:]]*=' /etc/swanctl/conf.d/azure.conf
swanctl --load-all                    # reload; expect: loaded connection 'azure' + 1 secret
swanctl --initiate --child azure      # or wait for start_action=start
swanctl --list-sas                    # success = ESTABLISHED + INSTALLED 192.168.50.0/24 === 10.100.0.0/16
```

The `grep` output must show the new Azure IP for `remote_addrs`, `remote { id = ... }`, and
the `secrets` entry. Do not change the local identity.

**OpenWrt ≤ 24.x / strongSwan 5.x (legacy `ipsec.conf`)**:

```sh
cp /etc/ipsec.conf /etc/ipsec.conf.bak
OLD_IP="$(awk -F= '/^[[:space:]]*right=/{gsub(/[[:space:]]/, "", $2); print $2; exit}' /etc/ipsec.conf)"
NEW_IP="<paste VPN_GATEWAY_PUBLIC_IP>"
test -n "$OLD_IP" || { echo "Could not find right="; exit 1; }
sed -i "s/${OLD_IP}/${NEW_IP}/g" /etc/ipsec.conf
grep -E 'right=|rightid=' /etc/ipsec.conf
ipsec reload
ipsec down azure 2>/dev/null
ipsec up azure
ipsec statusall                       # look for ESTABLISHED + 192.168.50.0/24 === 10.100.0.0/16
```

The strongSwan 6 command updates the peer identity in the `swanctl` `secrets` block but does
not change its PSK value. The legacy `/etc/ipsec.secrets` needs no edit when it uses the
documented generic `: PSK` entry. Change the PSK value only if you entered a different
`sharedKey` during `azd up`.

### 4. Refresh the Foundry spoke DNS (only if using the spoke)

APIM can land on a **different private IP** after recreate. The Foundry setup hook reads
`APIM_PRIVATE_IP` and `APIM_PRIVATE_DNS_ZONE`, detects the connected spoke, and reconciles
the private DNS record, VNet links, APIM backend/API, and RBAC. Run the hook directly if
`azd up` skipped or failed during `postup`:

```bash
pwsh -NoProfile -File ./scripts/setup-foundry.ps1
```

See [peering/readme.md](../peering/readme.md) for the full peering + DNS walkthrough.

---

## Verify

```bash
# Azure side — allow ~1 min after the tunnel initiates:
az network vpn-connection show \
  --name "$(azd env get-value VPN_CONNECTION_NAME)" \
  --resource-group "$(azd env get-value AZURE_RESOURCE_GROUP)" \
  --query connectionStatus -o tsv          # expect: Connected

# From the Foundry spoke (if deployed):
nslookup apim-<token>.azure-api.net        # resolves to APIM's current private IP
curl -sk https://apim-<token>.azure-api.net/onprem/json
```

---

## Teardown

```bash
azd down                                   # removes the hub RG (VNet, VPN gw, APIM)
```

The **Foundry spoke is not** removed by `azd down` — tear it down manually in
capability-host purge order (see [peering/readme.md](../peering/readme.md) and foundry-samples
template 19 cleanup) if you want to drop its ongoing cost too.

> **Failed Foundry retry:** deleting a failed Foundry resource group does not immediately
> release its Key Vault or Cognitive Services names because both services retain soft-deleted
> resources. Retry with a fresh `FOUNDRY_RG` name (which generates a new deterministic
> suffix), or purge the deleted resources before reusing the original group name. Also rerun
> regional preflight: in the September 2026 deployment, West US 3 succeeded after AI Search
> capacity failures in Sweden Central and East US 2 and a Cosmos DB capacity failure in
> Canada Central.

---

## Appendix — pin the gateway IP for zero on-prem churn

To make the **gateway public IP survive teardown** (so on-prem never needs editing), the
public IP must live **outside** the azd-managed resource group that `azd down` deletes.
Options, in order of simplicity:

1. **Don't tear down the gateway.** Keep a minimal always-on RG with just the VNet + VPN
   gateway + public IP, and only `azd down`/`azd up` the APIM (the actual cost driver). This
   requires splitting the Bicep into a persistent network stack and an ephemeral APIM stack.
2. **Reference an existing static public IP.** Pre-create a Standard static public IP in a
   persistent RG and pass its resource ID into the gateway's `ipConfigurations` instead of
   creating `pip-vng-<token>` inline. `azd down` then leaves the address intact.

Both are **infra changes** (not covered by this runbook). Say the word and I can split the
stack or parameterize an existing public IP so the gateway IP is stable across cycles.

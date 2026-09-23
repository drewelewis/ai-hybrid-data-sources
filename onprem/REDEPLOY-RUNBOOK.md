# Redeploy runbook — tear down / bring up without breaking on-prem

This repo's baseline is meant to be **torn down when idle and brought back up on demand**
(APIM Premium v2 is an always-on tier). This runbook lists exactly what to reconfigure on
each `azd up`, and how to keep on-prem churn to a minimum so the tunnel comes back with the
least effort.

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
| **APIM private IP** (`10.100.1.x`) | ⚠️ May change | Premium v2 assigns dynamically → **update Foundry DNS** |
| **IPsec PSK** (`sharedKey`) | ⚠️ Prompted | Re-enter the **same** value to avoid on-prem edits |
| Foundry spoke (Cosmos/Search/ACR/model) | ❌ Manual | `azd down` does **not** remove it; teardown is manual |

**Bottom line:** keep the azd environment name, subscription, region, and PSK the same, and
the *only* thing you touch on-prem each cycle is the **gateway public IP**.

---

## Before you start — pin these so names don't drift

Reuse the **same azd environment** every cycle (this preserves `resourceToken`, so names,
subnets, and the APIM FQDN all stay identical):

```bash
azd env list                       # confirm the environment you want
azd env select <your-env-name>     # e.g. dev1
```

Do **not** change subscription or region between cycles — either one changes the token and
every resource name (and the APIM FQDN the Foundry spoke resolves) will differ.

---

## Bring-up steps

### 1. Provision

```bash
azd auth login
azd up
```

At the prompt, re-enter the **same** IPsec `sharedKey` and `apimPublisherEmail` you used
before. Reusing the PSK means the on-prem secret does **not** need editing.

> The `postup` hook then offers to (re)deploy and peer the Foundry spoke — default **Yes**.
> If the spoke already exists, decline with **n** (or `AZD_SKIP_FOUNDRY=true`) to skip the
> ~45–60 min redeploy and just refresh peering/DNS manually (Step 4).

### 2. Capture the new outputs

```bash
azd env get-value VPN_GATEWAY_PUBLIC_IP    # <-- the value that changed; update on-prem
azd env get-value VPN_CONNECTION_NAME
azd env get-value APIM_NAME
azd env get-value AZURE_RESOURCE_GROUP
```

### 3. Update the on-prem gateway IP (the only routine on-prem change)

The on-prem endpoint points at the Azure gateway public IP in **three** places: the
connection's `remote_addrs`, its `remote id`, and the PSK `secrets` id. Update all three to
the new `VPN_GATEWAY_PUBLIC_IP`.

**OpenWrt 25.x+ / strongSwan 6 (`swanctl`)** — edit `/etc/swanctl/conf.d/azure.conf`:

```sh
NEW_IP="<paste VPN_GATEWAY_PUBLIC_IP>"
sed -i "s/^\(\s*remote_addrs\s*=\s*\).*/\1${NEW_IP}/" /etc/swanctl/conf.d/azure.conf
# update the two id = <old ip> lines (remote{} and secrets{}) to the new IP as well
vi /etc/swanctl/conf.d/azure.conf     # set remote{ id } and secrets{ id } to $NEW_IP
swanctl --load-all                    # reload; expect: loaded connection 'azure' + 1 secret
swanctl --initiate --child azure      # or wait for start_action=start
swanctl --list-sas                    # success = ESTABLISHED + INSTALLED 192.168.50.0/24 === 10.100.0.0/16
```

**OpenWrt ≤ 24.x / strongSwan 5.x (legacy `ipsec.conf`)** — edit `/etc/ipsec.conf`:

```sh
NEW_IP="<paste VPN_GATEWAY_PUBLIC_IP>"
sed -i "s/^\(\s*right=\).*/\1${NEW_IP}/; s/^\(\s*rightid=\).*/\1${NEW_IP}/" /etc/ipsec.conf
ipsec reload
ipsec up azure
ipsec statusall                       # look for ESTABLISHED + 192.168.50.0/24 === 10.100.0.0/16
```

> Only edit `/etc/ipsec.secrets` (or the `secrets{}` block) if you changed the PSK at the
> `azd up` prompt. If you reused it, leave the secret alone.

### 4. Refresh the Foundry spoke DNS (only if using the spoke)

APIM Premium v2 can land on a **different private IP** after recreate, and the Foundry spoke
resolves `apim-<token>.azure-api.net` to that IP via a private DNS A record. Confirm the
current IP and update the record if it moved:

```bash
# find APIM's current private IP (from a hub/on-prem host):
nmap -Pn -p443 --open 10.100.1.0/24        # the ASE front-end that answers 443

# re-run the peering + DNS module against the (still-existing) spoke:
az deployment sub create -l <region> \
  --template-file peering/peering.bicep \
  --parameters hubResourceGroup=$(azd env get-value AZURE_RESOURCE_GROUP) \
               hubVnetName=<hub-vnet> spokeResourceGroup=<spoke-rg> spokeVnetName=<spoke-vnet> \
               apimName=$(azd env get-value APIM_NAME) apimPrivateIp=<current-apim-ip>
```

See [peering/readme.md](peering/readme.md) for the full peering + DNS walkthrough.

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
capability-host purge order (see [peering/readme.md](peering/readme.md) and foundry-samples
template 19 cleanup) if you want to drop its ongoing cost too.

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

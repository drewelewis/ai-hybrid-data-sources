---
name: deploy-and-validate
description: 'Deploy this repo''s Azure infrastructure with azd and validate the Site-to-Site VPN tunnel and selectable APIM networking profile. Use for: provisioning the hybrid connectivity baseline, checking S2S/IPsec tunnel status, verifying Premium v2 injection or Standard v2 Private Link plus outbound integration, or tearing the environment down.'
---

# Deploy and validate the hybrid connectivity baseline

## When to use
- Provision or tear down the Foundry Option A baseline (VNet + S2S VPN + selectable APIM
  networking profile).
- Validate that the IPsec tunnel and selected APIM networking mode are configured correctly.

## Before you start
- Ensure `azd`, `az`, and Bicep are installed. Authenticate `az`, select the target
  subscription, then authenticate `azd` to the same tenant with
  `azd auth login --tenant-id <tenant-id>`.
- Compile first: `az bicep build --file infra/main.bicep`; fix errors before deploying.
- Only run `azd up`/`azd down` when the user explicitly asks.

## Deploy
1. `azd up` — answer the environment/subscription prompts. The `preup` hook runs a fresh
   regional preflight, removes unsupported or subscription-restricted candidates, then opens
   the APIM profile, hub, application, Foundry, and model pickers. Premium v2 injection is
   the default; Standard v2 Private Link plus outbound integration is the lower-cost
   alternative. A listed hub is eligible for an APIM create attempt, not capacity-approved.
   Confirm the IPsec `sharedKey` and `apimPublisherEmail` prompts. The selected APIM resource
   is staged first as the decisive live probe; VPN, App Service, DNS, identity, and Foundry
   continue only after APIM succeeds. Existing environments reuse saved choices only when
   fresh read-only checks still consider them eligible. Use separate azd environments for
   the two profiles. Standard v2 public-access disablement is asynchronous; the
   `postprovision` hook starts it once and polls for `Disabled`/`Succeeded`.
2. Capture outputs: `azd env get-values` — note `VPN_GATEWAY_PUBLIC_IP`,
   `VPN_CONNECTION_NAME`, `APIM_NAME`, `APIM_GATEWAY_URL`, `APIM_NETWORK_PROFILE`,
   `APIM_PRIVATE_IP`, `APIM_PRIVATE_DNS_ZONE`, and `VNET_ADDRESS_SPACE`.

## Configure on-prem
3. Put `VPN_GATEWAY_PUBLIC_IP` and your public IP/FQDN into `onprem/ipsec.conf`, and set the
   PSK in `/etc/ipsec.secrets` on the router — follow
   [../../../onprem/INSTALL-strongswan-openwrt-mx4300.md](../../../onprem/INSTALL-strongswan-openwrt-mx4300.md).

## Validate
4. Azure side — expect `Connected`:
   `az network vpn-connection show --name "$(azd env get-value VPN_CONNECTION_NAME)" --resource-group "$(azd env get-value AZURE_RESOURCE_GROUP)" --query connectionStatus -o tsv`
5. On-prem side — expect an ESTABLISHED SA for `192.168.50.0/24 === 10.100.0.0/16`:
   `ipsec statusall`
6. APIM:
   - `premiumV2Injection`: confirm `virtualNetworkType` is `Internal` and the gateway private
     IP is in `10.100.1.0/24`.
   - `standardV2PrivateLink`: confirm outbound integration uses `10.100.1.0/24`, the
     `Gateway` private endpoint is approved with an IP in `10.100.2.0/27`, DNS uses
     `privatelink.azure-api.net`, and `publicNetworkAccess` is `Disabled`.

## Tear down
7. `azd down` — APIM and the VPN are always-on and costly; drop them when not testing and
   re-`azd up` when needed.

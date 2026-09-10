---
name: deploy-and-validate
description: 'Deploy this repo''s Azure infrastructure with azd and validate the Site-to-Site VPN tunnel and APIM Premium v2. Use for: provisioning the hybrid connectivity baseline, checking S2S/IPsec tunnel status, verifying APIM VNet injection, or tearing the environment down.'
---

# Deploy and validate the hybrid connectivity baseline

## When to use
- Provision or tear down the Foundry Option A baseline (VNet + S2S VPN + APIM Premium v2).
- Validate that the IPsec tunnel is connected and APIM injected correctly.

## Before you start
- Ensure `azd`, `az`, and Bicep are installed and authenticated (`azd auth login`).
- Compile first: `az bicep build --file infra/main.bicep`; fix errors before deploying.
- Only run `azd up`/`azd down` when the user explicitly asks.

## Deploy
1. `azd up` — answer the prompts (env name, subscription, region, IPsec `sharedKey`,
   `apimPublisherEmail`). Premium v2 provisioning takes time.
2. Capture outputs: `azd env get-values` — note `VPN_GATEWAY_PUBLIC_IP`,
   `VPN_CONNECTION_NAME`, `APIM_NAME`, `APIM_GATEWAY_URL`, `VNET_ADDRESS_SPACE`.

## Configure on-prem
3. Put `VPN_GATEWAY_PUBLIC_IP` and your public IP/FQDN into `onprem/ipsec.conf`, and set the
   PSK in `/etc/ipsec.secrets` on the router — follow
   [../../../onprem/INSTALL-strongswan-openwrt-mx4300.md](../../../onprem/INSTALL-strongswan-openwrt-mx4300.md).

## Validate
4. Azure side — expect `Connected`:
   `az network vpn-connection show --name "$(azd env get-value VPN_CONNECTION_NAME)" --resource-group "$(azd env get-value AZURE_RESOURCE_GROUP)" --query connectionStatus -o tsv`
5. On-prem side — expect an ESTABLISHED SA for `192.168.50.0/24 === 10.100.0.0/16`:
   `ipsec statusall`
6. APIM — confirm the instance provisioned and holds a private IP in `10.100.1.0/24`
   (`Internal` injection; it may not answer ICMP).

## Tear down
7. `azd down` — Premium v2 is always-on and costly; drop it when not testing and re-`azd up`
   when needed.

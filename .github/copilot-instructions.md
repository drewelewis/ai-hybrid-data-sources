# Project Guidelines

Azure reference architecture that privately connects an on-premises estate to cloud AI
agents on **Azure AI Foundry** and **Microsoft Copilot Studio**. Infrastructure-only,
deployed with `azd`. See [README.md](../README.md) for the full architecture and the option
matrix; on-prem device setup is in
[onprem/INSTALL-strongswan-openwrt-mx4300.md](../onprem/INSTALL-strongswan-openwrt-mx4300.md).

## Architecture

- The deployed baseline is **Foundry Option A**: a hub VNet, a VpnGw1AZ Site-to-Site IPsec
  VPN to on-prem, and a selectable APIM profile. `premiumV2Injection` is the default and
  injects Premium v2 in `Internal` mode; `standardV2PrivateLink` uses Standard v2 inbound
  Private Link plus outbound VNet integration. Copilot Studio Option A reuses the tunnel.
- IaC lives in `infra/` (`main.bicep` → `resources.bicep`); `azure.yaml` drives `azd`. No
  application services are deployed.

## Build and validate

- Compile Bicep before committing IaC: `az bicep build --file infra/main.bicep` — it must
  succeed (the pre-existing `BCP035` warnings on the VPN connection are benign).
- Provision / tear down with `azd up` / `azd down`. `azd up` prompts for the IPsec
  `sharedKey` and `apimPublisherEmail`.
- Only run `azd up`/`azd down` when the user explicitly asks; never deploy automatically.

## Conventions

- Name resources with the `resourceToken` suffix pattern already used in `resources.bicep`.
- `main.parameters.json` uses `${ENV_VAR}` substitution only. Secure params with no default
  (`sharedKey`, `apimPublisherEmail`) are prompted by `azd`, so keep them OUT of that file.
- **APIM Premium v2 requires API version `2025-09-01-preview`** — `PremiumV2` is absent from
  the stable `2024-05-01` SKU enum. Do not lower the APIM `apiVersion`.
- The APIM subnet must stay **dedicated**, with an NSG allowing outbound 443 to
  `AzureKeyVault`. Premium v2 injection delegates it to
  `Microsoft.Web/hostingEnvironments`; Standard v2 outbound integration delegates it to
  `Microsoft.Web/serverFarms`. The Standard v2 private endpoint uses a separate subnet.
- The VPN gateway must use a zone-redundant **AZ SKU** (`VpnGw1AZ`) with a **zone-redundant
  public IP** (`zones: ['1','2','3']`) — non-AZ `VpnGw` SKUs are retired.
- APIM tier availability and subscription access vary by region, and the SKU API does not
  guarantee physical capacity. Keep the selected profile wired into regional preflight and
  retain APIM-first deployment staging.
- On-prem strongSwan differs by OpenWrt version: **25.x+ uses `apk` + strongSwan 6 (`swanctl`,
  `/etc/swanctl/conf.d/`, `/etc/init.d/swanctl`)**; ≤24.x uses `opkg` + `ipsec.conf`.
- Keep IPsec crypto and subnets in sync across `infra/resources.bicep`, `onprem/ipsec.conf`,
  and the strongSwan guide: VNet `10.100.0.0/16`, on-prem LAN `192.168.50.0/24`, IKEv2
  `AES256 / SHA256 / DHGroup14 / no PFS`.

## Security

- Never commit secrets. The real `onprem/ipsec.secrets`, `*.env`, `*.pem`, `*.key`,
  `.azure/`, and compiled `infra/main.json` are git-ignored — keep it that way.
- Only placeholder values belong in `onprem/ipsec.secrets.example` and `onprem/ipsec.conf`.

## Docs

- Keep the README platform-first (Azure AI Foundry, then Microsoft Copilot Studio) with
  options ordered most-secure-first (Option A). Update the "All options at a glance" table
  when options change.
- Do not create new markdown files to document changes unless asked.

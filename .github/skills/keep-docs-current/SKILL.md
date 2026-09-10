---
name: keep-docs-current
description: 'Keep this repo''s README.md and the on-prem strongSwan guide accurate and in sync when infra, connectivity options, or on-prem steps change — including recording real-deployment learnings (e.g., OpenWrt/strongSwan version divergences). Use when: updating the README option matrix or cost, documenting a deployment gotcha, syncing IPsec crypto/subnet values across files, or refreshing the MX4300 guide.'
---

# Keep the docs current

## When to use
- Infra changed in `infra/` (SKU, API version, subnets, resources) and docs must follow.
- A real deployment surfaced a gotcha worth capturing (versions, package managers, commands).
- The connectivity option set or cost changed.
- The on-prem strongSwan/tunnel steps need a fix.

## Rules
- **Edit existing docs in place.** Do not create new markdown files to describe changes.
- Keep the README **platform-first** (Azure AI Foundry, then Microsoft Copilot Studio) with
  options ordered **most-secure-first (Option A)**.
- Prefer concise, actionable edits; link rather than duplicate.

## Procedure
1. Identify what changed and which files it touches ([README.md](../../../README.md),
   [onprem/INSTALL-strongswan-openwrt-mx4300.md](../../../onprem/INSTALL-strongswan-openwrt-mx4300.md),
   or both).
2. Make the edit in place. For the README, also update the **"All options at a glance"**
   table and the **Cost comparison** if an option/footprint changed.
3. Run the **cross-file invariants** checklist below and reconcile any drift.
4. If IaC changed, recompile: `az bicep build --file infra/main.bicep` (must succeed).
5. Validate: check the file for errors and confirm relative links resolve.

## Cross-file invariants (must match everywhere they appear)
- **IPsec crypto:** IKEv2 `AES256 / SHA256 / DHGroup14 (modp2048) / no PFS` — keep aligned
  across `infra/resources.bicep` (`ipsecPolicies`), `onprem/ipsec.conf` (legacy) or
  `swanctl.conf` (strongSwan 6), and the guide.
- **Addressing:** VNet `10.100.0.0/16`, GatewaySubnet `10.100.0.0/27`, APIM subnet
  `10.100.1.0/24`, on-prem LAN `192.168.50.0/24`.
- **APIM:** Premium v2 requires API version `2025-09-01-preview` (`PremiumV2` SKU); injection
  subnet delegated to `Microsoft.Web/hostingEnvironments` with an NSG allowing outbound 443
  to `AzureKeyVault`.
- **azd outputs** referenced in the guide exist in `infra/main.bicep`
  (`VPN_GATEWAY_PUBLIC_IP`, `VPN_CONNECTION_NAME`, `APIM_NAME`, `APIM_GATEWAY_URL`).

## Recording an OpenWrt / strongSwan learning
The MX4300 guide must cover both toolchains, because the router build dictates which applies:
- **OpenWrt ≤ 24.x:** `opkg` package manager + strongSwan 5.x — legacy `/etc/ipsec.conf` +
  `/etc/ipsec.secrets`, driven by the `ipsec` command (`ipsec statusall`, `ipsec up azure`).
- **OpenWrt 25.x+:** `apk` package manager + strongSwan 6.x — the `ipsec`/starter/stroke
  tooling is **removed**; use `/etc/swanctl/swanctl.conf` and `swanctl`
  (`swanctl --load-all`, `swanctl --initiate --child azure`, `swanctl --list-sas`).
- Detect with `command -v apk opkg` and `swanctl --version` / `ipsec version`.
- The OpenWrt `fw4`/nftables firewall steps and the flow-offloading disable are the **same**
  for both toolchains.

When you capture a new learning, add it to the guide's Troubleshooting/notes in place and,
if it affects a value above, update every file in the invariants list in the same change.

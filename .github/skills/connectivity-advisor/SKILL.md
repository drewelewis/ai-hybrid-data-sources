---
name: connectivity-advisor
description: 'Recommend and explain how to connect on-premises data and agents to Azure AI Foundry or Microsoft Copilot Studio. Use for: choosing between Foundry Option A/B or Copilot Option A/B/C, private vs public data paths, connecting an on-prem MCP server to Copilot Studio, and Power Platform VNet-injection caveats (auth/token routing, connector re-save, DNS, TLS).'
---

# Hybrid connectivity advisor

## When to use
- Someone asks which connectivity option fits (Foundry A/B, Copilot A/B/C).
- Connecting an on-prem MCP server or database to Copilot Studio or Foundry.
- Explaining private-network vs API/gateway trade-offs.

## Decision
1. Which platform hosts the agent? **Azure AI Foundry** (compute you control) or **Microsoft
   Copilot Studio** (Microsoft SaaS — not VNet-injectable).
2. Private-only mandate or need for raw private-IP access? → **Option A** (private network
   path). Otherwise a lighter API/gateway option.
3. Full option matrix, trade-offs, and cost are in
   [../../../README.md](../../../README.md).

## Foundry
- **Option A (default, deployed by this repo):** VNet + S2S VPN/ExpressRoute, APIM Premium v2
  injected. Private end-to-end; raw private-IP / native-protocol access.
- **Option B:** APIM self-hosted gateway. API-only; data path over public TLS.

## Copilot Studio
- **Option A (private):** Power Platform VNet integration (subnet-delegated enterprise
  policy) → VPN/ExpressRoute. Reuses this repo's tunnel.
- **Option B:** On-premises data gateway + connectors (dial-out; transits Microsoft cloud).
- **Option C:** Custom connector to a published (APIM) API (public endpoint).

## Copilot Studio + on-prem MCP over VNet — caveats
An MCP server in Copilot Studio is a **custom connector**, so custom-connector VNet limits
apply:

- **Auth is public:** OAuth/token requests do NOT transit the VNet — only API-endpoint calls
  do. Use an API key or a public IdP (Entra ID); never a private-only token endpoint. Keep a
  **NAT gateway** on the delegated subnet so token requests can egress.
- **Ordering:** enable subnet injection BEFORE creating the MCP connector, or re-save an
  existing connector afterward.
- **TLS:** the MCP endpoint must present a full chain from a well-known public CA; private
  root CAs are rejected.
- **Transport:** MCP request/response (Streamable HTTP); avoid async/`Location`-header
  patterns.
- **DNS/subnet are fixed after delegation:** set VNet DNS to resolve the MCP FQDN to its
  on-prem private IP, and size the delegated subnet, BEFORE enabling injection (changing
  either later requires disable/re-enable).

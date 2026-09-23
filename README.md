# AI Hybrid Data Sources

A recommended Azure reference architecture for connecting an **on-premises estate** to
cloud AI agents on **Azure AI Foundry** and **Microsoft Copilot Studio** — in both
directions, deployable with a single `azd up`.

It solves two problems at once, without exposing any private system to the public internet:

1. On-premises agents that need to **call Azure AI models**.
2. Cloud-hosted agents (Foundry or Copilot Studio) that need to **reach on-premises
   databases**.

> **What `azd up` deploys:** the **Foundry Option A** baseline as **one hub and two spokes**:
>
> - **Selected hub region:** VNet, **VpnGw1AZ** Site-to-Site VPN, and **APIM Premium v2**
>   VNet-injected in `Internal` mode.
> - **Canada East spoke:** a globally peered VNet with an empty Linux App Service. Its
>   application is maintained and deployed from a separate repository.
> - **Sweden Central spoke:** the globally peered, network-isolated Azure AI Foundry
>   deployment and its private dependencies. An existing connected deployment is reused.
> - **Microsoft Entra ID:** separate development and production SPA registrations plus one
>   shared protected API registration and `Chat.Invoke` delegated scope.
>
> Copilot Studio **Option A** reuses the hub tunnel. Every other option is documented here
> as guidance you layer on yourself.
>
> **Region note:** APIM Premium v2 isn't offered in every region. Its subscription SKU API can
> eliminate missing or formally restricted regions, but does not report transient physical
> capacity. The deployment therefore stages the final APIM instance first. The gateway uses a
> zone-redundant **VpnGw1AZ** SKU with a zone-redundant public IP (non-AZ `VpnGw` SKUs are retired).

## Contents

- [The core idea: two platforms, two directions](#the-core-idea-two-platforms-two-directions)
- [Azure AI Foundry](#azure-ai-foundry)
- [Microsoft Copilot Studio](#microsoft-copilot-studio)
- [Cost comparison](#cost-comparison)
- [Getting started](#getting-started)
- [Repository layout](#repository-layout)
- [Glossary](#glossary)
- [References](#references)

---

## The core idea: two platforms, two directions

Organize the choice by **which platform hosts the agent** — **Azure AI Foundry** or
**Microsoft Copilot Studio** — then pick a connectivity **option** under that platform.
Options are ordered **most-secure / most-enterprise first** (**Option A**), with
lighter-weight options after.

Two traffic directions apply across both platforms:

- **Egress** — on-prem agents calling Azure **models** (outbound only; the easy direction).
- **Ingress** — cloud-hosted agents reaching **on-prem data** (the hard direction — this is
  where the options differ).

```mermaid
flowchart TD
    Start["Which platform hosts the agent?"]
    Start --> Foundry["Azure AI Foundry"]
    Start --> Copilot["Microsoft Copilot Studio"]
    Foundry --> FA["Option A — VNet + VPN/ExpressRoute<br/>(private, enterprise)"]
    Foundry --> FB["Option B — APIM self-hosted gateway"]
    Copilot --> CA["Option A — Power Platform VNet integration<br/>(private, enterprise)"]
    Copilot --> CB["Option B — On-premises data gateway"]
    Copilot --> CC["Option C — Custom connector to a published API"]
```

One **Azure API Management (APIM)** control plane serves both platforms and both directions:
an AI Gateway for outbound model calls and a private ingress path to on-prem data.

### All options at a glance

| Platform | Option | Mechanism | Private-only data path | Access style | Deployed by this repo |
| --- | --- | --- | --- | --- | --- |
| **Foundry** | **A** | VNet + VPN/ExpressRoute; APIM Premium v2 injected | ✅ Yes | Raw private-IP / native protocol | ✅ Yes |
| **Foundry** | B | APIM self-hosted gateway (dial-out) | ❌ TLS over public internet | Governed APIs | — |
| **Copilot Studio** | **A** | Power Platform VNet integration → VPN/ExpressRoute | ✅ Yes | Connector over private path | Reuses the tunnel |
| **Copilot Studio** | B | On-premises data gateway + connectors | ❌ Dial-out via Microsoft cloud | Connectors / APIs | — |
| **Copilot Studio** | C | Custom connector → published (APIM) API | ❌ Public endpoint | APIs | — |

---

# Azure AI Foundry

Foundry-hosted agents run on **compute you configure**, so you can place the agent on your
own network (VNet injection, private endpoints). That makes a **fully private network path**
the default enterprise choice — hence it leads as **Option A** below.

## Egress — on-prem agents calling Azure models

For agents that **already run on-premises** (like your HR agents). They stay where they are,
read their data locally, and only reach **out** to Azure for model inference — a single
recommended pattern, with no option to choose.

- **Outbound HTTPS (443) only** to Azure Foundry / Azure OpenAI inference endpoints. No
  inbound connectivity and no VPN required.
- **Front model calls with APIM as an AI Gateway** — token-based rate limiting, semantic
  caching, cost attribution, and multi-model routing. Point the agent's model base URL at
  the APIM endpoint.
- **Authenticate with Microsoft Entra ID** (service principal or federated workload
  identity). No API keys stored in the on-prem app.
- **Telemetry & governance via the Agent 365 (A365) SDK** flow over the *same* outbound
  HTTPS 443 path — agents report telemetry and enroll for policy/governance to Azure/M365
  endpoints. This keeps the pattern identical: agent-initiated, outbound-only, no inbound.
- **Local data never leaves the premises** — only prompts, completions, and telemetry
  metadata transit to Azure.

---

## Ingress — Foundry agents reaching on-prem databases

For the **new agents you build in Foundry** that must reach back into private databases.
This is the harder direction, and the one where you choose an option.

### Choosing an option

> **Do you have a compliance or network mandate that private-data traffic must never
> traverse a public endpoint, or do agents need raw private-IP / native-protocol access?**

| | **Option A** — VNet + VPN/ExpressRoute | **Option B** — self-hosted gateway |
| --- | --- | --- |
| Private-only networking mandate | **Yes** | No |
| Typical fit | Regulated / high-assurance (finance, healthcare, gov); the enterprise default here | Teams without a private-only mandate |
| Access style | Raw **private-IP / network** access | Agents call **APIs** |
| Throughput | High / deterministic (ExpressRoute) | Standard |
| Relative cost | Higher (always-on gateway + Premium v2) | Lower (no VPN) |

This reference implementation **leads with Option A** as the enterprise-grade default — and
it's the option the Bicep here deploys. Choose **Option B** when you don't need a private
network path and prefer a lighter, API-only footprint.

### Option A — VNet + VPN / ExpressRoute (enterprise, private) ⭐ deployed by this repo

Use this when a mandate requires private-data traffic to stay off public endpoints, when
agents need raw private-IP access rather than API calls, or when you need deterministic high
throughput. You extend your network into Azure so services on a VNet have direct
line-of-sight to on-premises hosts by private IP.

- **Site-to-Site (S2S) IPsec VPN** — an IKEv2 tunnel to a route-based Azure **Virtual
  Network Gateway**. Fits smaller sites and labs.
- **ExpressRoute (private fiber)** — for production/high-throughput, deterministic links.
- **APIM Premium v2 injected into the VNet** (this repo deploys it in `Internal` mode) for
  native private networking plus the AI-gateway features (semantic caching, token rate
  limiting).

**Benefits**

- **Security & compliance:** the data path is **private end-to-end** — no public endpoint
  exposure. Satisfies regulatory mandates and lets you layer NSGs, private endpoints, and
  network segmentation.
- **Latency & performance:** ExpressRoute delivers deterministic, low-latency,
  high-throughput links backed by an SLA; even S2S VPN gives a stable dedicated tunnel.
- **Native access:** agents get raw private-IP / network reach — use native database
  protocols (SQL, etc.) directly, not just APIs.
- **Deterministic routing:** predictable hub-spoke routing tables for enterprise network
  integration.

**Trade-offs / issues**

- **Cost & complexity:** an always-on VPN gateway or ExpressRoute circuit **plus** a higher
  APIM tier (Premium v2), and more moving parts — VNet, gateway, routing, DNS, private
  endpoints — to design and operate.
- **VPN latency variability:** IPsec adds encryption overhead and still rides the public
  internet path; only ExpressRoute removes that variability (at higher cost and lead time).
- **Setup & lead time:** ExpressRoute provisioning can take weeks and needs a connectivity
  provider; VPN requires on-prem device configuration and key management.
- **Network-layer attack surface:** opening network reach (even private) demands careful
  segmentation and firewall/NSG rules; a misconfiguration has a larger blast radius than a
  single API gateway.
- **Ongoing operations:** monitor the VPN gateway and tunnel, maintain static routes, and
  rotate the IPsec pre-shared key. BGP and certificate rotation apply only if you extend
  this baseline to use them.

```mermaid
flowchart LR
    subgraph OnPrem["On-premises"]
        DB[(Internal DB / APIs)]
        Edge["Edge / VPN endpoint"]
        DB --- Edge
    end

    subgraph CanadaCentral["Canada Central — hub"]
        subgraph Hub["Hub VNet — 10.100.0.0/16"]
            VPN["VpnGw1AZ"]
            HubFabric["Hub VNet routing"]
            APIM["APIM Premium v2<br/>(VNet injected, Internal)"]
            VPN --- HubFabric
            HubFabric --- APIM
        end
    end

    subgraph CanadaEast["Canada East — App Service spoke"]
        AppVNet["App spoke VNet<br/>10.101.0.0/16"]
        App["Linux App Service<br/>(application deployed separately)"]
        App --- AppVNet
    end

    subgraph SwedenCentral["Sweden Central — Foundry spoke"]
        FoundryVNet["agent-vnet<br/>172.16.0.0/16"]
        Foundry["Azure AI Foundry<br/>and private dependencies"]
        Foundry --- FoundryVNet
    end

    Edge <-->|"S2S IPsec VPN"| VPN
    AppVNet <-->|"global VNet peering"| HubFabric
    FoundryVNet <-->|"global VNet peering"| HubFabric
```

The regions are intentionally split by service availability and subscription quota:
APIM Premium v2 and the VPN hub run in **Canada Central**, the B1 App Service plan runs in
**Canada East**, and the existing Foundry deployment and its private dependencies run in
**Sweden Central**. Both spokes use global VNet peering to reach the hub; neither is deployed
inside the hub VNet.

### Option B — APIM self-hosted gateway

Deploy the **APIM self-hosted gateway** as a container workload next to your data. It proxies
calls to internal databases while keeping them local, and Foundry reaches them through APIM —
the **same APIM instance** used for egress, so both directions share one control plane.

**Benefits**

- **Security:** no inbound firewall ports; databases are never exposed to the internet. The
  gateway is outbound-only over 443, with unified Entra ID auth and centrally managed policy.
- **Simplicity:** reuses existing on-prem hardware, no VPN gateway or VNet to design.
- **Governance & observability:** policies, keys, and config are pulled from Azure; metrics
  and logs flow back to a central monitoring workspace.
- **Portability:** runs on any Docker/Kubernetes host and isn't coupled to a network topology
  or region.

**Trade-offs / issues**

- **Latency:** the request path (Foundry agent → APIM → self-hosted gateway → DB) crosses the
  public internet over TLS, adding round-trip latency and jitter versus a private link.
- **Performance ceiling:** throughput is bounded by your gateway host sizing and internet
  egress bandwidth — there is no network SLA on the path.
- **API-only access:** you must expose databases as governed **APIs**. No raw SQL or
  private-IP/native-protocol access.
- **You operate the gateway:** run, patch, scale, and monitor the container (HA replicas).
- **Compliance fit:** the (encrypted) data path still traverses public internet, which may
  not satisfy strict private-only mandates — that's the trigger to use Option A.

```mermaid
flowchart LR
    subgraph Azure["Azure"]
        Foundry["Azure AI Foundry"]
        APIM["APIM control plane"]
        Foundry --> APIM
    end

    subgraph OnPrem["On-premises / data center"]
        FW["Enterprise firewall / DMZ"]
        SHGW["APIM self-hosted gateway"]
        DB[(Internal DB / APIs)]
        FW --> SHGW
        SHGW --> DB
    end

    SHGW -- "outbound HTTPS 443 (dial-out)" --> APIM
```

---

# Microsoft Copilot Studio

Copilot Studio agents run in **Microsoft-managed SaaS (Power Platform)** — you **can't**
inject the agent into your VNet. On-prem reach therefore uses **Power Platform connectivity**
rather than the agent's own network stack. The directions are the same as Foundry, but the
mechanisms differ; options below are ordered **most-secure first**.

## Egress — models

Foundation models are **platform-managed**; govern usage with **Power Platform DLP**. To put
the APIM AI Gateway in front of custom or bring-your-own models, expose them through a
**custom connector**. There's no on-prem egress pattern here — a Copilot Studio agent never
runs on-premises.

## Ingress — Copilot Studio agents reaching on-prem data

### Option A — Power Platform VNet integration (enterprise, private)

A subnet-delegated **enterprise policy** routes connector traffic through a delegated subnet
in your VNet, which reaches on-prem privately over **VPN / ExpressRoute**. The agent stays
SaaS; only the **connector data path** becomes private — the closest Copilot Studio
equivalent to Foundry **Option A**, and it can ride the **same S2S tunnel this repo deploys**.

**Benefits**

- **Security & compliance:** no public endpoint for the data path; layer NSGs, private
  endpoints, and segmentation. Best fit for private-only mandates.
- **Reuses your network:** shares the VPN / ExpressRoute link and hub VNet already built for
  Foundry Option A.
- **Governance:** Power Platform DLP + connector governance + Purview + Agent 365.

**Trade-offs / issues**

- **Agent still SaaS:** the agent gets a private *connector* path, not raw private-IP reach —
  no native-protocol access from the agent itself.
- **Setup:** enterprise policy + subnet delegation to configure and operate.
- **Topology coupling:** tied to the Power Platform environment region and the hub VNet.
- **Cost:** always-on VPN gateway (and typically higher Power Platform / APIM tiers).

```mermaid
flowchart LR
    subgraph M365["Microsoft cloud (SaaS)"]
        CS["Copilot Studio agent"]
        EP["Power Platform<br/>VNet integration<br/>(delegated subnet)"]
        CS --> EP
    end

    subgraph Azure["Azure (your VNet)"]
        Edge["VPN / ExpressRoute edge"]
    end

    subgraph OnPrem["On-premises"]
        DB[(Internal DB / APIs)]
    end

    EP -- "private connector path" --> Edge
    Edge -- "S2S VPN / ExpressRoute (same tunnel as Foundry Option A)" --> DB
```

### Option B — On-premises data gateway (connector / API path)

Install the **on-premises data gateway** next to your data; connectors **dial out** to Power
Platform over 443. No inbound firewall ports — analogous to the Foundry self-hosted gateway,
but it's the Power Platform gateway driving connectors.

**Benefits**

- **No inbound ports:** databases are never exposed to the internet; the gateway is
  outbound-only.
- **Reuses on-prem hardware** and the broad Power Platform **connector catalog**; can also
  front the same APIM-published APIs.
- **Governance:** Power Platform DLP + connector governance.

**Trade-offs / issues**

- **Not a private-only path:** the (encrypted) data path transits the Microsoft cloud, so it
  may not satisfy strict private-only mandates — that's the trigger to use Option A.
- **You operate the gateway:** install, patch, and monitor it (with clustering for HA).
- **Connector / API-only:** no raw private-IP or native-protocol access.
- **Throughput:** bounded by the gateway host and its internet link.

```mermaid
flowchart LR
    subgraph OnPrem["On-premises"]
        OPDG["On-prem data gateway"]
        DB[(Internal DB / APIs)]
        OPDG --> DB
    end

    subgraph M365["Microsoft cloud (SaaS)"]
        CS["Copilot Studio agent"]
    end

    CS -- "connector (dial-out HTTPS 443)" --> OPDG
```

### Option C — Custom connector to a published API (simplest)

Point a **custom connector** at an internet-reachable HTTPS API — for example an APIM-fronted
endpoint (or the APIM self-hosted gateway's published APIs).

**Benefits**

- **Simplest:** no gateway or VNet to run; stand up an API and connect.
- **Governed by APIM + DLP:** auth, rate limiting, and policy still apply at the gateway.

**Trade-offs / issues**

- **Public endpoint:** the API is reachable on the internet (protected by auth / APIM policy,
  but not network-isolated) — **not** for private-only mandates.
- **API-only:** no raw private-IP or native-protocol access.
- **You own the API surface:** design, auth, schema, and versioning.

```mermaid
flowchart LR
    subgraph M365["Microsoft cloud (SaaS)"]
        CS["Copilot Studio agent"]
    end

    subgraph Azure["Azure"]
        APIM["APIM (public endpoint)"]
    end

    subgraph OnPrem["On-premises"]
        DB[(Internal DB / APIs)]
    end

    CS -- "custom connector (HTTPS 443)" --> APIM
    APIM -- "published API" --> DB
```

---

## Cost comparison

Monthly estimates use **East US retail (USD)**, **730 hours/month**, pay-as-you-go rates.
The table compares the connectivity footprints only. It **excludes** the Canada East App
Service plan, Foundry spoke resources (Cosmos DB, AI Search, ACR, monitoring, storage),
global VNet-peering transfer, other data transfer, and Azure AI Foundry token consumption.
Those costs are workload- and region-dependent. Indicative as of 2026-09 — confirm with the
[Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/).

### Fixed component rates

| Component | SKU | Hourly | Monthly (~730h) |
| --- | --- | ---: | ---: |
| APIM (dev/test) | Developer | $0.0658 | ~$48 |
| APIM (production) | Standard v2 | $0.9589 | ~$700 |
| APIM (VNet-injected) | Premium v2 (per unit) | $1.9178 | ~$1,400 |
| APIM self-hosted gateway | per gateway | $0.3425 | ~$250 |
| VPN Gateway | VpnGw1AZ | $0.21 | ~$153 |
| VPN Gateway | VpnGw2AZ | $0.54 | ~$394 |
| S2S tunnel connection | any VpnGw | $0.015 | ~$11 |

### Total by ingress footprint

Costs group into two Azure networking footprints. **Option A** on either platform (Foundry
VNet+VPN, Copilot Power Platform VNet integration) maps to the **VNet + VPN** footprint;
**Foundry Option B** maps to the **self-hosted gateway** footprint. **Copilot Option B**
(on-prem data gateway) adds no Azure networking cost — the gateway runs on-prem and dials
out — and **Copilot Option C** is APIM-only.

| | **Self-hosted gateway** footprint | **VNet + VPN** footprint |
| --- | --- | --- |
| Maps to | Foundry Option B | Foundry Option A · Copilot Option A |
| APIM tier | Standard v2 (~$700) | Premium v2, 1 unit (~$1,400) |
| Gateway / connectivity | 1 self-hosted gateway (~$250) | VpnGw1AZ + 1 tunnel (~$164) |
| On-prem hardware | Existing servers ($0 Azure) | None |
| **Azure fixed subtotal** | **~$950 / month** | **~$1,565 / month** |
| AI usage | Token-based (same) | Token-based (same) |

- **Egress adds no fixed networking cost** — it reuses the same APIM instance; you pay only
  for model tokens.
- **Dev/test self-hosted footprint ≈ ~$300/month** using the APIM Developer tier (~$48) plus
  one self-hosted gateway (~$250) — note Developer has no SLA.
- **ExpressRoute** (a VNet+VPN alternative to S2S VPN) is priced separately: a metered
  circuit starts ~**$55/month** for 50 Mbps, unlimited plans reach the thousands, plus a
  connectivity-provider fee.
- **Copilot Option B** uses the Power Platform on-prem data gateway (no Azure gateway cost;
  licensed via Power Platform) plus whatever APIM tier you choose.
- Scaling out multiplies the variable pieces — each extra APIM unit or self-hosted gateway
  adds its full monthly rate.

---

## Getting started

### Prerequisites

- [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Azure CLI (`az`)](https://learn.microsoft.com/cli/azure/install-azure-cli)
- [PowerShell 7 (`pwsh`)](https://learn.microsoft.com/powershell/scripting/install/installing-powershell)
  for the cross-platform regional preflight and placement picker
- An Azure subscription with rights to create resource groups and the resources above
- Microsoft Entra permission to create app registrations (`Application.ReadWrite.All`) for
  the signed-in identity running `azd up`
- For the **self-hosted gateway** option (Foundry Option B): a reachable container host
  (Docker or Kubernetes) on-premises

### Deploy

Run the read-only regional preflight before the first deployment to a subscription, after a
capacity error, or when changing regions:

```powershell
az extension add --name quota --upgrade

.\scripts\regional-preflight.ps1 `
  -SubscriptionId <subscription-id> `
  -HubRegions canadacentral,centralus `
  -AppRegions canadaeast,eastus2 `
  -FoundryRegions swedencentral,centralus
```

The version-controlled regional preflight skill writes its detailed report to
`.azure/preflight/regional-preflight.json`. It queries the subscription-scoped APIM SKU and
restriction API in addition to advertised services, models, and quota. `PASS` confirms the
queried requirement; `CONDITIONAL` or `UNKNOWN` means Azure does not expose enough information
to guarantee deploy-time capacity; `FAIL` eliminates that placement. The preflight is
read-only and does not run `azd up`, register providers, or request quota. By default it selects the
first generally available `GlobalStandard` small chat model for each Foundry candidate
region; use `-ModelSelection Exact` only when a specific model and version are required.
The Foundry deployment currently defaults to `gpt-5.4-mini` version `2026-03-17`, and
`FOUNDRY_MODEL` / `FOUNDRY_MODEL_VERSION` can override that choice.

```bash
az login                # authenticate Azure CLI and select the target subscription
az account set --subscription <subscription-id>
azd auth login --tenant-id <tenant-id> # authenticate azd to the same tenant
azd up                  # provision the shared infrastructure
```

`azd up` prompts for an environment name and subscription, then the `preup` hook prints
`Checking advertised regional services, subscription SKU restrictions, models, and quotas...`
and runs a fresh, read-only global preflight. Unsupported and formally restricted candidates
are removed before the placement picker selects and persists the hub, application, Foundry,
and small-model choices in the active `azd` environment. A listed hub is eligible for an APIM
create attempt; it is not capacity-approved. Its preferred ordering starts with:

| Placement | Default |
| --- | --- |
| Hub / VPN / APIM | Canada Central |
| Application App Service | Canada East |
| Foundry spoke | Sweden Central |
| Foundry model | `gpt-5.4-mini` `2026-03-17` (`GlobalStandard`) |

Every run refreshes regional evidence before the picker displays the saved placement and
defaults to reusing it. A preflight execution error stops `azd up` before provisioning;
`CONDITIONAL` and `UNKNOWN` evidence remains visible because Azure does not expose physical
capacity for every SKU. ARM `validate` and `what-if` do not exercise APIM's transient capacity
gate. The deployment therefore creates the final VNet-injected APIM instance immediately
after its NSG and hub VNet. VPN, App Service, DNS, identity, and Foundry provisioning starts
only after APIM reaches `Succeeded`, so an APIM rejection fails early without creating those
dependent resources. Changing placement on an already provisioned environment can replace or
add resources, so review changes before answering **No** to the reuse prompt. In
non-interactive runs, or with `AZD_SKIP_REGION_PICKER=true`, the hook still runs preflight,
then uses saved values when they remain viable and fills missing or failed values from the
fresh candidate list.

The `preup` hook first binds `AZURE_SUBSCRIPTION_ID` and `AZURE_TENANT_ID` to the active
`az account show` context. It also compares the signed-in `az` and `azd` identities and
stops before provisioning with an explicit `azd auth login --tenant-id ...` command when
they differ. `az` and `azd` have independent authentication caches; logging in to one does
not switch the other.

After placement selection, `azd up` prompts for the **IPsec pre-shared key** and an **APIM
publisher email**, then provisions the recommended baseline
(**Foundry Option A**: the VNet + S2S VPN path with **APIM Premium v2** VNet-injected). By
default, the picker provisions an empty Linux App Service in a **Canada East** spoke VNet
and peers that VNet globally with the selected hub. The separate application
repository owns build and code deployment to this App Service; this repository only creates
its hosting and network infrastructure. `azd up` then **also deploys a network-isolated Foundry spoke**
(foundry-samples template 19) and peers it into the hub, so a single command stands up the
shared infrastructure. That step adds ~45–60 min and ongoing cost (Cosmos DB, AI Search
**Basic**, ACR Premium, a model); opt out by answering **No** at the prompt, running
non-interactively (CI), or setting `AZD_SKIP_FOUNDRY=true`. The recommended Foundry default
is **Sweden Central** (it peers cross-region back to the hub): the template's Cosmos DB and
AI Search dependencies had no capacity for this subscription in Canada Central or East US.
On subsequent runs, the post-provision hook detects a Foundry resource group already
connected to the hub, reuses it, and only reconciles peering, DNS, and APIM configuration
instead of redeploying the Foundry resources. Set `FOUNDRY_RG` only when intentionally
targeting a different Foundry resource group.

`az` and `azd` keep separate subscription context. The pre-provision hook compares the
subscription selected for the `azd` environment with `az account show` and stops before
creating resources if they differ. Select the same subscription at the `azd up` prompt;
the post-provision Foundry and peering scripts then pass that subscription explicitly to
every Azure CLI command.

Because Premium v2 is an always-on, higher-cost tier, tear the environment down when you're
not actively testing and re-run `azd up` when you need it:

```bash
azd down
```

The main Bicep deployment also creates three environment-specific Microsoft Entra app
registrations:

| Registration | Purpose | Redirect URI |
| --- | --- | --- |
| `ai-hybrid-data-sources-<env>-spa-dev` | Local `npm run dev` client | `http://localhost:5173` |
| `ai-hybrid-data-sources-<env>-spa-prod` | Production App Service client | The provisioned `https://app-<token>.azurewebsites.net` origin |
| `ai-hybrid-data-sources-<env>-api` | Shared protected API and `Chat.Invoke` scope | None |

`azd env get-values` exports `ENTRA_DEV_SPA_CLIENT_ID`,
`ENTRA_PROD_SPA_CLIENT_ID`, `ENTRA_API_CLIENT_ID`, `ENTRA_API_AUDIENCE`, and
`ENTRA_API_SCOPE`. The React app uses the development SPA ID with `npm run dev`; its GitHub
Actions production build uses the production SPA ID. There is no `npm run prod`: production
is compiled with `npm run build`, and App Service launches the deployed Express server with
`npm start`.

---

## Repository layout

> Infrastructure-as-code assets live under `infra/`, with `azure.yaml` at the repository
> root driving `azd`. The deployed baseline provisions **Foundry Option A** — the VNet,
> VpnGw1AZ gateway, local gateway, and IPsec connection, **plus** an **APIM Premium v2**
> instance VNet-injected in `Internal` mode — the single control plane both platforms reuse.
> It also creates an empty App Service in a globally peered Canada East spoke; application
> code is deployed from its own repository. Copilot Option A rides the same tunnel. On-prem
> strongSwan config lives under `onprem/`
> — see [onprem/INSTALL-strongswan-openwrt-mx4300.md](onprem/INSTALL-strongswan-openwrt-mx4300.md)
> for the router-side tunnel setup.

---

## Glossary

| Term | Meaning |
| --- | --- |
| **APIM** | Azure API Management — the shared control plane / AI Gateway |
| **A365** | Agent 365 — telemetry & governance SDK for agents |
| **VNet injection** | Placing a service (e.g. APIM Premium v2) directly inside your virtual network |
| **S2S / IKEv2** | Site-to-Site IPsec VPN tunnel to Azure |
| **PSK** | Pre-shared key that authenticates the IPsec tunnel |
| **ExpressRoute** | Private fiber circuit into Azure (alternative to S2S VPN) |
| **NSG** | Network Security Group — subnet-level firewall rules |
| **DLP** | Data Loss Prevention — Power Platform governance policy |
| **Enterprise policy** | Power Platform resource binding an environment to a delegated subnet |

---

## References

- [Azure AI Foundry](https://learn.microsoft.com/azure/foundry/what-is-foundry)
- [APIM self-hosted gateway overview](https://learn.microsoft.com/azure/api-management/self-hosted-gateway-overview)
- [APIM Premium v2 VNet injection](https://learn.microsoft.com/azure/api-management/inject-vnet-v2)
- [API gateway in Azure API Management](https://learn.microsoft.com/azure/api-management/api-management-gateways-overview)
- [Create a Site-to-Site VPN connection (Azure portal)](https://learn.microsoft.com/azure/vpn-gateway/tutorial-site-to-site-portal)
- [Power Platform virtual network support](https://learn.microsoft.com/power-platform/admin/vnet-support-overview)
- [On-premises data gateway](https://learn.microsoft.com/data-integration/gateway/service-gateway-onprem)

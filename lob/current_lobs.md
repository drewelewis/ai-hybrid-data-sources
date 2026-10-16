# Contoso Bank Lines of Business

Contoso Bank organizes its operations into five core lines of business.

| Line of business | Principal businesses and services |
| --- | --- |
| **Services** | Treasury and Trade Solutions, including payments, liquidity and cash management, trade finance, and commercial cards; and Securities Services, including custody, clearing, and fund services. |
| **Markets** | Fixed income, currencies, commodities, and equities; including trading, financing, market-making, and risk-management solutions. |
| **Banking** | Investment Banking, Corporate Banking, and Commercial Banking; including advisory services, capital raising, corporate lending, and services for mid-sized companies. |
| **Wealth** | Private Banking, affluent wealth management, and workplace wealth services; including investment, lending, trust, and advisory services for affluent, high-net-worth, and ultra-high-net-worth clients. |
| **U.S. Personal Banking** | Branded credit cards, Retail Services, retail banking, deposits, lending, mortgages, and small-business services in the United States. |

## Agent application portfolio

Each use case is managed as an independently promoted agent application. A
repository entry identifies the intended application and source location; it
does not by itself indicate that an environment has been deployed.

### IT hosting and promotion mandate

- Every agent runtime is self-hosted on premises in every environment.
- Using APIM, Microsoft Foundry models, Agent 365, or other cloud services does
  not move the agent runtime into the cloud.
- Applications follow the required promotion order:
  `local` -> `dev` -> `tst` -> `prd`.
- Each stage receives its own environment configuration, credentials, Agent
  Identity, telemetry attribution, and approved data access.
- A later stage remains unavailable until the application has been promoted
  through the preceding stages.

| Stage | Hosting | Purpose |
| --- | --- | --- |
| `local` | On-premises developer workstation or approved local container host | Build, unit test, and developer validation |
| `dev` | Shared on-premises development runtime | Integrated development validation |
| `tst` | Shared on-premises test runtime | Controlled functional, security, policy, and release validation |
| `prd` | On-premises production runtime | Approved production operation |

### Applications

| Line of business | Application | Folder | Current implementation | Hosting | Required lifecycle | Scope |
| --- | --- | --- | --- | --- | --- | --- |
| **Banking** | Corporate Credit Memo Analyst | [`banking/credit-memo-analyst`](./banking/credit-memo-analyst/) | Planned placeholder; no runtime deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Assemble borrower financials, covenant history, collateral, and risk factors into an analyst-reviewed credit memo. |
| **Banking** | Deal Diligence Coordinator | [`banking/deal-diligence-coordinator`](./banking/deal-diligence-coordinator/) | Planned placeholder; no runtime deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Track diligence requests, summarize approved deal-room material, identify missing items, and prepare review checklists. |
| **Markets** | Markets Risk Analyst | [`markets/markets-risk-analyst`](./markets/markets-risk-analyst/) | Runnable in `local`; `dev`, `tst`, and `prd` are not deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Explain user-provided position, limit, stress, and exposure information for risk review without executing trades. |
| **Markets** | Trade Surveillance Analyst | [`markets/trade-surveillance-analyst`](./markets/trade-surveillance-analyst/) | Runnable in `local`; `dev`, `tst`, and `prd` are not deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Analyze approved user-provided orders, trades, alerts, and communications for human surveillance review. |
| **Services** | Treasury Liquidity Manager | [`services/treasury-liquidity-manager`](./services/treasury-liquidity-manager/) | Planned placeholder; no runtime deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Consolidate cash positions and forecasts, identify liquidity gaps, and propose analyst-reviewed funding actions. |
| **Services** | Trade Finance Operations | [`services/trade-finance-operations`](./services/trade-finance-operations/) | Planned placeholder; no runtime deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Review trade-finance documents for discrepancies, track processing status, and route exceptions to operations staff. |
| **U.S. Personal Banking** | Card Dispute Assistant | [`us-personal-banking/card-dispute-assistant`](./us-personal-banking/card-dispute-assistant/) | Planned placeholder; no runtime deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Guide dispute intake, summarize transaction evidence, classify the case, and explain next steps without deciding claims. |
| **U.S. Personal Banking** | Mortgage Servicing Assistant | [`us-personal-banking/mortgage-servicing-assistant`](./us-personal-banking/mortgage-servicing-assistant/) | Planned placeholder; no runtime deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Answer servicing questions, explain escrow and payment changes, and route hardship cases to authorized specialists. |
| **Wealth** | Portfolio Manager | [`wealth/portfolio-manager`](./wealth/portfolio-manager/) | Runnable in `local`; `dev`, `tst`, and `prd` are not deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Query the portfolio event ledger, reconstruct positions, and support portfolio analysis through governed tools. |
| **Wealth** | Client Advisor | [`wealth/client-advisor`](./wealth/client-advisor/) | Planned placeholder; no runtime deployed | On premises only | `local` -> `dev` -> `tst` -> `prd` | Prepare advisor briefings from approved client, portfolio, goal, and interaction data while keeping recommendations human-reviewed. |

For a nonbinding sequence covering application waves, environment gates,
blueprints, identities, and regional instances, see the
[hypothetical LOB agent rollout strategy](../A365/lob_rollout_strategy.md).

## Other reporting category

Contoso Bank also uses **All Other** for certain corporate activities and
remaining legacy businesses or divestitures. It is a financial-reporting
category rather than a core customer-facing line of business.
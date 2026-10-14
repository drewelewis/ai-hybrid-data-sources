# Line-of-Business Blueprint Guidance

## Purpose

This guide explains how Contoso Bank's lines of business (LOBs) should
influence Microsoft Entra Agent ID blueprint design. It supplements the
enterprise [blueprint guide](./blueprints.md); it does not replace the
identity, credential, permission, or lifecycle rules in that guide.

The five core LOBs covered here are:

- Services
- Markets
- Banking
- Wealth
- U.S. Personal Banking

`All Other` is a financial-reporting category, not a core customer-facing LOB,
and is not assigned a default blueprint profile.

## Governing principle

**One LOB does not necessarily equal one blueprint.**

An LOB is a governance and ownership attribute. A blueprint is an agent-family
boundary for shared credentials, authentication configuration, inheritable
permissions, publisher ownership, and incident blast radius.

Create a blueprint for an agent family only after evaluating its actual trust
boundary. Do not pre-create an empty blueprint merely because an LOB exists.

## Enterprise taxonomy

```text
Contoso Bank Agent 365 estate
|
+-- Services
|   +-- Agent-family blueprint(s), as approved
|
+-- Markets
|   +-- Agent-family blueprint(s), as approved
|
+-- Banking
|   +-- Agent-family blueprint(s), as approved
|
+-- Wealth
|   +-- Portfolio Manager blueprint
|       +-- Local development agent identity
|       +-- Test agent identity
|       +-- Production agent identity
|
+-- U.S. Personal Banking
    +-- Agent-family blueprint(s), as approved
```

Each running or deployable instance should have its own agent identity. Several
instances may share a blueprint when they remain inside the same approved
credential, permission, ownership, and risk boundary.

## Blueprint boundary decision

### Instances may share a blueprint when they share

- The same agent purpose and codebase.
- The same LOB business owner and publisher.
- The same authentication architecture.
- The same minimal inheritable permissions.
- The same data classification and regulatory posture.
- An acceptable shared credential and incident-response blast radius.

### Use separate blueprints when agents differ in

- Business sponsor, publisher, or accountable owner.
- Agent purpose or product family.
- Credential authority or federated trust.
- Inheritable permissions or consent requirements.
- Regulated versus nonregulated data handling.
- Customer, legal-entity, or geographic isolation requirements.
- Production versus experimental trust boundaries.
- Incident-response ownership or acceptable blast radius.
- Single-tenant versus multitenant publication.

Different permissions that apply to only one instance should normally be
assigned directly to that agent identity. They should not be added to the
blueprint as inheritable permissions unless every child identity requires
them.

## Required LOB blueprint profile

Document the following before registering a blueprint:

| Field | Required information |
|---|---|
| LOB | One of the five core LOBs |
| Agent family | Stable product or agent-family name |
| Business purpose | Approved outcome and prohibited uses |
| Business sponsor | Accountable person or approved group |
| Technical owner | Team responsible for code and runtime |
| Security contact | Incident-response owner |
| Compliance contact | Data and regulatory reviewer |
| Data classification | Highest classification the family may process |
| Data domains | Approved systems and datasets |
| Tool boundary | Approved APIs, MCP servers, and actions |
| Authentication mode | S2S, OBO, or approved agent-user scenario |
| Inheritable permissions | Minimal permissions required by every instance |
| Instance permissions | Permissions assigned only to specific identities |
| Credential strategy | Federation, certificate, or approved temporary secret |
| Environments | Development, test, and production separation |
| Policy and tags | Agent 365 policies and inventory metadata |
| Review cadence | Permission, sponsor, and lifecycle review schedule |
| Retirement owner | Team authorized to disable and delete the family |

Never put passwords, client secrets, tokens, private keys, connection strings,
or sensitive customer data in the profile.

## LOB profiles

These profiles are design starting points. They do not grant permission,
constitute compliance approval, or create tenant objects.

### Services

**Typical scope**

- Payments, liquidity, and cash management.
- Trade finance and commercial cards.
- Custody, clearing, and fund services.

**Blueprint considerations**

- Separate payment-execution agents from informational or reconciliation
  agents because their tool authority and transaction risk differ.
- Isolate credentials and permissions for payment initiation, custody, and
  securities-processing systems.
- Require explicit controls for transaction approval, sanctions screening,
  customer isolation, and cross-border data handling where applicable.
- Route incidents to the Services application owner and the relevant payment
  or securities operations team.

### Markets

**Typical scope**

- Fixed income, currencies, commodities, and equities.
- Trading, financing, market-making, and risk-management workflows.

**Blueprint considerations**

- Separate research or analytics agents from order-routing or trade-execution
  agents.
- Treat market data, positions, client activity, and trading strategies
  according to their classification and licensing restrictions.
- Isolate production trading credentials from simulation and experimentation.
- Require controls for pre-trade checks, market conduct, model risk, and
  time-sensitive incident response where applicable.

### Banking

**Typical scope**

- Investment Banking and Corporate Banking.
- Commercial Banking.
- Advisory, capital raising, corporate lending, and related services.

**Blueprint considerations**

- Separate public-information agents from agents that can access confidential
  deal, lending, or client information.
- Establish deal-team, client, and information-barrier boundaries at the data
  and authorization layers; a blueprint alone does not enforce them.
- Avoid broad inheritable permissions to document repositories or client
  systems.
- Route sponsorship and compliance review to the relevant Banking product
  owner and control function.

### Wealth

**Typical scope**

- Private Banking, affluent wealth management, and workplace wealth services.
- Investment, lending, trust, and advisory services.

**Blueprint considerations**

- Protect portfolio, holdings, transaction, suitability, and client-profile
  data as confidential financial information.
- Separate advisory and analytics agents from agents authorized to initiate
  trades or move funds.
- Apply least privilege to portfolio systems, market-data tools, and
  client-specific records.
- Require a Wealth sponsor, technical owner, privacy review, and defined
  escalation path for unsuitable or unauthorized actions.

### U.S. Personal Banking

**Typical scope**

- Branded credit cards and Retail Services.
- Retail deposits, lending, mortgages, and small-business services.

**Blueprint considerations**

- Separate customer-service agents from agents making or executing credit,
  lending, collections, or account-control decisions.
- Protect consumer identity, account, transaction, and credit information.
- Require appropriate review for fair-lending, adverse-action, servicing,
  privacy, and consumer-protection obligations.
- Use instance-level access controls for channel, product, and customer-data
  boundaries rather than broad LOB-wide inherited access.

## Current Wealth portfolio-manager profile

This profile documents the current repository implementation. It does not
authorize additional permissions or represent a production approval.

| Field | Current value |
|---|---|
| LOB | Wealth |
| Agent family | Trading Platform / Portfolio Manager |
| Repository location | `lob/wealth/ai-agent-starter-portfolio-manager/` |
| Business purpose | Query and analyze a portfolio event ledger through REST, chat, and MCP-compatible surfaces |
| Blueprint | `trading-platform-agent` |
| Current instance | Local development agent identity |
| Data classification | Confidential portfolio and trade data |
| Authentication | Blueprint-backed Agent ID flow; user access to APIM uses the documented device-code flow |
| Approved tools | Portfolio database operations and repository-documented portfolio tools |
| Observability | Agent 365-compatible Microsoft OpenTelemetry |
| Content capture | Governed by the current observability and privacy configuration |
| Business sponsor | Must remain assigned and current in Entra Agent ID |
| Technical owner | Portfolio-manager application owner |
| Environment boundary | Local development is documented; production requires a separate review and identity |

Before adding production, trade execution, fund movement, Work IQ, Microsoft
Graph, or new customer-data access, repeat the blueprint boundary review and
obtain the approvals required by the
[tenant governance guide](./tenant_governance.md).

## Naming and inventory metadata

Use names that identify the LOB, agent family, and environment without
embedding confidential project or customer information.

Suggested pattern:

```text
Blueprint:     <lob>-<agent-family>
Agent identity: <lob>-<agent-family>-<environment>
```

Examples:

```text
wealth-portfolio-manager
wealth-portfolio-manager-local-dev
wealth-portfolio-manager-production
```

Recommended inventory metadata:

- `lob-<lob-name>`
- `owner-<approved-team-name>`
- `environment-<environment>`
- `data-<classification>`
- `identity-agent-id`

Treat naming and tags as discovery aids. Authorization must be enforced by
identity, application, data, network, and policy controls.

## Review and approval workflow

1. Classify the agent family and assign its LOB.
2. Complete the required LOB blueprint profile.
3. Determine whether an existing blueprint has the same purpose and trust
   boundary.
4. Prefer a new agent identity under that blueprint when the boundary matches.
5. Propose a separate blueprint when ownership, credentials, inheritable
   permissions, regulatory posture, or blast radius differs.
6. Obtain business, identity, security, privacy, and compliance approvals
   required for the proposed access.
7. Register the blueprint and BlueprintPrincipal through the approved
   provisioning process.
8. Create separately sponsored agent identities for approved instances.
9. Validate identity, permissions, telemetry, policy, and incident routing.
10. Record creation, validation, changes, and retirement in the Agent 365
    change ledger.

## Anti-patterns

- Creating exactly five enterprise-wide blueprints solely because five LOBs
  exist.
- Sharing one enterprise blueprint across unrelated agent families.
- Using an LOB name as a substitute for a named sponsor or technical owner.
- Granting every LOB system permission at the blueprint level.
- Combining informational and transactional agents despite materially
  different authority.
- Sharing production credentials with experiments.
- Treating blueprint registration as data-access authorization.
- Encoding secrets or sensitive client information in names, tags, or
  documentation.

## Related documentation

- [Agent Identity Blueprint guide](./blueprints.md)
- [Agent 365 tenant governance](./tenant_governance.md)
- [Security and privacy](./security_and_privacy.md)
- [Provisioning runbook](./provisioning_runbook.md)
- [Configuration reference](./configuration_reference.md)
- [Contoso Bank lines of business](../lob/current_lobs.md)

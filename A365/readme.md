# Trading Platform Agent - Microsoft Agent 365

## Overview

This folder documents the Microsoft Agent 365 (A365) integration for the
Trading Platform Agent.

The Trading Platform Agent is a custom Python agent that runs outside Microsoft
Copilot Studio and Microsoft Foundry Agent Service. Agent 365 supports this
scenario through developer-integrated identity and observability:

- Microsoft Entra Agent ID provides the governed agent identity.
- Microsoft OpenTelemetry Distro exports Agent 365-compatible telemetry.
- Agent 365 provides centralized inventory, governance, audit, and security
  integration in the tenant.

## Start here

Use this collection according to the work being performed:

1. **Develop or review an integration:** Start with the
   [developer guide](./developers_guide.md).
2. **Understand the design:** Read this page, then the
   [implementation plan](./implementation_plan.md).
3. **Design the identity boundary:** Use the
   [blueprint guide](./blueprints.md) and
   [LOB blueprint guidance](./lob_blueprints.md).
4. **Register and configure an agent:** Follow the
   [provisioning runbook](./provisioning_runbook.md), then the
   [configuration reference](./configuration_reference.md).
5. **Wire an application:** Use the
   [existing-agent onboarding guide](./onboarding_agents.md) and the concrete
   [LOB application wiring guide](./lob_app_wiring.md).
6. **Prove the integration:** Run the
   [verification process](./verification_process.md).
7. **Investigate component data:** Use the
   [Defender guide](./components/defender_guide.md),
   [Purview guide](./components/purview_guide.md), and
   [Entra guide](./components/entra_guide.md).
8. **Operate and govern it:** Use the
   [operations runbook](./operations_runbook.md),
   [tenant governance guide](./tenant_governance.md), and
   [security and privacy guide](./security_and_privacy.md).

## Documentation by lifecycle

### Architecture and planning

| Document | Purpose |
|---|---|
| [Developer guide](./developers_guide.md) | Canonical logical design, code responsibilities, implementation method, validation gates, and Microsoft-guidance crosswalk |
| [Implementation plan](./implementation_plan.md) | Phases, decisions, tests, rollout, and definition of done |
| [Blueprints](./blueprints.md) | Beginner and architecture guide for Agent ID blueprints |
| [LOB blueprint guidance](./lob_blueprints.md) | Enterprise taxonomy, boundary rules, and profiles for Contoso Bank lines of business |
| [Tenant governance](./tenant_governance.md) | Roles, RACI, policies, risk, licensing, and approvals |
| [Security and privacy](./security_and_privacy.md) | Trust boundaries, data classification, threats, and retention |

### Provisioning and implementation

| Document | Purpose |
|---|---|
| [Agent 365 CLI guide](./agent365_cli.md) | Installation, authentication, setup, diagnostics, automation, and cleanup |
| [Provisioning runbook](./provisioning_runbook.md) | Registration, verification, consent, artifacts, and cleanup |
| [Configuration reference](./configuration_reference.md) | Environment variables, secrets, and compatibility |
| [Existing-agent onboarding](./onboarding_agents.md) | End-to-end steps for adding Agent 365 to an existing runtime |
| [LOB application wiring](./lob_app_wiring.md) | File-by-file runtime wiring for identity, authentication, telemetry, Purview, and Defender |
| [Observability reference](./observability_reference.md) | Trace model, attributes, privacy, and hunting queries |

### Validation and operations

| Document | Purpose |
|---|---|
| [Verification process](./verification_process.md) | ARRANGE, ACT, ASSERT verification for identity, telemetry, privacy, and portal arrival |
| [Defender component guide](./components/defender_guide.md) | Security Dashboard for AI, Advanced Hunting, detections, alerts, incidents, and current Defender evidence |
| [Purview component guide](./components/purview_guide.md) | Unified DSPM, AI observability, Activity Explorer, policies, alerts, audit, and Purview RBAC |
| [Entra component guide](./components/entra_guide.md) | Agent ID objects, credentials, permissions, sign-ins, audit logs, risk, and Conditional Access |
| [Defender query CLI](./query-defender.ps1) | Run read-only Advanced Hunting queries from PowerShell |
| [Operations runbook](./operations_runbook.md) | Monitoring, rotation, incidents, rollback, and retirement |
| [Troubleshooting](./troubleshooting.md) | Identity, token, exporter, CLI, and telemetry failures |

## Status

| Capability | Status |
|---|---|
| Existing Python/FastAPI agent | Implemented |
| Private APIM model routing | Implemented |
| User device-code authentication to APIM | Implemented |
| PostgreSQL portfolio tools | Implemented |
| APIM token governance | Implemented |
| Entra Agent ID blueprint | Implemented |
| Agent identity instance and sponsor | Implemented |
| Agent 365 inventory registration | Implemented |
| Microsoft OpenTelemetry Distro | Implemented |
| Agent 365 S2S telemetry authentication | Implemented |
| Microsoft 365 Admin Center inventory | Implemented |
| Purview Activity Explorer ingestion | Verified |
| Purview policy evaluation | Awaiting policy evaluation window |
| Defender Advanced Hunting ingestion | Blocked: `CloudAppEvents` has no Agent 365 rows |
| Work IQ tooling | Out of scope |
| Notifications and agent user account | Out of scope |

The local-development identity, inventory registration, runtime exporter, and
Purview Activity Explorer ingestion are implemented. Defender ingestion and
policy-generated findings remain separate downstream assertions. Use
[the ARRANGE, ACT, ASSERT process](./verification_process.md) to validate each
surface without treating one successful portal as proof of all others.

## Why this integration path

Agent 365 supports three broad integration mechanisms:

1. Built-in integration for Microsoft-hosted agent platforms.
2. Registry synchronization for supported third-party platforms.
3. Agent 365 SDK integration for self-hosted, code-based agents.

This agent uses option 3 because it is a self-hosted Microsoft Agent Framework
application. The SDK does not replace the framework, model, tools, hosting, or
APIM gateway. It adds tenant identity and governance capabilities alongside the
existing runtime.

Observability is implemented separately with Microsoft OpenTelemetry. The
deprecated Agent 365 Observability SDK must not be used.

## Existing agent architecture

```text
User
  |
  | device-code sign-in
  v
chat.py
  |
  | HTTP + user bearer token
  v
FastAPI /chat (local Docker)
  |                         |
  | asyncpg                 | APIM subscription key
  v                         | + user bearer token
PostgreSQL                  v
portfolio ledger      Private APIM AI gateway
                              |
                              v
                        Azure model deployment
```

The user token authorizes model invocation through APIM. It is not the agent's
Agent 365 identity and must not be used to export telemetry.

## Target A365 architecture

```text
                       Microsoft Entra tenant
                 +--------------------------------+
                 | Agent Identity Blueprint       |
                 |   -> BlueprintPrincipal        |
                 |   -> Local/dev Agent Identity  |
                 |   -> Sponsor and policy        |
                 +---------------+----------------+
                                 |
                         S2S Agent ID token
                                 |
+-------------+          +-------v----------------+
| chat.py     |--------->| FastAPI / Agent        |
| user token  |          | Framework / Tools      |
+-------------+          +---+----------------+---+
                            |                |
                            |                | OpenTelemetry
                            |                | invoke/model/tool spans
                            |                v
                            |       Microsoft Agent 365
                            |       observability endpoint
                            |
                            v
                     APIM + PostgreSQL
                     existing data path
```

The two authentication paths remain separate:

| Path | Identity | Purpose |
|---|---|---|
| User to APIM | Device-code user token | Authorize the interactive model request |
| Agent to A365 | Agent Identity S2S token | Attribute telemetry and governance to the agent |

## Agent 365 capabilities and boundaries

### Identity and inventory

The local-development integration has:

- One Agent Identity Blueprint for the agent type.
- A mandatory BlueprintPrincipal.
- A distinct agent identity per environment.
- A human sponsor responsible for lifecycle decisions.
- Tenant-visible identity, permissions, sign-in activity, and audit records.

Credentials belong to the blueprint, not the agent identity. Production should
use managed identity and federation. A local development secret, if needed,
must be short-lived and must never be committed.

### Observability

The Python runtime uses `microsoft-opentelemetry` and emits:

- One `invoke_agent` root span for each chat turn.
- Child model inference spans.
- Child tool execution spans.
- HTTP and database dependency spans where supported.
- Success, failure, and rate-limit outcomes.
- Agent ID and tenant correlation baggage.

Microsoft OpenTelemetry must initialize before instrumented libraries are
loaded.

### Governance

The registered identity enables governance controls such as:

- Central agent inventory.
- Sponsor and lifecycle accountability.
- Conditional Access and permission review.
- Independent disable/revocation.
- Defender threat investigation.
- Purview audit and compliance review.
- Tenant-level agent policy and access controls.

Registration does not automatically grant the agent access to Microsoft 365
data. Work IQ, Graph permissions, and notifications remain disabled unless
they are separately justified and approved.

## Telemetry content decision

Telemetry content capture is a deliberate governance decision, not an
incidental exporter setting. `A365_RECORD_CONTENT` defaults to `false`, making
metadata-only export the baseline for normal development and production.

Metadata-only environments must not export:

- Raw user prompts.
- Model responses.
- Account IDs.
- Trade records.
- SQL text or database results.
- APIM subscription keys.
- Bearer tokens or device codes.
- PostgreSQL credentials or connection strings.

An approved nonproduction policy test can set `A365_RECORD_CONTENT=true` to
export prompts, responses, and supported tool or inference content. Enable
that mode only after privacy, compliance, access, retention, and billing
review, then return it to `false`. Tests must inspect exported attributes to
verify the effective policy rather than relying only on configuration.

## Licensing and tenant requirements

Before onboarding:

- Agent 365 must be enabled in the tenant.
- The operator needs Global Administrator or Agent ID Developer access.
- A Global Administrator must be available for required consent.
- At least one tenant user must have Microsoft 365 E7 or Microsoft Agent 365
  assigned.

The observability license requirement is critical: telemetry ingestion can
return HTTP 200 while the service drops all telemetry if the required license
is not assigned.

Work IQ requires Microsoft 365 Copilot and is not part of this implementation.
An agent user account, mailbox, Teams presence, and notifications require the
Frontier preview program and are also out of scope.

## Configuration entry point

Set the required mode and non-secret identifiers explicitly:

```dotenv
ENABLE_A365_OBSERVABILITY=true
A365_TENANT_ID=
A365_BLUEPRINT_CLIENT_ID=
A365_AGENT_ID=
A365_RECORD_CONTENT=false
```

The local-development blueprint credential is supplied separately through
ignored local configuration. Production must use an approved secret store or
federated identity. Credentials must not be added to examples, Compose
defaults, or source code. See the
[configuration reference](./configuration_reference.md) for the complete
setting contract.

## Operational behavior

- A365 export is feature-flagged.
- Disabling A365 must not change APIM, database, or chat behavior.
- Telemetry is asynchronous and must not automatically retry a user request.
- Export failures are logged without tokens or sensitive payloads.
- Bounded queues and timeouts prevent telemetry backpressure from hanging chat.
- Agent and telemetry authentication failures are distinguishable.
- Graceful shutdown flushes queued spans within a bounded timeout.

## Validation summary

The completed integration must prove:

1. The blueprint, principal, agent identity, and sponsor exist.
2. The agent appears in Agent 365 inventory.
3. A normal chat interaction still works.
4. A root `invoke_agent` span is emitted.
5. Model and tool spans are children of the same trace.
6. Telemetry appears in Microsoft Defender, Microsoft Purview, and Microsoft
   365 admin center.
7. Agent and tenant IDs match the registered identity.
8. No sensitive portfolio content is exported.
9. A365 can be disabled without code changes.

See the full checklist and rollout phases in
[implementation_plan.md](./implementation_plan.md).

## Authoritative documentation

- [Microsoft Agent 365 guidance](https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/)
- [Connect existing agents](https://learn.microsoft.com/en-us/microsoft-agent-365/connect-existing-agents)
- [Choose an integration option](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/choose-integration-option)
- [Agent 365 SDK overview](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk)
- [Agent 365 identity](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/identity)
- [Setup agent blueprint](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/registration)
- [Microsoft OpenTelemetry Distro](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry)
- [Observability authentication setup](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability-authentication-setup)
- [Validation checklist](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/validation-checklist)
- [Govern local agents](https://learn.microsoft.com/en-us/microsoft-agent-365/guidance/govern-local-agents)

Documentation reviewed: October 14, 2026.

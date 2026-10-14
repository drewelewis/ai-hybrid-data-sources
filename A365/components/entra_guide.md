# Microsoft Entra Guide for Agent 365

## Purpose

This guide maps the major Microsoft Entra surfaces where Agent 365 identity,
credentials, permissions, ownership, sign-ins, audit events, risk, and access
policy can be inspected.

Microsoft Entra answers identity questions:

- What is the registered blueprint?
- Which tenant principal represents that blueprint?
- Which child Agent Identity runs this environment?
- Who sponsors and owns it?
- What permissions and credentials can it use?
- Did the expected agent identity authenticate?
- Who changed an identity object or policy?

Entra sign-in success does not prove that Agent 365 telemetry reached
Defender, Purview, or Microsoft 365 Admin Center. Validate those services
separately with the [verification process](../verification_process.md).

## Reference identifiers

| Identifier | Value |
|---|---|
| Tenant ID | `00648bab-6c91-4292-9a2a-2297df511222` |
| Blueprint display name | `trading-platform-agent Blueprint` |
| Blueprint application ID | `341ff526-fa67-4487-a028-5d61dd6e5a92` |
| Agent Identity display name | `trading-platform-agent-local-dev` |
| Agent Identity application ID | `7f2edbcc-8375-4d1d-a430-93c14e8db94e` |
| Runtime agent name | `TradingPlatformAgent` |

Microsoft Entra commonly exposes both:

- **Application/client ID:** stable identifier used by OAuth clients and this
  runtime configuration.
- **Object ID:** tenant object identifier for an application, service
  principal, agent identity, or blueprint principal.

Do not substitute one for the other. In particular, the audit-log
`blueprintId` is an object ID, not the blueprint application ID shown above.

## Agent identity object model

| Object | Entra representation | Credentials | Main purpose |
|---|---|---|---|
| Agent Identity Blueprint | Application object | Holds credential or federation | Template and authentication foundation |
| BlueprintPrincipal | Specialized tenant service principal | Uses blueprint trust | Represents the blueprint in the tenant |
| Agent Identity | Specialized service principal with agent semantics | Has no independent credential | Identifies one running agent instance |
| Sponsor | Human user or approved group relationship | None | Business accountability and lifecycle decisions |
| Owner | Administrative relationship | None | Technical administration |
| Agent user account | Optional user object | User-account controls | Only for scenarios requiring user-like resources |

This implementation has no agent user account. Human device-code
authentication is a separate application identity path and must not be
confused with the Agent Identity used for telemetry.

## Major Entra areas at a glance

| Area | What to look for | Primary question |
|---|---|---|
| Agent ID inventory | Blueprint, Agent Identities, status, sponsor, relationships | Is the governed agent identity present and accountable? |
| App registrations | Blueprint application, credentials, API permissions, manifest relationships | Is the template configured safely? |
| Enterprise applications | BlueprintPrincipal and Agent Identity service principals | What tenant principals and grants exist? |
| Sign-in logs | Agent type, Is Agent, client, resource, result, Conditional Access | Did the intended identity authenticate? |
| Audit logs | `agentType`, `blueprintId`, changed properties, actor, target | Who created, changed, or deleted an agent object? |
| Identity Protection | Risky workload or agent identity findings | Is the identity showing compromise risk? |
| Conditional Access | Workload/agent policy assignment and result | Were approved access controls evaluated? |
| Permissions and consent | Direct and inherited permissions, admin consent | What can the agent access and why? |

## 1. Agent ID inventory

Open the [Microsoft Entra admin center](https://entra.microsoft.com) and use
the Agent ID areas available in the tenant to review blueprints and agent
identities.

For the target Agent Identity, verify:

- Display name and application ID.
- Agent identity status.
- Parent blueprint relationship.
- Sponsor and technical owner.
- Environment purpose, such as local development versus production.
- Permissions, inherited permissions, and resource assignments.
- Creation and last-use context when available.

For the blueprint, verify:

- Blueprint application ID and object ID.
- BlueprintPrincipal exists in the tenant.
- Approved manager application relationships.
- Credential strategy.
- Inherited permissions and intended child scope.
- Owners and lifecycle responsibility.

A visible child Agent Identity without a sponsor, parent relationship, or
approved lifecycle owner is not ready for production.

## 2. App registrations

Go to **Entra ID > App registrations** and search for the blueprint application
ID.

The blueprint application is the template and credential boundary. Review:

- **Overview:** application/client ID, object ID, tenant, and supported account
  types.
- **Certificates & secrets:** credential type, owner, creation, and expiry.
- **Federated credentials:** workload identity federation configuration when
  implemented.
- **API permissions:** delegated or application permissions and admin-consent
  state.
- **Manifest or Graph relationships:** approved `managerApplications` and
  other blueprint-specific properties.
- **Owners:** technical administrators for the application object.

The current local implementation uses a blueprint client secret. Production
managed identity/workload identity federation is a documented target, not an
implemented runtime path.

Never copy a secret value into a ticket, guide, screenshot, terminal history,
or audit record. Record only credential type, owner, and expiry.

## 3. Enterprise applications

Go to **Entra ID > Enterprise applications**.

Use this area to inspect tenant service-principal objects:

- The **BlueprintPrincipal**, which represents the blueprint in the tenant.
- The child **Agent Identity**, which is a specialized service principal for
  the running agent instance.
- Assigned permissions, app-role assignments, owners, and sign-in activity.
- Whether either identity is enabled or blocked.

An Agent Identity uses agent-specific service-principal semantics. Do not
replace it with a regular app registration or traditional service principal
merely because those objects are familiar.

When names are similar, compare both application ID and object ID before
changing or deleting anything.

## 4. Sponsors, owners, and managers

Microsoft Entra separates:

- **Sponsor:** business accountability and lifecycle decisions.
- **Owner:** technical administration.
- **Manager:** operational relationship for an optional agent user account.

This agent requires a sponsor and technical owner. It does not require a
manager because it has no agent user account.

Review these relationships during onboarding, permission review, credential
rotation, incident response, and retirement. An ownerless or sponsorless
identity should be treated as a governance finding.

## 5. Sign-in logs

Go to **Entra ID > Monitoring & health > Sign-in logs**.

Microsoft documents agent-specific filters:

- **Agent type:** Agent ID user, Agent Identity, Agent Identity Blueprint, or
  Not Agentic.
- **Is Agent:** Yes or No.

Agent-related sign-ins can appear across interactive user, non-interactive
user, service principal, and managed identity views depending on the flow.
For this implementation, focus on app-only/service-principal activity for the
Agent Identity S2S exchange.

Filter by:

1. Agent Identity application ID.
2. UTC test window.
3. Agent type or Is Agent.
4. Target resource.
5. Success/failure result.

Inspect:

- Client application and service principal.
- Target resource and audience.
- Authentication requirement.
- Conditional Access result.
- IP and location context appropriate to the host.
- Correlation and request IDs.
- Failure code and sanitized reason.

A successful sign-in proves token issuance or resource authentication. It does
not prove the exporter used the token successfully or that a downstream
service indexed telemetry.

## 6. Audit logs

Go to **Entra ID > Monitoring & health > Audit logs**.

Agent objects appear as their base directory object types:

| Agent object | Audit event family | `agentType` |
|---|---|---|
| Blueprint | Application event | `agenticApp` |
| Agent Identity | Service principal event | `agenticAppInstance` |
| BlueprintPrincipal | Service principal event | `agentIdentityBlueprintPrincipal` |
| Agent user account | User event | `agentIDuser` |

Use `blueprintId` to correlate an Agent Identity instance back to its blueprint.
Review:

- Activity and category.
- Result and failure reason.
- Initiated by and performed by.
- Target resources.
- Changed properties.
- `agentType`.
- `blueprintId`.
- Correlation ID and UTC time.

Expected audit activities include creating, updating, or deleting application,
service-principal, and user objects. An unexpected credential, permission,
sponsor, or enablement change should enter the identity incident process.

Microsoft Graph beta can retrieve Agent Identity sign-ins:

```http
GET https://graph.microsoft.com/beta/auditLogs/signIns?$filter=signInEventTypes/any(t: t eq 'servicePrincipal') and agent/agentType eq 'AgentIdentity'
```

Use read-only queries first and record no access token or sensitive payload.

## 7. Permissions and consent

Review permissions at both blueprint and child levels:

- Permissions inherited from the blueprint.
- Direct assignments to the Agent Identity.
- Application versus delegated permissions.
- Tenant-wide admin consent.
- Azure RBAC assignments.
- Resource-specific authorization enforced outside Entra.

The Agent 365 CLI can inspect inheritance and blueprint scopes:

```powershell
a365 query-entra blueprint-scopes --agent-name "trading-platform-agent"
a365 query-entra inheritance --agent-name "trading-platform-agent"
```

See the [Agent 365 CLI guide](../agent365_cli.md) before running commands.

The absence of a Microsoft Graph permission does not mean the agent has no
access. It can still have Azure RBAC, APIM authorization, database
credentials, model permissions, or application-defined tool access.

## 8. Identity Protection and Security Dashboard for AI

Use Microsoft Entra ID Protection and
[Security Dashboard for AI](https://ai.security.microsoft.com) for:

- Risky workload or agent identities.
- Suspicious sign-in patterns.
- Misconfiguration or attack-path findings.
- Agent-sprawl and unauthorized-access recommendations.
- Cross-product handoff into Defender or Purview.

Correlate every risk item with the exact Agent Identity. A risk finding for a
blueprint, agent user account, cloud app, or different child identity is not
automatically a finding for this runtime.

## 9. Conditional Access

Agent identities do not perform human MFA. Use workload- or agent-appropriate
Conditional Access rather than a human sign-in policy.

Review:

- Policy target and exclusions.
- Report-only versus enforced state.
- Conditions appropriate to workload identity.
- Sign-in log policy result.
- Emergency disable and rollback plan.

Do not weaken Security Defaults or a human Conditional Access policy to make
an agent sign-in succeed. Design the supported workload identity control
instead.

Workload Conditional Access for this local-development identity remains a
review item and is not yet verified as implemented.

## Identity investigation workflow

1. Start with the Agent Identity application ID and UTC window.
2. Confirm the child identity, blueprint, BlueprintPrincipal, and sponsor.
3. Review current credentials and expiry metadata on the blueprint.
4. Review direct and inherited permissions.
5. Search agent-filtered sign-in logs.
6. Search audit logs for recent identity or permission changes.
7. Review Conditional Access and Identity Protection results.
8. Compare the identity evidence with runtime health.
9. Validate Purview and Defender independently.

## Current tenant evidence

| Assertion | Current state |
|---|---|
| Blueprint exists | Verified |
| BlueprintPrincipal exists | Verified |
| Local-development Agent Identity exists | Verified |
| Sponsor is assigned | Verified |
| Agent 365 inventory registration exists | Verified |
| App-only Agent Identity token exchange succeeds | Verified by runtime health and focused tests |
| Production managed identity/federation exists | Not implemented |
| Workload Conditional Access assignment is verified | Pending |
| Agent user account exists | Intentionally not enabled |

## Common mistakes

| Mistake | Correct interpretation |
|---|---|
| Using the application ID where an object ID is required | Identify which ID the field expects. |
| Looking only in App registrations | Blueprint principals and Agent Identities are tenant principals. |
| Looking only in Enterprise applications | The blueprint definition is an application object. |
| Adding a secret to the child Agent Identity | Credentials belong on the blueprint. |
| Treating a successful sign-in as telemetry proof | Check downstream indexing separately. |
| Applying a human MFA policy to the agent | Use workload/agent identity controls. |
| Assuming sponsor and owner are the same role | Validate business and technical accountability separately. |

## References

- [Microsoft Entra Agent ID key concepts](https://learn.microsoft.com/en-us/entra/agent-id/key-concepts)
- [Agent identities](https://learn.microsoft.com/en-us/entra/agent-id/agent-identities)
- [Agent identity blueprints](https://learn.microsoft.com/en-us/entra/agent-id/agent-blueprint)
- [Owners, sponsors, and managers](https://learn.microsoft.com/en-us/entra/agent-id/agent-owners-sponsors-managers)
- [Agent identities, service principals, and applications](https://learn.microsoft.com/en-us/entra/agent-id/agent-service-principals)
- [Microsoft Entra Agent ID logs](https://learn.microsoft.com/en-us/entra/agent-id/sign-in-audit-logs-agents)
- [Sign-in logs](https://learn.microsoft.com/en-us/entra/identity/monitoring-health/concept-sign-ins)

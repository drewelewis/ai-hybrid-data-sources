# Microsoft Entra Agent ID Blueprints

## A comprehensive guide for new users

## 1. Purpose and scope

This document explains Microsoft Entra Agent ID **agent identity blueprints**:

- What they are.
- Why they exist.
- How they relate to Agent 365.
- When to use them.
- When not to use them.
- How to choose blueprint boundaries.
- How credentials, permissions, sponsors, and agent instances work.
- What to consider before production use.

This document is not about the retired Azure Blueprints service, infrastructure
templates, prompt templates, or Copilot Studio topics. In this document,
**blueprint** always means a Microsoft Entra Agent ID agent identity blueprint.

Agent ID and Agent 365 features are evolving. Verify current Microsoft
documentation, tenant licensing, API versions, and preview limitations before
production deployment.

## 2. The short explanation

An agent identity blueprint is a Microsoft Entra application object that
defines the shared identity and authentication foundation for a type of AI
agent.

One blueprint can create many distinct agent identities:

```text
Agent Identity Blueprint
  |
  +-- BlueprintPrincipal
  |
  +-- Agent Identity: local-dev
  +-- Agent Identity: test
  +-- Agent Identity: production
  +-- Agent Identity: customer-001
```

The blueprint:

- Defines the agent type or family.
- Holds credentials used to authenticate agent instances.
- Declares shared or inheritable permissions.
- Establishes a policy and credential boundary.
- Can be associated with many separately governed agent identities.

Each agent identity:

- Represents one running or deployable agent instance.
- Has its own object ID and client/application ID.
- Has at least one accountable sponsor.
- Can have instance-specific permission assignments.
- Appears separately in identity, audit, and governance experiences.
- Does not hold credentials directly.

The blueprint is not the running agent, and the agent identity is not a human
user.

## 3. Why blueprints exist

Traditional application registrations and service principals work well for
deterministic applications and background services. AI agents introduce
additional governance needs:

- A single agent type can have many separately deployed instances.
- Agents can make dynamic decisions and call multiple tools.
- Security teams need to know which agent instance acted.
- Business accountability must be assigned to a human sponsor.
- Permissions and lifecycle decisions need to apply at both the family and
  instance levels.
- A platform might publish one agent type into many customer tenants.

Blueprints provide a one-to-many identity model that traditional application
registrations do not provide directly.

## 4. Core object model

### 4.1 Agent identity blueprint

The blueprint is the application-level template for an agent family. It is the
place where shared authentication material and protocol configuration live.

A blueprint can define:

- Display name and publisher information.
- Credentials, certificates, or federated identity credentials.
- Identifier URIs and OAuth protocol settings.
- App roles and exposed scopes.
- Declared and inheritable permissions.
- Manager applications required by Agent 365.
- Owners and sponsors.
- Single-tenant or multitenant publication behavior.

Use the blueprint as a **credential boundary**. Agent identities created from
the same blueprint share the blueprint's credential foundation.

### 4.2 BlueprintPrincipal

The BlueprintPrincipal is the tenant service principal representing the
blueprint.

It enables the blueprint to:

- Exist as an enterprise identity in the tenant.
- Participate in token acquisition.
- Appear in audit and sign-in records.
- Serve as the parent for agent identities.

Some supported tools create the BlueprintPrincipal as part of registration.
When using Microsoft Graph directly, do not assume it exists. Verify it and
create it explicitly when required. An agent identity cannot be created
successfully if its BlueprintPrincipal is missing.

### 4.3 Agent identity

An agent identity represents one agent instance. It is a specialized Microsoft
Entra service principal, not a normal application registration.

An agent identity:

- Has its own identity identifiers.
- Is associated with exactly one blueprint.
- Is single-tenant in the tenant where it is created.
- Has one or more sponsors.
- Can receive direct permissions and assignments.
- Can be enabled, disabled, reviewed, and deleted independently.

An agent identity does not have a backing application object and cannot hold
its own passwords, certificates, or federated credentials. Credentials belong
to the blueprint.

### 4.4 Agent's user account

An agent's user account is optional and is separate from the agent identity.
It exists for scenarios that require a user object, such as:

- A mailbox.
- Calendar ownership.
- OneDrive storage.
- Teams presence.
- Being addressed through Outlook, Word comments, email, or Teams.

An agent user account does not replace the agent identity. Most API, telemetry,
and tool-calling agents do not need one.

Agent user accounts require additional licensing and are available only in
supported preview/tenant programs. Do not create one merely to make an agent
look like a person.

### 4.5 Owners, sponsors, and managers

These relationships serve different purposes:

| Relationship | Purpose |
|---|---|
| Owner | Technical administration and configuration |
| Sponsor | Business accountability and lifecycle decisions |
| Manager | Organizational relationship for an optional agent user account |

Every blueprint and agent identity requires an accountable sponsor. Sponsors
should be people or approved groups that can decide whether an agent remains
necessary, should be disabled, or needs investigation.

## 5. Blueprint versus related identity types

| Identity type | Best suited for | Credentials | Multiple agent instances | Agent-aware governance |
|---|---|---|---|---|
| Agent identity blueprint | An AI agent family or product | On blueprint | Yes | Yes |
| Agent identity | One agent instance | Inherited through blueprint | One identity per instance | Yes |
| Traditional app registration/service principal | Deterministic app or service | On app registration | Usually one SP per tenant | Limited agent semantics |
| Managed identity | Azure workload authentication | Platform-managed | One workload identity | Azure workload focused |
| Human user account | Interactive human | Human authentication methods | No | Human governance |
| Agent user account | Agent needing user resources | Paired with agent identity | One per agent identity | Agent-specific, limited availability |

A managed identity and an agent identity can work together. For example, an
Azure managed identity can be federated to the blueprint so the workload can
obtain tokens for a specific agent identity without storing a secret.

## 6. When to use a blueprint

Use a blueprint when one or more of these statements are true.

### 6.1 You need Agent 365 registration and governance

Use a blueprint when a custom or externally hosted agent must appear in Agent
365 inventory with:

- A distinct identity.
- A sponsor.
- Central policy.
- Auditability.
- Lifecycle controls.
- Defender or Purview integration.

### 6.2 You have multiple instances of the same agent type

Examples:

- Development, test, and production instances.
- A separate instance per business unit.
- A separate instance per geography.
- A separate instance per customer tenant.
- Multiple scaled workers that must be represented independently.

One blueprint can describe the common agent type while each instance receives
its own agent identity.

### 6.3 You need instance-level permission control

Use a blueprint when instances share a baseline but require different
permissions. For example:

- Production can read a governed data source.
- Development can access only synthetic data.
- A finance instance has a finance-specific API role.
- A customer instance has access only to that customer's resources.

### 6.4 You need autonomous or OBO agent authentication

Blueprint-backed identities support:

- Service-to-service operation where the agent acts as itself.
- On-behalf-of operation where the agent acts for a signed-in user.
- Optional agent-user scenarios where the agent needs user resources.

The selected runtime flow, permissions, and consent model must match the actual
operation.

### 6.5 You need a reusable published agent type

A multitenant blueprint can represent a published agent type. Each consuming
tenant creates its own tenant-local agent identities from the blueprint.

### 6.6 You need a clear credential boundary

Use a separate blueprint when a set of agent instances must not share:

- Credentials.
- Federated trust.
- Inherited permissions.
- Publisher ownership.
- Incident-response blast radius.

## 7. When not to use a blueprint

### 7.1 The workload is not an AI agent

A deterministic API, scheduled job, ETL process, or conventional web
application might be better represented by a normal application registration
or managed identity.

Do not use Agent ID solely because the workload calls an AI model. The workload
should have agent-like autonomy, tool use, or governance requirements.

### 7.2 A built-in platform already handles registration

Agents hosted by supported Microsoft platforms may already receive Agent 365
identity and governance integration. Confirm the current platform behavior
before creating a duplicate blueprint manually.

Examples can include supported Copilot Studio and Foundry Agent Service
scenarios.

### 7.3 Registry synchronization fully satisfies the requirement

Agent 365 can synchronize agents from supported third-party platforms. If
registry synchronization already supplies the required inventory and
observability, a custom SDK and blueprint integration might be unnecessary.

### 7.4 You only need basic application telemetry

If the requirement is only to send standard application logs to Azure Monitor
or another OpenTelemetry backend, an Agent ID blueprint might be unnecessary.

However, standard telemetry alone does not provide Agent 365 inventory,
sponsorship, agent-specific identity, or instance governance.

### 7.5 You are trying to create a human substitute account

Do not create an agent user account or blueprint merely to bypass human
identity controls, licensing, MFA, consent, or Conditional Access.

### 7.6 You cannot establish ownership and lifecycle controls

Do not create unmanaged agent identities without:

- A sponsor.
- A technical owner.
- A permission review.
- A credential strategy.
- A disable/delete procedure.
- An incident response contact.

## 8. Choosing the correct blueprint boundary

The most important design question is not "How many agents do I have?" It is
"Which agent instances can safely share a credential and inherited permission
boundary?"

### Use one blueprint when instances share

- The same agent purpose and codebase.
- The same publisher and ownership model.
- The same baseline permissions.
- The same authentication architecture.
- An acceptable shared credential blast radius.

### Use separate blueprints when instances differ in

- Business owner or publisher.
- Production versus experimental trust boundary.
- Regulated versus nonregulated data.
- Credential authority.
- Required inherited permissions.
- Customer isolation.
- Incident-response isolation.
- Single-tenant versus multitenant publication.

### Environment guidance

Development and production can use separate agent identities under one
blueprint if sharing the blueprint credential boundary is acceptable.

Use separate blueprints when production must have:

- A different credential issuer.
- Separate federation.
- Stronger inherited permissions.
- A different sponsor or publisher.
- Independent emergency revocation.

## 9. Credentials and runtime authentication

### 9.1 Where credentials belong

Credentials belong on the blueprint, not the agent identity.

Supported blueprint credential types include:

- Federated identity credentials.
- Certificates and cryptographic keys.
- Client secrets.

Recommended order:

1. Managed identity plus federated identity credential.
2. Workload identity federation.
3. Certificate where federation is not available.
4. Client secret only for constrained local development or transition.

### 9.2 Why a shared credential can still identify an instance

The blueprint credential proves that the parent blueprint is allowed to
request a token. The agent identity token flow then produces a token associated
with the specific agent identity.

The runtime must perform the supported agent token exchange. Using the
blueprint's ordinary application token directly loses per-instance identity
and can produce incorrect token claims or authorization failures.

### 9.3 Runtime helpers

Use supported helpers rather than hand-building token exchanges where possible:

- .NET: `Microsoft.Identity.Web.AgentIdentities`.
- Python, Node.js, Go, Java, and other runtimes: Microsoft Entra ID Auth SDK
  sidecar.
- Microsoft Graph: provisioning and lifecycle operations when CLI or SDK
  tooling does not fit.

Keep the sidecar accessible only to the agent workload. Do not expose it through
an ingress, public load balancer, or general-purpose network endpoint.

### 9.4 Authentication modes

| Mode | Agent acts as | Permission type | Typical use |
|---|---|---|---|
| S2S | Its agent identity | Application | Background work, telemetry, monitoring |
| OBO | Signed-in user, with agent as actor | Delegated | User-authorized interactive actions |
| Agentic-User | Its optional agent user account | User context | Mailbox, calendar, Teams presence |

Choose the operating mode before choosing permissions.

## 10. Permissions and consent

### 10.1 Declaring is not granting

A permission declared on a blueprint is not automatically granted. An
administrator must grant consent or assign the permission to the relevant
principal or agent identity.

### 10.2 Baseline versus instance-specific permissions

Use inheritable blueprint permissions for the minimum baseline every instance
requires.

Assign permissions directly to an agent identity when only that instance needs
them.

Examples:

```text
Blueprint baseline:
  - Read a common metadata API

Production agent identity:
  - Read production portfolio data

Development agent identity:
  - Read synthetic development data
```

### 10.3 Azure RBAC

Azure role assignments are not inherited from the blueprint. Assign Azure RBAC
roles directly to each agent identity that needs them.

### 10.4 Least privilege

For every permission, document:

- Resource/API.
- Permission name and ID.
- Application or delegated type.
- Business justification.
- Granting administrator.
- Review date.
- Revocation process.

Some high-risk permissions are blocked for agent identities. Redesign the
operation rather than trying to bypass those restrictions.

## 11. Registration and provisioning

### 11.1 Recommended tools

Use this order of preference:

1. Agent 365 CLI or supported Agent 365 setup skills for standard onboarding.
2. Microsoft Entra Agent ID SDK/tooling for runtime token handling.
3. Typed Microsoft Graph Agent ID APIs for custom automation.

Supported tools handle details that are easy to miss, including:

- Blueprint registration.
- BlueprintPrincipal creation.
- `managerApplications`.
- Agent identity creation.
- Permission wiring.
- Generated configuration.

### 11.2 Typical provisioning sequence

```text
1. Confirm tenant roles, licensing, sponsor, and naming.
2. Create the blueprint.
3. Create or verify the BlueprintPrincipal.
4. Configure managerApplications where Agent 365 requires it.
5. Configure identifier URIs and protocol settings.
6. Add the selected blueprint credential.
7. Declare minimum inheritable permissions.
8. Obtain required administrative consent.
9. Create the agent identity.
10. Assign the sponsor.
11. Apply instance-specific permissions.
12. Validate token claims and resource access.
13. Confirm Agent 365 inventory and telemetry.
```

Provisioning should be idempotent. Directory propagation can cause immediate
follow-up requests to fail temporarily. Use bounded exponential backoff and
verify objects after creation.

### 11.3 `managerApplications`

Agent 365 requires supported management applications to be associated with a
blueprint. Current Agent 365 CLI workflows configure this automatically.

Blueprints created manually or with older tooling might lack this property and
can be rejected by Agent 365. Verify it as part of registration validation.

## 12. Single-tenant and multitenant design

Agent identities are tenant-local. A blueprint can be single-tenant or
multitenant.

### Single-tenant blueprint

Use when:

- The agent is internal to one organization.
- The publisher and consumer are the same tenant.
- Cross-tenant distribution is not required.

### Multitenant blueprint

Use when:

- A software publisher distributes one agent type to customers.
- Each customer needs tenant-local agent identities.
- The publisher controls the blueprint while customers control their local
  identity grants and policies.

Do not assume that a token exchange should target the blueprint publisher's
tenant. Cross-tenant flows can require the agent identity's home tenant at a
specific exchange step. Follow current cross-tenant Agent ID guidance.

## 13. Governance and security considerations

### 13.1 Sponsorship

Sponsors are not decorative metadata. They establish business accountability.

A sponsor should be able to answer:

- What business purpose does this agent serve?
- What data and tools can it access?
- Who uses it?
- What happens if it is disabled?
- When should it be reviewed or retired?

### 13.2 Conditional Access

Agent identities do not perform MFA. Apply Conditional Access controls designed
for workload and agent identities rather than human sign-in policies.

### 13.3 Credential blast radius

Every identity under one blueprint shares the blueprint credential foundation.
A compromised blueprint credential can affect every child agent identity.

Mitigations:

- Prefer federation over secrets.
- Separate high-risk environments.
- Rotate credentials.
- Minimize inherited permissions.
- Monitor sign-in activity.
- Disable affected identities promptly.

### 13.4 Telemetry and privacy

Registration and telemetry are different capabilities. A registered identity
does not automatically produce useful telemetry.

For Agent 365 observability:

- Emit a valid root `invoke_agent` span.
- Include the correct tenant ID and agent ID.
- Use the correct S2S or OBO token.
- Disable prompt and response content capture by default.
- Never emit credentials or tokens.
- Verify the required Agent 365/Microsoft 365 license.

### 13.5 Audit and investigation

Audit systems can represent blueprint and agent operations under general
application-management or service-principal categories. Record object IDs and
client IDs so investigators can correlate events correctly.

## 14. Lifecycle management

### 14.1 Create

Before creation:

- Assign sponsor and owner.
- Select blueprint boundary.
- Review permissions.
- Select credential mechanism.
- Define environment and naming.
- Define expected retirement date or review cadence.

### 14.2 Operate

During operation:

- Review sign-ins and audit events.
- Review direct and inherited permissions.
- Rotate credentials.
- Validate sponsors.
- Monitor telemetry and failures.
- Confirm the instance remains necessary.

### 14.3 Disable

Disable an individual agent identity when:

- One instance is compromised.
- One environment is retired.
- Investigation is in progress.
- A sponsor no longer approves it.

Disable or revoke the blueprint credential when the entire agent family is at
risk.

### 14.4 Delete

Recommended deletion order:

1. Stop the runtime.
2. Preserve required audit evidence.
3. Remove direct permission assignments.
4. Delete the agent identity.
5. Repeat for all child identities.
6. Remove blueprint credentials.
7. Delete the BlueprintPrincipal and blueprint only when no instances remain.
8. Delete any orphaned agent user accounts separately.

Deleting a blueprint or agent identity does not automatically delete associated
agent user accounts.

## 15. Common architecture patterns

### Pattern A: One internal agent, one environment

```text
Blueprint: expense-review-agent
  +-- Agent identity: expense-review-prod
```

Good for a simple internal production agent.

### Pattern B: One agent family, multiple environments

```text
Blueprint: trading-platform-agent
  +-- Agent identity: trading-platform-dev
  +-- Agent identity: trading-platform-test
  +-- Agent identity: trading-platform-prod
```

Good when the environments can safely share a blueprint credential boundary.

### Pattern C: Separate production trust boundary

```text
Blueprint: trading-platform-nonprod
  +-- dev
  +-- test

Blueprint: trading-platform-prod
  +-- prod
```

Good when production requires independent credentials, ownership, and incident
containment.

### Pattern D: Software publisher

```text
Multitenant blueprint: vendor-risk-agent

Customer tenant A:
  +-- Agent identity: vendor-risk-agent-a

Customer tenant B:
  +-- Agent identity: vendor-risk-agent-b
```

Good for distributing one agent type while preserving tenant-local identities.

## 16. Anti-patterns

Avoid these designs:

- One blueprint for every process replica without a governance reason.
- One blueprint for the entire enterprise regardless of purpose.
- Production and experiments sharing a high-privilege secret.
- Credentials placed directly on agent identities.
- Human user accounts used as agent identities.
- Agent user accounts created for telemetry-only agents.
- Every possible permission declared as inheritable.
- Assuming declared permissions are already consented.
- Reusing the blueprint application token as the per-agent token.
- Omitting sponsors.
- Exposing the Agent ID sidecar publicly.
- Deleting a blueprint before understanding its child identities.
- Treating Agent ID as a replacement for application authorization.
- Assuming registration alone enables observability.

## 17. Blueprint design checklist

### Purpose

- [ ] Is this workload truly an AI agent?
- [ ] Is its purpose documented?
- [ ] Is the business owner known?

### Boundary

- [ ] Which instances will share the blueprint?
- [ ] Can they safely share credentials?
- [ ] Can they safely share inherited permissions?
- [ ] Should production use a separate blueprint?

### Identity

- [ ] Is the BlueprintPrincipal present?
- [ ] Is `managerApplications` configured?
- [ ] Is every agent identity linked to the intended blueprint?
- [ ] Does every object have an accountable sponsor?

### Credentials

- [ ] Is federation used where possible?
- [ ] Are secrets short-lived and stored securely?
- [ ] Is there a rotation procedure?
- [ ] Is the blast radius understood?

### Permissions

- [ ] Are inheritable permissions minimal?
- [ ] Are instance-specific permissions assigned directly?
- [ ] Has consent been granted by the correct administrator?
- [ ] Are Azure roles assigned to the individual identity?

### Runtime

- [ ] Is the correct S2S, OBO, or Agentic-User mode selected?
- [ ] Does the runtime obtain a token for the agent identity?
- [ ] Are token audience, subject, tenant, and expiry validated?
- [ ] Is the sidecar private to the workload?

### Operations

- [ ] Are sign-in and audit records monitored?
- [ ] Are telemetry and content policies documented?
- [ ] Can one instance be disabled independently?
- [ ] Is deletion order documented?

## 18. FAQ

### What is an agent identity blueprint?

It is a Microsoft Entra application object that defines the shared
authentication, protocol, permission, and policy foundation for one or more AI
agent identities.

### Is a blueprint the running agent?

No. The running agent is your application or service. The blueprint is its
identity template and authentication foundation.

### Is a blueprint the same as an app registration?

A blueprint is application-based, but it uses an Agent ID-specific type and
supports a one-to-many relationship with agent identities. A traditional app
registration normally maps to conventional service principals and lacks
agent-specific sponsorship and lifecycle semantics.

### Is this the same as Azure Blueprints?

No. Azure Blueprints was an Azure governance service for packaging policy,
roles, and resource templates. Agent identity blueprints are Microsoft Entra
identity objects for AI agents.

### What is the difference between a blueprint and a BlueprintPrincipal?

The blueprint is the application definition. The BlueprintPrincipal is the
tenant service principal representing that blueprint. The principal must exist
before the blueprint can create and support agent identities.

### Does creating a blueprint automatically create its BlueprintPrincipal?

Do not depend on that assumption. Supported Agent 365 tooling may create both,
but direct Microsoft Graph provisioning can require an explicit principal
creation step. Always verify it.

### What is the difference between a blueprint and an agent identity?

The blueprint represents an agent type or family and holds credentials. An
agent identity represents one tenant-local instance and has its own sponsor,
permissions, and lifecycle.

### Can an agent identity have a client secret?

No. Credentials belong to the blueprint. Agent identities cannot hold their
own password credentials.

### If identities share blueprint credentials, how are they distinct?

The supported agent token flow uses the blueprint credential as the parent
proof and obtains a token for a specific child agent identity. The resulting
token and audit trail identify the instance.

### Should development and production use the same blueprint?

Only if sharing credentials and inherited permissions is acceptable. Use
separate blueprints when production needs an independent trust, ownership, or
incident boundary.

### Do I need a blueprint for a single agent instance?

You can. A blueprint is still useful for Agent 365 registration, sponsorship,
governance, and future instances. The number of instances is not the only
reason to use one.

### Do I need a blueprint just because my application calls an LLM?

No. A conventional application that makes deterministic model calls might be
better represented by a normal app registration or managed identity. Use Agent
ID when agent identity and governance semantics are needed.

### Does a blueprint grant permissions automatically?

No. Declaring a permission does not grant it. Administrative consent or an
explicit assignment is still required.

### Where should common permissions be assigned?

Declare only the minimum common baseline as inheritable blueprint permissions.
Assign permissions needed by only one instance directly to that agent
identity.

### Can a blueprint inherit Azure RBAC roles to its instances?

No. Assign Azure RBAC roles directly to each agent identity.

### What is a sponsor?

A sponsor is the human or approved group accountable for the agent's business
purpose and lifecycle. A sponsor is not necessarily the technical
administrator.

### Can a service principal be the blueprint sponsor?

Current provisioning rules require a user sponsor when creating a blueprint.
Agent identity sponsorship can support users or groups depending on the
operation and API. Verify current API requirements.

### Does an agent identity use MFA?

No. Agent identities do not sign in like humans and do not use passwords,
authenticator applications, or SMS MFA. Use workload/agent Conditional Access,
federation, credential controls, and least privilege.

### When does an agent need an agent user account?

Only when it needs user-backed resources or experiences such as a mailbox,
calendar, OneDrive, Teams presence, or participation in Microsoft 365
communication channels.

### Does every Agent 365 agent need an agent user account?

No. Identity, telemetry, APIs, and tools generally do not require one.

### Can a blueprint be multitenant?

Yes. A multitenant blueprint can be published across tenants, while each agent
identity remains tenant-local.

### Can I use a managed identity with a blueprint?

Yes. A managed identity can be federated to the blueprint so an Azure workload
can authenticate without storing a client secret.

### What should a Python or Java agent use for runtime token acquisition?

Use the Microsoft Entra ID Auth SDK sidecar when appropriate. It provides a
language-neutral HTTP interface for token acquisition and validation. Keep it
private to the agent workload.

### What should a .NET agent use?

Use `Microsoft.Identity.Web.AgentIdentities` where supported. It provides
higher-level Agent ID token and federation helpers.

### Does registering the blueprint automatically enable telemetry?

No. Registration establishes identity and inventory. The application must also
emit correctly structured telemetry, authenticate the exporter, include the
tenant and agent identity, and produce a valid `invoke_agent` root span.

### Why might telemetry return HTTP 200 but not appear?

Common causes include:

- No required Agent 365 or Microsoft 365 E7 license in the tenant.
- No valid root `invoke_agent` span.
- Missing tenant or agent ID baggage.
- Wrong token audience.
- Agent ID mismatch between token, baggage, and export URL.
- Telemetry content or exporter configuration errors.

### What is `managerApplications`?

It identifies approved management applications for the blueprint. Agent 365
requires it for platform manageability. Current Agent 365 CLI workflows
configure it, but older or manually created blueprints might not have it.

### Can I use Azure CLI credentials to provision Agent ID objects?

Do not assume a normal Azure CLI access token will work. Some Azure CLI tokens
include permissions that Agent ID APIs reject. Use the supported Agent 365 CLI,
Microsoft Graph authentication with explicit Agent ID permissions, or a
dedicated provisioning application.

### Why can provisioning fail immediately after object creation?

Microsoft Entra directory objects can take time to propagate. Blueprint,
principal, and identity operations performed immediately in sequence can fail
temporarily. Use idempotent logic and bounded exponential backoff.

### Are there scale limits?

Current Microsoft guidance documents limits for some management patterns,
including a 250-agent-identity-per-blueprint limit for non-Microsoft management
platforms using app-only provisioning. Delegated and Microsoft-owned platform
paths can differ. Verify current limits before large-scale design.

### What happens when I delete a blueprint?

Its agent identities can no longer rely on that identity foundation. Associated
agent user accounts are not automatically deleted and can become orphaned.
Inventory child identities and dependent resources before deletion.

### Can one compromised blueprint affect multiple agents?

Yes. Blueprint credentials are shared across child identities. Treat a
blueprint as a security and blast-radius boundary.

### Should I create one blueprint for the whole organization?

Usually not. Separate blueprints by agent purpose, publisher, credential
boundary, inherited permissions, regulatory boundary, and incident blast
radius.

### Should every container replica get its own agent identity?

Not necessarily. Create identities according to governance and authorization
boundaries, not transient process count. Replicas of one logical instance can
often share one agent identity, while separate customers or environments
usually need distinct identities.

### Can I disable one agent without disabling the whole blueprint?

Yes. Disable the specific agent identity when only one instance is affected.
Disable or revoke the blueprint credential when the entire family is at risk.

### Where should I start?

Start with:

1. Confirm that the workload is an AI agent.
2. Choose the blueprint credential boundary.
3. Assign a sponsor and owner.
4. Select S2S, OBO, or Agentic-User operation.
5. Define least-privilege permissions.
6. Register with supported Agent 365 tooling.
7. Validate identity, tokens, inventory, and telemetry.

## 19. Authoritative references

- [Microsoft Entra Agent ID key concepts](https://learn.microsoft.com/en-us/entra/agent-id/key-concepts)
- [Microsoft Entra Agent ID FAQ](https://learn.microsoft.com/en-us/entra/agent-id/faq)
- [Agent 365 identity](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/identity)
- [Setup an Agent 365 blueprint](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/registration)
- [Create an Agent 365 instance](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/create-instance)
- [Choose an Agent 365 integration option](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/choose-integration-option)
- [Microsoft Entra ID Auth SDK for Agent ID](https://learn.microsoft.com/en-us/entra/msidweb/agent-id-sdk/overview)
- [Microsoft Agent 365 SDK validation checklist](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/validation-checklist)

Documentation reviewed: October 5, 2026.

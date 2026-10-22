# Agent 365 Provisioning Runbook

## Purpose

This runbook covers approved identity and registration operations. Start with
the [onboarding guide](./onboarding_agents.md) to select the Microsoft
integration path, validate prerequisites, and choose single-agent versus
bulk execution. The Trading Platform Agent remains the concrete self-hosted
reference; onboarding must not move its runtime from its current Docker host.

It provisions identity and registry artifacts only. It must not create or
migrate application hosting unless that change is separately approved.

Use the [DevOps and GitOps guide](./devops.md) for source-of-truth,
plan/apply, approval, promotion, evidence, drift, and tool-selection policy.

## Selected approach

Use Microsoft's documented path for the selected scenario:

1. Check built-in integration and registry sync before custom registration.
2. For a custom agent, validate one nonproduction integration using the
   [existing-agent quickstart](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/get-started)
   or [single-agent CLI workflow](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/agent-365-onboarding-cli).
3. For reviewed batches, use the
   [official bulk PowerShell workflow](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/bulk-agent-365-onboarding).
   Its full CSV, runner authentication, WhatIf limits, and recovery procedure
   are covered in the [onboarding guide](./onboarding_agents.md).
4. Use typed Graph APIs only for a documented gap or approved enterprise
   executor. The Markets prototype is not a complete registration workflow.
5. Review the actual dry-run, permissions, consent, and output artifacts
   before approval.

The current config-free `a365 setup all --agent-name ... --aiteammate false`
walkthrough assumes external hosting and creates no Azure hosting resources.
Config-file deployment can create hosting. Inspect installed-version help,
configuration mode, authentication, and the plan rather than assuming all
`setup all` invocations have the same effects.

## Required roles and prerequisites

- Agent 365 enabled in the tenant.
- For the interactive CLI walkthrough, at least Agent ID Developer for
  creation and a Global Administrator consent handoff. Its S2S variant
  additionally requires Application Administrator or Global Administrator.
- For unattended bulk provisioning, an approved runner with the required
  Graph application roles and separate administrator consent. Interactive
  operator roles do not replace application-role grants.
- Azure CLI authenticated to the intended tenant.
- PowerShell 7 or a supported shell.
- .NET 8 or later for the Agent 365 CLI.
- Approved blueprint and agent identity sponsors.
- At least one user actually assigned Microsoft 365 E7 or Agent 365 for
  observability, per the current quickstart; an available unassigned SKU is
  insufficient. Verify current licensing before execution.

Install the approved CLI version, or perform a separately approved update:

```powershell
dotnet tool install --global Microsoft.Agents.A365.DevTools.Cli
dotnet tool update --global Microsoft.Agents.A365.DevTools.Cli
a365 setup requirements
```

Record the CLI version and tenant before provisioning.

## Naming

| Object | Recommended name |
|---|---|
| Blueprint | `trading-platform-agent` |
| BlueprintPrincipal | Created for the blueprint |
| Current local instance | `trading-platform-agent-local-dev` (existing legacy display name) |
| Future local standard | `trading-platform-agent-local` |
| Development instance | `trading-platform-agent-dev` |
| Test instance | `trading-platform-agent-tst` |
| Production instance | `trading-platform-agent-prd` |
| Sponsor | Approved accountable user or group |

Every runtime is hosted on premises. Do not reuse the current local identity
for `dev`; create a separate identity as the application is promoted through
`local` -> `dev` -> `tst` -> `prd`.

## Preflight

- [ ] Confirm the signed-in tenant ID.
- [ ] Confirm the sponsor object ID.
- [ ] Confirm whether `local`, `dev`, `tst`, and `prd` share a blueprint.
- [ ] Confirm metadata-only telemetry.
- [ ] Confirm no Microsoft 365 Work IQ permissions are requested.
- [ ] Confirm no agent user account is requested.
- [ ] Back up generated Agent 365 configuration.
- [ ] Confirm generated configuration and secrets are git-ignored.

## Supported workflow path

From the application directory, invoke the supported existing-agent onboarding
workflow with the outcome:

```text
Register this existing Python Microsoft Agent Framework agent with Agent 365.
Do not create or migrate application hosting. Register an Agent ID blueprint
and one local development agent identity, assign the approved sponsor, and
return all generated object IDs for verification.
```

Before approving changes, inspect the proposed resources. Stop if the workflow
would create unapproved hosting, networking, or public endpoints.

## Microsoft Graph fallback

For a one-agent pilot, prefer the supported workflow above. An approved
enterprise adapter may also use Graph for demonstrated lifecycle or policy
gaps; this is not a recommendation to replace the official batch workflow.
The following steps provision directory identity objects, not a complete
Agent 365 registration or runtime integration.

Required Graph permissions depend on the provisioning identity and operation.
Typical permissions include:

- `AgentIdentityBlueprint.Create`
- `AgentIdentityBlueprint.ReadWrite.All`
- `AgentIdentityBlueprintPrincipal.Create`
- `AgentIdentity.Create.All`
- `AgentIdentity.ReadWrite.All`
- `Application.ReadWrite.All`

Use explicit Graph authentication. Do not assume an Azure CLI token is accepted
by Agent ID APIs.

Provision in this order:

1. Create the blueprint:

   ```http
   POST /v1.0/applications/microsoft.graph.agentIdentityBlueprint
   ```

2. Create or verify its BlueprintPrincipal:

   ```http
   POST /v1.0/servicePrincipals/microsoft.graph.agentIdentityBlueprintPrincipal
   ```

3. Configure required protocol properties and `managerApplications`.
4. Add the approved credential to the blueprint, never to the agent identity.
5. Create the agent identity:

   ```http
   POST /v1.0/servicePrincipals/microsoft.graph.agentIdentity
   ```

6. Assign the sponsor.
7. Apply only approved permissions.
8. Create and verify the Agent 365 registration through the supported
   registration workflow or an explicit `AgentRegistration` bulk row. The
   identity endpoints below do not create an inventory record.

The endpoint above matches Microsoft guidance reviewed on October 16, 2026;
verify the currently supported API version and request shape immediately
before execution. The typed API references expose v1.0 creation endpoints for
all three objects. One higher-level Agent Identity guide still contains an
older beta example. All requests that use `@odata.type` should include
`OData-Version: 4.0`. Use idempotent lookups and bounded exponential backoff
because directory propagation can delay dependent operations.

## Required artifact record

Store non-secret identifiers in an approved local generated configuration:

| Artifact | Required |
|---|---|
| Tenant ID | Yes |
| Blueprint display name | Yes |
| Blueprint application/client ID | Yes |
| Blueprint object ID | Yes |
| BlueprintPrincipal object ID | Yes |
| Agent identity client ID | Yes |
| Agent identity object ID | Yes |
| Agent 365 registration ID | Yes, separate from the directory identity |
| Sponsor object ID | Yes |
| `managerApplications` values | Yes |
| Credential type and expiry | Yes, not the credential value |
| Provisioning operator and timestamp | Yes |

Never record a secret value, token, certificate private key, or federated token.

## Verification

- [ ] Blueprint exists in Microsoft Entra.
- [ ] BlueprintPrincipal exists.
- [ ] `managerApplications` is populated.
- [ ] Agent identity references the expected blueprint.
- [ ] Sponsor is assigned.
- [ ] No credentials exist on the agent identity.
- [ ] Blueprint credential is approved and time-bounded.
- [ ] Inherited permissions are minimal.
- [ ] Instance-specific permissions are assigned directly.
- [ ] Agent appears in Microsoft 365 admin center inventory.
- [ ] Generated IDs match local configuration.

Useful CLI diagnostics:

```powershell
a365 --version
a365 setup requirements
Get-Content a365.generated.config.json | ConvertFrom-Json
```

## Consent

Declaring a permission does not grant it. Record:

- Resource application ID.
- Permission ID and name.
- Application or delegated type.
- Business justification.
- Consenting administrator.
- Consent timestamp.
- Review/expiry date.

Do not grant Work IQ, notification, mail, Teams, SharePoint, or Graph
permissions during the initial telemetry-only onboarding.

## Cleanup

Before cleanup, preserve required audit evidence and inventory all child
identities.

Recommended order:

1. Stop the runtime.
2. Disable the affected agent identity.
3. Remove direct permission assignments.
4. Delete the agent identity.
5. Remove blueprint credentials.
6. Delete the BlueprintPrincipal and blueprint only after all instances are
   removed.
7. Delete orphaned agent user accounts separately, if any.

If CLI-managed resources were created, review before running:

```powershell
a365 cleanup --agent-name trading-platform-agent
```

Do not use cleanup until its target resources are confirmed.

## References

- [Agent 365 CLI](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-cli)
- [Setup agent blueprint](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/registration)
- [Create agent instance](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/create-instance)
- [Agent 365 identity](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/identity)
- [Microsoft Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/key-concepts)

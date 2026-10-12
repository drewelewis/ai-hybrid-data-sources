# Agent 365 Provisioning Runbook

## Purpose

This runbook registers the existing Trading Platform Agent with Microsoft
Agent 365 without moving the runtime from its current Docker host.

It provisions identity and registry artifacts only. It must not create or
migrate application hosting unless that change is separately approved.

## Selected approach

Use this order:

1. Use the supported Agent 365 existing-agent registration skill/workflow.
2. Confirm that the workflow can register the agent without creating an unused
   App Service Plan or Web App.
3. If registration-only behavior is unavailable, use the typed Microsoft Graph
   Agent ID APIs.
4. Do not run `a365 setup all` until its planned Azure resources and cost have
   been reviewed.

## Required roles and prerequisites

- Agent 365 enabled in the tenant.
- Global Administrator or Agent ID Developer for registration.
- Global Administrator available for consent.
- Azure CLI authenticated to the intended tenant.
- PowerShell 7 or a supported shell.
- .NET 8 SDK for the Agent 365 CLI.
- Approved blueprint and agent identity sponsors.
- At least one Microsoft 365 E7 or Agent 365 license for observability.

Install or update the CLI:

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
| Local/dev instance | `trading-platform-agent-local-dev` |
| Production instance | `trading-platform-agent-prod` |
| Sponsor | Approved accountable user or group |

## Preflight

- [ ] Confirm the signed-in tenant ID.
- [ ] Confirm the sponsor object ID.
- [ ] Confirm whether dev and production share a blueprint.
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

Use Graph only when the supported registration workflow cannot perform
registration-only onboarding.

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

All requests should include `OData-Version: 4.0`. Use idempotent lookups and
bounded exponential backoff because directory propagation can delay dependent
operations.

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

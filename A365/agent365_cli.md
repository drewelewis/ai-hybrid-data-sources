# Agent 365 CLI Guide

## Purpose

This guide covers installation, first use, day-to-day operation, advanced
commands, automation, security, troubleshooting, and cleanup for the Microsoft
Agent 365 CLI (`a365`).

It combines the current Microsoft command reference with lessons from
onboarding the existing Trading Platform Agent. Command behavior can change
between preview releases, so treat the help installed with your CLI as the
authoritative syntax:

```powershell
a365 --version
a365 --help
a365 <command> --help
```

This document was reviewed against Microsoft Learn on October 12, 2026. The
Trading Platform Agent was validated with Agent 365 CLI `1.1.226`; that is a
compatibility record, not a recommendation to remain on an old version.

## What the CLI does

The Agent 365 CLI is a cross-platform .NET global tool for developing,
registering, publishing, querying, and cleaning up Agent 365 resources. Its
major command families are:

| Command family | Purpose |
|---|---|
| `setup` | Validate prerequisites, create blueprints, and configure permissions |
| `query-entra` | Inspect blueprint and instance permissions and inheritance |
| `publish` | Update a Microsoft 365 manifest and create `manifest.zip` |
| `develop` | Discover, configure, authorize, and test MCP tool servers |
| `develop-mcp` | Manage MCP servers in Dataverse environments |
| `logs` | Export redacted CLI diagnostic logs |
| `cleanup` | Remove blueprint, instance, or CLI-created Azure resources |

The CLI can create or modify Microsoft Entra, Agent 365, Microsoft 365, and
Azure objects. Running it is an administrative operation, not just a local
build step.

## Safety rules

Before running a state-changing command:

1. Confirm the signed-in tenant and Azure subscription.
2. Read the command-specific help for the installed version.
3. Identify every object, permission, endpoint, and Azure resource the command
   can create or delete.
4. Use `--dry-run` when the command supports it.
5. Obtain approval for tenant, identity, permission, consent, license,
   production, or Azure changes.
6. Record the intended action and rollback in `../a365-changes.md`.
7. Preserve non-secret output needed for verification.
8. Validate the actual result instead of assuming a zero exit code proves
   end-to-end success.

Never run these blindly:

```powershell
a365 setup all
a365 cleanup
a365 cleanup --yes
```

`setup all` can create Azure resources and grant or request permissions.
Unqualified `cleanup` removes all CLI-managed blueprint, instance, and Azure
resources represented by the active configuration.

## Prerequisites

### Workstation

- Windows, macOS, Linux, or WSL.
- .NET SDK 8.0 or later.
- Internet access to NuGet, Microsoft Entra, Microsoft Graph, Agent 365
  services, and any required Azure endpoints.
- PowerShell 7 or another supported shell.
- Azure CLI authenticated when config-free setup must resolve an Azure tenant
  or subscription.

Check the local tools:

```powershell
dotnet --info
az version
az account show
```

Inspect `az account show` carefully. A valid Azure login can still point to the
wrong tenant or subscription.

### Tenant and service prerequisites

Requirements vary by capability, but normally include:

- Agent 365 enabled for the target tenant.
- Appropriate Agent 365 or Microsoft 365 licensing.
- An approved blueprint and agent sponsor.
- Access to the Microsoft Entra and Agent 365 administration surfaces needed
  for verification.
- An Azure subscription only when the selected workflow creates or manages
  Azure hosting resources.

Registration-only onboarding for an already-hosted agent should not create
Azure hosting merely because a general setup workflow supports it.

### Roles

Always check the current command reference because role requirements differ by
command. Common roles include:

| Operation | Typical minimum role |
|---|---|
| Read blueprint or instance permissions | Directory Reader |
| Create an Agent Identity Blueprint | Agent ID Developer |
| Configure S2S agent identity grants | Agent ID Administrator or higher |
| Grant tenant-wide OAuth2 consent | Global Administrator |
| Create or remove CLI-managed Azure resources | Azure Contributor |
| Export local redacted logs | No tenant role |

An Agent ID Developer can complete many setup steps, but a Global
Administrator must separately grant OAuth2 admin consent. The CLI prints a
consent URL or next steps when the signed-in developer cannot complete that
phase.

## Install, update, and remove the CLI

### Install

Install the CLI as a per-user .NET global tool:

```powershell
dotnet tool install --global Microsoft.Agents.A365.DevTools.Cli
```

Verify the executable and capture its version:

```powershell
a365 --version
a365 --help
```

Default executable locations are:

| Platform | Path |
|---|---|
| Windows | `%USERPROFILE%\.dotnet\tools` |
| macOS and Linux | `$HOME/.dotnet/tools` |

If `a365` is not found after installation, start a new terminal and verify that
the global-tools directory is on `PATH`.

### Install .NET per user on Windows

Machine-wide installation is not required. If elevation is unavailable, a
per-user .NET SDK can be installed and exposed through user environment
variables. In this repository's validated workstation setup:

- `DOTNET_ROOT` pointed to `%LOCALAPPDATA%\Microsoft\dotnet`.
- `%LOCALAPPDATA%\Microsoft\dotnet` and
  `%USERPROFILE%\.dotnet\tools` were added to the user `PATH`.

After changing user environment variables, open a new terminal:

```powershell
dotnet --info
a365 --version
```

### Update

Update before troubleshooting authentication or missing-scope behavior:

```powershell
dotnet tool update --global Microsoft.Agents.A365.DevTools.Cli
a365 --version
```

Review release behavior and rerun focused validation after updating. Preview
CLI changes can affect authentication, generated configuration, permission
requests, and cleanup behavior.

### Uninstall

Uninstalling the local tool does not delete tenant or Azure resources:

```powershell
dotnet tool uninstall --global Microsoft.Agents.A365.DevTools.Cli
```

Tenant and Azure cleanup must be performed and verified separately before
uninstalling if those objects are no longer required.

## Authentication model

### Microsoft-managed CLI application

The default setup flow uses the Microsoft-managed enterprise application when
it is available in the tenant:

| Property | Value |
|---|---|
| Display name | `Agent 365 CLI` |
| Application ID | `f54280f4-395e-4ea8-9e48-bf2d4952aa14` |

Verify it in Microsoft Entra under **Enterprise applications** by application
ID. The tenant-specific service principal Object ID is not interchangeable
with the application/client ID.

The Microsoft-managed application does not elevate the signed-in operator,
bypass Conditional Access, or remove admin-consent requirements.

### Interactive authentication

| Environment | Default method |
|---|---|
| Native Windows | Web Account Manager (WAM) |
| WSL, macOS, Linux | Device code |
| Tenant-owned application without WAM | System browser |

If device code is blocked by Security Defaults or Conditional Access, do not
weaken the policy. Prefer native Windows with WAM or an approved tenant-owned
client and supported browser authentication.

### Tenant-owned CLI application

If the Microsoft-managed application is unavailable, config-free setup looks
for a tenant-owned application named `Agent 365 CLI`. If neither exists, the
CLI can prompt for a client ID or offer an administrator-driven creation path.

Use a tenant-owned client only with explicit approval. Record:

- Application and service principal IDs.
- Redirect URIs and authentication mode.
- Delegated permissions requested.
- Administrator consent.
- Owners and review date.
- Any optional claims required by the CLI.

The `wids` optional claim is important for role detection. Current
`a365 setup requirements` can detect a missing claim and provide repair
instructions. After changing claims, sign out and authenticate again so the
new token includes them.

## First-use workflow

### 1. Confirm context

```powershell
a365 --version
az account show
```

Record the CLI version, tenant ID, subscription ID when applicable, signed-in
operator, and intended agent name.

### 2. Inspect help

```powershell
a365 setup --help
a365 setup requirements --help
a365 setup blueprint --help
a365 cleanup --help
```

This prevents a guide written for another preview version from being treated
as exact local syntax.

### 3. Run requirements checks

```powershell
a365 setup requirements
```

The command performs modular checks and continues through failures before
printing a summary. It may install or validate supporting PowerShell modules,
authenticate the operator, verify the client application, and inspect tenant
requirements.

Narrow checks during troubleshooting:

```powershell
a365 setup requirements --category authentication
a365 setup requirements --category azure
a365 setup requirements --category powershell
a365 setup requirements --category "tenant enrollment"
```

Available categories can vary. Confirm them with local help.

`setup requirements` can prompt to create or select a tenant-owned client
application. Stop at that prompt unless application creation and permissions
have already been approved.

### 4. Choose a setup mode

The CLI supports two configuration styles.

#### Config-free

Provide an agent name and let the CLI resolve context:

```powershell
a365 setup blueprint --agent-name "my-agent"
```

Use `--tenant-id` when tenant auto-detection is inappropriate:

```powershell
a365 setup blueprint `
  --agent-name "my-agent" `
  --tenant-id "00000000-0000-0000-0000-000000000000"
```

Config-free setup is convenient, but explicit context is safer in
multi-tenant administration.

#### Configuration file

Run from a directory containing `a365.config.json`:

```powershell
a365 setup blueprint
```

Use a configuration file for repeatable advanced settings such as custom
client applications, permissions, cloud endpoints, AI teammate configuration,
or Azure deployment details. Review the schema for the installed CLI version;
do not copy a secret-bearing generated file into source control as a template.

## Generated files

Setup writes `a365.generated.config.json` in the working directory. Depending
on the workflow and CLI version, it can include:

- Tenant and subscription context.
- Blueprint application and object IDs.
- BlueprintPrincipal or service principal IDs.
- Managed identity and Azure resource information.
- Agent instance and registration identifiers.
- Messaging endpoints.
- Permission and consent status.
- CLI version and completion timestamps.
- A protected or plaintext credential field.

Treat the entire generated file as sensitive even when most values are
non-secret.

Inspect it locally without printing it into shared logs:

```powershell
$config = Get-Content .\a365.generated.config.json -Raw | ConvertFrom-Json
$config |
  Select-Object agentBlueprintId, agentBlueprintObjectId, completed, cliVersion
```

Repository requirements:

- `a365.generated.config.json` must remain Git-ignored.
- It must be excluded from Docker build contexts.
- Do not paste it into issues, pull requests, chat, or support cases.
- Record non-secret IDs separately in an approved inventory.
- Store credentials in a secret manager or git-ignored local environment.
- Back it up securely before cleanup or workstation replacement if it is
  needed to manage created resources.

The `--show-secret` option on `setup blueprint` can display the stored
blueprint secret in plaintext. Avoid it unless credential recovery is
explicitly required and the terminal, screen capture, history, and output
handling are controlled.

## Setup commands in depth

### Recommended granular order

Use granular setup when you need to review each permission or avoid
unnecessary resources:

```powershell
# 0. Validate prerequisites
a365 setup requirements

# 1. Create the blueprint
a365 setup blueprint

# 2. Add MCP permissions only when required
a365 setup permissions mcp

# 3. Add messaging bot permissions only when required
a365 setup permissions bot

# 4. Add Copilot Studio permissions only when required
a365 setup permissions copilotstudio

# 5. Add explicitly approved custom permissions only when required
a365 setup permissions custom
```

Each later step depends on the blueprint. The bot permission phase also
depends on the MCP permission phase in the current reference workflow.

### `setup blueprint`

Create the Agent Identity Blueprint:

```powershell
a365 setup blueprint --agent-name "my-agent"
```

Important options:

| Option | Effect |
|---|---|
| `--tenant-id <id>` | Overrides tenant auto-detection |
| `--dry-run` | Shows planned work without executing it |
| `--skip-requirements` | Skips validation; use only with strong justification |
| `--no-endpoint` | Creates the blueprint without registering messaging |
| `--endpoint-only` | Registers messaging for an existing blueprint |
| `--messaging-endpoint <url>` | Supplies the HTTPS callback URL |
| `--update-endpoint <url>` | Replaces the current messaging endpoint |
| `--m365` | Uses the Microsoft 365 messaging registration path |
| `--show-secret` | Displays the stored blueprint secret |
| `--verbose` | Enables detailed diagnostics |

#### Existing self-hosted standard agent

For an agent that already has hosting and does not need Teams or Microsoft 365
messaging, use registration-only intent:

```powershell
a365 setup blueprint `
  --agent-name "my-existing-agent" `
  --no-endpoint `
  --dry-run
```

Review the dry run, then repeat without `--dry-run` only after approval.

This is the pattern used for the Trading Platform Agent. It avoided creating a
messaging endpoint and preserved the existing Docker, APIM, and PostgreSQL
runtime.

#### Messaging endpoint management

Register messaging after the HTTPS endpoint exists:

```powershell
a365 setup blueprint `
  --agent-name "my-agent" `
  --endpoint-only `
  --messaging-endpoint "https://example.contoso.com/api/messages"
```

Replace an existing endpoint:

```powershell
a365 setup blueprint `
  --agent-name "my-agent" `
  --update-endpoint "https://new.example.contoso.com/api/messages"
```

Endpoint registration is for Microsoft 365 messaging scenarios. It is not
required merely to obtain Agent Identity or S2S observability.

### `setup permissions`

Permission commands can declare inheritable permissions on the blueprint and
create OAuth2 grants. Declaration and consent are separate. Always capture:

- Resource application ID.
- Permission name and ID.
- Delegated scope or application role.
- Authentication mode.
- Business justification.
- Consenting administrator.
- Review and removal date.

#### MCP permissions

```powershell
a365 setup permissions mcp --dry-run
a365 setup permissions mcp
```

Current versions support per-server MCP permissions. The
`--remove-legacy-scopes` option removes older shared MCP scopes after
migration. Do not use it until every dependent runtime uses the compatible V2
SDK; older agents can lose tool access.

#### Bot permissions

```powershell
a365 setup permissions bot --dry-run
a365 setup permissions bot
```

Use only for agents that require Microsoft 365 messaging. Do not add these
permissions to a telemetry-only standard agent.

#### Copilot Studio permissions

```powershell
a365 setup permissions copilotstudio --dry-run
a365 setup permissions copilotstudio
```

Use only when the agent must invoke Copilot Studio through the Power Platform
API.

#### Custom permissions

Inline example:

```powershell
a365 setup permissions custom `
  --resource-app-id "00000003-0000-0000-c000-000000000000" `
  --scopes "User.Read" `
  --dry-run
```

After review, remove `--dry-run` to apply. Prefer configuration-file-driven
permissions for repeatable environments.

Custom permissions are not a shortcut around least privilege. Confirm whether
the agent needs delegated or app-only access and whether the selected runtime
can safely use it.

### `setup all`

Config-file mode:

```powershell
a365 setup all
```

Config-free mode:

```powershell
a365 setup all --agent-name "my-agent"
```

Optional modes include `--m365` for Microsoft 365 messaging and
`--aiteammate` for AI teammate setup. Check local help for the current option
set.

Use `setup all` only when its complete plan matches the desired architecture.
Depending on configuration, it can:

- Create an Azure resource group.
- Create an App Service Plan and Web App.
- Enable a managed identity.
- Create the blueprint and related Entra applications.
- Configure `managerApplications`.
- Configure inheritable and direct permissions.
- Request or grant OAuth2 consent.
- Write generated IDs, endpoints, and credentials.

Microsoft's current
[single-agent onboarding walkthrough](https://learn.microsoft.com/en-us/microsoft-agent-365/admin/agent-365-onboarding-cli)
explicitly distinguishes config-free standard-agent setup: with no project
configuration, it assumes external hosting, creates identity and registration
objects, and does not create Azure hosting or update the application.
Its example uses `--aiteammate false` and defaults to OBO; review permissions
and authentication before using it for another scenario.

The Trading Platform pilot used granular `setup blueprint --no-endpoint`.
That is a historical implementation choice, not proof that config-free
`setup all` creates hosting or should be avoided for every existing agent.
Use the [onboarding guide](./onboarding_agents.md) for the current supported
single-agent/bulk choice and separate runtime telemetry acceptance.

## Inspect Entra configuration

The `query-entra` family is read-only and requires Directory Reader for the
documented operations.

### Blueprint permissions

```powershell
a365 query-entra blueprint-scopes --agent-name "my-agent"
```

This lists delegated and application permissions declared or granted on the
blueprint service principal.

### Permission inheritance

```powershell
a365 query-entra inheritance --agent-name "my-agent"
```

The command checks `allAllowed` inheritance configuration and whether grants
actually exist:

| Result | Meaning |
|---|---|
| `Effective inheritance: OK` | Configuration and grants permit inheritance |
| `Effective inheritance: NONE` | Structure is valid but no grants exist |
| `Effective inheritance: BROKEN` | Inheritable-permission structure is invalid |

The command exits with code `1` when any checked resource is not `OK`, which
makes it useful as a CI or release gate.

### Instance permissions

```powershell
a365 query-entra instance-scopes --agent-name "my-agent"
```

Reading tenant-wide OAuth2 grants can require the admin-only
`DelegatedPermissionGrant.Read.All` scope. Without it, the CLI should direct
the operator to Entra rather than incorrectly reporting that consent is
missing.

## MCP development commands

Use `a365 develop --help` for the installed command surface. Current
subcommands include:

| Command | Purpose |
|---|---|
| `develop list-available` | List MCP servers available in the catalog |
| `develop list-configured` | Read configured servers from `ToolingManifest.json` |
| `develop add-mcp-servers` | Add catalog servers to the local configuration |
| `develop remove-mcp-servers` | Remove configured servers |
| `develop add-permissions` | Add MCP API permissions to development applications |
| `develop get-token` | Obtain a bearer token for MCP testing |
| `develop start-mock-tooling-server` | Run a local mock tool server |

Example discovery flow:

```powershell
a365 develop list-available
a365 develop list-configured
a365 develop add-mcp-servers --help
```

`develop get-token` emits security-sensitive authentication material. Never
store its output in source control, shell transcripts, CI logs, or support
bundles.

The separate `develop-mcp` family manages MCP servers in Dataverse
environments. It can list environments and servers, evaluate production
readiness, publish or unpublish servers, register external MCP servers, and
grant agents access. These are service-changing operations and require their
own approval and rollback plan.

## Publishing Microsoft 365 packages

`a365 publish` updates IDs in `manifest.json` and creates `manifest.zip`:

```powershell
a365 publish --dry-run
a365 publish
```

Useful options:

| Option | Purpose |
|---|---|
| `--agent-name <name>` | Uses config-free agent lookup |
| `--tenant-id <id>` | Overrides tenant auto-detection |
| `--dry-run` | Previews file changes without writing them |
| `--aiteammate` | Selects AI teammate behavior |
| `--use-blueprint` | Identifies a blueprint-based agent flow |
| `--verbose` | Enables detailed output |

Publishing a package and uploading it to Microsoft 365 are separate steps.
Follow the CLI's printed admin-center instructions and verify the resulting
agent inventory and package metadata.

The Trading Platform Agent does not use this path because it has no Teams or
Microsoft 365 application package.

## Diagnostic logs

Every top-level command writes a local diagnostic log. On Windows, logs are
typically under:

```text
%LOCALAPPDATA%\Microsoft.Agents.A365.DevTools.Cli\logs\
```

Export a redacted setup log:

```powershell
a365 logs export setup
```

Export all available logs:

```powershell
a365 logs export --output .\support-bundle
```

The exporter redacts common JWTs, email addresses, tenant-specific GUIDs, and
OS-path usernames while preserving useful trace, correlation, request, and
client-request IDs.

Redaction is not a guarantee that every custom secret format is removed.
Review exported files before sharing:

```powershell
Select-String `
  -Path .\support-bundle\*.log `
  -Pattern "CorrelationId|TraceId|request-id" |
  Select-Object -First 10

Select-String `
  -Path .\support-bundle\*.log `
  -Pattern "<id-|<email-|<JWT-TOKEN>|<username-" |
  Measure-Object
```

Never share original unredacted CLI logs.

## Cleanup and retirement

### Preview first

```powershell
a365 cleanup --agent-name "my-agent" --dry-run
```

Do not add `--yes` until the preview has been reviewed and deletion approved.

### Granular cleanup

Remove only CLI-created Azure hosting:

```powershell
a365 cleanup azure --agent-name "my-agent" --dry-run
```

Remove an agent instance identity and associated user:

```powershell
a365 cleanup instance --agent-name "my-agent" --dry-run
```

Remove the blueprint:

```powershell
a365 cleanup blueprint --agent-name "my-agent" --dry-run
```

Clear only messaging endpoint registration:

```powershell
a365 cleanup blueprint `
  --agent-name "my-agent" `
  --endpoint-only `
  --dry-run
```

After approval, repeat the exact command without `--dry-run`.

Blueprint cleanup can delete its service principal and linked instances, and a
Registry entry might also be removed. Preserve audit evidence and inventory
child identities before deletion.

### Full cleanup

```powershell
a365 cleanup --agent-name "my-agent" --dry-run
```

Full cleanup targets blueprint, instance, and Azure resources. Use it only
when all three categories are intended for retirement.

When `--agent-name` is supplied, the CLI cross-checks Entra and local generated
configuration. If they refer to different blueprints, it stops rather than
deleting the wrong objects. Resolve the mismatch; do not bypass it casually.

### Retirement order

1. Stop the runtime and preserve required telemetry.
2. Inventory agent instances, users, Registry records, permissions, sponsors,
   credentials, and Azure resources.
3. Disable the affected Agent Identity.
4. Remove direct permissions and credentials.
5. Delete instances.
6. Remove messaging endpoints and Azure hosting if applicable.
7. Delete the blueprint only after all dependent instances are gone.
8. Verify deletion independently in Entra, Agent Registry, Microsoft 365 admin
   center, and Azure.
9. Update the change ledger and retained inventory.

## Automation and CI/CD

Use the [DevOps and GitOps guide](./devops.md) to decide whether a task belongs
in Agent 365 CLI, the official bulk-onboarding workflow, or the controlled
Graph provisioning adapter.

The CLI is interactive by design for several authentication and consent
operations. Before placing it in automation:

- Confirm that the command supports the required noninteractive flow.
- Pin or deliberately update the CLI version.
- Run `--dry-run` in a review stage where supported.
- Use explicit tenant and agent names.
- Separate deployment identities from human admin-consent identities.
- Keep generated configuration and secrets out of build artifacts and logs.
- Capture exit codes and redacted diagnostics.
- Add independent postconditions using `query-entra`, Graph, Agent Registry,
  or Azure queries.
- Never use `--yes` for cleanup in an unreviewed pipeline.

PowerShell pattern:

```powershell
$ErrorActionPreference = "Stop"

a365 --version
a365 setup requirements --category authentication
if ($LASTEXITCODE -ne 0) {
    throw "Agent 365 authentication requirements failed."
}

a365 query-entra inheritance --agent-name "my-agent"
if ($LASTEXITCODE -ne 0) {
    throw "Agent permission inheritance is not ready."
}
```

Do not treat output text parsing as a stable API unless Microsoft documents an
output contract for that command.

For onboarding many agents, Microsoft provides separate bulk-onboarding
PowerShell scripts driven by CSV. They are an alternative workflow, not an
`a365` subcommand. Use them only after reviewing their automation application,
CSV schema, permissions, and rollback behavior.

## US Government clouds

The CLI defaults to the commercial cloud. Government environments require
explicit environment and endpoint configuration.

Supported environment names include:

- `gcc`
- `gcc-high`
- `dod`

The CLI can read cloud settings from `a365.config.json` or environment
variables:

| Variable | Purpose |
|---|---|
| `A365_ENVIRONMENT` | Selects the cloud environment |
| `A365_AUTHORITY_HOST_<ENV>` | Overrides the OAuth authority |
| `A365_GRAPH_BASE_URL_<ENV>` | Overrides Microsoft Graph |
| `A365_DISCOVER_ENDPOINT_<ENV>` | Agent 365 Tools discovery endpoint |
| `A365_CREATE_ENDPOINT_<ENV>` | Messaging registration endpoint |
| `A365_DELETE_ENDPOINT_<ENV>` | Messaging removal endpoint |
| `A365_MCP_APP_ID_<ENV>` | Agent 365 Tools resource application ID |

Selecting an environment name does not populate every endpoint automatically.
Use Microsoft's current government-cloud endpoint guide and validate the
effective tenant and service URLs before making changes.

## Troubleshooting

### `a365` command not found

```powershell
dotnet tool list --global
$env:PATH -split [IO.Path]::PathSeparator
```

Confirm `%USERPROFILE%\.dotnet\tools` on Windows or `$HOME/.dotnet/tools` on
macOS/Linux is present, then open a new terminal.

### Microsoft-managed application unavailable

1. Update the CLI.
2. Run `a365 setup requirements`.
3. Search Entra enterprise applications for application ID
   `f54280f4-395e-4ea8-9e48-bf2d4952aa14`.
4. If absent, use an explicitly approved tenant-owned CLI application.

### `AADSTS530035`

Device code is blocked by policy. Do not disable Security Defaults or
Conditional Access. Run on native Windows with WAM or use an approved
tenant-owned application and permitted browser flow.

### `AADSTS70007`

Older CLI authentication behavior might be incompatible:

```powershell
dotnet tool update --global Microsoft.Agents.A365.DevTools.Cli
a365 setup requirements
```

### Missing delegated scopes

Update the CLI and rerun requirements. Do not modify the Microsoft-managed
application's redirect URIs, optional claims, permissions, or tenant-local
grants. For a tenant-owned application, validate its documented configuration
and ensure a fresh token contains the expected scopes.

### Role appears missing

For a tenant-owned CLI client:

1. Check whether the access token carries the `wids` claim.
2. Run `a365 setup requirements`.
3. Apply only the repair recommended for the custom client.
4. Sign out and authenticate again.

### Blueprint creation partially succeeds

Directory and service propagation are eventually consistent. Inspect the
generated configuration and Entra before retrying. Do not repeatedly run setup
without determining which objects already exist.

### Agent absent from Registry or admin center

Blueprint creation, Agent Identity creation, sponsor assignment, Registry
registration, and portal indexing are distinct. Verify each object and
relationship independently. A generated file alone does not prove Registry
registration.

### Inheritance reports `NONE` or `BROKEN`

```powershell
a365 query-entra blueprint-scopes --agent-name "my-agent"
a365 query-entra inheritance --agent-name "my-agent"
```

`NONE` usually means the structure exists but the blueprint service principal
has no corresponding grants. `BROKEN` means the inheritance structure itself
needs reconciliation.

### Cleanup refuses an agent-name mismatch

The safety check found that Entra and local generated configuration refer to
different blueprints. Confirm the intended target. Use the correct agent name
or, only when appropriate, run cleanup from the directory containing the
matching generated configuration.

### Support escalation

1. Reproduce once with `--verbose` if it is safe.
2. Export redacted logs:

   ```powershell
   a365 logs export --output .\support-bundle
   ```

3. Review the exported files manually.
4. Record timestamps, CLI version, error code, trace ID, correlation ID,
   request ID, command family, and sanitized expected/actual behavior.
5. Do not attach generated configuration, tokens, client secrets, or original
   logs.

See [troubleshooting.md](./troubleshooting.md) for runtime identity and
observability failures beyond the CLI.

## Repository-specific Trading Platform Agent pattern

The Trading Platform Agent was already hosted in Docker and already used APIM
and PostgreSQL. Its onboarding therefore used the smallest CLI scope:

1. Install the CLI on the administrator workstation.
2. Run `a365 setup requirements`.
3. Approve the tenant-owned CLI client only because the Microsoft-managed
   application was unavailable.
4. Preview blueprint creation.
5. Run granular blueprint setup with `--no-endpoint`.
6. Create the environment-specific Agent Identity and sponsor relationship.
7. Complete Agent Registry registration.
8. Keep generated configuration and its protected credential out of Git and
   Docker.
9. Add S2S observability in the Python runtime separately.

It did not use:

- `a365 setup all`
- CLI-created App Service hosting
- Teams or Microsoft 365 messaging endpoints
- Work IQ
- Agent users
- Broad Microsoft 365 delegated permissions

For the complete repository workflow, use:

- [Existing-agent onboarding](./onboarding_agents.md)
- [Provisioning runbook](./provisioning_runbook.md)
- [Configuration reference](./configuration_reference.md)
- [Verification process](./verification_process.md)
- [Operations runbook](./operations_runbook.md)
- [Security and privacy](./security_and_privacy.md)

## Quick command reference

```powershell
# Local tool
a365 --version
a365 --help

# Prerequisites
a365 setup requirements
a365 setup requirements --category authentication

# Blueprint
a365 setup blueprint --agent-name "my-agent" --dry-run
a365 setup blueprint --agent-name "my-agent" --no-endpoint

# Permissions
a365 setup permissions mcp --dry-run
a365 setup permissions bot --dry-run
a365 setup permissions copilotstudio --dry-run
a365 setup permissions custom --help

# Entra inspection
a365 query-entra blueprint-scopes --agent-name "my-agent"
a365 query-entra inheritance --agent-name "my-agent"
a365 query-entra instance-scopes --agent-name "my-agent"

# Publishing
a365 publish --dry-run

# Diagnostics
a365 logs export setup
a365 logs export --output .\support-bundle

# Cleanup preview
a365 cleanup --agent-name "my-agent" --dry-run
a365 cleanup blueprint --agent-name "my-agent" --dry-run
a365 cleanup instance --agent-name "my-agent" --dry-run
a365 cleanup azure --agent-name "my-agent" --dry-run
```

## Official references

- [Install and use the Agent 365 CLI](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-cli)
- [Agent 365 CLI command reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/)
- [Setup command reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/setup)
- [Query Entra command reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/query-entra)
- [Develop command reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/develop)
- [Publish command reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/publish)
- [Logs command reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/logs)
- [Cleanup command reference](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/reference/cli/cleanup)
- [Custom CLI client registration](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/custom-client-app-registration)
- [Set up an Agent Identity Blueprint](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/registration)
# IT-to-Developer: Agent 365 CLI Onboarding

**One provisioning tool: Agent 365 CLI.** Use the Entra portal to select/
verify identities and Microsoft 365 admin center to verify registration.
There are no manual Graph requests or Graph PowerShell procedures here.
PowerShell code-block labels mean **Windows terminal syntax**, not another SDK.

**Scope:** existing on-premises/non-Azure agent, own UI/API, no Teams publishing.
**Verified version:** `1.1.226+9b233a7c52`, October 23, 2026.
Examples are help/source-validated, not live tenant tests.

## 1. Developer requests; IT selects the blueprint

**Developer submits Jira:** application/environment, owner/sponsor, required
controls, data classification, exact API permissions and delegated/app-only
access, credential custody and acceptance tests.

**IT opens Entra admin center > Entra ID > Agents > Agent blueprints.**
Search the few existing blueprints and choose:

| Decision | What IT records | Why |
|---|---|---|
| Reuse | Exact display name, application/client ID, application object ID, BlueprintPrincipal object ID | Same purpose, environment, acceptable inherited access and credential custody |
| Create | Approved new family name, owner/sponsor and access requirements | Existing families do not meet those boundaries |

Read permissions, linked children and credentials before approving reuse.
A shared blueprint credential is **not restricted to one child**.
Record the decision and approved changes in Jira. Developers do not provision.

**If no suitable blueprint exists:** IT approves **Create**, chooses a new,
unique name such as `portfolio-review-nonprod Blueprint`, and continues to
steps 2-4. Do not pre-create it in the portal. The approved Step 4
`a365 setup all` command creates the blueprint and its tenant principal,
then the child identity and registration. No existing blueprint IDs are needed.

## 2. IT prepares one protected request workspace

**Location:** IT's approved, access-controlled Windows workstation/storage,
not the agent's runtime host or source repository.

**Source control: do not put the live request workspace in Git, even a private
repository.** Do not initialize a repository here or place this folder inside
an existing checkout. It is provisioning state, not the agent's code project.

| Material | Source-control policy and reason |
|---|---|
| `a365.generated.config.json`, credentials and protected credential values | **Never commit.** Generated state can contain credentials; Windows protection does not make the file safe to publish or portable. Retain state in protected IT storage and runtime secrets in the approved secret store. |
| Raw logs, support bundles and the live `evidence\` / `handoff\` folders | **Do not commit the folders or exports.** They can contain sensitive identity, operator or operational details, even after automated redaction. Keep them in controlled IT storage; send reviewed material through the approved Jira/SharePoint channel. |
| Runbook, placeholder-only configuration template, approved permission definitions, reviewed non-secret desired-state copy | **May be versioned separately** in an IT-owned repository if policy permits. This supports review, approvals and repeatability without copying the live workspace. IDs are not secrets, but review tenant-specific metadata and exclude credentials and generated state. |

The working `a365.config.json` stays in this protected folder; a reviewed
non-secret copy is a separate source-control artifact, not a workspace backup.
Git history and clones retain committed content after a later deletion;
private repository access is not a substitute for secret storage.
Ignore rules are defense in depth, not permission to commit sensitive files,
and do not protect files already tracked. If a credential is committed, treat
it as exposed and have IAM revoke/rotate it under the incident process.

For a **new** Jira request:

```powershell
New-Item -ItemType Directory -Path "C:\A365-Requests\A365-1042"
Set-Location "C:\A365-Requests\A365-1042"
New-Item -ItemType Directory -Path ".\evidence", ".\handoff"
```

These are local folder operations, not tenant provisioning; they do not set
access permissions. IT ensures the approved parent folder's access controls.
Use a fresh directory with no parent CLI configuration or tooling manifest.
**On a retry:** enter the existing folder with `Set-Location`; do not recreate
or clear it.

**Expected layout after approved setup:**

```text
C:\A365-Requests\A365-1042\
|-- a365.config.json              IT creates in step 3; CLI input
|-- a365.generated.config.json    CLI writes during setup apply; sensitive state
|-- evidence\                    IT saves sanitized approvals/results here
`-- handoff\                     IT prepares the non-secret developer package here
```

The CLI does **not** automatically populate `evidence` or `handoff`, create an
agent-code folder, or copy this workspace onto the runtime host. Those two
subfolder names are this runbook's convention, not CLI requirements.
Before apply, the generated file normally does not exist; a failed apply
can leave partial state.

**Diagnostics are separate:** the Windows default CLI log directory is
`%LOCALAPPDATA%\Microsoft.Agents.A365.DevTools.Cli\logs\`, under the operator's
profile, not this request folder. Treat original logs as restricted.

| Command | Why run it | Outcome |
|---|---|---|
| `a365 --version` | Confirm the approved CLI | Prints version; creates nothing |
| `az login --tenant "<tenant-guid>"` | Establish the CLI's prerequisite operator context | Signs in locally; creates no identity objects |

Azure CLI is used only for login here and the **read-only client lookup**
in Step 3, not a second provisioning procedure.
The workstation needs the CLI's approved .NET/Azure CLI/PowerShell-module
prerequisites; operators do not run the underlying Graph modules themselves.
Do not bypass failed requirements or auto-approve extra clients/consent.

IT needs Agent ID creation/management authority. Secret creation requires
Agent ID Administrator or higher; the CLI's tenant-wide consent path expects
Global Administrator. Separate approval and consent roles as policy requires.

## 3. IT creates the CLI configuration from this template

**For a new request, IT creates this file from scratch.** It does not need
to exist beforehand and is not downloaded from the registry or exported
from a blueprint. Even an existing blueprint might have no CLI configuration
file; IT assembles this request's input from the template and approved settings.

1. **Get your `clientAppId`.** IT runs this read-only command after the
   Step 2 login to find the CLI's sign-in application in the approved tenant:

   ```powershell
   az ad sp list --filter "displayName eq 'Agent 365 CLI'" --query "[].appId" --output tsv
   ```

   **Expected output for the Microsoft-managed CLI client used here:**

   ```text
   f54280f4-395e-4ea8-9e48-bf2d4952aa14
   ```

   **Outcome:** prints application/client IDs; creates or changes nothing.
   Copy the expected ID into `clientAppId` below, **not** a service principal
   object ID, blueprint ID or child identity ID. If the command fails, prints
   nothing, or does not include the expected ID, stop and ask IAM to confirm
   the approved CLI client; do not create one or choose another by guesswork.
   If multiple IDs appear, use the expected Microsoft-managed ID only.
   A365 CLI has no standalone client-ID lookup command.

2. Copy the JSON below into a text editor.
3. Replace `<cli-client-app-id>` with the ID from item 1 and the tenant/name
   placeholders using the sources in the table.
4. Save as `C:\A365-Requests\A365-1042\a365.config.json`, not
   `a365.config.json.txt`. Run Step 4 from this same folder.

**Retrying an existing request:** keep its existing configuration and generated
state; do not recreate the workspace or overwrite it with the starter template.

| File | Who creates it and when | Purpose |
|---|---|---|
| `a365.config.json` | **IT**, now, using the template below | Input: tenant, blueprint/child names and approved settings |
| `a365.generated.config.json` | **CLI**, during the approved setup apply | Output: created/discovered IDs and protected credential state; do not author it for a new child |

```json
{
  "tenantId": "<tenant-guid>",
  "clientAppId": "<cli-client-app-id>",
  "agentBlueprintDisplayName": "portfolio-review-nonprod Blueprint",
  "agentIdentityDisplayName": "portfolio-review-nonprod-01 Identity",
  "agentDescription": "A365-1042: external portfolio review agent",
  "aiTeammate": false,
  "useBlueprint": true,
  "authMode": "s2s",
  "customBlueprintPermissions": []
}
```

| Parameter | Source and exact use |
|---|---|
| `tenantId` | Entra ID > Overview > Tenant ID; must match the approved login |
| `clientAppId` | Step 3, item 1: ID returned for the approved Microsoft Agent 365 CLI public client; **not** a service principal object ID or blueprint/child ID |
| `agentBlueprintDisplayName` | Create: approved new name from Jira. Reuse: exact existing name from step 1 |
| `agentIdentityDisplayName` | New runtime name approved in Jira; a same-name child under that blueprint is reused |
| `agentDescription` | Jira key and approved business purpose |
| `authMode` | `s2s` for this registered-agent telemetry baseline; business OBO access needs separate approval/configuration |
| `customBlueprintPermissions` | IT's approved family-wide custom delegated permission inventory; `[]` only when none are required |

**For a new blueprint:** use the first JSON template with the approved new
name. Do not add the existing-blueprint ID properties below; those IDs do
not exist yet. Step 4 discovers or creates the objects and saves their IDs.

**For reuse:** change the blueprint name, for example to
`trading-platform-agent Blueprint`, and add these properties to the **same**
JSON object using the IDs from step 1:

```json
{
  "agentBlueprintId": "<existing-blueprint-application-id>",
  "agentBlueprintObjectId": "<existing-blueprint-application-object-id>",
  "agentBlueprintServicePrincipalObjectId": "<existing-blueprint-principal-object-id>"
}
```

These IDs aid discovery; lookup is still **display-name-first**, not a strict
ID-only binding. Confirm name/IDs match in Entra before applying.
There is no `--existing-blueprint-id` flag.

**Do not copy another child's generated state.** Its `agenticAppId`/
`agentRegistrationId` would cause that child/registration to be reused.
The empty custom list above is valid only when no custom family permissions
are required. For an existing family, obtain its complete approved custom
list and `ToolingManifest.json` from IT's owner: omitted custom entries can
be removed by full setup.

## 4. IT previews, approves and applies

Run **without `--agent-name`** so the separate blueprint/child names in
the configuration are retained. The CLI reads the `a365.config.json`
that IT saved in step 3 from the current workspace.

**Preview:**

```powershell
a365 setup all --aiteammate false --authmode s2s --dry-run
```

**Why:** review names, credentials, permissions and registration before change.
**Outcome:** plan only; no identity creation. It is not a live authorization/
existence test and can describe creation based on cached state.

**Approval must cover these version-specific defaults:**

- New blueprints are **multitenant**; created secrets request **two-year**
  expiry, subject to tenant policy. A fresh reuse workspace also attempts to
  add a credential to the existing blueprint.
- Setup includes Graph delegated specs `Mail.ReadWrite`, `Mail.Send`,
  `Chat.ReadWrite`, `User.Read.All`, `Sites.Read.All`, `Files.ReadWrite.All`,
  `ChannelMessage.Read.All`, `ChannelMessage.Send`, and Power Platform
  `Connectivity.Connections.Read`. S2S does not convert them to Graph app roles.
- Setup can reconcile shared scopes/permissions and configure eligible
  inheritance as `allAllowed` for both scopes and roles. It can affect siblings.
  MCP/custom configuration adds further resources; missing resource service
  principals may be provisioned after prompts.

Do not consent to business permissions just for telemetry. Registered-agent
S2S export does not require `OtelWrite` by default. If defaults exceed policy,
**stop and request an IAM exception procedure**; do not invent suppression flags.

**Approved apply:**

```powershell
a365 setup all --aiteammate false --authmode s2s
```

| Object/artifact | New family | Existing family |
|---|---|---|
| Blueprint application + BlueprintPrincipal | Creates both | Reuses matching objects; may repair a missing principal |
| Blueprint credential/configuration | Creates secret, exposes `access_agent_as_user`, configures approved permissions/inheritance | May add credential and reconcile shared configuration |
| Child Agent Identity service principal | Creates the configured child | Creates child under selected blueprint; reuses it if already found |
| Registry registration | Creates registration linked to child/blueprint | Creates or verifies/reuses registration according to stored state |
| Local CLI state | Writes `a365.generated.config.json` | Writes this request's state; retain for retries |
| Not created | No agent user/mailbox, Teams package or application code; external hosting is not moved to Azure | Same |

**Where the created objects live:** blueprint applications, BlueprintPrincipals
and child identities are stored in **the tenant's Microsoft Entra directory**.
Registrations are stored in **Microsoft 365's agent registry**, visible under
**Agents > All Agents**. The local generated file records their IDs/state;
it is not the blueprint or registry itself.

Pending consent/action-required messages mean the work is **not complete**.
Setup is not transactional: preserve partial state and inspect actual objects
before retrying. Do not delete a shared blueprint to recover one request.

## 5. IT adds approved family-wide delegated permissions, if needed

Skip this step when no additional business access is approved.
Example: the existing Portfolio API exposes delegated scope `Portfolio.Read`.
Run in the same workspace:

```powershell
a365 setup permissions custom --resource-app-id "<Portfolio-API-application-id>" `
  --scopes "Portfolio.Read" --dry-run
```

After approval:

```powershell
a365 setup permissions custom --resource-app-id "<Portfolio-API-application-id>" `
  --scopes "Portfolio.Read"
```

**Why:** authorize approved family-wide API access.
**Parameters:** resource **application/client ID**, not its SP object ID;
`--scopes` accepts comma-separated delegated scope names.
**Outcome:** ensures resource SP, adds blueprint scope declaration, creates/
merges tenant-wide delegated consent on the BlueprintPrincipal, and configures
eligible `allAllowed` inheritance for scopes and roles. No new child is created.
Insufficient authority leaves consent pending.

Also merge the following field into the existing `a365.config.json`, preserving
other approved entries so a future full setup does not remove this access:

```json
{
  "customBlueprintPermissions": [
    {
      "resourceAppId": "<Portfolio-API-application-id>",
      "resourceName": "Portfolio API",
      "scopes": ["Portfolio.Read"]
    }
  ]
}
```

This is **not** a child-only grant or an application-role assignment command.
If those are required, return the ticket to IAM's specialist process; do not
broaden family permissions as a workaround. This guide intentionally does
not introduce another toolchain for that exception.

## 6. IT verifies and hands off

Run in the same workspace:

| Command | Why run it | Outcome |
|---|---|---|
| `a365 query-entra blueprint-scopes` | Inspect blueprint grants | Read-only permission report |
| `a365 query-entra instance-scopes` | Inspect the configured identity's delegated grants | Read-only report; confirm it identifies the child, not the blueprint fallback |
| `a365 query-entra inheritance` | Inspect configured inheritance/effective grants | Read-only diagnostic; no grants can produce a warning/nonzero exit |

This CLI version's instance query can confuse appId/object-ID lookup. If it
fails or targets the blueprint, verify the child by object ID in Entra;
**do not recreate the identity**.

**Entra:** match blueprint and child IDs, family linkage, enabled state,
owners/sponsors, credential expiry and approved access.
**Microsoft 365 admin center > Agents > All Agents:** verify the registration
matches this child. A blueprint alone is not a registry entry.

Relative folders below are inside `C:\A365-Requests\A365-1042`.

| Artifact | Where it lives after onboarding | Developer receives |
|---|---|---|
| Jira decision, approvals and capability/test contract | Jira; sanitized local copies in `evidence\` if retained | Approved scope and required tests |
| `a365.config.json` | IT's request folder; retained as the approved input | No automatic transfer; only approved settings |
| `a365.generated.config.json` | IT's request folder; protected state for retries/lifecycle management | **Never the file** |
| Tenant; blueprint application/object/principal IDs; child identity/object ID; registration ID | IT inventory; labeled non-secret copy prepared in `handoff\` | That reviewed copy through approved Jira/SharePoint delivery |
| Permission/consent results | Sanitized evidence in `evidence\`; approved access summary in `handoff\` | Approved resources, scopes/roles and user scope |
| Runtime credential | Approved secret store, expiry/rotation owner | Secure injection/access instructions, not a Jira secret |

**Optional support export**, run from the request folder:

```powershell
a365 logs export setup --output ".\evidence\support-bundle"
```

**Why/outcome:** writes redacted setup-log copies to
`C:\A365-Requests\A365-1042\evidence\support-bundle`; it does not move the
original logs or create tenant objects. Review redaction before sharing.

IT retains the input/generated state in controlled storage under its retention
policy; do not delete the workspace after handoff. Back it up securely in
approved IT storage, **not Git**, following Step 2's source-control policy.
Windows-protected credentials can require the original operator/machine;
copying the file alone is not a tested credential-recovery procedure.
Deleting local folders does **not** delete tenant identities or registrations.

The CLI's `agenticAppId` stores the returned child SP object ID despite its
name. Credentials belong to the **blueprint**, not the child. A protected CLI
secret is not a portable vault value; platform staff supply the approved
secret-store transfer/injection procedure.

**Only if registry registration failed**, after verifying child/state:

```powershell
a365 setup all --aiteammate false --agent-registration-only
```

**Why/outcome:** creates a missing registration or verifies/reuses the stored
one. It does not create a missing child or fix permissions.

**Only if IT wants a blueprint without a child/registration:**

```powershell
a365 setup blueprint --no-endpoint
```

Run using the approved configuration. This creates/reuses the blueprint and
principal and performs credential/Graph configuration; `--no-endpoint` does
not suppress permissions. It is **not needed in addition to normal full setup**.

## 7. Developer wires the issued identity; both teams validate

Developers do not rerun setup, consent or publishing. For Portfolio Manager,
inject these settings into the existing approved deployment:

```dotenv
ENABLE_A365_OBSERVABILITY=true
A365_TENANT_ID=<issued-tenant-id>
A365_BLUEPRINT_CLIENT_ID=<issued-blueprint-application-id>
A365_AGENT_ID=<issued-child-identity-id>
A365_RECORD_CONTENT=false
A365_CHANNEL_NAME=onprem-api
ENABLE_GRAPH_CALENDAR=false
ENABLE_GRAPH_CALENDAR_WRITE=false
```

Platform staff separately inject `A365_BLUEPRINT_CLIENT_SECRET`. The current
helper supports that pilot credential; certificate/federation needs additional
runtime implementation, not a variable rename.
These settings create **no directory objects**. A registry manifest is not
a substitute for these IDs, credential arrangement and SDK integration.

**Developer/runtime location:** application code remains in the developer's
existing repository and the on-premises deployment folder, **not** the IT
request folder. For this checkout, the reference application is
`C:\gitrepos\ai-hybrid-data-sources\lob\wealth\portfolio-manager`.
The deployment/platform owner supplies runtime settings and credential
injection there. CLI setup does not create application files or an `.env`;
never copy `a365.generated.config.json` into the application or image.

For a local approved reference run, from `lob\wealth\portfolio-manager`:

| Action/example | Why | Outcome |
|---|---|---|
| `.\.venv\Scripts\python.exe .\main.py` | Start through telemetry initialization | Starts API/exporter; no provisioning. Bare `uvicorn api.main:app` bypasses initialization |
| Open `http://127.0.0.1:8989/health` | Check local readiness | Health JSON, not proof of destination ingestion |
| `.\.venv\Scripts\python.exe .\chat.py` | Run one approved synthetic interaction | Agent/model/tool activity; may incur model usage; no identity creation |

Developer returns build/version, UTC test window, trace/conversation
correlation and access-test results to Jira. Missing access returns to IT,
not another setup attempt by the developer.

**Close only when:** identity/registry match; required licenses are assigned;
correlated telemetry arrives; approved access passes positive/negative tests;
required SOC/Purview controls are evidenced; rotation/support ownership is
accepted. No setup command automatically enables Defender detections or inline
DLP. The current reference does not implement inline DLP; a required DLP gate
stays open until separate implementation and block/allow tests pass.

## References, not additional onboarding steps

- [CLI command reference](./agent365_cli.md) and [Microsoft CLI onboarding][ms-cli].
- [Runtime/SDK wiring](./lob_app_wiring.md) and
  [spans/instrumentation](../lob/wealth/portfolio-manager/README.md#spans-and-automatic-instrumentation).
- [Control verification](./verification_process.md) and
  [specialist onboarding alternatives](./onboarding_agents.md).
- Installed-version sources: [blueprint/credentials][cli-blueprint],
  [setup permissions][cli-helpers], [identity/registration][cli-graph].

[ms-cli]: https://learn.microsoft.com/en-us/microsoft-agent-365/admin/agent-365-onboarding-cli
[cli-blueprint]: https://github.com/microsoft/Agent365-devTools/blob/9b233a7c5288a78fe7ef106c7578adbd408e914d/src/Microsoft.Agents.A365.DevTools.Cli/Commands/SetupSubcommands/BlueprintSubcommand.cs
[cli-helpers]: https://github.com/microsoft/Agent365-devTools/blob/9b233a7c5288a78fe7ef106c7578adbd408e914d/src/Microsoft.Agents.A365.DevTools.Cli/Commands/SetupSubcommands/SetupHelpers.cs
[cli-graph]: https://github.com/microsoft/Agent365-devTools/blob/9b233a7c5288a78fe7ef106c7578adbd408e914d/src/Microsoft.Agents.A365.DevTools.Cli/Services/GraphApiService.cs

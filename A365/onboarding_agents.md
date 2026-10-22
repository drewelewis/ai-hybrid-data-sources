# Agent 365 Onboarding: Microsoft Paths and Bank Acceptance

## Purpose

This is the onboarding entry point for agents governed by this repository.
It selects the Microsoft integration path, explains single-agent and batch
registration, separates runtime integration from provisioning, and defines
the evidence needed before production. The existing Python Trading Platform
Agent walkthrough is retained below as a reference implementation, not as
the only supported way to onboard an agent.

**Microsoft sources last checked: October 20, 2026.** Microsoft Learn owns
product behavior, supported authentication, prerequisites, and availability.
This repository records the bank's implementation and additional controls;
it does not supersede Microsoft documentation. Recheck the linked guidance
and the approved installed tool's help before execution. Record differences
and stop when the proposed changes do not match the approved design.

The Microsoft-supported starting point is **choose an integration mechanism,
validate one nonproduction agent, then use the official bulk workflow for
reviewed batches**. Protected DevOps execution is the bank's control around
these mechanisms. A custom Graph adapter is an exception for demonstrated
gaps, not a prerequisite for enterprise onboarding.

The [developer guide](./developers_guide.md) owns the canonical logical design,
layer responsibilities, implementation methodology, validation gates, and
Microsoft-guidance crosswalk. The detailed tenant commands and verification
steps remain in the
[provisioning runbook](./provisioning_runbook.md), and the telemetry contract
remains in the [observability reference](./observability_reference.md). The
concrete application bootstrap, authentication, request, span, and shutdown
path is documented in the
[LOB application wiring guide](./lob_app_wiring.md).

## 1. Select the Microsoft integration path

Start with Microsoft's [integration selector][ms-selection] and
[existing-agent overview][ms-existing]. Do not create a second identity or
instrumentation stack merely because an agent appears in this repository.

| Estate or requirement | First path to evaluate | Required verification |
|---|---|---|
| Integrated Microsoft platform, including supported Copilot Studio and Foundry scenarios | Built-in integration; no custom SDK merely for registration | Check the specific platform, hosting, registration, administrative enablement, and data-collection requirements; integration is scenario-dependent |
| Supported external managed platform | Connected platforms / registry sync | Verify the platform's supported agent types, source credentials, sync results, and available observability |
| Bank-built or self-hosted code agent needing code-level capabilities | Agent 365 SDK for required identity/tooling/notification capabilities; Microsoft OpenTelemetry for observability | Register the identity, integrate the runtime, and verify each destination |
| Existing platform integration that lacks a required code-level capability | Add only the missing supported integration | Document why native integration or registry sync is insufficient and avoid duplicate registration/export |

For [connected platforms][ms-platforms], current Microsoft limitations include
manual synchronization, platform-dependent observability, and no guaranteed
automatic reconciliation of source deletions. Set an operational sync cadence
and reconcile inventory; do not promise continuous discovery or uniform
security telemetry.

**Decision record:** document the chosen path, source platform, target tenant,
environment, accountable owner/sponsor, required capabilities, and why the
other paths are unnecessary. A connector inventory entry is not proof of
code-level authentication or complete security telemetry.

## 2. Complete preflight and approve the boundary

Use the [Microsoft quickstart][ms-quickstart] and the selected workflow's
prerequisites. The following are separate checks:

| Check | Evidence to retain |
|---|---|
| Tenant and feature availability | Tenant ID, approved environment, Agent 365 availability, required feature/preview enrollment |
| Licensing | Required licenses actually assigned, not merely purchased or present as available SKUs |
| Business accountability | Approved sponsor, runtime owner, support group, risk tier, legal entity, and region |
| Identity design | Blueprint sharing rationale, new versus existing identities, production boundary, required permissions |
| Provisioning authority | Interactive roles or runner application permissions, separate consent authority, approved credential method |
| Runtime and network | Healthy existing agent, supported stack/dependencies, allowed identity and telemetry egress, TLS/proxy behavior |
| Privacy and residency | Approved fields/content, destinations, retention, access roles, and cross-border review |
| Execution and recovery | Tool versions/commit, reviewed input, change approval, evidence location, partial-failure and containment owner |

Microsoft's quickstart distinguishes identity enablement from observability
licensing: identity requires an Agent 365-enabled tenant; observability
requires at least one user assigned Microsoft 365 E7 or Microsoft Agent 365.
It explicitly warns that missing assignment can silently drop telemetry even
when export returns HTTP 200. Verify current licensing with the tenant
administrator; Work IQ and optional agent-user capabilities have separate
requirements.

For a CLI pilot, Microsoft documents .NET 8+, Azure CLI, an Azure subscription,
subscription Contributor, at least Agent ID Developer for creation, and a
Global Administrator consent handoff. Changing that walkthrough to S2S has
additional Application Administrator or Global Administrator requirements.
Do not copy those interactive requirements to an app-only bulk runner:
unattended authorization depends on the runner's granted application roles.

Bank controls, additional to those walkthroughs:

- Use separate production and nonproduction credential boundaries by default.
  A blueprint is a shared credential and inherited-permission boundary, not
  simply an LOB label. See [LOB blueprints](./lob_blueprints.md).
- Separate build, provision, consent, runtime, and audit identities. Require
  independent production approval; application authors do not approve their
  own tenant grants.
- Review the permission set for the selected operations. Do not grant the
  bulk example's broad `-Scenario All` union merely for convenience.
- Keep runtime credentials and generated secret-bearing configuration outside
  Git, build contexts, logs, and ordinary pipeline artifacts.
- Obtain approval before executing tenant changes. The examples below are
  procedures, not authorization to run them.

## 3. Validate one agent using Microsoft's supported workflow

### Skills-assisted developer integration

The [existing-agent quickstart][ms-quickstart] documents Agent 365 Skills as
the guided developer path. Use the bank-approved Skills package/version and
review generated changes; automatic tool installation or update still needs
workstation approval.

| Microsoft workflow | Desired outcome | Acceptance |
|---|---|---|
| `a365-setup` | Detect stack, check prerequisites, select standard agent versus AI teammate and required authentication | Recorded target and reviewed capability choices |
| `make-a365-agent` | Register a standard agent | Blueprint, Agent Identity, required permissions, and Agent 365 registration verified |
| `instrument-observability` | Add Microsoft OpenTelemetry and export authentication | Valid invocation trace and destination evidence, not just package installation |
| Optional Work IQ, notifications, DLP | Add only separately approved business capabilities | Capability-specific licensing, permissions, enforcement tests, and support confirmed |
| Validation checklist | Confirm code, identity, telemetry, and selected capabilities | No unresolved required gate |

Standard agents do not require their own user account. An AI teammate with
mailbox or Teams presence is a different path with Frontier requirements.
Do not introduce that path just to obtain identity or telemetry.

### Direct CLI pilot

The [single-agent CLI walkthrough][ms-single] is the explicit operator
alternative. Use a separate approved working directory without an existing
`a365.config.json` when following its config-free example. Install the
approved CLI version using the [CLI guide](./agent365_cli.md), then check:

```powershell
a365 --version
az account show --query "{tenantId:tenantId, subscriptionId:id}" --output table
a365 setup requirements
a365 setup all --help
```

Resolve every required preflight failure. For a standard agent acting for a
signed-in employee, Microsoft's config-free **OBO** example is:

```powershell
a365 setup all `
  --agent-name "Bank Expense Review" `
  --tenant-id "<approved-tenant-id>" `
  --aiteammate false `
  --dry-run
```

Review the tenant, object names, authentication, permissions, consent, and
output location. Only after approval, repeat the identical command without
`--dry-run`. Complete all outstanding consent actions and verify the
generated IDs against **Microsoft 365 admin center > Agents > All Agents**.
Protect `a365.generated.config.json`; do not paste its full contents into
logs or tickets.

**Do not apply this OBO example unchanged to a telemetry-only S2S agent.**
Select the required authentication through the supported setup workflow and
approved installed-version options. A human chatting with an application
does not automatically mean the exporter or every downstream call uses OBO.

Microsoft now explicitly states that this **config-free** workflow assumes
external hosting and does not create Azure hosting or update the agent
project. Config-file deployment workflows can create hosting. Therefore
`setup all` is not categorically prohibited for existing agents, but its mode
and actual plan must match the approved architecture. The pilot's older
`setup blueprint --no-endpoint` sequence remains a historical implementation,
not a replacement for today's documented complete registration workflow.

## 4. Onboard reviewed batches with official bulk PowerShell

After validating the single-agent pattern, follow Microsoft's
[bulk-onboarding procedure][ms-bulk]. These scripts are **separate from the
CLI**. Do not loop the single-agent CLI setup for the entire estate or use
the Microsoft-managed interactive CLI application as the bulk runner.

### Prepare tooling and runner

Use PowerShell 7+, Microsoft.Graph.Authentication 2.x, and a reviewed,
immutable revision of the official DevTools scripts. In an approved tooling
workspace, the source acquisition pattern is:

```powershell
git clone https://github.com/microsoft/Agent365-devTools.git
Set-Location .\Agent365-devTools
git checkout --detach "<approved-commit>"
Set-Location .\scripts\bulk-agent-registration
```

Keep the orchestrator and object-specific scripts together. Record the commit
and module version. Do not install modules or execute freshly downloaded
scripts before their review/approval.

Have the IAM team create or approve a tenant-owned automation application,
inspect the selected scenario's declared permissions, and separately grant
the required consent. App-only provisioning rights are not supplied by the
operator's directory role. Runner consent and consent for the agents being
created are different approvals.

| Bulk runner authentication | Current Microsoft support |
|---|---|
| Certificate | Recommended unattended production option; private key accessible only to the runner |
| System-assigned managed identity | Supported on an Azure-hosted runner with required Graph roles |
| Client secret | Testing or short-lived automation, not the bank production default |
| Interactive delegated | Operator-driven execution with required scopes and directory roles |
| Federated/OIDC credential or selected user-assigned managed identity | Not currently supported by the bulk runner |

This restriction is about the **bulk runner**, not every Agent ID runtime.
Do not assume the Markets OIDC adapter can invoke these scripts with its
existing authentication unchanged.

For an approved certificate already configured on the automation application:

```powershell
$authParameters = @{
    TenantId = '<approved-tenant-id>'
    ClientId = '<automation-application-client-id>'
    CertificateThumbprint = '<approved-certificate-thumbprint>'
}
```

Use exactly one supported certificate source. Follow Microsoft's certificate
store requirements; batches containing AgentUser rows have additional
certificate-location considerations. Do not put private keys or certificate
passwords into the CSV.

### Prepare the complete CSV

Start from `sample-bulk-onboarding.csv` at the approved script revision.
Keep **every published header**, remove unwanted sample rows, replace sample
values, and leave nonapplicable fields blank. A simplified four-column table
in this guide is not a runnable replacement for that CSV.

| ObjectType | Relationship and important requirement |
|---|---|
| `Blueprint` | Parent of identities; creation requires a sponsor |
| `AgentIdentity` | `ParentKey` references the blueprint row; creation requires a sponsor |
| `AgentRegistration` | `ParentKey` references the identity row; explicit registration required for inventory visibility |
| `AgentUser` | Optional independent child of the identity; only for approved user-account capabilities |

Use unique case-insensitive `Key` values within the file. `ExistingId` can
anchor an existing blueprint using its **application ID**, or an existing
Agent Identity using its **object ID**. Anchor rows are unchanged: their
`ParentKey` and object-setting fields must be blank. Registrations and agent
users do not support `ExistingId` anchors.

For unattended registration, select `Auth=Same` as documented. Keep agent
permission declaration and `GrantAdminConsent` choices explicit; do not
implicitly authorize all requested downstream permissions.

### Validate, approve, apply, and read back

With the reviewed CSV in the protected working directory:

```powershell
.\A365-BulkOnboarding.ps1 `
  -CsvPath .\approved-wave.csv `
  @authParameters `
  -WhatIf
```

`-WhatIf` validates the complete CSV and dependency plan without sending
onboarding rows to Graph. It **does not prove** that referenced tenant
objects resolve or that the runner has sufficient authorization. Add approved
read-only resolution/permission checks and a bounded nonproduction pilot;
do not label structural validation a complete enterprise plan.

Approve the exact CSV digest, script commit, target, authentication principal,
and expected objects. Then execute:

```powershell
.\A365-BulkOnboarding.ps1 `
  -CsvPath .\approved-wave.csv `
  @authParameters `
  -LogPath .\logs `
  -OutputJsonPath .\bulk-onboarding-result.json
```

Protect and retain the report/logs in the approved evidence store. Review
every row, its resulting ID, and outstanding consent. Read the objects back
and verify registrations in administration. Leave secret output disabled:
do not use `-IncludeBlueprintSecretsInOutput` in routine automation.

### Recover from partial success

This is not a transaction or a general desired-state reconciler:

1. Preserve the aggregate report, logs, correlation ID, and input digest.
2. Treat `Failed` and `SkippedDependency` as unsuccessful onboarding, even
   though independent trees may have succeeded.
3. Read actual tenant state before retrying. Parents can exist despite later
   failures; successful work is not automatically rolled back.
4. Prepare a reviewed retry input using supported blueprint/identity anchors.
   Inspect registration and agent-user state separately; their rows cannot
   use `ExistingId` anchors.
5. Never blindly replay the full CSV or delete a shared blueprint to make a
   run appear clean. Obtain separate approval for repair or cleanup.

Extend the [DevOps guide](./devops.md) around these supported primitives.
Use a custom Graph executor only for a documented unmet operation or control
and verify its supported endpoints, permissions, retry, and read-back behavior.
Shared blueprints alone do not justify custom code; bulk supports them.

## 5. Integrate runtime identity and telemetry separately

Registration does not instrument an application. Follow the
[Microsoft identity model][ms-identity],
[OpenTelemetry Distro][ms-otel], and
[observability authentication guidance][ms-auth].

| Authentication concern | Required decision |
|---|---|
| Provisioning | Who may create/read/change directory and registry objects? |
| Business operations | Does each tool call act as the agent (S2S), for a human (OBO), or as an optional agent user? |
| Telemetry export | Which registered agent and tenant authenticate the exporter, using which route/token resolver? |
| Human attribution | Which validated initiating human is recorded and correlated, independently of exporter authentication? |

For registered blueprint agents, Microsoft recommends an **S2S exporter with
an app-only token resolver**. The distro defaults to the delegated route;
explicitly select the S2S endpoint (Python:
`a365_use_s2s_endpoint=True`) and implement the supported agentic token
acquisition/refresh pattern. Registered-instance S2S export does not require
an Observability permission grant or Observability admin consent. This does
not remove provisioning consent or permissions for business operations.

Do not generalize that exemption to unregistered standard applications.
Microsoft documents separate permissions for those scenarios and for
delegated export. Match the registered agent client ID and tenant across
runtime identity, baggage, exporter URL, and token. Never substitute a
blueprint ID, unrelated service principal object ID, or APIM user token.

Runtime acceptance requires:

1. Initialize Microsoft OpenTelemetry before instrumented imports; do not add
   the deprecated Agent 365 Observability SDK or duplicate exporters.
2. Create one correctly formed root invocation scope per logical invocation.
   The SDK operation is `InvokeAgent`; Microsoft describes the root telemetry
   span as `invoke_agent`. Preserve parent-child correlation for supported
   model, tool, HTTP, and database spans.
3. Bind the registered identity using the framework's supported integration.
   The Python reference below sets `ChatAgent.id`; do not assume that exact
   API applies to every framework.
4. Validate human identity cryptographically for human-initiated requests.
   Record approved caller metadata at the root and correlate children;
   a child span's agent-user fields are not necessarily the human caller.
5. Test token refresh, exporter errors, queue bounds, shutdown flush, and
   missing-telemetry monitoring. Define the bank's business-action policy
   during monitoring loss; the pilot's fail-open export is not automatic
   approval for high-risk actions.
6. Approve content settings before the first export. Metadata can itself be
   personal data. Content-dependent detections may require approved content;
   metadata-only is not a promise of every Defender or Purview capability.

The distro supports simultaneous Agent 365, Azure Monitor, and OTLP export.
Validate each configured destination and supported signal type independently;
do not assume all logs, metrics, and traces are copied identically to all
backends or that an on-prem collector can proxy Agent 365 authentication.
Private model/APIM connectivity does not establish private SaaS telemetry
transport or prove residency compliance.

## 6. Production acceptance and handoff

Microsoft's [quickstart][ms-quickstart] separates registration,
instrumentation, and validation. The bank additionally requires a signed-off
evidence record; use the [verification process](./verification_process.md)
and [operations runbook](./operations_runbook.md).

| Gate | Required evidence; insufficient proxy |
|---|---|
| Identity | Correct blueprint/instance, sponsor, credential boundary, approved grants and read-back; a successful creation command alone is insufficient |
| Inventory | Registration exists and matches the expected identity; Entra identity existence is insufficient |
| Runtime | Existing model/tools still work, registered identity is bound, unauthorized callers rejected; package installation is insufficient |
| Export | Correct token/route, valid root and child traces, refresh/error tests; HTTP 200 alone is insufficient |
| Human attribution | Validated root caller and child correlation, explicit autonomous cases; an alert User entity alone is insufficient |
| Destinations | Time-bounded, agent-correlated arrival in every required Admin Center, Defender, Purview, and Azure Monitor surface |
| Security and compliance | Approved safe test cases and expected policy outcomes; a normal interaction need not create an alert, and ingestion does not prove enforcement |
| Privacy | Approved fields/content and access/retention/residency verified; absence of raw prompts in one sink is insufficient |
| Operations | Named owner, credential rotation, telemetry-loss alarms, incident containment, retirement, and rollback tested |

Count distinct logical invocations and correlate traces; distinguish raw
event rows, retries, spans, interactions, and alerts. Investigate mismatches
rather than assuming one row per turn. Record observation windows and
ingestion latency; missing required evidence leaves that gate incomplete.

If export is accepted but activity is missing, first check actual license
assignment, registration, identity/token alignment, and a valid root span.
Then inspect destination access, ingestion delay, and exporter errors.
Do not solve missing telemetry by granting unrelated Work IQ permissions or
turning on unrestricted content capture.

The current Markets workflow is a dormant **create-or-verify core identity
prototype**, not an end-to-end implementation of these gates. Registration,
credentials/consent, runtime binding, and telemetry acceptance are separate
work. See its [current implementation scope](../lob/markets/markets-risk-analyst/identities/README.md).
Likewise, the Trading Platform pilot proves its observed test results, not
blanket production readiness for every LOB.

Stopping telemetry is not stopping an agent. Production containment must
separately address agent identity, runtime execution, and downstream model/
data access, while preserving required evidence. Tenant cleanup needs separate
approval; see the [provisioning runbook](./provisioning_runbook.md).

## Reference implementation: selected architecture

The Trading Platform Agent uses the Agent 365 **standard existing-agent**
path:

```text
User
  |
  v
Trading Platform API and Microsoft Agent Framework
  |
  +--> Existing APIM-governed model route
  |
  +--> Existing PostgreSQL portfolio ledger
  |
  +--> Microsoft OpenTelemetry Distro
          |
          +--> Agent 365 S2S observability endpoint
                  |
                  +--> Agent Registry and Admin Center activity
                  +--> Microsoft security and compliance destinations
```

The Python application, Docker deployment, APIM authorization, tools, and
database remain in place. Agent 365 adds governed identity, registration, and
observability around that runtime.

This path does not require conversion to a hosted Foundry agent or a Microsoft
365 Agents Toolkit project. Agents Toolkit is needed only if a future
requirement introduces Microsoft 365 or Teams channel packaging, Bot Framework
messaging, Adaptive Cards, delegated SSO, or app-catalog distribution.

## Reference implementation: onboarding sequence

### 1. Validate the existing runtime

Before creating tenant objects:

1. Confirm the API, agent, database, and existing model route are healthy.
2. Record the target tenant, environment, runtime owner, and approved sponsor.
3. Confirm whether telemetry will record metadata only or full content.
4. Confirm generated configuration and local secrets are git-ignored.
5. Obtain approval before creating identities, granting consent, assigning
   sponsors, or changing tenant configuration.

Do not use Agent 365 onboarding to change a working hosting architecture.

### 2. Create the governed identity hierarchy

Provision tenant objects in this order:

1. An Agent Identity Blueprint for the agent family.
2. Its required BlueprintPrincipal.
3. A separate Agent Identity for each environment, such as local development
   and production.
4. An approved accountable human sponsor.
5. An Agent Registry record that associates the instance with its blueprint,
   identity, sponsor, and originating repository.

The Trading Platform Agent used `a365 setup blueprint --no-endpoint` so the
workflow created identity and registration artifacts without creating
application hosting or a messaging endpoint.

Keep permissions minimal. Initial observability onboarding does not require
Work IQ, mail, Teams, SharePoint, notification, or broad Microsoft 365 data
permissions. Review the exact permission set and consent separately for every
new agent.

### 3. Store configuration safely

Record non-secret object IDs in an approved generated configuration. Store the
blueprint credential only in the environment's secret store. For local
development, the Trading Platform Agent uses a git-ignored `.env`.

Never commit:

- Blueprint client secrets.
- Access or refresh tokens.
- Device codes.
- Certificate private keys.
- Database credentials.
- APIM subscription keys.

The generated `a365.generated.config.json` file is excluded from both Git and
the Docker build context.

### 4. Add app-only Agent 365 authentication

The runtime performs the Agent ID two-step service-to-service exchange:

1. The blueprint application authenticates with its protected credential and
   requests an intermediate token using the registered Agent Identity as
   `fmi_path`.
2. The Agent Identity exchanges that assertion for an app-only token scoped to
   the Agent 365 observability resource.

The runtime validates the final token's audience, app-only token type, subject,
and expiry. It caches the token in memory, refreshes it before expiration, and
never logs it.

This exchange is independent from the user token used to call the existing
APIM model route. Do not reuse an interactive APIM token as the Agent 365
exporter token.

### 5. Bind the agent runtime to the registered identity

When Agent 365 observability is enabled, the application assigns
`A365_AGENT_ID` to the Microsoft Agent Framework `ChatAgent.id`.

This binding is required. Allowing the framework to generate an unrelated
runtime ID can cause telemetry to be dropped or prevent Agent 365 from
attributing it to the Registry entry.

The implementation is in:

- `../lob/wealth/portfolio-manager/agents/trading_platform_agent.py`
- `../lob/wealth/portfolio-manager/observability/a365.py`

### 6. Initialize Microsoft OpenTelemetry

The application initializes the Microsoft OpenTelemetry Distro before Uvicorn
imports the instrumented API modules. The configuration:

- Enables the Agent 365 exporter and S2S endpoint.
- Supplies the in-memory Agent ID token resolver.
- Sets service name and version resource attributes.
- Configures bounded batching, queue size, delay, and export timeout.
- Disables unencrypted offline storage.
- Enables or suppresses sensitive content according to
  `A365_RECORD_CONTENT`.

The runtime currently pins `microsoft-opentelemetry==1.3.9` to preserve the
validated dependency set.

### 7. Create one root scope per agent invocation

Every `/chat` request is wrapped in a root `InvokeAgent` scope. Model, tool,
HTTP, and database spans are correlated beneath that root where supported by
instrumentation.

The root scope includes:

- Registered tenant, blueprint, and Agent Identity attribution.
- Agent and service names.
- A SHA-256 hash of the local conversation/session ID.
- Channel name and server endpoint.
- Status and sanitized error information.
- Optional prompt and response content.

The API starts background token refresh during startup, reports Agent 365
readiness through `/health`, records invocation errors, flushes telemetry on
shutdown, and does not fail the user request merely because export fails.

### 8. Add approved human user attribution

For device-code callers, the API cryptographically validates the Entra bearer
token's signature, issuer, audience, expiry, tenant, and object ID. It then
passes the actual validated Entra object ID through
`CallerDetails(UserDetails(user_id=...))`, with available UPN and display
name. The same fields populate request-scoped telemetry baggage.

This approved identity metadata is independent of content recording:
`InvokeAgent` `UserKey` must contain the human object ID and `UserId`
the available caller UPN. Tokens and device codes are never exported.
Session/conversation IDs remain hashed. Agent identity and its own optional
user account remain distinct from the initiating human.

### 9. Select and disclose the content policy

`A365_RECORD_CONTENT` controls whether prompts, responses, and supported tool
or inference content are captured.

The Trading Platform Agent defaults to metadata-only mode. Set
`A365_RECORD_CONTENT=true` only for an approved, time-bounded nonproduction
policy test. Full-content mode can transmit account identifiers, holdings,
trade data, SQL, prompts, responses, and tool data to Microsoft observability
services. Review tenant access, retention, residency, Defender, Purview, and
billing before enabling it, then return the setting to `false`.

## Runtime configuration

The integration uses these settings:

| Setting | Purpose |
|---|---|
| `ENABLE_A365_OBSERVABILITY` | Enables identity attribution and export |
| `A365_TENANT_ID` | Tenant containing the registered agent |
| `A365_BLUEPRINT_CLIENT_ID` | Blueprint application used for token exchange |
| `A365_BLUEPRINT_CLIENT_SECRET` | Protected blueprint credential |
| `A365_AGENT_ID` | Registered environment-specific Agent Identity |
| `A365_RECORD_CONTENT` | Enables or suppresses content capture |
| `A365_CHANNEL_NAME` | Stable invocation channel, currently `local-cli` |
| `A365_SERVER_ADDRESS` | API host represented in telemetry |
| `A365_SERVER_PORT` | API port represented in telemetry |

Observability is feature-gated. Disabling it must leave the agent's normal
model, tool, and database behavior unchanged.

## Validation performed for the Trading Platform Agent

The implementation was validated through:

- Focused configuration, token-exchange, privacy, endpoint, and telemetry
  tests.
- Python compilation and dependency checks.
- Healthy API, database, and agent startup after container rebuild.
- Verification that the runtime uses the registered Agent Identity.
- Successful authenticated chat requests.
- Agent Registry inventory visibility and Purview Activity Explorer ingestion.
- A live exporter response with HTTP 200, zero rejected spans, and successful
  sink statuses.
- Sanitized checks that secrets were not logged and only approved caller
  identity metadata was exported.

Agent 365 exporter acceptance and Defender visibility are separate checks. A
successful HTTP 200 export proves that Agent 365 accepted the batch; it does
not by itself prove that the data has been indexed in Defender
`CloudAppEvents`, Purview, or every customer-facing portal.

Follow the [verification process](./verification_process.md) for the complete
identity, runtime, Registry, Defender, and compliance validation sequence.

## Capabilities intentionally not added

The initial onboarding did not add:

- Agent 365-managed application hosting.
- Microsoft 365 Agents Toolkit scaffolding.
- Teams, Outlook, or Copilot channel packaging.
- Bot Framework messaging endpoints.
- Agent users or AI-teammate messaging.
- Work IQ access.
- Mail, SharePoint, Teams, or notification permissions.
- Purview DLP code integration.
- Broad delegated Microsoft Graph permissions.

Adopt any of these only as a separately designed, approved, licensed, and
validated capability.

## Reusing this pattern for another agent

For each additional agent:

1. Decide whether it shares an existing line-of-business blueprint or requires
   a new one.
2. Create a distinct Agent Identity per environment.
3. Assign an approved sponsor and create the Registry record.
4. Keep the blueprint credential in the environment's secret store.
5. Bind the runtime agent ID to the registered identity.
6. Add the two-step S2S token exchange and Microsoft OpenTelemetry
   initialization.
7. Wrap one root `InvokeAgent` scope around each user invocation.
8. Decide and document the content policy before enabling export.
9. Validate identity, privacy, exporter acceptance, Registry activity, and
   each required downstream destination independently.
10. Record every investigation and change in `../a365-changes.md`.

## Rollback

To stop runtime export without deleting tenant objects:

1. Set `ENABLE_A365_OBSERVABILITY=false`.
2. Restart the API.
3. Verify `/health` reports Agent 365 as disabled.
4. Confirm normal agent, APIM, tool, and database behavior still works.

Tenant cleanup is a separate governed operation. Disable the affected Agent
Identity before deleting it, remove direct permissions, preserve required
audit evidence, and delete the blueprint only after all of its instances have
been removed. Follow the cleanup procedure in the
[provisioning runbook](./provisioning_runbook.md).

## Microsoft source map

These are product references, not evidence that this repository has
implemented every capability. Revalidate current prerequisites and version
support before a rollout.

| Source | What this guide takes from it |
|---|---|
| [Choose an integration option][ms-selection] | Built-in first, registry sync where sufficient, SDK for required code-level integration |
| [Connect existing agents][ms-existing] | Existing-agent integration without replacing the framework |
| [Connected platforms][ms-platforms] | Platform coverage, manual sync, observability and deletion limitations |
| [Existing-agent quickstart][ms-quickstart] | Skills-assisted sequence, capability-specific licensing, registration versus instrumentation, root-span checks |
| [Single-agent CLI onboarding][ms-single] | Nonproduction pilot, roles, dry-run, OBO example, config-free external hosting, consent and inventory verification |
| [Bulk onboarding][ms-bulk] | Official scripts, runner authentication, full CSV schema, validation limits, reports, partial-run recovery |
| [Agent 365 identity][ms-identity] | Blueprint credential boundary, execution modes, optional agent user |
| [Microsoft OpenTelemetry Distro][ms-otel] | Supported instrumentation/export configuration and deprecated-SDK replacement |
| [Observability authentication][ms-auth] | Registered-instance app-only S2S route, token resolver, matching IDs, permission distinctions |

[ms-selection]: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/choose-integration-option
[ms-existing]: https://learn.microsoft.com/en-us/microsoft-agent-365/connect-existing-agents
[ms-platforms]: https://learn.microsoft.com/en-us/microsoft-agent-365/admin/connected-platforms
[ms-quickstart]: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/get-started
[ms-single]: https://learn.microsoft.com/en-us/microsoft-agent-365/admin/agent-365-onboarding-cli
[ms-bulk]: https://learn.microsoft.com/en-us/microsoft-agent-365/admin/bulk-agent-365-onboarding
[ms-identity]: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/identity
[ms-otel]: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry
[ms-auth]: https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability-authentication-setup
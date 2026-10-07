# Microsoft Agent 365 Change Ledger

This ledger records all Microsoft Agent 365, Microsoft Entra Agent ID, and
related onboarding changes for the Trading Platform Agent.

Do not record secrets, tokens, passwords, device codes, private keys,
connection strings, or sensitive portfolio content.

## 2026-10-06 18:40 EDT - Reviewed onboarding design

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Determine whether the working self-hosted Trading Platform Agent
  is ready for Microsoft Agent 365 onboarding.
- **Change:** Performed read-only review of the existing Agent 365 design and
  runbooks under `lob/ai-agent-starter-portfolio-manager/A365/`. No repository,
  tenant, Azure, or runtime state was changed.
- **Result:** Selected the existing-agent SDK integration path: preserve the
  Python, Docker, APIM, and PostgreSQL runtime; add Entra Agent ID identity and
  metadata-only Microsoft OpenTelemetry in later phases. Work IQ and broad
  Microsoft 365 permissions remain out of scope.
- **Validation:** Compared the design with current Microsoft documentation for
  connecting existing agents.
- **Rollback:** Not applicable.
- **Follow-up:** Capture the runtime baseline and validate local provisioning
  prerequisites.

## 2026-10-06 18:44 EDT - Captured agent and tenant baseline

- **Status:** Succeeded
- **Scope:** Workstation, Runtime, Tenant
- **Requested by:** User
- **Purpose:** Verify the existing agent before Agent 365 changes.
- **Change:** Performed read-only checks of the Azure CLI context, Docker
  services, and local API health endpoint.
- **Result:** Confirmed tenant
  `00648bab-6c91-4292-9a2a-2297df511222`; confirmed the API, PostgreSQL, and
  Adminer containers were running; confirmed the Trading Platform Agent health
  endpoint reported healthy, agent ready, and database connected.
- **Validation:** `docker compose ps` and `GET http://127.0.0.1:8989/health`.
- **Rollback:** Not applicable.
- **Follow-up:** Install the Agent 365 provisioning CLI prerequisites on the
  administrator workstation.

## 2026-10-06 19:12 EDT - Installed local Agent 365 provisioning tools

- **Status:** Partially succeeded
- **Scope:** Workstation
- **Requested by:** User
- **Purpose:** Prepare the administrator workstation to register the existing
  agent without adding .NET to the Python application or its container.
- **Change:** Attempted a machine-wide .NET 8 SDK installation through WinGet.
  The noninteractive installer stalled while launching its elevated engine and
  was stopped. Installed .NET SDK 8.0.425 per-user under
  `%LOCALAPPDATA%\Microsoft\dotnet`; installed Agent 365 CLI 1.1.226 as a .NET
  global tool under `%USERPROFILE%\.dotnet\tools`; set user `DOTNET_ROOT` to
  the per-user SDK and added the SDK and global-tools directories to the user
  `PATH`.
- **Result:** Per-user .NET and the Agent 365 CLI are operational. The failed
  machine-wide attempt left no .NET 8 SDK package registered with WinGet; a
  pre-existing machine-wide .NET host and runtimes remain. The Python
  application and container were not modified.
- **Validation:** `dotnet --info` reported SDK 8.0.425 and `a365 --version`
  reported `1.1.226+9b233a7c52`.
- **Rollback:** Remove the Agent 365 global tool, remove
  `%LOCALAPPDATA%\Microsoft\dotnet`, and remove the added user environment
  values after confirming no other user workload depends on them.
- **Follow-up:** Complete Agent 365 tenant requirements and identity
  registration.

## 2026-10-06 19:15 EDT - Ran Agent 365 requirements check

- **Status:** Partially succeeded
- **Scope:** Workstation, Tenant
- **Requested by:** User
- **Purpose:** Determine whether the tenant and workstation meet Agent 365 CLI
  requirements before creating identity objects.
- **Change:** Ran `a365 setup requirements`. The CLI installed the
  `Microsoft.Graph.Authentication` and `Microsoft.Graph.Applications`
  PowerShell modules. It authenticated the administrator through Windows
  Account Manager and inspected the target tenant.
- **Result:** PowerShell module requirements passed. Tenant enrollment in the
  Frontier Preview Program could not be verified automatically. The
  Microsoft-managed `Agent 365 CLI` enterprise application was not present.
  The CLI offered to use or create a tenant-owned client application; the
  prompt was cancelled. No client application, blueprint, BlueprintPrincipal,
  agent identity, sponsor assignment, permission consent, hosting resource, or
  runtime integration was created.
- **Validation:** The CLI reported one passed requirement, one warning, and
  zero failed requirements before the missing client-application prompt.
- **Rollback:** The two PowerShell modules may be removed if they are not used
  by other administrative workflows.
- **Follow-up:** Obtain explicit approval before creating a tenant-owned Agent
  365 CLI client application or select a separately approved Microsoft Graph
  provisioning path.

## 2026-10-06 19:23 EDT - Added mandatory A365 change tracking

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Require an auditable record before any further Agent 365 work.
- **Change:** Added the workspace skill
  `.github/skills/track-a365-changes/SKILL.md` and initialized this root change
  ledger with all Agent 365 discovery and workstation changes already
  performed.
- **Result:** Future A365 investigations, provisioning, configuration, code
  changes, validation, rollback, and cleanup must load the skill and update
  this ledger.
- **Validation:** Confirmed the skill folder name matches its frontmatter name,
  the discovery description includes Agent 365 and Agent ID triggers, and the
  ledger path is repository-root `/a365-changes.md`.
- **Rollback:** Delete the skill and ledger only with explicit user approval.
- **Follow-up:** Review and approve the next tenant change before execution.

## 2026-10-06 19:25 EDT - Recorded pre-existing end-user license assignment

- **Status:** Succeeded
- **Scope:** Repository, Tenant
- **Requested by:** User
- **Purpose:** Correct the ledger to include the Agent 365 license already
  assigned to an end user before tenant onboarding began.
- **Change:** Recorded the user-reported fact that an end user in tenant
  `00648bab-6c91-4292-9a2a-2297df511222` has an Agent 365 license assigned.
  This session did not purchase, install, assign, modify, or remove the
  license.
- **Result:** The license prerequisite is provisionally recorded as satisfied
  based on the user's report. The exact SKU, licensed user, assignment
  timestamp, service-plan state, and applicability to Agent 365 observability
  have not yet been independently verified.
- **Validation:** User attestation only; no Microsoft 365 licensing API or
  admin-center verification has been performed.
- **Rollback:** Not applicable because this session did not perform the license
  assignment. Any future license removal must be separately approved and
  recorded.
- **Follow-up:** Before observability validation, verify the assigned SKU and
  enabled service plans in the Microsoft 365 admin center or through an
  approved read-only licensing query.

## 2026-10-06 19:27 EDT - Provision Agent 365 identity and registry objects

- **Status:** Succeeded
- **Scope:** Tenant, Workstation
- **Requested by:** User
- **Purpose:** Establish the governed identity and Agent 365 registration
  required for metadata-only S2S telemetry from the existing self-hosted
  Trading Platform Agent.
- **Change:** After explicit approval, create or authorize the tenant-owned
  `Agent 365 CLI` provisioning client because the Microsoft-managed client is
  unavailable in this tenant. Use the granular `a365 setup blueprint` workflow
  with `--no-endpoint` to create the `trading-platform-agent` Agent Identity
  Blueprint, mandatory BlueprintPrincipal, and
  `trading-platform-agent-local-dev` agent identity/registration with an
  approved human sponsor. The selected sponsor is
  `admin@MngEnvMCAP623732.onmicrosoft.com`. Do not run `a365 setup all`. Do not
  create hosting, messaging endpoints, agent users, Work IQ access, Microsoft
  365 data permissions, or delegated observability permissions.
- **Result:** The tenant-owned `Agent 365 CLI` application was created with
  client ID `f853bbf8-6f86-4de0-b55f-a89ad5826ab9`. The CLI requested
  tenant-wide admin consent for
  `AgentIdentityBlueprint.ReadWrite.All`,
  `AgentIdentityBlueprintPrincipal.Create`,
  `AgentRegistration.ReadWrite.All`, `AgentIdentity.Read.All`,
  `AgentIdentity.DeleteRestore.All`, `Application.Read.All`, and `User.Read`.
  Consent was not granted because the noninteractive input ended at the
  consent prompt. The requirements operation was cancelled. No blueprint,
  BlueprintPrincipal, agent identity, registration, hosting, endpoint, or
  runtime change was created. After explicit approval, the requirements check
  was rerun and tenant-wide consent was successfully granted for the six
  provisioning permissions requested on that run:
  `AgentIdentityBlueprint.ReadWrite.All`,
  `AgentIdentityBlueprintPrincipal.Create`,
  `AgentRegistration.ReadWrite.All`, `AgentIdentity.Read.All`,
  `AgentIdentity.DeleteRestore.All`, and `Application.Read.All`. The CLI
  validated two requirements with zero warnings or failures. A subsequent
  `a365 setup blueprint --no-endpoint --dry-run` made no changes but disclosed
  that the blueprint workflow would also request unspecified Graph and
  Connectivity API consent. Those additional permissions are not approved and
  were denied. The guarded blueprint run created `trading-platform-agent
  Blueprint` with client/application and object ID
  `341ff526-fa67-4487-a028-5d61dd6e5a92`, BlueprintPrincipal object ID
  `43c8fed0-1800-4c60-b220-355b741809d7`, platform manager application ID
  `e8be65d6-d430-4289-a665-51bf2a194bda`, and a protected local-development
  client secret stored only in the generated configuration. The generated
  configuration is now covered by the repository-wide
  `**/a365.generated.config.json` Git ignore rule. No broad Microsoft Graph
  delegated scopes were granted or retained in `requiredResourceAccess`.
  `AgentIdentity.CreateAsManager` is the only granted blueprint application
  role. The CLI created `allAllowed` inheritance metadata; its delegated side
  currently has nothing to inherit. The local agent identity
  `trading-platform-agent-local-dev` was then created with client/application
  and object ID `7f2edbcc-8375-4d1d-a430-93c14e8db94e` and sponsor object ID
  `69149650-b87e-44cf-9413-db5c1a5b6d3f`. An interactive attempt to create
  the Agent 365 registry record timed out after 120 seconds without completing
  sign-in. Two coordinated retries also timed out: one requested a second
  incremental sign-in, and one used the already-consented Microsoft Graph
  `.default` scope. A final coordinated `.default` attempt also expired after
  120 seconds. Browser-assisted authentication subsequently completed both
  device-login prompts. The first registry request reached the API but failed
  because `managedByAppId` referred to the provisioning application. The
  request was corrected to owner-based management, which is supported because
  `ownerIds` is present. Agent 365 registry record
  `7f2edbcc-8375-4d1d-a430-93c14e8db94e` was then created for the local-dev
  identity with owner `69149650-b87e-44cf-9413-db5c1a5b6d3f`, blueprint
  `341ff526-fa67-4487-a028-5d61dd6e5a92`, no `managedByAppId`, and originating
  store `ai-hybrid-data-sources`. The protected generated configuration was
  updated with the tenant, agent identity, registration, and sponsor IDs.
- **Validation:** Queried the Agent Registration API and confirmed the record
  ID, display name, owner, agent identity, blueprint, source identity, and
  originating store. Queried blueprint permissions and confirmed no delegated
  Graph grants and only `AgentIdentity.CreateAsManager` as an application
  role. Confirmed the generated configuration remains Git-ignored.
- **Rollback:** Disable and delete the local-dev agent identity, remove the
  BlueprintPrincipal and blueprint after confirming no remaining instances,
  and remove the tenant-owned CLI client only if no other A365 administration
  depends on it.
- **Follow-up:** Add local S2S token acquisition and metadata-only Microsoft
  OpenTelemetry, then validate telemetry and governance visibility.

## 2026-10-06 20:30 EDT - Add metadata-only Agent 365 telemetry

- **Status:** Partially succeeded
- **Scope:** Repository, Runtime, Tenant
- **Requested by:** User
- **Purpose:** Export governed invocation, model, tool, HTTP, and database
  telemetry for the registered local-development Trading Platform Agent
  without exposing portfolio content or changing its APIM authorization.
- **Change:** Add a pinned Microsoft OpenTelemetry dependency, feature-gated
  A365 configuration, app-only S2S token resolution for the registered agent,
  one `invoke_agent` root scope per `/chat` turn, graceful flushing, Docker
  configuration, startup validation, redaction tests, and related
  documentation. Keep content recording disabled. Do not grant Microsoft 365
  data permissions, Work IQ, notifications, an agent user account, or any new
  tenant-wide consent. Reuse the existing protected blueprint development
  credential only through a local secret source.
- **Result:** Added feature-gated metadata-only Agent 365 telemetry to the
  Python runtime. Implemented strict configuration, a two-step app-only
  `fmi_path` exchange, JWT claim and expiry checks, an in-memory token cache,
  a synchronous exporter resolver, hashed conversation identifiers, one
  `invoke_agent` scope per `/chat` turn, degraded telemetry health reporting,
  error recording, and shutdown flushing. The Microsoft distribution is
  configured for the S2S observability endpoint with sensitive-data capture,
  invoke-agent input capture, and unencrypted offline storage disabled.
  Added Docker and local `.env` wiring; the existing protected blueprint
  development credential was decrypted directly into the git-ignored `.env`
  without displaying it. No tenant object, permission, consent, license, or
  Microsoft 365 data access changed. Pinned
  `microsoft-opentelemetry==1.3.9`,
  `agent-dev-cli==0.0.1b260128`, and `mcp==1.23.2` after fresh-image
  resolution exposed incompatible newer beta dependencies. Excluded
  `a365.generated.config.json` from Docker build context. The first live
  export showed that Agent Framework generated a different runtime agent ID
  and dropped its telemetry chunk; the factory now assigns registered Agent
  Identity `7f2edbcc-8375-4d1d-a430-93c14e8db94e` to every `ChatAgent`.
  Rebuilt and restarted only the local API container. The final live chat
  completed without exporter authentication or dropped-chunk errors.
- **Validation:** `27` focused telemetry, privacy, endpoint, credential, and
  rate-limit tests passed; `compileall` passed; `pip check` passed on the
  workstation and in the Linux image. The metadata test confirms prompt
  content is absent, session/conversation IDs are hashed, content recording
  is false, and the registered identity is used. The live S2S exchange
  returned a valid app-only token for the registered agent. The rebuilt
  image imported Agent Framework, MCP, and Microsoft OpenTelemetry
  successfully. `/health` returned `healthy`, database `connected`, and A365
  observability `ready` with `content_recording: false`. Two authenticated
  `/chat` requests returned responses; after correcting the runtime agent ID,
  logs contained no token-resolution, dropped-chunk, or exporter errors.
  Agent 365 portal-side arrival and rendering have not yet been independently
  confirmed.
- **Rollback:** Set `ENABLE_A365_OBSERVABILITY=false`, remove the runtime
  configuration and dependency changes, and rebuild the existing container.
  Identity and registry objects remain independently governable.
- **Follow-up:** Confirm the invocation in the Agent 365 administration,
  Defender, or Purview experience after ingestion delay. Then apply and
  verify sponsor, lifecycle, Conditional Access, permission-review, retention,
  credential-rotation, and incident-response governance controls. Replace
  the local blueprint secret with managed identity and workload identity
  federation before production hosting.

## 2026-10-07 09:20 EDT - Document A365 verification process

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Provide a repeatable verification process for the completed
  Agent 365 identity and metadata-only telemetry integration.
- **Change:** Document verification in
  `lob/ai-agent-starter-portfolio-manager/A365/verification_process.md` using
  ARRANGE, ACT, ASSERT for local configuration, automated tests, container
  security, runtime health, authenticated chat, telemetry export, privacy,
  portal arrival, failure behavior, and evidence capture. Link the process
  from the A365 documentation index and synchronize implementation status.
- **Result:** Added ten ARRANGE, ACT, ASSERT scenarios covering registration
  alignment, focused tests, dependency integrity, image secret exclusion,
  live token readiness, authenticated chat, exporter logs, metadata-only
  privacy, portal attribution, degraded behavior, and emergency disablement.
  Added explicit pass criteria, safe PowerShell commands, prohibited evidence
  rules, an evidence template, and an overall `INCONCLUSIVE` result until
  portal ingestion is observed. Updated `A365/readme.md` to link the process
  and identify the implemented identity and telemetry capabilities.
- **Validation:** Checked every command and expected assertion against the
  implemented environment variables, `/health` response, Compose service
  name, runtime status model, focused tests, Agent Identity IDs, privacy
  controls, and current security constraints. Documentation-only change; no
  runtime or tenant state was modified.
- **Rollback:** Remove the verification document and this ledger entry before
  publication.
- **Follow-up:** Execute the process and retain a sanitized evidence record;
  portal arrival remains the outstanding end-to-end assertion.

## 2026-10-07 09:25 EDT - Correct A365 verification for operators

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Replace the engineering-centric checklist with an operator
  journey that explains how to start using the deployed agent and verify the
  working Agent 365 experience and available features.
- **Change:** Rewrite `A365/verification_process.md` around real agent startup,
  representative user prompts, Microsoft 365 Admin Center registry and
  Activity validation, Defender activity hunting, Purview applicability,
  identity/governance checks, failure tests, and an explicit
  implemented-versus-not-enabled feature matrix. Retain ARRANGE, ACT, ASSERT.
- **Result:** Replaced the engineering-centric checklist with an operator
  acceptance journey. The process now starts the deployed Compose stack,
  launches `chat.py`, provides representative read-only questions, generates
  recognizable successful and failed activity, and walks through Agent
  Registry, the agent Activity tab, Defender Advanced Hunting, Entra identity
  and workload sign-ins, Purview applicability, and safe governance review.
  Added the deployed tenant, blueprint, and Agent Identity values; an
  implemented-versus-governance-pending-versus-intentionally-disabled feature
  matrix; ingestion troubleshooting; and an explicit final acceptance
  decision. Clarified that Teams, install/pin, Work IQ, Microsoft 365 data
  tools, agent users, autonomous triggers, connected agents, and computer use
  are not part of the deployed local CLI agent.
- **Validation:** Verified Microsoft 365 Admin Center navigation as
  **Agents** > **All agents** > **Registry**, the capability-dependent
  Details/Data & Tools/Security/Permissions/Activity tabs, and current Agent
  365 observability concepts against Microsoft documentation updated through
  October 2026. Checked the operational commands, names, IDs, expected health
  shape, privacy expectations, Defender query, and capability claims against
  the deployed Trading Platform Agent. Documentation-only correction; no
  runtime or tenant state changed.
- **Rollback:** Restore the earlier engineering verification checklist.
- **Follow-up:** Run the operator journey and capture sanitized evidence,
  especially the outstanding Agent Registry Activity and Defender assertions.

## 2026-10-07 09:40 EDT - Diagnose idle A365 degraded health

- **Status:** Succeeded
- **Scope:** Runtime
- **Requested by:** User
- **Purpose:** Determine why the healthy deployed agent reports Agent 365
  observability as degraded with no cached token and no recorded error.
- **Change:** Inspect non-secret container settings, runtime age, logs, and
  image identity; execute one harmless authenticated chat to invoke the
  existing just-in-time token refresh; then recheck health and exporter logs.
- **Result:** Read-only discovery found that all required Agent 365 settings
  are present, the blueprint secret is non-empty, the running container uses
  the expected image, and the container has been continuously running for
  approximately 13 hours. No telemetry authentication error was logged.
  The cached short-lived observability token had expired during idle time;
  `last_error: null` correctly showed that no exchange had failed. A harmless
  `/chat` request invoked the existing just-in-time refresh and immediately
  returned A365 health to `ready` with `token_ready: true`, although the
  separate APIM/model call timed out and the chat returned HTTP 500.
  Implemented a background refresh task that renews the A365 token two
  minutes before expiry and cancels cleanly during shutdown. Added a focused
  lifecycle test and documented the idle behavior. Updated the Dockerfile to
  use Microsoft's package proxy after Docker's direct connection to
  `files.pythonhosted.org` again failed its TLS handshake; no TLS validation
  was disabled. Rebuilt and recreated only the API container.
- **Validation:** `28` focused tests passed, Python compilation passed, and
  `pip check` passed locally and in the rebuilt Linux image. The recreated
  API container is healthy; `/health` reports Agent 365 `ready`,
  `token_ready: true`, `last_error: null`, and
  `content_recording: false`. Startup logs contain no Agent 365
  authentication or exporter error. The repeated chat timeout was traced
  before APIM: the API container resolved the APIM hostname to private IP
  `10.100.2.4`, but TCP 443 timed out. The user confirmed that the workstation
  was not connected to the OpenWrt gateway network required to route to the
  private APIM endpoint. This is separate from Agent 365 token readiness.
- **Rollback:** Not applicable; the chat uses the existing runtime and a
  read-only price lookup.
- **Follow-up:** Connect the workstation to the OpenWrt gateway network, retry
  the interactive `chat.py` test, then confirm Registry Activity and Defender
  ingestion after a successful chat.

## 2026-10-07 10:35 EDT - Correct redundant ticker confirmation

- **Status:** Partially succeeded
- **Scope:** Repository, Runtime
- **Requested by:** User
- **Purpose:** Correct the user experience found during Agent 365 acceptance
  testing where an explicitly supplied ticker is requested again.
- **Change:** Update the Trading Platform Agent instructions to ask for an
  account or ticker only when it is missing or ambiguous, add a prompt-contract
  regression test, and rebuild only the local API container.
- **Result:** Updated the agent instructions to use an explicitly supplied
  account or ticker without reconfirmation, added a prompt-contract test,
  rebuilt the image, and recreated only the API container. The user stopped
  execution before the exact `MSFT` end-to-end assertion was run.
- **Validation:** `29` focused tests and Python compilation passed. The rebuilt
  API container started successfully. The user later confirmed a separate
  cross-account valuation question completed successfully, proving the
  deployed prompt, APIM/model, agent, and database-tool path works; the exact
  ticker-confirmation scenario remains unobserved.
- **Rollback:** Restore the prior instruction and rebuild the API container.
- **Follow-up:** Confirm the successful run appears in Agent 365 Activity.

## 2026-10-07 13:47 EDT - Verify successful live agent run

- **Status:** Succeeded
- **Scope:** Runtime
- **Requested by:** User
- **Purpose:** Confirm the restored OpenWrt/private APIM path and Agent 365
  runtime during a real database-backed user interaction.
- **Change:** Read-only verification after the user successfully requested a
  ranking of accounts by current value. No returned account identifiers or
  portfolio values were copied into the ledger.
- **Result:** The interactive agent returned a ranked result and offered
  follow-up analyses, confirming user authentication, private APIM/model
  routing, agent reasoning, and PostgreSQL tool execution.
- **Validation:** `/health` reports service `healthy`, agent `ready`, database
  `connected`, Agent 365 `ready`, `token_ready: true`, `last_error: null`, and
  `content_recording: false`. Recent filtered logs contained no token
  resolution, dropped chunk, authentication, identity mismatch, or exporter
  failure.
- **Rollback:** Not applicable; read-only verification.
- **Follow-up:** Locate this run in the Agent Registry **Activity** tab and
  Microsoft Defender using the registered Agent Identity and its UTC window.

## 2026-10-07 14:10 EDT - Validate deployed A365 setup

- **Status:** Partially succeeded
- **Scope:** Runtime, Tenant
- **Requested by:** User
- **Purpose:** Verify that the actively used Trading Platform Agent is
  correctly registered, observable, private, and least privilege in Agent 365.
- **Change:** Performed read-only runtime, image, Microsoft 365 Admin Center,
  Activity, Security, Data & Tools, Permissions, and Microsoft Graph grant
  checks. No tenant object or grant was modified.
- **Result:** Runtime checks passed: service healthy, agent ready, database
  connected, Agent 365 ready, token cached, content recording disabled, image
  free of `.env` and generated credential files, dependencies valid, six of
  eight recent chats successful, and no exporter failure. Agent Registry
  contains **Trading Platform Agent - Local Dev** as Available on platform
  `ai-hybrid-data-sources`, with the correct Entra Agent ID
  `7f2edbcc-8375-4d1d-a430-93c14e8db94e`, owner, and last use on October 7.
  Activity proves end-to-end ingestion: 13 sessions, 7 successful sessions,
  6 exceptions, and 0.16 hours runtime. Zero active users is expected for the
  app-only local channel. Data & Tools reports no Microsoft 365 data/tool
  information. Security shows Entra identity and Purview protections.
  Least-privilege validation failed: BlueprintPrincipal
  `43c8fed0-1800-4c60-b220-355b741809d7` has one delegated Microsoft Graph
  grant containing `Mail.ReadWrite`, `Mail.Send`, `Chat.ReadWrite`,
  `User.Read.All`, `Sites.Read.All`, `Files.ReadWrite.All`,
  `ChannelMessage.Read.All`, and `ChannelMessage.Send`. The Agent Identity
  itself has no delegated or application grants. The blueprint declares no
  required resource access. The BlueprintPrincipal's only application role is
  the intended `AgentIdentity.CreateAsManager`.
- **Validation:** Confirmed portal metrics and identity directly, then
  independently queried Graph `oauth2PermissionGrants`,
  `appRoleAssignments`, and blueprint `requiredResourceAccess`. This corrects
  the earlier ledger claim that no delegated permission was retained; the
  broad delegated grant exists on the BlueprintPrincipal even though it is
  absent from the blueprint application declaration.
- **Rollback:** Not applicable; read-only validation.
- **Follow-up:** With explicit administrator approval, delete the single
  residual delegated OAuth grant from the BlueprintPrincipal, preserve
  `AgentIdentity.CreateAsManager`, refresh Agent Registry permissions, and
  revalidate runtime telemetry.

## 2026-10-07 14:16 EDT - Remove residual delegated Graph grant

- **Status:** Succeeded
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Restore the telemetry-only Agent 365 design to least privilege.
- **Change:** Delete only the single `oauth2PermissionGrant` assigned to
  BlueprintPrincipal `43c8fed0-1800-4c60-b220-355b741809d7`, guarded by an
  exact match to the eight identified delegated scopes. Preserve the
  `AgentIdentity.CreateAsManager` application role and all identity, registry,
  sponsor, and telemetry objects.
- **Result:** The guarded deletion succeeded. The BlueprintPrincipal and Agent
  Identity now have zero delegated grants. The BlueprintPrincipal retains its
  one required `AgentIdentity.CreateAsManager` application role. No identity,
  registry, sponsor, or telemetry object was changed. Runtime health remained
  healthy with Agent 365 ready.
- **Validation:** Direct Microsoft Graph queries confirmed zero delegated
  grants on both principals and one application role assignment on the
  BlueprintPrincipal. After selecting **Refresh** in the Microsoft 365 Admin
  Center Permissions tab, the eight delegated scopes disappeared and only
  `AgentIdentity.CreateAsManager` remained as an Application permission.
- **Rollback:** Regranting broad scopes is not an approved rollback. If an
  actual future capability requires a permission, request and consent only
  the minimum specific scope through a separate approved change.
- **Follow-up:** None.

## 2026-10-07 14:17 EDT - Check Defender telemetry visibility

- **Status:** Partially succeeded
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Complete the Agent 365 validity review by checking whether the
  tenant exposes Agent 365 events through Microsoft Defender Advanced Hunting.
- **Change:** Opened Microsoft Defender Advanced Hunting and ran a metadata-only
  query scoped to the registered Agent Identity. No tenant state was changed,
  and no event payload or portfolio content was recorded.
- **Result:** Advanced Hunting is accessible, but the tenant does not expose
  the `CloudAppEvents` table. The query could not execute and returned
  `Failed to resolve table or column expression named 'CloudAppEvents'`.
  Defender event-level verification is therefore unavailable in the current
  tenant licensing or data configuration.
- **Validation:** The Advanced Hunting query editor loaded and accepted the
  query; the service returned a semantic table-resolution error rather than
  an agent identity, authentication, or runtime telemetry error.
- **Rollback:** Not applicable; read-only validation.
- **Follow-up:** If Defender event-level validation is required, verify that
  the tenant has the applicable Microsoft Defender licensing, permissions,
  and Cloud Apps data source. Agent 365 Activity already confirms telemetry
  ingestion independently.

## 2026-10-07 14:20 EDT - Assess telemetry and governance coverage

- **Status:** Succeeded
- **Scope:** Repository, Runtime, Tenant
- **Requested by:** User
- **Purpose:** Determine whether the current on-premises Agent 365 integration
  delivers meaningful telemetry and enforceable governance rather than only an
  inventory record.
- **Change:** Performed a read-only comparison of the runtime integration,
  Microsoft 365 Admin Center surfaces, Defender availability, and current
  Microsoft Agent 365 documentation. No repository, runtime, tenant, identity,
  permission, policy, or license state was changed.
- **Result:** The current integration provides identity, registry inventory,
  ownership, permission visibility, and aggregate `invoke_agent` activity.
  Detailed inference and tool telemetry is designed to appear in Microsoft
  Defender, but this tenant currently does not expose the `CloudAppEvents`
  table. The runtime uses the Agent Identity only for Agent 365 telemetry
  authentication. Telemetry authentication is deliberately fail-open:
  `ensure_token()` returns `false` on failure, `invoke_scope()` becomes a
  no-op, and the chat request continues. Consequently, the current Agent 365
  identity and registry state do not authorize or prevent the agent's APIM,
  model, database, or tool execution.
- **Validation:** Microsoft 365 Admin Center shows aggregate session activity
  and the intended application permission. Defender returned a semantic error
  because `CloudAppEvents` is unavailable. Repository inspection confirmed
  that `/chat` continues after `prepare_a365_telemetry()` returns and that a
  missing telemetry token yields an empty invocation scope. Microsoft
  documentation confirms that Admin Center consumes root `invoke_agent`
  records while run, inference, and tool detail appears in Defender.
- **Rollback:** Not applicable; read-only assessment.
- **Follow-up:** Treat the current onboarding as incomplete for the stated
  telemetry-and-governance objective. Provision Defender visibility and make
  the Agent Identity part of the actual APIM/tool authorization path, with an
  explicitly approved fail-open or fail-closed policy.

## 2026-10-07 14:24 EDT - Diagnose Defender hunting access

- **Status:** Succeeded
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Determine whether a missing Defender role prevents the
  administrator from querying Agent 365 telemetry in Advanced Hunting.
- **Change:** Performed read-only Microsoft Graph checks of the signed-in
  administrator's directory roles, assigned license SKUs, and service-plan
  provisioning states. No role, license, service plan, or tenant setting was
  changed.
- **Result:** The signed-in account is a Global Administrator, which Microsoft
  documents as providing full read access to Advanced Hunting data. The
  account has `AGENT_365` assigned, and all 14 Agent 365 service plans are
  successfully provisioned, including `DEFENDER_FOR_AI`. The account also has
  Microsoft 365 E5 without Teams assigned, but its `MTP` and
  `ADALLOM_S_STANDALONE` service plans are disabled. Those disabled Defender
  XDR and Defender for Cloud Apps plans are the strongest identified
  explanation for the missing `CloudAppEvents` schema. At the tenant level,
  the Agent 365, `DEFENDER_FOR_AI`, `MTP`, and Defender for Cloud Apps
  capabilities are all enabled and the subscribed SKUs are active. Assigning
  Security Reader would be redundant and would not correct disabled service
  plans.
- **Validation:** Microsoft Graph returned the Global Administrator role and
  assigned SKU/service-plan states. Microsoft Defender allowed Advanced
  Hunting queries but reported that `CloudAppEvents` could not be resolved.
  The Defender portal also returned an MTP-server `404` and had no Defender
  subscription ID for the signed-in session.
  Microsoft documentation lists Global Administrator, Security Administrator,
  Security Reader, and Global Reader as roles granting full read access to
  Advanced Hunting data.
- **Rollback:** Not applicable; read-only validation.
- **Follow-up:** With explicit administrator approval, preserve the current E5
  license assignment and enable only its `MTP` and
  `ADALLOM_S_STANDALONE` service plans for the validating administrator. After
  propagation and a new sign-in, confirm that `CloudAppEvents` appears and
  query the Agent Identity. If it remains absent, escalate as an Agent 365
  Defender backend provisioning issue. Any service-plan change requires
  explicit administrator approval.

## 2026-10-07 14:29 EDT - Enable Defender validation service plans

- **Status:** Partially succeeded
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Enable the minimum Defender services needed to validate Agent
  365 detailed telemetry in Advanced Hunting.
- **Change:** Preserve the validating administrator's existing Microsoft 365
  E5 without Teams license and its current disabled-plan set, except enable
  only `MTP` and `ADALLOM_S_STANDALONE`. Do not change any other SKU, role,
  user, service plan, permission, or tenant setting.
- **Result:** The first Microsoft Graph call was rejected because Azure CLI did
  not transmit the inline JSON payload correctly; Graph made no change. The
  retry used the same guarded payload from a temporary file and succeeded.
  Only `MTP` and `ADALLOM_S_STANDALONE` were removed from the E5 disabled-plan
  set, reducing it from 80 to 78 entries. Both plans now report `Success`.
  No other license, service plan, SKU, role, or user was changed. The temporary
  request file was deleted. The licensing change succeeded, but detailed Agent
  365 telemetry is not yet available.
- **Validation:** Post-change Graph validation confirmed the resulting
  disabled-plan set exactly matched the approved two-plan delta and both target
  plans were successfully provisioned. The administrator signed out and back
  in to obtain a fresh Defender session. Defender still has no subscription ID,
  its MTP settings request returns `404`, and `CloudAppEvents` remains an
  unresolved table. At 15:42 EDT, more than an hour after the change, a clean
  `CloudAppEvents | take 1` schema test still failed with
  `Failed to resolve table or column expression named 'CloudAppEvents'`.
  A second clean-editor retry at 15:43 EDT returned the identical semantic
  error.
  This isolates the remaining problem to Defender backend provisioning rather
  than Entra or Defender roles, browser state, query syntax, or the agent
  exporter.
- **Rollback:** Restore the exact pre-change E5 disabled-plan set captured
  immediately before the update.
- **Follow-up:** The administrator elected to retain both plans while Defender
  backend provisioning propagates. Because the subscription ID and
  `CloudAppEvents` remain absent after a fresh session and delayed retry, open
  a Microsoft support request for Agent 365 Defender backend provisioning.

## 2026-10-07 15:50 EDT - Provision Defender Cloud Apps connector

- **Status:** Failed
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Provision the Defender for Cloud Apps backend required for the
  `CloudAppEvents` Advanced Hunting table and detailed Agent 365 telemetry.
- **Change:** Create the Microsoft 365 app connector through Microsoft's
  supported Defender/automated setup experience and enable only
  **Microsoft 365 activities**. Do not enable file monitoring or other optional
  Microsoft 365 components. The connector may create the required Microsoft
  first-party Defender for Cloud Apps service principals and begin ingesting
  Microsoft 365 audit activity.
- **Result:** No tenant state changed. Microsoft documentation confirms that
  `CloudAppEvents` requires Defender for Cloud Apps plus a Microsoft 365 app
  connector with Microsoft 365 activities enabled. Read-only Graph checks
  found the Defender for Cloud Apps Customer Experience service principal, but
  the required API Connectors and Information Protection service principals
  are not provisioned. Both documented App Connectors portal routes redirect
  to Defender Home because the Cloud Apps backend is not instantiated. The
  Microsoft 365 automated setup guide loaded successfully, but it only offered
  broader cloud-discovery sources and AI/OAuth protection deployments, not the
  approved minimum Microsoft 365 activity connector. Those broader options
  were not selected, and Microsoft first-party service principals were not
  created manually.
- **Validation:** Confirmed the required service-principal application IDs
  against Microsoft's Defender for Cloud Apps quickstart, queried their tenant
  presence through Microsoft Graph, tested the current and legacy App
  Connectors portal routes, and inspected the supported automated setup guide.
  `CloudAppEvents` remains unavailable.
- **Rollback:** Disconnect the Microsoft 365 app connector and disable only the
  first-party integration artifacts created by this action if Microsoft
  documents that they are safe to disable. Retain audit history according to
  Microsoft service behavior.
- **Follow-up:** Open a Microsoft support request to provision the tenant's
  Defender for Cloud Apps/Defender XDR backend. After Microsoft creates the
  backend, configure only the Microsoft 365 activities connector and run the
  Agent Identity-scoped metadata query.

## 2026-10-07 15:54 EDT - Prepare Defender provisioning support case

- **Status:** Cancelled
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Ask Microsoft to provision the tenant's missing Defender for
  Cloud Apps/Defender XDR backend so Agent 365 telemetry can appear in
  `CloudAppEvents`.
- **Change:** Open the Microsoft 365 Admin Center support workflow and prepare
  a case containing the verified licensing, roles, service-plan states,
  missing first-party service principals, portal redirects/errors, and
  Advanced Hunting result. Do not include secrets, tokens, portfolio content,
  or credentials. Stop before final submission for administrator review.
- **Result:** The support workflow was interrupted before a case or draft was
  created when the user elected to try the broader Defender for Cloud Apps
  setup guide instead.
- **Validation:** No support case number or draft was created and no support
  information was submitted.
- **Rollback:** Close the support workflow without submitting it.
- **Follow-up:** Reopen the support workflow if supported setup does not
  provision the Defender backend.

## 2026-10-07 15:54 EDT - Assess broad Defender setup cost

- **Status:** Succeeded
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Determine the financial and operational impact of selecting
  every option in the Defender for Cloud Apps automated setup guide.
- **Change:** Performed a read-only review of the guide options and current
  Microsoft licensing and deployment documentation. No setup option, connector,
  license, service plan, policy, collector, gateway, or endpoint integration
  was changed.
- **Result:** The tenant's Microsoft 365 E5 entitlement includes Defender for
  Cloud Apps, so the Microsoft connector features generally do not add a
  separate per-feature charge. Selecting every option can nevertheless create
  substantial indirect cost and scope: Defender for Endpoint must be licensed
  and deployed to applicable devices, continuous collection requires a
  maintained Docker/VM log collector and log routing, and Corrata, iboss, Menlo
  Security, or Zscaler integrations require separately licensed third-party
  secure web gateways. It also expands monitoring, data ingestion, privacy
  review, alert triage, and operational ownership well beyond Agent 365
  telemetry validation.
- **Validation:** Compared the setup guide's native discovery, manual upload,
  collector, gateway, Security for AI apps, and app-to-app options with the
  Microsoft Defender service description and Cloud Discovery deployment
  guidance.
- **Rollback:** Not applicable; read-only assessment.
- **Follow-up:** Prefer only Security for AI apps plus app-to-app protection if
  attempting the broader supported provisioning path. Do not select unrelated
  collectors or gateways without an implementation and cost plan.

## 2026-10-07 16:01 EDT - Enable focused Defender protections

- **Status:** Cancelled
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Use Microsoft's supported Defender for Cloud Apps setup workflow
  to attempt backend provisioning for Agent 365 telemetry without deploying
  unrelated endpoint, collector, or secure-web-gateway integrations.
- **Change:** In the Microsoft Defender for Cloud Apps automated setup guide,
  select only **Security for AI apps (Generative AI & Copilot)** and
  **App-to-app protection (OAuth & non-human apps)**. Do not select Defender
  for Endpoint discovery, manual log upload, log collectors, Corrata, iboss,
  Menlo Security, Zscaler, or other unrelated integrations. Review subsequent
  policy and consent screens before applying them.
- **Result:** The two approved protection options were selected in the setup
  form, but the guide required an additional cloud-discovery data source before
  enabling Next. No form was submitted and no tenant state changed. The user
  elected not to add an unrelated discovery source solely to bypass the guide.
- **Validation:** Next remained disabled without a native discovery source,
  and the guide never advanced to an apply or consent step.
- **Rollback:** Disable only the policies/integrations created by this guide
  and restore their captured prior states. Do not remove Microsoft first-party
  service principals without Microsoft guidance.
- **Follow-up:** Use Microsoft support to provision the missing Defender for
  Cloud Apps/Defender XDR backend.

## 2026-10-07 16:04 EDT - Prepare Defender backend support case

- **Status:** Cancelled
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Request supported provisioning of the tenant's missing Defender
  for Cloud Apps/Defender XDR backend.
- **Change:** Cancel the unsaved Cloud Discovery setup and prepare a Microsoft
  365 Admin Center support case containing the verified license, service-plan,
  role, missing service-principal, portal redirect, MTP `404`, missing
  subscription ID, and `CloudAppEvents` evidence. Do not include secrets,
  tokens, credentials, or portfolio data. Stop before final submission.
- **Result:** The user clarified that the intended next action is to proceed
  with Manual log upload in the Defender setup guide, not create a support
  case. No support workflow was opened and no case or draft was created.
- **Validation:** No support case number, draft, or submission exists.
- **Rollback:** Close the support workflow without submission.
- **Follow-up:** Continue the explicitly approved Defender setup combination.

## 2026-10-07 16:05 EDT - Enable Defender AI and manual discovery

- **Status:** Partially succeeded
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Attempt supported Defender for Cloud Apps backend provisioning
  using the minimum cloud-discovery source accepted by the automated guide.
- **Change:** Select **Manual log upload**, **Security for AI apps (Generative
  AI & Copilot)**, and **App-to-app protection (OAuth & non-human apps)**.
  Do not select Defender for Endpoint, log collector, or any third-party secure
  web gateway. Manual discovery remains inactive unless an administrator later
  uploads firewall or proxy logs. Review later policy and consent steps before
  applying them.
- **Result:** The automated setup guide completed with Manual log upload,
  Security for AI apps, and app-to-app protection selected. Manual upload was
  added as a task with status `Not started`; no firewall or proxy log was
  requested or ingested. Microsoft 365 was the only app connector selected by
  default. The guide then generated instructions and checklist tasks, but every
  discovery, connector, threat-protection, and app-governance task remained
  `Not started`. No connector, policy, consent, log source, AI protection, or
  OAuth protection was actually enabled.
- **Validation:** After guide completion, the Defender for Cloud Apps API
  Connectors and Information Protection service principals remained absent,
  the App Connectors route still redirected to Defender Home, Defender still
  reported no subscription ID and an MTP `404`, and
  `CloudAppEvents | take 1` returned
  `Failed to resolve table or column expression named 'CloudAppEvents'`.
- **Rollback:** Disable only the policies/integrations created by this guide.
  Do not remove first-party Microsoft service principals without guidance.
- **Follow-up:** The setup guide cannot instantiate this tenant's backend.
  Open a Microsoft support request for Defender for Cloud Apps/Defender XDR
  provisioning, then configure the Microsoft 365 activities connector when
  the backend becomes available.

## 2026-10-07 16:14 EDT - Reconcile Agent 365 Defender documentation

- **Status:** Succeeded
- **Scope:** Repository | Tenant
- **Requested by:** User
- **Purpose:** Reconcile Agent 365-specific observability requirements with
  generic Defender for Cloud Apps guidance before making further tenant
  changes.
- **Change:** Performed a read-only review of the official Agent 365
  quickstart, observability concepts, direct OpenTelemetry troubleshooting,
  Microsoft OpenTelemetry Distro troubleshooting, Defender transition
  guidance, and `CloudAppEvents` prerequisites. Corrected the local
  verification documentation without changing tenant state.
- **Result:** Agent 365 documentation says assigning at least one Microsoft
  Agent 365 or Microsoft 365 E7 license enables observability routing and does
  not list the Microsoft 365 Activities connector as an Agent 365 telemetry
  prerequisite. Microsoft OpenTelemetry Distro documentation separately says
  Defender viewing requires Advanced Hunting access to `CloudAppEvents`.
  Generic Defender for Cloud Apps documentation describes the Microsoft 365
  connector for its broader Microsoft 365 activity feed; it does not establish
  that the connector is required for Agent 365 spans. The earlier 16:05
  follow-up requiring that connector was therefore too strong.
- **Validation:** The runtime code explicitly enables the Agent 365 exporter,
  uses the registered agent identity, emits an `invoke_agent` root, and
  disables sensitive content. Admin Center Activity proves accepted root
  activity. Defender still cannot resolve `CloudAppEvents`, so child inference
  and tool-span acceptance cannot yet be confirmed there. No exporter error
  diagnostics appeared in the current six-hour container log window.
- **Rollback:** Revert only the documentation clarification; no tenant state
  changed.
- **Follow-up:** Escalate the missing Defender backend/table to Microsoft using
  the Agent 365-specific license-triggered workflow. Do not require or deploy
  the Microsoft 365 Activities connector solely for Agent 365 spans unless
  Microsoft support provides product-specific guidance. Capture per-span
  destination results if the exporter exposes them in a future diagnostic run.

## 2026-10-07 16:53 EDT - Check prevalence of missing Defender telemetry

- **Status:** Succeeded
- **Scope:** Repository | Tenant
- **Requested by:** User
- **Purpose:** Determine whether the missing `CloudAppEvents` table and
  Defender backend symptoms are a common or currently acknowledged issue
  before opening a Microsoft support case.
- **Change:** Performed read-only searches of Microsoft documentation,
  Microsoft Q&A, Tech Community, public GitHub issues, historical service
  incidents, and this tenant's Microsoft 365 Service health page. No tenant,
  license, connector, policy, identity, or runtime state changed.
- **Result:** Public reports confirm that delayed or incomplete Defender
  backend provisioning after license activation occurs across Defender
  products, but no public report was found that exactly matches Agent 365
  Activity working while the tenant has no Defender subscription ID, an MTP
  `404`, and an unresolved `CloudAppEvents` table. Reports about an empty
  `CloudAppEvents` table usually concern Microsoft 365 app-connector
  configuration and are not the same as this tenant's absent table. An open
  Agent 365 Samples issue describes the inverse condition: events in
  `CloudAppEvents` but no Admin Center Activity.
- **Validation:** This tenant currently has active Microsoft Defender XDR
  advisory `DZ1489394`, started October 6, 2026 at 06:52 EDT. Microsoft states
  that an authentication component failure is delaying Defender for Cloud Apps
  alert and activity processing, including data appearing in Advanced Hunting
  and the `CloudAppEvents` table. Microsoft resumed backlog processing and
  scheduled its next update for October 8, 2026 at 03:30 EDT. The E5 `MTP` and
  `ADALLOM_S_STANDALONE` plans were also enabled only at 14:29 EDT today.
- **Rollback:** Not applicable; read-only investigation and audit
  documentation only.
- **Follow-up:** Do not open a support case while `DZ1489394` is active. After
  Microsoft marks it resolved and processes the backlog, wait through the
  Defender service-plan propagation window, sign out and back in, then retest
  `CloudAppEvents | take 1`, the Defender subscription ID, and MTP settings.
  Open a case only if the table remains unresolved after that clean retest.

## 2026-10-07 18:26 EDT - Publish repository work to GitHub

- **Status:** Planned
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Persist the accumulated infrastructure, APIM observability,
  diagnostic, LOB agent, and Agent 365 work in the GitHub repository.
- **Change:** Validate the pending repository snapshot, commit the coherent
  source, tests, documentation, diagrams, and audit history on `main`, and push
  it to `origin/main`. Exclude ignored credentials, compiled Bicep JSON,
  captured runtime output, and an obsolete duplicate APIM policy copy.
- **Result:** Pending.
- **Validation:** Pending Bicep compilation, focused PowerShell/Node checks,
  Python tests, staged secret review, commit creation, and remote push
  verification.
- **Rollback:** Revert the published commit with a new commit if necessary; do
  not rewrite shared branch history.
- **Follow-up:** Complete validation, commit, push, and update this entry with
  the resulting commit identifier.

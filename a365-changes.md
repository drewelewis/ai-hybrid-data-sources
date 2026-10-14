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

## 2026-10-12 13:23 EDT - Scrub organization name

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Replace organization-identifying names and links with the
  approved codename `Contoso Bank`.
- **Change:** Update current repository content and historical ledger wording
  that identifies the organization, replace branded business-unit names with
  generic equivalents, and remove identifying external corporate source
  links. Git history will not be rewritten. No tenant, Azure, identity,
  permission, license, or runtime object will be changed.
- **Result:** Replaced organization-identifying names in the LOB documentation,
  Agent 365 guidance, documentation index, and historical ledger wording with
  `Contoso Bank`. Generalized branded commercial-bank and wealth-business
  names and removed the identifying corporate report links. Git history was
  not rewritten. No tenant, Azure, identity, permission, license, or runtime
  object was changed.
- **Validation:** A case-insensitive current-worktree content scan found no
  occurrences of the removed organization names, branded affluent-service
  name, or corporate domain. A recursive filename scan excluding `.git` found
  no identifying paths. Confirmed `Contoso Bank` appears in the intended four
  documentation and ledger files.
- **Rollback:** Restore the affected documentation and ledger wording from the
  prior revision. Re-adding identifying names requires explicit approval.
- **Follow-up:** Rewrite Git history separately only if removal from prior
  commits is required.

## 2026-10-12 13:25 EDT - Publish LOB and Agent 365 reorganization

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Commit and push the approved LOB structure, Agent 365
  documentation relocation, Contoso Bank scrub, launchers, and moved
  portfolio-manager project to GitHub.
- **Change:** Stage only `A365/`, `lob/`, `a365-changes.md`, `startapi.bat`,
  and `startchat.bat`; exclude unrelated infrastructure mapping and copied
  APIM policy files; validate the staged change; commit to `main`; and push to
  `origin/main`.
- **Result:** Published commit `f0c9a3e` with the approved LOB and Agent 365
  scope. The selected moved tree also contained a generated MCP test-output
  artifact with sample portfolio results and a service endpoint. It contained
  no credential, but it was removed immediately and `output/` was added to the
  project ignore rules in cleanup commit `147185a`. Unrelated
  `infra/mapping-storage.json` and
  `peering/modules/apim-foundry-policy copy.xml` remain uncommitted.
- **Validation:** Confirmed the staged scope before commit, `git diff
  --cached --check` passed, a staged-addition credential-pattern scan found no
  matches, local and remote `main` were synchronized before publication, and
  both commits were accepted by `origin/main`. Tests were not run because the
  earlier test request was declined.
- **Rollback:** Revert the published commit with a new revert commit; do not
  rewrite shared branch history.
- **Follow-up:** Run the relocated portfolio-manager tests when authorized.

## 2026-10-12 10:05 EDT - Assess LOB-specific blueprint guidance

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Determine whether Agent 365 blueprint documentation should
  account for Contoso Bank's five lines of business.
- **Change:** Performed a read-only comparison of the current Agent Identity
  blueprint boundary guidance, tenant governance model, and documented Contoso Bank
  LOB structure. No repository content other than this audit entry and no
  tenant, Azure, identity, permission, license, or runtime object was changed.
- **Result:** LOB-specific blueprint profiles are useful for documenting
  ownership, data classification, permissions, policy, sponsorship, and
  incident routing. A blueprint should not be created merely because an LOB
  exists; the actual boundary should remain the agent family plus its shared
  credential, permission, publisher, regulatory, and blast-radius boundary.
- **Validation:** Confirmed the current blueprint guide already requires
  separate blueprints when business ownership, regulated data, inherited
  permissions, credentials, or incident isolation differ, while allowing
  instances with a common purpose and trust boundary to share a blueprint.
- **Rollback:** Remove this audit entry; no operational rollback is required.
- **Follow-up:** Optionally add an enterprise blueprint taxonomy and one
  documented blueprint profile for each LOB without provisioning tenant
  objects.

## 2026-10-12 10:06 EDT - Add LOB blueprint guidance

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Document how Contoso Bank lines of business should influence Agent
  Identity Blueprint boundaries and governance.
- **Change:** Add `A365/lob_bluprints.md` with an enterprise taxonomy, boundary
  rules, five LOB profiles, and a concrete Wealth portfolio-manager profile;
  link it from `A365/readme.md`. No blueprint or other tenant object will be
  created or modified.
- **Result:** Added `A365/lob_bluprints.md` with the enterprise taxonomy,
  blueprint boundary rules, a reusable profile schema, profiles for Services,
  Markets, Banking, Wealth, and U.S. Personal Banking, and a current-state
  Wealth portfolio-manager profile. Linked the guide from `A365/readme.md`.
  No blueprint or other tenant object was created or modified.
- **Validation:** Confirmed the document contains headings for all five LOBs
  and the Wealth portfolio-manager profile, the Agent 365 documentation map
  links to it, and all six local related-document targets exist.
- **Rollback:** Delete `A365/lob_bluprints.md`, remove its index link, and
  retain this ledger entry as history.
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

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Persist the accumulated infrastructure, APIM observability,
  diagnostic, LOB agent, and Agent 365 work in the GitHub repository.
- **Change:** Validate the pending repository snapshot, commit the coherent
  source, tests, documentation, diagrams, and audit history on `main`, and push
  it to `origin/main`. Exclude ignored credentials, compiled Bicep JSON,
  captured runtime output, and an obsolete duplicate APIM policy copy.
- **Result:** Published commit `8ec5092` (`Add APIM observability and Agent 365
  integration`) to `origin/main`. The commit contains 96 changed files and
  includes the required Copilot co-author trailer. The real `.env`, `.azure`,
  compiled `infra/mapping-storage.json`, captured MCP output, and obsolete
  duplicate APIM policy copy were not committed.
- **Validation:** `infra/main.bicep` and `peering/peering.bicep` compiled
  successfully. Five focused APIM PowerShell/Node validation routines passed.
  The focused Python suite passed all 30 tests. Staged whitespace and
  high-confidence secret-pattern checks passed. `git fetch` showed no
  pre-push divergence, and GitHub accepted `main` advancing from `65b6dc1` to
  `8ec5092`.
- **Rollback:** Revert the published commit with a new commit if necessary; do
  not rewrite shared branch history.
- **Follow-up:** Publish this audit-entry completion and verify local `main`
  matches `origin/main`.

## 2026-10-08 09:11 EDT - Retest Defender telemetry provisioning

- **Status:** Partially succeeded
- **Scope:** Tenant | Repository
- **Requested by:** User
- **Purpose:** Determine whether Defender and `CloudAppEvents` provisioned
  overnight after the service-plan changes and Microsoft service degradation.
- **Change:** Performed read-only checks of Microsoft 365 Service health,
  Defender Advanced Hunting, the validating administrator's Defender service
  plans, relevant first-party service principals, and the Defender for Cloud
  Apps App Connectors route. No tenant or runtime state changed.
- **Result:** Microsoft marked advisory `DZ1489394` **Service restored** after
  backlog processing completed. Impact ended October 8 at 03:37 EDT, and the
  final update was posted at 05:02 EDT. `MTP`, `ADALLOM_S_STANDALONE`, and
  `DEFENDER_FOR_AI` still report `Success`. The previously absent Microsoft
  Defender for Cloud Apps APIs service principal
  (`972bb84a-1d27-4bd3-8306-6b8e57679e8c`) now exists and is enabled, which
  shows partial backend provisioning progress. The Information Protection
  service principal (`9ba4f733-be8f-4112-9c4a-e3b417c44e7d`) remains absent,
  and the App Connectors route still redirects to Defender Home.
- **Validation:** A fresh 09:10 EDT Advanced Hunting execution of
  `CloudAppEvents | take 1` still returned
  `Failed to resolve table or column expression named 'CloudAppEvents'`.
  Because the table is absent, the registered Agent Identity query could not
  be run.
- **Rollback:** Not applicable; read-only investigation and audit
  documentation only.
- **Follow-up:** Provisioning is not complete, but it changed overnight. Wait
  at least 24 hours after the 03:37 EDT service restoration before escalating.
  Then rerun the schema query, App Connectors route, backend-principal check,
  Defender subscription ID, and MTP settings check from a fresh sign-in.

## 2026-10-08 15:34 EDT - Review Purview DSPM setup applicability

- **Status:** Succeeded
- **Scope:** Tenant | Repository
- **Requested by:** User
- **Purpose:** Explain the Purview unified DSPM setup prompt and determine
  which options are applicable to the metadata-only on-prem Agent 365 agent.
- **Change:** Performed a read-only review of Microsoft's Agent 365 Purview
  capability matrix, DSPM setup tasks, unified audit requirements, collection
  policies, Entra-registered AI app integration, and Purview billing models.
  No setup button was selected and no audit, policy, billing, role, or tenant
  setting changed.
- **Result:** The wizard combines required **Auditing and analytics** with
  optional AI collection policies. Unified audit is currently not enabled,
  and enabling it requires the Exchange Online `Audit Logs` role; Global
  Administrator alone does not satisfy that check. Agent 365 audit supports
  `AIInvokeAgent`, `AIInferenceCall`, `AIExecuteTool`, and `AIGuardrail`.
  Collection policies for Copilot experiences and Enterprise AI are
  pay-as-you-go and can capture prompts and responses. Entra-registered custom
  AI apps require Microsoft Purview SDK integration plus pay-as-you-go for
  full Purview interaction management. Network detection separately requires
  a supported SASE or secure enterprise browser integration.
- **Validation:** Compared the screenshot with Microsoft Learn documentation
  for Agent 365, Entra-registered AI apps, DSPM setup, audit enablement,
  collection policies, and billing. The current agent intentionally suppresses
  prompt and response content and has no Purview SDK, Microsoft 365 channel,
  or SASE integration, so optional content-classification, DLP, eDiscovery,
  and risk insights would be limited without an explicitly approved content
  integration.
- **Rollback:** Not applicable; read-only investigation and audit
  documentation only.
- **Follow-up:** Do not select **Start setup** as a single combined action.
  First decide whether to enable unified audit only through an administrator
  with the `Audit Logs` role. Review the three collection policies, Azure
  billing linkage, scope, content capture, privacy, retention, and expected
  cost separately before enabling any pay-as-you-go policy.

## 2026-10-08 15:52 EDT - Enable unified audit only

- **Status:** Failed
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Enable the minimum Purview prerequisite needed to search Agent
  365 invocation, inference, tool, and guardrail audit activities without
  enabling content collection or pay-as-you-go features.
- **Change:** Use Exchange Online to set
  `UnifiedAuditLogIngestionEnabled` from `False` to `True` for tenant
  `00648bab-6c91-4292-9a2a-2297df511222`. Do not start the combined DSPM
  wizard and do not create or modify collection policies, Azure billing,
  Purview SDK integration, DLP, retention, eDiscovery, or content capture.
- **Result:** Exchange rejected two attempts to enable unified audit before
  changing the setting. Both returned
  `InvalidOperationInDehydratedContextException` and required the separate
  one-time `Enable-OrganizationCustomization` operation. No audit, collection
  policy, billing, role, or content-capture setting changed.
- **Validation:** A read-only Exchange check confirmed the value remains
  `False`. The signed-in administrator has the required `Audit Logs` role
  through the Exchange `Organization Management` role group.
  `Get-OrganizationConfig` reported `IsDehydrated: False`, but both write
  attempts still returned the same server-side customization prerequisite.
- **Rollback:** Run
  `Set-AdminAuditLogConfig -UnifiedAuditLogIngestionEnabled $false` using an
  authorized Exchange Online administrator.
- **Follow-up:** Obtain explicit administrator approval for the separate,
  tenant-wide `Enable-OrganizationCustomization` prerequisite. If approved,
  run it once, wait for propagation, retry unified audit, verify the flag, and
  search for Agent 365 audit operations after ingestion.

## 2026-10-08 16:09 EDT - Customize Exchange and enable audit

- **Status:** Failed
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Satisfy Exchange Online's one-time organization customization
  prerequisite so unified audit can be enabled for Agent 365 auditing.
- **Change:** Run `Enable-OrganizationCustomization` once for the tenant, wait
  for Exchange propagation, then set
  `UnifiedAuditLogIngestionEnabled` to `True`. Do not enable Purview
  collection policies, content capture, Azure billing, DLP, retention,
  eDiscovery, or Purview SDK integration.
- **Result:** `Enable-OrganizationCustomization` returned that the
  organization is already enabled for customization and made no change.
  Purview's dedicated **Start recording user and admin activity** control was
  then selected, but the authoritative audit flag remained `False`. No audit,
  collection policy, content capture, billing, DLP, retention, eDiscovery, or
  Purview SDK setting changed.
- **Validation:** Exchange reports `IsDehydrated: False`,
  `IsUpgradingOrganization: False`, and
  `IsUpdatingServicePlan: False`, while two direct audit write attempts still
  return `InvalidOperationInDehydratedContextException`. The Purview Audit
  page says it cannot determine whether activity is being recorded, and a
  post-UI Exchange check confirms
  `UnifiedAuditLogIngestionEnabled: False`. This corrects the setup wizard's
  permission implication: the signed-in administrator does have the required
  `Audit Logs` role, so the blocker is inconsistent Exchange/Purview backend
  state rather than missing administrator permission.
- **Rollback:** Exchange organization customization has no rollback command.
  Unified audit can be disabled with
  `Set-AdminAuditLogConfig -UnifiedAuditLogIngestionEnabled $false`.
- **Follow-up:** Do not use unsupported workarounds or start the combined DSPM
  wizard. Allow tenant provisioning to converge and retry the authoritative
  audit write later. If Exchange continues to report both customized and
  dehydrated states, include the contradictory command evidence in a Microsoft
  support case.

## 2026-10-08 16:30 EDT - Compare integration with Agent 365 quickstart

- **Status:** Succeeded
- **Scope:** Repository | Tenant | Runtime
- **Requested by:** User
- **Purpose:** Determine whether Microsoft's current Connect an Existing Agent
  quickstart identifies an onboarding step missing from this implementation.
- **Change:** Performed a read-only comparison of the official quickstart and
  SDK validation checklist with the deployed identity, S2S observability,
  runtime, permissions, licensing, and portal evidence. No repository,
  runtime, tenant, role, license, policy, or billing state changed.
- **Result:** The implementation follows the documented **standard agent**
  path: registered blueprint, Agent Identity, sponsor, S2S authentication,
  observability package, registered Agent Identity attribution, and root
  `invoke_agent` activity. Normal agent behavior, tool execution, metadata
  privacy, secret exclusion, and Admin Center Activity are validated. Work IQ,
  AI-teammate messaging, notifications, and local Agents Playground are not
  applicable to this standard S2S agent. Purview DLP is an optional,
  independently adopted capability requiring DSPM onboarding, licensing,
  pay-as-you-go billing, and additional code integration; it is not a missing
  prerequisite for basic observability.
- **Validation:** Compared every applicable section of Microsoft's quickstart
  and validation checklist. The remaining failed required checks are
  destination-side: `CloudAppEvents` is still unavailable in Defender and
  Purview unified audit remains disabled because Exchange's write path
  inconsistently reports a dehydrated organization. Admin Center Activity
  proves accepted root telemetry.
- **Rollback:** Not applicable; read-only documentation comparison.
- **Follow-up:** Do not rerun broad setup or enable optional capabilities to
  mask destination provisioning failures. Retry Defender and Purview after
  propagation, then escalate the two specific backend blockers if they remain.

## 2026-10-08 16:52 EDT - Clarify Agents Toolkit requirement

- **Status:** Succeeded
- **Scope:** Workstation | Repository | Runtime
- **Requested by:** User
- **Purpose:** Determine whether an existing third-party agent must be
  scaffolded with Microsoft 365 Agents Toolkit to onboard to Agent 365.
- **Change:** Performed a read-only review of the downloaded
  `Agent365-LangChain-Guide-v3.1 (1).pdf`, Microsoft 365 Agents Toolkit
  guidance, the official Agent 365 existing-agent quickstart, and the current
  Python trading agent. Installed `pypdf` 6.19.0 only in session artifact
  storage to extract the 25-page PDF; no project dependency or runtime changed.
- **Result:** Microsoft 365 Agents Toolkit is not required for Agent 365
  identity, Registry, or S2S observability. It scaffolds and automates
  Microsoft 365/Teams-facing experiences such as Bot Framework messaging,
  application manifests and packages, local Agents Playground, provisioning,
  deployment, SSO, and channel UX. The trading agent already follows the
  supported standard-agent path through Microsoft Agent Framework plus manual
  Agent 365 identity and observability integration. The PDF describes a
  different AI-teammate path: Node.js LangChain on AWS, Teams messaging, an
  agent user, Frontier preview, and Work IQ MCP access.
- **Validation:** The trading agent is present in Agent Registry and Admin
  Center Activity without an Agents Toolkit project, directly proving Toolkit
  scaffolding is not an onboarding prerequisite. Official guidance supports
  both Skills-based and manual integration of existing agents.
- **Rollback:** Delete the session-only PDF extraction package and text
  artifact if no longer needed; no tenant or application state changed.
- **Follow-up:** Keep the existing Python runtime. Add an Agents Toolkit
  channel adapter or separately scaffolded Microsoft 365 app only if Teams,
  Outlook, Copilot, Adaptive Cards, delegated user SSO, or app-catalog
  distribution becomes a requirement. Do not expect Toolkit to fix Defender,
  Purview, or APIM authorization.

## 2026-10-08 17:40 EDT - Confirm Defender CloudAppEvents provisioning

- **Status:** Succeeded
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Confirm whether the previously unavailable Defender Advanced
  Hunting `CloudAppEvents` table has finished provisioning.
- **Change:** Reviewed the user-provided Defender query-history evidence for
  repeated `CloudAppEvents | take 1` schema checks. No tenant, query, policy,
  license, connector, or runtime state was changed.
- **Result:** The table now resolves. Query attempts at 17:38:19, 17:38:21,
  and 17:38:24 failed, while attempts beginning at 17:38:40 and continuing
  through 17:39:22 completed successfully. This clears the prior Defender
  table-provisioning blocker.
- **Validation:** Defender Advanced Hunting query history showed multiple
  consecutive completed executions with query times between 0.63 seconds and
  1 second.
- **Rollback:** Not applicable; read-only validation.
- **Follow-up:** Query recent `CloudAppEvents` records for the Trading Platform
  Agent Identity and inspect the available schema before finalizing the
  production hunting query. A completed `take 1` proves table availability but
  does not by itself prove that this agent's telemetry is present.

## 2026-10-08 17:43 EDT - Test Defender hunting CLI access

- **Status:** Partially succeeded
- **Scope:** Workstation | Tenant
- **Requested by:** User
- **Purpose:** Establish a faster command-line loop for Agent 365 Defender
  Advanced Hunting queries.
- **Change:** Used the existing authenticated Azure CLI session to submit the
  read-only query `CloudAppEvents | take 1` to Microsoft Graph
  `POST /v1.0/security/runHuntingQuery`. No package, application, permission,
  consent, role, or tenant configuration was changed. The temporary JSON
  request file was removed immediately.
- **Result:** Microsoft Graph accepted the endpoint and request format but
  returned `Forbidden` because the Azure CLI token lacks the required
  delegated `ThreatHunting.Read.All` scope. The signed-in administrator and
  tenant context were otherwise valid.
- **Validation:** The final Graph response explicitly identified
  `ThreatHunting.Read.All` as the missing required scope. Request ID
  `c230adf1-098b-406f-bfc5-8ac129bd9c93` at 2026-10-08 21:43:56 UTC.
- **Rollback:** Not applicable; read-only query attempt and temporary local
  payload cleanup only.
- **Follow-up:** Obtain explicit approval before adding delegated
  `ThreatHunting.Read.All`. Prefer a dedicated least-privilege CLI application
  for repeatable hunting, or continue using the Defender portal without a
  tenant permission change.

## 2026-10-08 17:45 EDT - Provision dedicated Defender hunting CLI

- **Status:** Succeeded
- **Scope:** Workstation | Tenant
- **Requested by:** User
- **Purpose:** Provide a fast, repeatable command-line workflow for validating
  Agent 365 telemetry in Microsoft Defender Advanced Hunting.
- **Change:** Create a single-tenant public-client application named
  `A365 Defender Hunting CLI - Local`, grant only delegated Microsoft Graph
  `ThreatHunting.Read.All`, and obtain administrator consent. Do not create a
  client secret, certificate, application permission, additional Graph scope,
  or Defender role assignment. Added `A365/query-defender.ps1` as a read-only
  query wrapper that reuses authentication within one PowerShell session.
- **Result:** Created application ID
  `9a65a06f-b725-4769-92e9-e262f763d3e4`, application object ID
  `0ce59406-d298-43e3-939b-5000c7e7ca9c`, and service-principal object ID
  `91891e16-d2d7-4880-b528-cc5ee7e8af1a`. Administrator consent was granted
  only for delegated `ThreatHunting.Read.All`; no credential was created.
  The Graph hunting endpoint returned the complete `CloudAppEvents` schema
  and zero rows for `CloudAppEvents | take 1`.
- **Validation:** Authenticate by device code through the dedicated client and
  execute `CloudAppEvents | take 1` using Microsoft Graph
  `/v1.0/security/runHuntingQuery`. Authentication and the Graph request
  succeeded. The local script passed PowerShell parser validation. Two later
  fresh-process script tests timed out waiting for device-code completion, so
  the script now intentionally reuses the Graph context in one open PowerShell
  session rather than relying on a persistent token cache.
- **Rollback:** Delete the dedicated app registration and its service
  principal; remove any local query script created for it.
- **Follow-up:** Use the script in one persistent PowerShell session to query
  for newly ingested Trading Platform Agent events. The current successful
  API response contained no `CloudAppEvents` rows.

## 2026-10-08 18:03 EDT - Test Defender ingestion through CLI

- **Status:** Partially succeeded
- **Scope:** Workstation | Tenant | Runtime
- **Requested by:** User
- **Purpose:** Determine whether recent Trading Platform Agent activity has
  reached Defender after `CloudAppEvents` became available.
- **Change:** Authenticated the dedicated hunting CLI by device code and ran a
  read-only, unfiltered `CloudAppEvents` query for the previous two hours.
  Checked the local health endpoint and recent container logs for A365
  authentication, exporter errors, and HTTP outcomes. No tenant or runtime
  configuration changed. Corrected only the local script's optional schema
  display formatting.
- **Result:** The Graph hunting request completed successfully but returned
  zero rows for the entire `CloudAppEvents` table in the two-hour window.
  Local A365 observability reports `enabled`, `ready`, `token_ready`, no last
  error, and content recording disabled. Three chat requests completed with
  HTTP 200 at 17:36:58, 17:37:31, and 17:39:36 EDT; one earlier request at
  17:27:30 returned HTTP 500. No A365, OTLP, telemetry-export, or exception
  error appeared in the targeted container-log search.
- **Validation:** Microsoft Graph returned a successful hunting response with
  no matching rows. The local `/health` response was healthy, the script
  passed PowerShell parser validation, and container access logs confirmed the
  three successful invocations. No prompt, response, account, holding, SQL, or
  other portfolio content was recorded.
- **Rollback:** Revert the schema-display formatting correction if needed; all
  other actions were read-only.
- **Follow-up:** Allow Defender ingestion to catch up after the newly
  provisioned table, then rerun the broad query before applying the Agent
  Identity filter. If the table remains empty after the documented propagation
  window, inspect exporter delivery diagnostics or escalate the tenant's Agent
  365-to-Defender routing.

## 2026-10-08 18:10 EDT - Validate exporter delivery to Agent 365

- **Status:** Succeeded
- **Scope:** Runtime | Tenant
- **Requested by:** User
- **Purpose:** Determine whether the empty Defender table is caused by span
  creation, exporter filtering, authentication, HTTP delivery, or downstream
  ingestion.
- **Change:** In an isolated process inside the existing API container, loaded
  the deployed metadata-only A365 configuration, acquired the Agent Identity
  token, created one controlled `InvokeAgent` span with marker
  `defender-debug-44041021-8e07-4bca-8283-3997fbc4a8a5`, and force-flushed the
  exporter. Enabled targeted exporter debug logging only for this process. No
  prompt, response, portfolio data, credential, or token was logged or
  exported.
- **Result:** The span was eligible and partitioned under tenant
  `00648bab-6c91-4292-9a2a-2297df511222` and Agent Identity
  `7f2edbcc-8375-4d1d-a430-93c14e8db94e`. The exporter sent one 1,614-byte
  span to the Agent 365 S2S OTLP endpoint and received HTTP 200. The response
  reported zero rejected spans and sink status `sent` for `flashpoint`,
  `sentinel`, and `esp`.
- **Validation:** Agent 365 correlation ID
  `6edd2434-0d52-4235-b441-072f332cbee8`; exported span ID
  `1ce11f1271d9368a`. Token readiness and metadata-only privacy status were
  healthy in the isolated process.
- **Rollback:** Not applicable; this created one intentional metadata-only
  validation span and made no configuration change.
- **Follow-up:** Query Defender for the marker, Agent Identity, span ID, or
  correlation ID after downstream indexing. If the event does not arrive, use
  the HTTP 200 response and sink statuses to escalate Agent 365-to-Defender
  routing rather than changing application authentication or instrumentation.

## 2026-10-08 18:18 EDT - Isolate downstream Defender routing failure

- **Status:** Failed
- **Scope:** Workstation | Tenant | Runtime
- **Requested by:** User
- **Purpose:** Complete Microsoft's documented post-export verification and
  determine whether the controlled Agent 365 span reached Defender.
- **Change:** After the documented approximately five-minute indexing wait,
  queried `CloudAppEvents` across 24 hours using the controlled marker,
  registered Agent Identity, exported span ID, and ingestion correlation ID.
  Replaced the local helper's Microsoft Graph module login with direct Entra
  device-code authentication so it uses the full server-defined sign-in window
  and retains the access token only in the current PowerShell process. No token
  is printed or written to disk.
- **Result:** The post-wait Microsoft Graph hunting query completed
  successfully but returned no matching row. The preceding ingestion response
  had HTTP 200, `partialSuccess.rejectedSpans: 0`, and `sent` status for all
  returned sinks. Microsoft documentation says to inspect those fields, wait
  approximately five minutes, and then query Defender; all documented
  application-side verification steps now pass, but Defender indexing does
  not.
- **Validation:** Queried independently by marker
  `defender-debug-44041021-8e07-4bca-8283-3997fbc4a8a5`, Agent Identity
  `7f2edbcc-8375-4d1d-a430-93c14e8db94e`, span ID
  `1ce11f1271d9368a`, and correlation ID
  `6edd2434-0d52-4235-b441-072f332cbee8`. The query helper passed PowerShell
  parser and whitespace validation.
- **Rollback:** Revert the local device-flow helper changes if persistent
  in-process token reuse is not wanted; delete the dedicated hunting CLI app
  to remove its delegated permission. The intentional validation span cannot
  be deleted from Microsoft's telemetry pipeline.
- **Follow-up:** Escalate Agent 365-to-Defender downstream routing/indexing to
  Microsoft with the tenant ID, Agent Identity, UTC export time, correlation
  ID, span ID, HTTP response sink statuses, successful Graph query evidence,
  and the earlier `CloudAppEvents` provisioning transition. Do not change the
  working exporter or broaden permissions.

## 2026-10-09 08:59 EDT - Confirm overnight Defender non-arrival

- **Status:** Failed
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Determine whether additional overnight propagation resolved the
  missing Agent 365 events in Defender.
- **Change:** The administrator reran the dedicated read-only Defender hunting
  CLI after an overnight wait. No tenant, application, permission, runtime, or
  query-helper configuration changed.
- **Result:** Device-code authentication and the Microsoft Graph hunting query
  completed successfully, but the query still returned no matching
  `CloudAppEvents` rows. The delay now substantially exceeds Microsoft's
  documented approximately five-minute verification interval.
- **Validation:** Successful CLI output explicitly reported
  `Query completed successfully with no matching rows.` This follows the
  controlled exporter response that reported HTTP 200, zero rejected spans,
  and `sent` status for every returned sink.
- **Rollback:** Not applicable; read-only verification.
- **Follow-up:** Open a Microsoft support case for Agent 365-to-Defender
  downstream routing/indexing. Include correlation ID
  `6edd2434-0d52-4235-b441-072f332cbee8`, span ID
  `1ce11f1271d9368a`, Agent Identity
  `7f2edbcc-8375-4d1d-a430-93c14e8db94e`, tenant ID
  `00648bab-6c91-4292-9a2a-2297df511222`, the sink-status response, the
  `CloudAppEvents` provisioning transition, and both immediate and overnight
  successful no-result queries.

## 2026-10-09 09:02 EDT - Revalidate deployed LOB collection configuration

- **Status:** Succeeded
- **Scope:** Runtime | Repository
- **Requested by:** User
- **Purpose:** Confirm that the live LOB container, rather than only the source
  tree or isolated validation process, is correctly configured to emit Agent
  365 observability telemetry.
- **Change:** Performed read-only checks of the running container's non-secret
  A365 environment, installed package versions, startup command, and SHA-256
  hashes for the deployed observability and API modules. No secret value,
  token, prompt, response, or portfolio content was read or recorded.
- **Result:** The container has A365 observability enabled; tenant, blueprint,
  and Agent Identity IDs match the registered objects; content recording is
  disabled; and the channel is `local-cli`. The deployed
  `observability/a365.py` and `api/main.py` hashes exactly match the workspace.
  The container runs `microsoft-opentelemetry` 1.3.9 and the pinned Microsoft
  Agent Framework packages. Queue, delay, timeout, S2S endpoint, input
  suppression, and exporter-enable values that are absent from the environment
  are supplied explicitly or defaulted safely by `A365Settings` and
  `use_microsoft_opentelemetry`.
- **Validation:** Both deployed-file hashes matched their local counterparts.
  The controlled span executed this exact deployed code and received HTTP 200,
  zero rejected spans, and `sent` for all returned sinks. The live health
  endpoint reports A365 enabled, ready, token-ready, no last error, and content
  recording disabled.
- **Rollback:** Not applicable; read-only validation.
- **Follow-up:** Treat the empty Defender table as a tenant downstream
  routing/indexing issue. Do not change the validated LOB exporter
  configuration or broaden its permissions unless Microsoft identifies a
  specific unsupported setting.

## 2026-10-09 09:12 EDT - Test complete invoke-agent attribute set

- **Status:** Failed
- **Scope:** Runtime | Tenant
- **Requested by:** User
- **Purpose:** Test whether fields newly documented as mandatory explain why
  accepted Agent 365 spans do not appear in Defender.
- **Change:** Emit one synthetic metadata-only `invoke_agent` span containing
  the current required identity, conversation, channel, caller, client/server
  endpoint, input-envelope, and output-envelope fields. Use only the literal
  text `[REDACTED]`, the known administrator object ID, loopback client
  address, and local service endpoint; do not include a prompt, response,
  portfolio identifier, SQL, credential, or token. Capture the ingestion
  response and query Defender after the documented indexing interval.
- **Result:** The synthetic span contained every field currently documented as
  mandatory for a root `invoke_agent`: operation, tenant, agent ID/name,
  blueprint ID, conversation, channel, client address, server address/port,
  user ID, and redacted input/output message envelopes. Agent 365 accepted it
  with HTTP 200, zero rejected spans, and `sent` for all returned sinks.
  Correlation ID `d6bbe952-c35c-4e1f-bf3f-b610aac40041`; span ID
  `6c86212258f424b0`. After the documented indexing wait, the Defender query
  still returned no matching row.
- **Validation:** Compare the sanitized emitted attribute set with Microsoft's
  October 2026 attribute reference, require HTTP 200 with zero rejected spans,
  then query by Agent Identity and unique marker
  `complete-attrs-67ce0709-78b0-4cb3-b90c-c8ef5141d64f`. Local capture
  confirmed every mandatory field was present without printing message
  content.
- **Rollback:** Not applicable; the synthetic validation span cannot be
  removed from Microsoft's telemetry pipeline but contains no business
  content.
- **Follow-up:** Missing fields in the production metadata-only span are a
  conformance and experience-quality gap, but not the cause of the empty
  Defender table because the complete synthetic span also failed to appear.
  Correct the canonical channel and endpoint fields separately; review privacy
  before exporting user identity, client IP, or message envelopes. Escalate
  downstream routing with both ingestion correlation IDs.

## 2026-10-09 09:20 EDT - Reconcile design with current documentation

- **Status:** Succeeded
- **Scope:** Repository | Runtime | Tenant
- **Requested by:** User
- **Purpose:** Reassess the end-to-end design, implementation, and current
  Microsoft documentation before escalating the Defender issue.
- **Change:** Performed a read-only comparison against Microsoft's October
  2026 OpenTelemetry Distro, S2S authentication, attribute reference,
  observability concepts, direct OTel troubleshooting, CloudAppEvents, and
  Defender Advanced Hunting permission documentation. Inspected sanitized live
  span attributes and installed Agent Framework instrumentation.
- **Result:** The two-step `fmi_path` token exchange, app-only validation,
  token caching, S2S endpoint, registered Agent Identity, exporter enablement,
  batching, root scope, baggage identity, Agent Framework instrumentor, and
  metadata privacy controls align with the supported design. Global
  Administrator grants full Advanced Hunting read access, so Defender RBAC
  does not explain an empty result. Agent 365 documentation requires Purview
  auditing only for Purview and Defender Advanced Hunting access for Defender;
  it does not list a traditional Cloud Apps connector or Purview content
  collection policy as an OTel prerequisite.
- **Validation:** The deployed package exposes the documented
  `agent_framework` instrumentor. Source hashes match the running container.
  Both the production-shaped span and a fully populated synthetic span were
  accepted and routed to all returned sinks, while immediate, post-wait, and
  overnight Defender queries remained empty.
- **Rollback:** Not applicable; documentation and read-only implementation
  review only.
- **Follow-up:** Make the low-risk channel/endpoint metadata corrections for
  current-schema conformance, retain metadata-only message suppression unless
  privacy policy changes, and open Microsoft support for downstream Defender
  routing using both correlation IDs.

## 2026-10-09 09:28 EDT - Deploy metadata conformance correction

- **Status:** Partially succeeded
- **Scope:** Repository | Runtime
- **Requested by:** User
- **Purpose:** Bring the production metadata-only root span into conformance
  with the current canonical Agent 365 channel and service-endpoint fields
  before the final Defender retest.
- **Change:** Replace the obsolete `gen_ai.conversation.channel` attribute with
  SDK-generated `microsoft.channel.name`, add non-sensitive server address and
  port metadata, preserve prompt/response suppression, rebuild the local API
  image, and restart only the local API container. Do not add caller identity,
  client IP, prompt, response, tool arguments, or portfolio content.
- **Result:** The image was rebuilt and only the API container was recreated.
  The API container is running image
  `sha256:8de6334dc1d91f03cd9603578b5adf30f4ea8ecb2f4ce65d79451ab67381fbc3`.
  PostgreSQL and Adminer were not recreated. Exact live-request exporter
  acceptance and Defender indexing remain unverified.
- **Validation:** On 2026-10-09 at 14:19 EDT, SHA-256 hashes for
  `observability/a365.py`, `api/main.py`, and `main.py` matched between the
  workspace and running API container. The container is healthy and its live
  environment contains `A365_CHANNEL_NAME=local-cli`,
  `A365_RECORD_CONTENT=false`, `A365_SERVER_ADDRESS=localhost`, and
  `A365_SERVER_PORT=8989`. Focused tests, sanitized span inspection, healthy
  startup, and successful chat invocation passed earlier. Exact live-request
  HTTP 200 exporter evidence and a matching Defender row are still required.
- **Rollback:** Rebuild the prior source revision and restart only the local
  API container.
- **Follow-up:** Capture one live request's exporter response and query Defender
  using its correlation identifiers after the indexing interval.

## 2026-10-09 14:28 EDT - Add pseudonymous user attribution

- **Status:** Partially succeeded
- **Scope:** Repository | Runtime
- **Requested by:** User
- **Purpose:** Distinguish Agent 365 invocations made by different authenticated
  Entra users without exporting names, email addresses, raw access tokens, or
  raw Entra tenant and object IDs.
- **Change:** Cryptographically validate the console bearer token against the
  configured Entra tenant and APIM audience, derive a stable SHA-256 identifier
  from the validated `tid` and `oid` claims, and emit only that pseudonymous
  identifier as the root span `user.id`. Add focused tests and update the
  directly related Agent 365 privacy documentation. Do not install or upgrade
  dependencies.
- **Result:** Added signature, issuer, audience, expiry, tenant, and object-ID
  validation for device-code bearer tokens while Agent 365 is enabled. The API
  now hashes the validated `tid` and `oid` values and supplies only the
  resulting 64-character SHA-256 value as root span `user.id`. Updated the
  privacy documentation, rebuilt image
  `sha256:85e7cca402f0e4b62e07f79ec3e4d70c8a133698b9ecf15d8b7ef77ff934a6fb`,
  and recreated only the API container. An initial build command failed
  without changing runtime state because it looked for `.env` at the repository
  root; rerunning from the application directory succeeded. No dependency was
  installed or upgraded. The first live request returned HTTP 401 because the
  validator accepted only the configured `api://<application-id>` audience
  form. Corrected it to accept both that identifier URI and the equivalent
  configured application GUID, and changed 401 details to identify only a safe
  validation category without exposing tokens or claims. The next live request
  passed user-token validation and reached APIM, where it failed with HTTP 403
  because the Windows-hosted API resolved the private-only APIM hostname to its
  public address. Added an approved Windows hosts mapping to `10.100.2.4`.
  During repair, an elevated command unexpectedly truncated the hosts file.
  No backup existed, so it was immediately restored as a valid minimal file
  containing localhost plus the previously observed `10.100.1.4` APIM mapping
  and the approved `10.100.2.4` mapping. Any unobserved prior custom entries
  could not be recovered.
- **Validation:** The 23 focused authentication and Agent 365 observability
  tests passed. Changed Python files compiled successfully. The rebuilt API
  container started successfully and became healthy, while the existing
  PostgreSQL container and persistent volume were retained. The broader
  `test_api.py` suite could not collect because the pre-existing local MCP
  package lacks `streamable_http_client`; dependencies were intentionally left
  unchanged. After the audience correction, 24 focused tests passed. A new live
  request proved that bearer-token validation succeeds. Windows DNS now
  resolves the active APIM hostname to `10.100.2.4`; an HTTPS request reached
  that private address and returned HTTP 404 for the root path, confirming
  private routing and TLS. The user then retried from the signed-in console and
  confirmed that the agent replied successfully. Sanitized span inspection and
  Defender indexing are still required.
- **Rollback:** Remove inbound identity validation and the `user.id` span
  attribute, rebuild the prior API image, and recreate only the API container.
- **Follow-up:** Send one request from each signed-in console, capture the
  sanitized root spans, and confirm that `user.id` is stable within one user,
  differs between users, and contains neither raw Entra identifier.

## 2026-10-09 16:44 EDT - Capture live exporter acceptance

- **Status:** Succeeded
- **Scope:** Repository | Runtime | Tenant
- **Requested by:** User
- **Purpose:** Determine whether successful local agent requests are exported
  from the actual API process before escalating the still-empty Defender
  `CloudAppEvents` table as a downstream routing or indexing failure.
- **Change:** Add a temporary, opt-in exporter diagnostic that logs only span
  counts, destination, HTTP status, correlation ID, and the bounded Agent 365
  sink-status response. Do not log span payloads, tokens, prompts, responses,
  pseudonymous user IDs, or portfolio content.
- **Result:** A live local API request created three recording spans and forced
  the configured SDK tracer provider to export them. Agent 365 returned HTTP
  200 with correlation ID `b8b72f59-0357-4533-b53f-11d3947111e4`; the bounded
  response reported the visible span sink statuses as `sent` for Flashpoint,
  Sentinel, and ESP. The root `InvokeAgent` span ID was
  `9ab6ae0854d39c9c`. The batch contained three spans and was 27,381 bytes.
  Removed the automatic diagnostic switch from `startapi.bat` after capture;
  the diagnostic code remains opt-in for future investigations.
- **Validation:** The live API printed `recording=True`, used an SDK
  `TracerProvider`, returned `force_flush=True`, received exporter HTTP 200,
  and completed the `/chat` request with HTTP 200. Twenty-six focused Agent 365
  and identity tests passed before the live capture.
- **Rollback:** Disable the diagnostic environment switch and remove the
  temporary launcher setting after capturing the response.
- **Follow-up:** Query Defender after the indexing interval. If
  `CloudAppEvents` remains empty, escalate to Microsoft with the correlation
  ID, span ID, tenant ID, agent identity, timestamp, and prior controlled
  export evidence because the remaining failure is downstream of successful
  Agent 365 ingestion.

## 2026-10-09 17:17 EDT - Enable full observability content

- **Status:** Partially succeeded
- **Scope:** Repository | Runtime
- **Requested by:** User
- **Purpose:** Make Agent 365 useful for behavioral investigation by recording
  what users ask, how the agent responds, and available tool/inference content
  instead of limiting telemetry to metadata and aggregate metrics.
- **Change:** Enable full Agent 365 content recording in every environment,
  pass prompts and responses into the root `InvokeAgent` span, disable the
  Distro's invocation-input suppression, and enable sensitive-data capture.
  Update configuration and privacy documentation to disclose that portfolio
  prompts, responses, account identifiers, holdings, SQL, and tool data may be
  transmitted to Microsoft observability services.
- **Result:** Full-content mode is implemented and active in the local API.
  Prompts and responses are passed into the root `InvokeAgent` scope, invocation
  input suppression is disabled, and sensitive-data instrumentation is enabled.
  Local and Docker launch configuration now sets
  `A365_RECORD_CONTENT=true`. This does not prove that Microsoft exposes the
  captured content or optional token counts in a customer-facing Agent 365
  surface; the Registry Activity page remains an aggregate dashboard.
- **Validation:** Twenty-seven focused tests passed, including prompt and
  response recording. Changed Python files compiled successfully. The live API
  process started at 17:24 EDT and `/health` reports Agent 365 `ready`,
  `token_ready=true`, and `content_recording=true`. A live payload inspection
  and documented UI/query surface for prompts, responses, and token counts
  remain unverified.
- **Rollback:** Restore `A365_RECORD_CONTENT=false`, prompt suppression, and
  `enable_sensitive_data=False`, then restart the API.
- **Follow-up:** Inspect one sanitized live export payload to establish which
  content and token attributes are emitted, then verify only documented
  customer-facing Agent 365, Defender, or Purview surfaces. Do not claim that
  enabling capture makes those fields visible in the Registry Activity page.

## 2026-10-09 18:26 EDT - Distinguish Defender alert pipelines

- **Status:** Succeeded
- **Scope:** Tenant | Runtime
- **Requested by:** User
- **Purpose:** Determine whether a Defender
  `LLM Reconnaissance Attempt Detected (Preview)` incident proves that Agent
  365 telemetry is present in `CloudAppEvents`.
- **Change:** Read-only review of the incident screenshot, event timing, current
  Defender alert documentation, and Advanced Hunting table responsibilities.
- **Result:** The incident proves that Defender received and analyzed the
  system-prompt reconnaissance interaction, but it does not prove Agent 365
  OpenTelemetry reached `CloudAppEvents`. The incident activity occurred at
  approximately 16:02 EDT, before the confirmed 16:58 Agent 365 exporter
  capture and before full-content mode was enabled. Its title maps to Defender
  for Cloud AI workload alert `AI.Azure_LLMReconnaissance`, whose alert records
  are queried through `AlertInfo` and `AlertEvidence`. This is a separate
  detection pipeline from Agent 365 observability records in
  `CloudAppEvents`.
- **Validation:** `CloudAppEvents | take 1` is valid KQL and would return one
  accessible retained row if that table contained any. Defender incidents can
  coexist with an empty `CloudAppEvents` result because `AlertInfo` and
  `AlertEvidence` are separate Advanced Hunting tables and data pipelines.
- **Rollback:** Not applicable.
- **Follow-up:** Query the reconnaissance incident through `AlertInfo` and
  `AlertEvidence`; continue using the documented Agent 365 query separately
  for `CloudAppEvents`.

## 2026-10-12 09:40 EDT - Relocate portfolio manager under Wealth

- **Status:** Partially succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Organize the portfolio-manager agent beneath its owning Contoso Bank
  line of business.
- **Change:** Move `lob/ai-agent-starter-portfolio-manager/` to
  `lob/wealth/ai-agent-starter-portfolio-manager/` and update repository
  references to the old path. No tenant, Azure, identity, permission, license,
  or runtime objects will be changed.
- **Result:** The complete project, including its current modified, untracked,
  and local environment files, was moved to
  `lob/wealth/ai-agent-starter-portfolio-manager/`. Active paths in the API
  launcher, chat launcher, and Agent 365 verification runbook now use the new
  location. No tenant, Azure, identity, permission, license, or runtime object
  was changed.
- **Validation:** Confirmed the old directory is absent, the new directory and
  its Python virtual environment exist, and active launcher and runbook
  references use the new path. The user did not authorize the proposed
  targeted test run, so test validation was not performed.
- **Rollback:** Move the directory back to
  `lob/ai-agent-starter-portfolio-manager/` and restore the updated path
  references.
- **Follow-up:** Run the relocated project's tests when authorized.

## 2026-10-12 09:44 EDT - Relocate Agent 365 folder to repository root

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Make Agent 365 documentation and operator tooling shared
  repository-level resources rather than nesting them under the Wealth
  portfolio-manager project.
- **Change:** Move
  `lob/wealth/ai-agent-starter-portfolio-manager/A365/` to repository-root
  `A365/`, then update active links, commands, and relative paths affected by
  the relocation. No tenant, Azure, identity, permission, license, or runtime
  objects will be changed.
- **Result:** Moved all Agent 365 documentation and operator tooling to
  repository-root `A365/`. Updated the Wealth portfolio-manager README links
  and changed the Defender query instructions to run from the repository root.
  No tenant, Azure, identity, permission, license, or runtime object was
  changed.
- **Validation:** Confirmed the old directory is absent, root `A365/` exists
  with all 12 source items, and the only remaining references to the old path
  are this immutable change record's change and rollback descriptions.
- **Rollback:** Move root `A365/` back to
  `lob/wealth/ai-agent-starter-portfolio-manager/A365/` and restore updated
  references.
- **Follow-up:** None.

## 2026-10-12 15:17 EDT - Summarize Trading Platform Agent onboarding

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Explain how Microsoft Agent 365 was added to the existing
  Trading Platform Agent.
- **Change:** Performed a read-only review of the Agent 365 change ledger and
  the current identity, runtime observability, API, configuration, and
  validation code. No tenant, Azure, runtime, identity, permission, license,
  dependency, or application behavior was changed.
- **Result:** Confirmed that the existing Python and Docker agent was preserved
  and onboarded through the standard existing-agent path: Agent Identity
  Blueprint and BlueprintPrincipal provisioning, sponsored Agent Identity and
  Registry registration, app-only S2S token exchange, Microsoft OpenTelemetry
  initialization, registered identity attribution on the `ChatAgent`, one
  root `InvokeAgent` scope per chat request, pseudonymous user attribution,
  feature-gated content capture, health reporting, and graceful flushing.
  Microsoft 365 Agents Toolkit, hosted-agent conversion, Work IQ, messaging
  endpoints, and broad Microsoft 365 data permissions were not required.
- **Validation:** Correlated the historical provisioning and telemetry entries
  with the current `agents/trading_platform_agent.py`,
  `observability/a365.py`, `api/main.py`, `api/user_identity.py`, runtime
  configuration, dependency pin, and documented live exporter acceptance.
- **Rollback:** Not applicable; read-only investigation.
- **Follow-up:** None.

## 2026-10-12 15:21 EDT - Document existing-agent onboarding

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Add the implemented Trading Platform Agent onboarding details to
  the shared Agent 365 onboarding guide.
- **Change:** Populate `A365/onboarding_agents.md` with the selected
  existing-agent architecture, tenant identity and Registry sequence, runtime
  S2S authentication and observability integration, privacy controls,
  configuration, validation evidence, exclusions, and rollback guidance. Link
  to the detailed provisioning and observability runbooks rather than copying
  secret-bearing or environment-specific operator data.
- **Result:** Populated `A365/onboarding_agents.md` with the implemented
  standard existing-agent architecture and reusable onboarding sequence. The
  guide now covers identity hierarchy and sponsorship, Registry registration,
  protected configuration, the two-step app-only token exchange, registered
  runtime ID binding, Microsoft OpenTelemetry initialization, root
  `InvokeAgent` scopes, pseudonymous user attribution, content-policy choices,
  validation boundaries, explicitly excluded capabilities, reuse guidance,
  and rollback. It links to the authoritative provisioning, observability, and
  verification runbooks and contains no secret or environment-specific
  credential values.
- **Validation:** `git diff --check` passed for the onboarding guide and
  ledger. Confirmed that every referenced repository document and
  implementation path exists.
- **Rollback:** Restore `A365/onboarding_agents.md` to its previous empty
  state.
- **Follow-up:** None.

## 2026-10-12 15:23 EDT - Document Agent 365 CLI usage

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Provide a complete getting-started and in-depth operating guide
  for the Agent 365 CLI.
- **Change:** Populate `A365/agent365_cli.md` with current installation,
  authentication, roles, configuration modes, setup workflows, command
  families, generated-artifact handling, diagnostics, automation, cloud,
  security, troubleshooting, cleanup, and repository-specific guidance.
  Reconcile current Microsoft Learn references with the CLI behavior validated
  during Trading Platform Agent onboarding. Do not run the CLI or change
  tenant, identity, permission, Azure, license, or runtime state.
- **Result:** Populated `A365/agent365_cli.md` with a comprehensive guide to
  CLI purpose and safety, prerequisites and roles, installation and updates,
  Microsoft-managed and tenant-owned client authentication, first-use checks,
  config-free and file-based setup, generated-file security, granular and
  full setup, Entra inspection, MCP development, Microsoft 365 publishing,
  redacted diagnostic logs, granular and full cleanup, CI/CD, government
  clouds, troubleshooting, support escalation, and the repository's validated
  registration-only pattern. Added the guide to the `A365/readme.md`
  documentation map. No CLI command that authenticates or changes tenant,
  Azure, identity, permission, license, or runtime state was run.
- **Validation:** Reconciled the guide with current Microsoft Learn command
  references and the installed Agent 365 CLI `1.1.226` help for top-level,
  setup, query-entra, logs, and cleanup commands. `git diff --check` passed,
  all linked local documents exist, and the A365 documentation map contains
  the new guide.
- **Rollback:** Restore `A365/agent365_cli.md` to its previous empty state.
- **Follow-up:** Recheck command syntax and role requirements when upgrading
  the CLI because Agent 365 remains version-sensitive.

## 2026-10-12 15:55 EDT - Diagnose model request timeouts

- **Status:** Succeeded
- **Scope:** Workstation | Runtime | Azure
- **Requested by:** User
- **Purpose:** Determine why the local Trading Platform Agent returned HTTP 500
  after Azure OpenAI model requests timed out.
- **Change:** Performed read-only checks of the active Windows API process,
  local API and Agent 365 health, Docker state, sanitized model endpoint
  configuration, DNS, TCP connectivity, local routing, Azure VPN connection,
  APIM networking state, private endpoint address, VPN traffic counters, and
  IPsec traffic selectors. No process, container, tunnel, tenant, Azure,
  identity, permission, license, secret, or configuration was changed.
- **Result:** The Windows-hosted API on port 8989 is healthy, its database is
  connected, and Agent 365 observability is enabled, token-ready, and has no
  reported error. The Docker API container is stopped and is not serving the
  request. The configured APIM hostname resolves to approved private endpoint
  `10.100.2.4`, but TCP 443 and an eight-second HTTPS probe time out. Azure
  reports the VPN connection as `Connected`, APIM provisioning as
  `Succeeded`, public access as disabled, and the private endpoint as
  approved. VPN ingress and egress counters did not change during the failed
  probe, proving the packets did not reach the Azure VPN gateway. Azure
  selectors correctly advertise on-premises `192.168.50.0/24` and use the
  expected AES256/SHA256/DHGroup14/no-PFS policy. The model timeout is
  downstream of an on-premises IPsec child-SA or forwarding-path failure, not
  Agent 365, the Python API, APIM provisioning, or model service health.
- **Validation:** `GET /health` returned healthy with Agent 365 `ready`;
  `Resolve-DnsName` returned `10.100.2.4`; `Test-NetConnection` and `curl`
  could not connect to port 443; the controlled request produced zero-byte
  Azure VPN ingress and egress deltas; Azure Resource Health reported the
  model resource available.
- **Rollback:** Not applicable; read-only investigation.
- **Follow-up:** The user approved restarting the OpenWrt 25.x strongSwan
  service. Two noninteractive SSH attempts failed because the router requires
  password authentication and this session has no router credential or SSH
  key. A final read-only probe still timed out with zero Azure VPN counter
  movement. A 16:36 EDT recheck confirmed that the API, database, agent, and
  Agent 365 remained healthy and ready, but private APIM TCP 443 still timed
  out after eight seconds without connecting. In the user's authenticated
  router console, run
  `/etc/init.d/swanctl restart`, `swanctl --load-all`, and
  `swanctl --list-sas`; then verify an installed child SA for
  `192.168.50.0/24 === 10.100.0.0/16` before repeating TCP and `/chat`
  validation.

## 2026-10-12 16:37 EDT - Remove conflicting P2S route

- **Status:** Succeeded
- **Scope:** Workstation | Runtime
- **Requested by:** User
- **Purpose:** Restore the Trading Platform Agent's private APIM path through
  the approved OpenWrt Site-to-Site VPN.
- **Change:** Remove the active `10.0.0.0/8` route from Windows interface 48,
  `MSFT-AzVPN-Manual`, because it captures traffic for APIM private endpoint
  `10.100.2.4` and bypasses the OpenWrt S2S gateway. Do not modify the Azure
  VPN gateway, APIM, OpenWrt configuration, tenant objects, permissions,
  identities, licenses, or application code.
- **Result:** Used the user-shared authenticated OpenWrt LuCI session to
  restart only the enabled `swanctl` service. Router logs confirmed successful
  PSK authentication, an established IKE SA, and an established CHILD_SA for
  `192.168.50.0/24 === 10.100.0.0/16`. Traffic still failed because Windows
  selected disconnected point-to-site interface `MSFT-AzVPN-Manual` with
  source `100.96.192.125` for both private APIM and Azure management traffic.
  Disconnected the P2S session, then removed all stale IPv4 and IPv6 routes
  owned by interface 48 with an elevated, session-only script. The temporary
  script was deleted. Route selection now uses Wi-Fi address
  `192.168.50.176` and OpenWrt gateway `192.168.50.1`. No Azure, tenant,
  application, permission, identity, license, or source-code state changed.
- **Validation:** Private APIM returned the expected unauthenticated root HTTP
  404 from `10.100.2.4` with a 54 ms connection time. Azure reported the S2S
  VPN `Connected`. Azure CLI token acquisition succeeded after the stale P2S
  routes were removed. An authenticated end-to-end `POST /chat` returned HTTP
  200 from `TradingPlatformAgent` with the exact response
  `connectivity restored`.
- **Rollback:** Restore the route with
  `New-NetRoute -InterfaceIndex 48 -DestinationPrefix 10.0.0.0/8 -NextHop
  0.0.0.0 -RouteMetric 256` or reconnect the `MSFT-AzVPN-Manual` P2S client.
- **Follow-up:** Keep `MSFT-AzVPN-Manual` disconnected while using the on-prem
  S2S path. If it is reconnected, review its advertised routes so it does not
  recapture `10.100.0.0/16` or Azure public management endpoints.

## 2026-10-13 16:47 EDT - Grant Purview insider-risk alert access

- **Status:** Succeeded
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Allow the current operator to view Insider Risk Management
  alerts surfaced from Purview DSPM agent activity.
- **Change:** Added `Jim Plunkett`
  (`admin@MngEnvMCAP623732.onmicrosoft.com`) to the built-in Microsoft Purview
  `Insider Risk Management Analysts` role group at organization scope with no
  expiration. No other role groups, administrative units, policies, licenses,
  identities, or application settings were changed.
- **Result:** The role group member count changed from zero to one.
- **Validation:** Microsoft Purview **My permissions** listed
  `Insider Risk Management Analysts` for the signed-in user.
- **Rollback:** Remove `Jim Plunkett` from the `Insider Risk Management
  Analysts` role group in Microsoft Purview **Settings > Roles and scopes >
  Role groups**.
- **Follow-up:** Allow up to 30 minutes for all Purview services to recognize
  the assignment.

## 2026-10-13 16:57 EDT - Trace Trading Platform Agent into Purview

- **Status:** Succeeded
- **Scope:** Tenant | Runtime
- **Requested by:** User
- **Purpose:** Determine why recent Trading Platform Agent tests were not
  visible in Purview dashboards.
- **Change:** Performed read-only inspection of DSPM AI observability,
  Activity Explorer, effective role assignments, and Microsoft Purview
  documentation. No tenant, policy, identity, license, runtime, or application
  state changed.
- **Result:** Activity Explorer contains recent `AI Interaction` /
  `Invoke Agent` records from `Local-cli`, including an October 13, 2026
  20:23 UTC event attributed to `TradingPlatformAgent`. The record reports
  workload `Agent365`, agent participant ID
  `7f2edbcc-8375-4d1d-a430-93c14e8db94e`, and instance ID
  `341ff526-fa67-4487-a028-5d61dd6e5a92`, but reports user `N/A`, an all-zero
  Agent ID, and `Related activity not found`. AI observability reports 356
  cloud agents, zero local agents, zero AI apps, and zero risky interactions.
  The classic DSPM policy list contains zero policies.
- **Validation:** Opened the 20:23 UTC Activity Explorer record and verified
  its activity, location, workload, participant, and correlation fields.
  Microsoft documentation confirms custom enterprise AI app analytics require
  the KYD collection policy and that reports require roughly 24 hours after
  policy activation.
- **Rollback:** Not applicable; read-only investigation.
- **Follow-up:** Enable the documented custom-AI policies before expecting
  sensitive/risky analytics or alerts: `Secure interactions from enterprise
  apps (preview)`, `Control Unethical Behavior in AI`, and `Detect risky AI
  usage`. Separately correct runtime identity/correlation so exported events
  contain a real user or pseudonymous user, a nonzero Agent ID, and related
  interaction activity.

## 2026-10-13 17:04 EDT - Enable detect-only Purview AI policies

- **Status:** Partially succeeded
- **Scope:** Tenant
- **Requested by:** User
- **Purpose:** Collect enterprise AI prompt and response activity and detect
  potentially unethical interactions without blocking users.
- **Change:** Enabled the Purview recommendations `Secure interactions from
  enterprise AI apps` and `Detect unethical behavior in AI apps` after the
  user separately approved the disclosed pay-as-you-go billing for each
  policy and the tenant-wide scope and reviewer assignment for Communication
  Compliance. Retained the existing `Risky AI usage quick policy -
  10/13/2026`. No blocking DLP actions or Defender custom detection were
  created because `CloudAppEvents` returned zero rows.
- **Result:** Created `DSPM for AI - Capture interactions for enterprise AI
  apps` in audit mode with pay-as-you-go billing; its status is `On`. Created
  tenant-wide Communication Compliance policy `DSPM for AI - Unethical
  behavior in AI apps`, with `Jim Plunkett` as reviewer; its status is
  `Activating`. The existing Insider Risk Management policy remains `On`.
- **Validation:** The DSPM for AI policy list contains three policies:
  enterprise interaction capture (`On`), risky AI usage (`On`), and unethical
  behavior detection (`Activating`). Defender Advanced Hunting successfully
  resolved `CloudAppEvents | take 1` but returned zero rows for the last seven
  days, so no nonfunctional custom detection was created.
- **Rollback:** Disable or delete the two newly created policies from their
  corresponding Purview solution areas.
- **Follow-up:** Wait up to one hour for Communication Compliance activation
  and at least 24 hours for DSPM reports. Then generate synthetic test
  interactions, verify Purview detections, and query Defender
  `CloudAppEvents` before creating a custom detection rule. If the
  Communication Compliance policy reaches `On`, update this entry to
  `Succeeded`.

## 2026-10-13 18:00 EDT - Publish current repository changes

- **Status:** Succeeded
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Publish the complete current worktree to the GitHub `main`
  branch.
- **Change:** Stage, commit, and push all current tracked and untracked
  changes, including Agent 365 documentation, the Agent 365 change ledger,
  the compiled mapping-storage template, and the APIM policy copy.
- **Result:** Created commit `05d2328` (`Add Agent 365 guides and deployment
  artifacts`) with six changed files and pushed it to
  `drewelewis/ai-hybrid-data-sources` on `main`.
- **Validation:** GitHub accepted the push from `0bfa892` to `05d2328`.
- **Rollback:** Revert the published commit with a new commit and push the
  revert; do not rewrite shared branch history.
- **Follow-up:** None.

## 2026-10-13 18:07 EDT - Remove recurring P2S route conflict

- **Status:** Failed
- **Scope:** Workstation | Runtime
- **Requested by:** User
- **Purpose:** Restore Trading Platform Agent access to private APIM after
  model requests began timing out.
- **Change:** Remove only the active `10.0.0.0/8` route owned by Windows
  interface 57, `MSFT-AzVPN-Manual`. Leave the P2S connection and all Azure,
  OpenWrt, tenant, policy, identity, and application state unchanged.
- **Result:** Read-only validation confirmed that `10.100.2.4` selected
  `MSFT-AzVPN-Manual` with source `100.96.208.193` and TCP 443 failed. The
  unelevated route removal returned `Access is denied`. Two attempts to start
  the exact removal in an elevated one-purpose PowerShell process were
  canceled at the Windows UAC boundary, so the route remains unchanged.
- **Validation:** `Find-NetRoute -RemoteIPAddress 10.100.2.4` selected
  interface 57 and `Test-NetConnection 10.100.2.4 -Port 443` returned
  `TcpTestSucceeded: False`. Temporary elevation scripts were deleted.
- **Rollback:** Restore the route with
  `New-NetRoute -InterfaceIndex 57 -DestinationPrefix 10.0.0.0/8 -NextHop
  0.0.0.0 -RouteMetric 256`.
- **Follow-up:** Run the rollback-safe removal command from an administrator
  PowerShell window, then retest APIM and `/chat`. Review why the P2S client
  keeps reinstalling a broad `10.0.0.0/8` route that overlaps the
  Site-to-Site network.

## 2026-10-14 10:15 EDT - Extend console authentication session

- **Status:** Succeeded
- **Scope:** Repository | Runtime
- **Requested by:** User
- **Purpose:** Prevent a long-running Trading Platform Agent console from
  reusing an expired device-code access token and requiring unnecessarily
  frequent interactive sign-in.
- **Change:** Keep the Azure `DeviceCodeCredential` alive for the console
  process, request a cached or refreshed token before authenticated API
  commands, close the credential on exit, and add focused regression tests.
  Do not change tenant token lifetimes, Conditional Access, application
  permissions, or stored credentials.
- **Result:** The console now retains one `DeviceCodeCredential` for its
  process lifetime, requests a cached or refreshed access token before chat
  and clear-session commands, updates the API authorization header, and closes
  the credential on exit. This extends the console session through normal
  access-token renewal without changing Entra token policy.
- **Validation:** `azure-identity 1.26.0` exposes reusable
  `DeviceCodeCredential.get_token`. Focused pytest validation passed all eight
  tests in `test_chat_auth.py` and `test_model_credential.py`. Pylance
  reported no syntax errors in the changed implementation or tests.
- **Rollback:** Revert the console authentication and test changes.
- **Follow-up:** None.

## 2026-10-14 10:20 EDT - Preserve distinct Purview end users

- **Status:** Succeeded
- **Scope:** Repository | Runtime
- **Requested by:** User
- **Purpose:** Ensure Agent 365 and Purview distinguish invocations made by
  different authenticated users without exporting raw tenant IDs, object IDs,
  names, or email addresses.
- **Change:** Pass the validated pseudonymous user ID through the Agent 365
  SDK's supported `CallerDetails` and `UserDetails` model instead of relying
  on a generic span attribute. Keep the existing SHA-256 pseudonymization and
  add focused regression coverage.
- **Result:** Agent invocations now pass the validated SHA-256 pseudonymous
  user ID through `CallerDetails(UserDetails(user_id=...))`, which is the
  installed Agent 365 SDK's supported caller identity model. Raw user claims
  remain excluded. The redundant generic `user.id` attribute was removed.
- **Validation:** Runtime inspection of `microsoft-opentelemetry 1.3.9`
  confirmed `InvokeAgentScope.start(..., caller_details=...)` maps
  `UserDetails.user_id` to the standardized user identity tag. Thirty-one
  focused user-identity, Agent 365 observability, and console authentication
  tests passed. The tests prove that different Entra object IDs generate
  different pseudonymous IDs. Pylance reported no syntax errors in the
  changed implementation or tests.
- **Rollback:** Revert the caller-details integration and tests.
- **Follow-up:** Restart the API and generate one interaction from each test
  account, then compare the resulting Purview activity records after
  ingestion delay.

## 2026-10-14 10:21 EDT - Publish authentication and attribution fixes

- **Status:** Planned
- **Scope:** Repository
- **Requested by:** User
- **Purpose:** Publish the validated console token-refresh and Agent 365
  caller-attribution fixes to the GitHub `main` branch.
- **Change:** Commit and push the updated console authentication lifecycle,
  supported Agent 365 caller identity mapping, regression tests, and audit
  ledger.
- **Result:** Pending.
- **Validation:** Verify the commit exists locally, the push succeeds, the
  worktree is clean, and local `main` matches `origin/main`.
- **Rollback:** Revert the published commit with a new commit and push the
  revert; do not rewrite shared branch history.
- **Follow-up:** Restart the local API before runtime validation.

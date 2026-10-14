# Onboarding Existing Agents to Microsoft Agent 365

## Purpose

This guide explains how the existing Python Trading Platform Agent was added
to Microsoft Agent 365 without moving or replacing its Docker-hosted runtime.
Use it as the reference pattern for onboarding similar agents in this
repository.

The [developer guide](./developers_guide.md) owns the canonical logical design,
layer responsibilities, implementation methodology, validation gates, and
Microsoft-guidance crosswalk. The detailed tenant commands and verification
steps remain in the
[provisioning runbook](./provisioning_runbook.md), and the telemetry contract
remains in the [observability reference](./observability_reference.md). The
concrete application bootstrap, authentication, request, span, and shutdown
path is documented in the
[LOB application wiring guide](./lob_app_wiring.md).

## Selected architecture

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

## Onboarding sequence

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

- `../lob/wealth/ai-agent-starter-portfolio-manager/agents/trading_platform_agent.py`
- `../lob/wealth/ai-agent-starter-portfolio-manager/observability/a365.py`

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

### 8. Add privacy-preserving user attribution

For device-code callers, the API cryptographically validates the Entra bearer
token's signature, issuer, audience, expiry, tenant, and object ID. It then
passes a stable SHA-256 hash of the validated tenant and object IDs through
`CallerDetails(UserDetails(user_id=...))`.

Raw tenant IDs, user object IDs, names, email addresses, and bearer tokens are
not exported as user attribution.

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
- Sanitized checks that secrets and raw user identifiers were not logged.

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
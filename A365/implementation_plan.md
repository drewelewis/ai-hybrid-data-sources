# Microsoft Agent 365 Implementation Plan

## 1. Objective

Bring the externally hosted Trading Platform Agent under Microsoft Agent 365
(A365) management without moving the agent into Microsoft Copilot Studio or
Microsoft Foundry Agent Service.

The integration must:

- Register the agent in the tenant with Microsoft Entra Agent ID.
- Give the agent a distinct, auditable identity and accountable sponsor.
- Export Agent 365-compatible traces for agent invocations, model inference,
  and tool calls.
- Surface the agent in Agent 365 governance and observability experiences.
- Preserve the current Docker, FastAPI, PostgreSQL, APIM, and private-network
  architecture.
- Keep the user's delegated APIM token separate from the agent's telemetry
  identity.
- Avoid exporting portfolio prompts, responses, account IDs, trade rows, or
  database results by default.

## 2. Current State

The current agent is:

- A Python 3.11 application built with Microsoft Agent Framework and FastAPI.
- Hosted locally in Docker, outside Copilot Studio and Foundry Agent Service.
- Invoked through `chat.py` and `POST /chat`.
- Authenticated to the governed APIM model endpoint with:
  - A user bearer token acquired by `chat.py` with device-code authentication.
  - A server-held APIM subscription key.
- Connected to a local PostgreSQL portfolio ledger.
- Routed privately to APIM through OpenWrt and the Site-to-Site VPN.
- Not yet registered in Agent 365.
- Not yet instrumented with Microsoft OpenTelemetry.

## 3. Selected Integration Design

### 3.1 Integration mechanism

Use the **Agent 365 SDK integration path** because this is a self-hosted,
code-based Microsoft Agent Framework agent. Registry synchronization is for
supported external platforms such as Amazon Bedrock and Google Vertex AI; it
does not apply to this custom local Docker runtime.

Use the SDK only where needed:

- **Identity and registration:** Microsoft Entra Agent ID.
- **Observability:** Microsoft OpenTelemetry Distro.
- **Work IQ tooling:** Out of scope for the first implementation.
- **Notifications and agent user account:** Out of scope.

Do not use the deprecated Agent 365 Observability SDK.

### 3.2 Identity model

Create:

1. One Agent Identity Blueprint for the Trading Platform Agent type.
2. The mandatory BlueprintPrincipal.
3. One Agent Identity for the local/dev instance.
4. At least one human sponsor for the blueprint and agent identity.

Recommended names:

- Blueprint: `trading-platform-agent`
- Dev instance: `trading-platform-agent-local-dev`
- Future production instance: `trading-platform-agent-prod`

Use separate agent identities for development and production. Use separate
blueprints only if those environments must not share a credential boundary or
inherited permissions.

### 3.3 Runtime authentication

Use **Agent 365-enabled S2S authentication** for telemetry:

- The agent identity, not the signed-in chat user, authenticates telemetry.
- The final telemetry token must target:
  `api://9b975845-388f-4429-889e-eab1ef63949c/.default`.
- The token must be app-only and must represent the registered agent instance.
- The exporter uses the Agent 365 S2S endpoint.

For local development:

- A short-lived blueprint client secret may be used only if required.
- Store it only in the git-ignored `.env` or a local secret store.
- Prefer the Microsoft Entra SDK for AgentID sidecar to perform the two-step
  `fmi_path` exchange for the Python agent.
- Do not publish the sidecar port to the host or external network.

For an Azure-hosted production runtime:

- Use managed identity plus workload identity federation.
- Do not use a client secret.

Do not reuse any of these values for telemetry:

- The device-code user token from `chat.py`.
- The APIM subscription key.
- The PostgreSQL credentials.

### 3.4 Telemetry and privacy

Use the `microsoft-opentelemetry` Python package and initialize it before
FastAPI, Agent Framework, HTTP, database, or Azure SDK modules are loaded.

Each `POST /chat` request must produce:

- One root `invoke_agent` span.
- Child model/inference spans.
- Child tool spans.
- HTTP and database dependency spans where supported.
- Correlation attributes for the configured tenant and agent identity.

Default data policy:

- Metadata-only telemetry.
- Content recording disabled.
- No raw prompts or responses.
- No account IDs, ticker-holder lists, SQL, trade rows, credentials, bearer
  tokens, subscription keys, or database connection strings.
- Session correlation uses a generated or hashed value, not a human identity.

Content capture must remain disabled unless Security, Privacy, and Compliance
explicitly approve it.

## 4. Prerequisites and Decision Gates

Complete these checks before modifying runtime code:

- [ ] Agent 365 is enabled in the target tenant.
- [ ] At least one tenant user has a Microsoft 365 E7 or Microsoft Agent 365
      license. Without this, telemetry can be accepted with HTTP 200 and then
      silently dropped.
- [ ] The operator has Global Administrator or Agent ID Developer access.
- [ ] A Global Administrator is available for any required consent.
- [ ] An accountable sponsor user is selected.
- [ ] The tenant ID is confirmed.
- [ ] Development and production identity boundaries are approved.
- [ ] Metadata-only telemetry is approved.
- [ ] The Agent 365 CLI/Skills version is recorded.

Decision gate:

- Do not run `a365 setup all` blindly against this repository. Current
  documentation says that command can create an App Service Plan and Web App.
  This agent must remain in its current Docker host unless deployment migration
  is separately approved.
- Prefer the existing-agent registration workflow or typed Microsoft Graph
  Agent ID APIs when registration-only behavior is required.
- Ensure the resulting blueprint has `managerApplications` configured; Agent
  365 rejects unmanaged blueprints.

## 5. Phased Implementation

### Phase 0 - Capture a baseline

Tasks:

- [ ] Record the current API health result.
- [ ] Run focused agent, chat, credential, and endpoint tests.
- [ ] Record one successful portfolio chat interaction.
- [ ] Record the current Docker service topology.
- [ ] Confirm no A365 packages or configuration are already active.

Acceptance criteria:

- The current behavior is reproducible before A365 changes.
- Test commands and results are recorded in the implementation pull request.

### Phase 1 - Register identity and inventory

Tasks:

- [ ] Install or update the Agent 365 CLI and supported Agent 365 Skills.
- [ ] Register the `trading-platform-agent` blueprint.
- [ ] Verify that the BlueprintPrincipal exists.
- [ ] Verify that `managerApplications` is populated.
- [ ] Create `trading-platform-agent-local-dev` from the blueprint.
- [ ] Assign the approved sponsor.
- [ ] Confirm the identity is visible in Microsoft Entra.
- [ ] Confirm the agent appears in the Agent 365 inventory.
- [ ] Save generated non-secret IDs in local configuration.
- [ ] Add generated configuration and secrets to `.gitignore` if required.

Required recorded outputs:

- Tenant ID.
- Blueprint application/client ID.
- Blueprint object ID.
- BlueprintPrincipal object ID.
- Agent identity client ID and object ID.
- Sponsor object ID or group.
- Registration timestamp and operator.

Acceptance criteria:

- The blueprint, principal, and agent identity are distinct and queryable.
- The agent identity has the correct sponsor.
- No credentials are attached directly to the agent identity.
- No unnecessary Microsoft Graph or Azure roles are granted.

### Phase 2 - Add local S2S token acquisition

Tasks:

- [ ] Choose the supported local authentication implementation:
  - Preferred: Microsoft Entra SDK for AgentID sidecar.
  - Alternative: Direct, tested two-step `fmi_path` exchange.
- [ ] Add a local development credential to the blueprint only.
- [ ] Add the sidecar to `docker-compose.yaml` without publishing its port.
- [ ] Configure the sidecar with tenant ID, blueprint client ID, credential
      source, and Observability downstream scope.
- [ ] Add a health check for the sidecar.
- [ ] Make the API depend on sidecar health when A365 is enabled.
- [ ] Implement token caching and refresh before expiry.
- [ ] Validate final token claims before returning it to the exporter:
  - Audience is the Agent 365 observability resource.
  - Token is app-only.
  - Token is not expired.
  - Token subject corresponds to the registered agent identity.

Proposed non-secret environment variables:

```dotenv
ENABLE_A365_OBSERVABILITY=false
A365_TENANT_ID=
A365_BLUEPRINT_CLIENT_ID=
A365_AGENT_ID=
A365_AUTH_MODE=agent-id-sidecar
A365_AGENT_ID_SIDECAR_URL=http://agent-id-sidecar:5000
A365_RECORD_CONTENT=false
```

The blueprint credential must not be added to `env.sample`.

Acceptance criteria:

- A final Agent 365 observability token can be acquired locally.
- The token is not a user/OBO token.
- Token acquisition failure is logged explicitly.
- Telemetry failure does not return a successful telemetry status, but it also
  does not make the portfolio agent unavailable.

### Phase 3 - Instrument the Python runtime

Planned repository changes:

- `requirements.txt`
  - Add a pinned, tested `microsoft-opentelemetry` version.
  - Add only the identity/token packages required by the chosen flow.
- `main.py`
  - Initialize Microsoft OpenTelemetry before importing Uvicorn/FastAPI app
    modules.
- `observability/a365.py` (new)
  - Centralize feature flags, resource attributes, token resolution, baggage,
    redaction policy, and exporter initialization.
- `api/main.py`
  - Wrap each `/chat` execution in a root `invoke_agent` scope.
  - Add tenant ID and agent ID baggage.
  - Record success, controlled error, rate limit, and tool failure outcomes.
- `agents/trading_platform_agent.py`
  - Verify Agent Framework model/tool spans are auto-instrumented.
  - Add manual spans only where automatic instrumentation has gaps.
- `docker-compose.yaml`
  - Pass non-secret A365 settings.
  - Add the sidecar if selected.
- `env.sample`
  - Document non-secret A365 configuration and feature flags.
- `README.md`
  - Link to `A365/readme.md`.

Implementation requirements:

- Call `use_microsoft_opentelemetry()` as early as possible.
- Set `enable_a365=True`.
- Set `a365_use_s2s_endpoint=True`.
- Provide a custom token resolver.
- Set tenant and agent ID baggage before creating the root span.
- Ensure one user request and one agent response map to one trace.
- Flush telemetry on graceful shutdown.
- Log exporter/authentication failures without logging tokens.

Acceptance criteria:

- A normal chat request still returns the same functional result.
- A trace contains a valid root `invoke_agent` span.
- Model and tool operations appear as children of that root.
- No portfolio content or secrets appear in exported attributes.

### Phase 4 - Apply governance controls

Tasks:

- [ ] Confirm the agent is listed in Microsoft 365 admin center under Agents.
- [ ] Assign the approved sponsor and lifecycle owner.
- [ ] Apply least-privilege Conditional Access suitable for workload/agent
      identities.
- [ ] Review every inherited and direct permission.
- [ ] Confirm that the agent has no agent user account, mailbox, or Teams
      presence.
- [ ] Confirm that Work IQ, notifications, and Microsoft 365 data access remain
      disabled unless separately approved.
- [ ] Define credential rotation and identity disable/delete procedures.
- [ ] Define incident response contacts and log retention requirements.

Acceptance criteria:

- The agent can be located by identity and sponsor.
- Administrators can disable the agent identity independently.
- Governance changes do not modify APIM or PostgreSQL authorization.

### Phase 5 - Validate observability end to end

Functional scenarios:

1. Start the stack with A365 disabled and confirm unchanged behavior.
2. Start with A365 enabled and valid identity configuration.
3. Run `List all accounts`.
4. Run `What accounts hold MSFT?`.
5. Trigger a controlled invalid request.
6. Trigger or simulate APIM HTTP 429 handling.
7. Trigger a tool/database failure in a test environment.

Validation checklist:

- [ ] API and database remain healthy.
- [ ] Chat behavior is unchanged.
- [ ] Root `invoke_agent` span exists.
- [ ] Model and tool child spans exist.
- [ ] Error and rate-limit outcomes are represented.
- [ ] Telemetry appears in Microsoft Defender.
- [ ] Telemetry appears in Microsoft Purview.
- [ ] Telemetry appears in Microsoft 365 admin center.
- [ ] Agent identity and tenant attributes match registration.
- [ ] No sensitive content is present.
- [ ] Exporter retries are bounded and do not retry agent requests.
- [ ] No telemetry is silently reported as successful after auth failure.

### Phase 6 - Production hardening

Tasks:

- [ ] Replace the local blueprint secret with managed identity and federation.
- [ ] Create a separate production agent identity.
- [ ] Store all secrets in an approved secret store.
- [ ] Pin all A365 and OpenTelemetry dependencies.
- [ ] Add dependency and image vulnerability scanning.
- [ ] Restrict sidecar communication to the agent workload.
- [ ] Add exporter health/error metrics.
- [ ] Document credential rotation and emergency disable procedures.
- [ ] Complete a nonproduction soak test.

## 6. Test Strategy

Add focused tests for:

- Feature flag disabled behavior.
- Required A365 configuration validation.
- Token cache hit, refresh, and expiry.
- Invalid audience and non-app token rejection.
- Token resolver failure.
- Baggage creation with tenant and agent IDs.
- Root span creation for successful and failed chat requests.
- Sensitive attribute redaction.
- Exporter unavailable behavior.
- Existing chat authentication and APIM routing.

Do not make tests depend on production tenant credentials. Keep live A365 tests
separate and opt-in.

## 7. Rollback

Runtime rollback must be immediate:

1. Set `ENABLE_A365_OBSERVABILITY=false`.
2. Restart only the API container.
3. Confirm chat, APIM, and database behavior.
4. Preserve logs for diagnosis.

Identity rollback is separate:

1. Disable the agent identity.
2. Remove direct permission grants.
3. Remove credentials from the blueprint.
4. Delete the agent identity only after retention and investigation needs are
   satisfied.
5. Delete the blueprint last, after verifying no other instances use it.

Do not delete the existing APIM API registration or the public-client
registration used by `chat.py`; those identities serve different purposes.

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Telemetry accepted but not visible | Verify an E7 or Agent 365 license and a valid root `invoke_agent` span. |
| Portfolio data leaks into telemetry | Keep content recording disabled and test exported attributes. |
| Human APIM token reused as agent identity | Use a dedicated S2S Agent ID token resolver. |
| Unused Azure resources created by CLI | Review registration mode before running `a365 setup all`. |
| Secret committed to Git | Keep credentials in ignored local/secret-store configuration. |
| Sidecar exposed to the network | Do not publish its port; restrict it to the workload network. |
| Telemetry failure breaks chat | Export asynchronously, bound queues/timeouts, and log failures. |
| Blueprint and agent identity confused | Record both object types and validate the token subject. |
| Missing sponsor or lifecycle owner | Make sponsor verification an acceptance gate. |

## 9. Definition of Done

The integration is complete when:

- The agent has a registered blueprint, principal, instance identity, and
  sponsor.
- The agent appears in the Agent 365 inventory.
- The local runtime exports authenticated A365 telemetry through S2S.
- A valid `invoke_agent` root span contains model and tool child spans.
- Telemetry is visible in Defender, Purview, and Microsoft 365 admin center.
- No sensitive portfolio content is exported.
- Existing chat, APIM, database, and private-network behavior remains intact.
- A365 can be disabled through one feature flag without code changes.

## 10. Authoritative References

- [Connect existing agents to Microsoft Agent 365](https://learn.microsoft.com/en-us/microsoft-agent-365/connect-existing-agents)
- [Choose an Agent 365 integration option](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/choose-integration-option)
- [Quickstart: Connect an existing agent](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/get-started)
- [Agent 365 identity](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/identity)
- [Setup agent blueprint](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/registration)
- [Microsoft Agent 365 SDK overview](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk)
- [Microsoft OpenTelemetry Distro](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry)
- [Observability authentication setup](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability-authentication-setup)
- [Agent 365 SDK validation checklist](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/validation-checklist)
- [Microsoft Entra Agent ID setup](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-id-setup-instructions)

Documentation reviewed: October 5, 2026.

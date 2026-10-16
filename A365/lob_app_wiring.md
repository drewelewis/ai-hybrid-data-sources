# Wiring LOB Applications to Microsoft Agent 365

## Purpose

This guide shows how a self-hosted line-of-business (LOB) application is wired
to Microsoft Agent 365 without changing its hosting platform, model gateway,
tools, or database. It uses the Python Trading Platform Agent as the concrete
reference implementation.

Use the [developer guide](./developers_guide.md) for the canonical design and
implementation methodology. Use this document when implementing or reviewing
the reference application code. Use the
[onboarding guide](./onboarding_agents.md) for the tenant onboarding sequence,
the [provisioning runbook](./provisioning_runbook.md) for tenant commands, and
the
[observability reference](./observability_reference.md) for the telemetry
contract.

## End-to-end flow

![LOB application wiring to Microsoft Agent 365](../images/a365-lob-app-wiring.svg)

The three lanes separate the user request, identity and correlation, and
telemetry paths. Microsoft Agent 365 receives the exported spans and routes
eligible events to Admin Center, Purview, and Defender. Edit the native
[Draw.io source](../images/a365-lob-app-wiring.drawio) when the wiring changes.

<details>
<summary>Text alternative</summary>

```text
End user
  |
  | Device-code sign-in
  v
chat.py
  |
  | POST /chat
  | Authorization: Bearer <user token>
  v
FastAPI API
  |
  +-- Validate user token
  |     |
  |     +-- Validate signature, issuer, audience, expiry, tenant, and oid
  |     +-- Hash tenant ID + object ID into a pseudonymous user ID
  |
  +-- Create InvokeAgent scope
  |     |
  |     +-- Registered Agent ID and blueprint
  |     +-- Pseudonymous caller identity
  |     +-- Hashed conversation ID
  |     +-- Channel and service endpoint
  |     +-- Optional prompt content
  |
  +-- Run Microsoft Agent Framework agent
  |     |
  |     +-- Governed APIM model route
  |     +-- LOB tools and PostgreSQL
  |
  +-- Record response or sanitized error
  |
  v
Microsoft OpenTelemetry Distro
  |
  | Agent 365 S2S token
  v
Agent 365 observability endpoint
  |
  +-- Agent Registry and Admin Center
  +-- Microsoft Purview
  +-- Microsoft Defender
```

</details>

The application sends telemetry to the Agent 365 service-to-service endpoint.
It does not contain separate Purview or Defender exporters. Microsoft routes
eligible Agent 365 events into those products after ingestion and policy
processing.

## Reference implementation map

| Concern | Reference file | Responsibility |
|---|---|---|
| Process bootstrap | [main.py](../lob/wealth/portfolio-manager/main.py) | Initializes Agent 365 observability before Uvicorn imports instrumented modules |
| Interactive client | [chat.py](../lob/wealth/portfolio-manager/chat.py) | Performs device-code authentication, refreshes the user token, and calls `/chat` |
| API request lifecycle | [api/main.py](../lob/wealth/portfolio-manager/api/main.py) | Validates the caller, opens the root span, runs the agent, and records success or failure |
| User validation | [api/user_identity.py](../lob/wealth/portfolio-manager/api/user_identity.py) | Validates Entra token claims and produces the pseudonymous user ID |
| Agent construction | [agents/trading_platform_agent.py](../lob/wealth/portfolio-manager/agents/trading_platform_agent.py) | Binds the registered Agent ID to the Microsoft Agent Framework `ChatAgent` |
| Telemetry runtime | [observability/a365.py](../lob/wealth/portfolio-manager/observability/a365.py) | Handles Agent 365 token exchange, exporter configuration, spans, content, status, and flush |
| Configuration | [LOB application README](../lob/wealth/portfolio-manager/README.md) | Documents runtime settings without storing secrets |
| Observability tests | [test_a365_observability.py](../lob/wealth/portfolio-manager/test_a365_observability.py) | Verifies exporter, scope, content, and identity behavior |
| User identity tests | [test_user_identity.py](../lob/wealth/portfolio-manager/test_user_identity.py) | Verifies validation and pseudonymization |
| Console auth tests | [test_chat_auth.py](../lob/wealth/portfolio-manager/test_chat_auth.py) | Verifies token reuse, refresh, and credential cleanup |

## 1. Bootstrap telemetry before the application

The process entry point loads local configuration and initializes Agent 365
before importing Uvicorn:

```python
from observability.a365 import initialize_a365_observability

initialize_a365_observability(os.environ)

import uvicorn
```

This ordering matters. OpenTelemetry instrumentation should be configured
before importing FastAPI, HTTP, database, or Agent Framework modules that the
distro may instrument.

Do not initialize observability in multiple modules. The runtime rejects
duplicate initialization.

## 2. Load and validate Agent 365 settings

`A365Settings.load` treats Agent 365 as a feature-gated integration.
`ENABLE_A365_OBSERVABILITY=false` leaves the existing application behavior
unchanged.

When enabled, the runtime requires:

- `A365_TENANT_ID`
- `A365_BLUEPRINT_CLIENT_ID`
- `A365_BLUEPRINT_CLIENT_SECRET`
- `A365_AGENT_ID`

It also reads service identity, channel, endpoint, content policy, queue, batch,
delay, and exporter timeout settings. UUIDs, ports, and required values are
validated before the API starts.

The blueprint secret belongs in the environment's secret store. It must never
be committed, logged, attached to telemetry, or returned by health endpoints.

## 3. Authenticate the exporter with Agent ID

The telemetry runtime performs a two-step service-to-service exchange:

1. The blueprint credential requests an intermediate assertion for the
   registered Agent Identity using `fmi_path`.
2. The Agent Identity exchanges that assertion for an app-only token scoped
   to the Agent 365 observability resource.

The runtime validates the final token's audience, application identity, tenant,
and expiry. It caches the token in memory and refreshes it before expiry.

Microsoft OpenTelemetry receives a synchronous token resolver:

```python
use_microsoft_opentelemetry(
    enable_a365=True,
    a365_token_resolver=runtime.resolve_token,
    a365_use_s2s_endpoint=True,
    a365_enable_observability_exporter=True,
)
```

The resolver returns a token only when the requested tenant and Agent ID match
the configured registration.

## 4. Bind the registered identity to the runtime agent

When observability is enabled,
`agents/trading_platform_agent.py` assigns `A365_AGENT_ID` to `ChatAgent.id`.

```python
agent = ChatAgent(
    id=a365_agent_id,
    name="TradingPlatformAgent",
    ...
)
```

The Agent Framework runtime ID, exporter Agent ID, Agent ID token subject, and
Agent Registry instance must refer to the same identity. An unrelated generated
ID can cause dropped telemetry or records that cannot be correlated with the
registered agent.

## 5. Authenticate the human caller separately

Agent 365 exporter authentication and end-user authentication are different:

| Identity | Used for | Credential |
|---|---|---|
| Agent identity | Exporting telemetry and attributing the agent instance | Blueprint-backed Agent ID S2S token |
| End user | Calling the governed model route and attributing the human caller | Device-code bearer token |

`chat.py` keeps one `DeviceCodeCredential` alive for the console process. It
asks Azure Identity for a cached or refreshed token before authenticated API
commands. One console process remains associated with the account used during
its initial sign-in.

To switch test users, exit the console, start it again, and explicitly select
another account during device-code authentication.

## 6. Validate and pseudonymize the caller

The `/chat` endpoint receives the user bearer token and passes it to
`EntraUserTokenValidator`.

Validation includes:

- Signing key and signature.
- Allowed token algorithms.
- Audience.
- Issuer.
- Expiry.
- Tenant ID.
- Entra object ID.

After validation, the API computes:

```text
SHA-256("<tenant-id>:<object-id>")
```

This value is stable for the same user in the same tenant and different for
different object IDs. Raw IDs, names, email addresses, device codes, and tokens
are not exported.

## 7. Create one root scope per invocation

Every `/chat` request calls `a365_invoke_scope`, which creates:

- `Request` with prompt content when content recording is enabled.
- Hashed session and conversation IDs.
- Stable channel information.
- `AgentDetails` with Agent ID, blueprint, tenant, provider, and version.
- `CallerDetails(UserDetails(user_id=...))` with the pseudonymous end user.
- `InvokeAgentScopeDetails` with the API endpoint.
- Agent 365 baggage for downstream correlation.

The root scope is started with:

```python
with InvokeAgentScope.start(
    request,
    scope_details,
    agent_details,
    caller_details=caller_details,
) as scope:
    ...
```

Use the SDK's caller model. A generic OpenTelemetry `user.id` attribute does
not provide the same Agent 365 participant mapping.

## 8. Correlate model and tool activity

The Microsoft Agent Framework agent runs inside the root `InvokeAgent` scope.
Supported model, HTTP, and tool instrumentation can therefore appear as child
operations under the invocation.

The agent continues to use:

- APIM for the governed model route.
- Existing model credentials and subscription governance.
- Existing LOB tools.
- Existing PostgreSQL data access.

Agent 365 does not replace those components.

## 9. Record output and failures

On success, the API calls `record_a365_response`. Response content is recorded
only when `A365_RECORD_CONTENT=true`.

On failure, the API calls `scope.record_error(error)` before mapping the model
failure to an HTTP response. Do not attach credentials, raw tokens, connection
strings, or unsanitized sensitive exception data.

Telemetry export failures do not cause an otherwise successful LOB request to
fail. Export retries, queue limits, and timeouts remain bounded independently.

## 10. Refresh and flush

FastAPI startup starts background Agent 365 token refresh after the database is
ready. FastAPI shutdown:

1. Stops background token refresh.
2. Forces an OpenTelemetry provider flush.
3. Closes the database pool.

The health endpoint exposes only safe status:

- Enabled or disabled.
- Ready or degraded.
- Token readiness.
- Sanitized last-error category.
- Content-recording state.
- Export-debug state.

It never returns credentials or access tokens.

## 11. Content and privacy decisions

`A365_RECORD_CONTENT=true` can export prompts, responses, and content captured
by supported model or tool instrumentation. For an LOB application, this may
include customer identifiers, financial data, health data, SQL, or internal
business records.

Before enabling full content:

1. Classify the data.
2. Confirm retention and residency.
3. Restrict Purview, Defender, and Agent 365 access.
4. Enable the intended Purview policies.
5. Use synthetic data for validation.
6. Document approval in `a365-changes.md`.

Set `A365_RECORD_CONTENT=false` for metadata-only operation.

## Reuse checklist for another LOB application

1. Register a dedicated blueprint and environment-specific Agent Identity.
2. Assign an accountable sponsor and create the Agent Registry instance.
3. Store the blueprint credential in an approved secret store.
4. Add an application-owned telemetry module; do not scatter token exchange
   and exporter setup across business modules.
5. Initialize telemetry before instrumented imports.
6. Bind the registered Agent ID to the runtime agent.
7. Validate human caller tokens at the API boundary.
8. Export only a privacy-approved user identifier.
9. Create one root `InvokeAgent` scope per user invocation.
10. Keep model and tool calls inside the root scope.
11. Record final output and sanitized errors.
12. Start bounded token refresh and flush on shutdown.
13. Add tests for configuration, token exchange, user distinction, content
    suppression, scope structure, and credential exclusion.
14. Validate arrival in Agent 365, Purview, and Defender independently.

## Validation sequence

Use the [verification process](./verification_process.md):

1. **Arrange:** Confirm registration, identity, configuration, policies, and
   runtime health.
2. **Act:** Send one non-sensitive, uniquely marked request.
3. **Assert locally:** Confirm one root invocation, caller identity, response,
   and no credential leakage.
4. **Assert in services:** Confirm the event in Agent 365, Purview, and
   Defender after their respective ingestion delays.
5. **Repeat with another user:** Restart the console, sign in with another
   account, and confirm a different pseudonymous caller.

Do not treat local exporter success as proof of portal ingestion. Capture
evidence for each destination separately.

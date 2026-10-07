# Agent 365 Observability Reference

## Purpose

This document defines the telemetry contract for the Trading Platform Agent.
Use the Microsoft OpenTelemetry Distro, not the deprecated Agent 365
Observability SDK.

## Trace model

One user message and one agent response form one trace:

```text
invoke_agent
  +-- chat / model inference
  +-- execute_tool
  |     +-- database dependency
  +-- chat / model inference
  +-- output_messages
```

The `invoke_agent` span must be the root. Without it, telemetry can remain
queryable in Defender but fail to appear in Agent 365 views.

## Required operation names

| Operation | Purpose |
|---|---|
| `invoke_agent` | Root span for one agent run |
| `chat` | Model inference |
| `execute_tool` | Tool or function invocation |
| `output_messages` | Final agent output |

The Microsoft Distro should populate supported semantic attributes
automatically. Manual attributes must follow the current Agent 365 reference.
For direct OTLP payloads, values are encoded as `stringValue`, including token
counts and ports.

## Required identity and correlation

Every run must resolve:

- `microsoft.tenant.id`
- `gen_ai.agent.id`
- `gen_ai.agent.name`
- `microsoft.a365.agent.blueprint.id`
- `gen_ai.conversation.id`
- Stable channel value
- Server address and port
- Trace ID and span ID

Use the registered agent identity client ID consistently in:

- S2S token subject.
- Export URL.
- Agent ID baggage.
- Span attributes.

A mismatch can produce HTTP 403 or telemetry that cannot be attributed.

## Trading Platform values

| Attribute | Planned value |
|---|---|
| Agent name | `TradingPlatformAgent` |
| Service name | `ai-agent-starter-portfolio-manager` |
| Channel | `local-cli` |
| Tenant ID | `A365_TENANT_ID` |
| Agent ID | `A365_AGENT_ID` |
| Blueprint ID | Generated registration value |
| Server address | API host name |
| Server port | `8989` |

Generate one conversation ID per `chat.py` session. Do not use a username,
email address, account ID, or bearer-token claim as a conversation ID.

## Status and errors

| Outcome | Span status | Required metadata |
|---|---|---|
| Successful run | `OK` | Duration and operation |
| APIM 429 | `ERROR` | HTTP status, governed rate-limit category |
| Model failure | `ERROR` | Sanitized exception type |
| Tool failure | `ERROR` | Tool name and sanitized failure category |
| Database failure | `ERROR` | Dependency type, no connection string |
| Telemetry export failure | Local log/metric | Exporter category, no token |

Do not automatically retry the user request because telemetry export failed.
Exporter retries must be bounded independently.

## Content policy

`A365_RECORD_CONTENT` defaults to `false`.

Never export:

- User prompt text.
- Model response text.
- Tool arguments or results containing portfolio data.
- SQL text.
- Account IDs.
- Trade rows.
- APIM keys.
- Bearer tokens.
- Device codes.
- Database credentials.
- Full exception messages that could contain any of the above.

Use allowlisted metadata rather than attempting to redact arbitrary payloads
after collection.

## Sampling and cardinality

Initial validation uses 100% sampling in a nonproduction environment.

Before production:

- Select a trace sampling policy.
- Always retain errors and security-relevant runs where supported.
- Avoid unbounded attribute values.
- Do not use prompt text, SQL, account IDs, or exception text as dimensions.
- Monitor queue drops and exporter timeouts.

Record the final sampling policy in the production change record.

## Export configuration

Planned Python initialization:

```python
use_microsoft_opentelemetry(
    enable_a365=True,
    a365_token_resolver=token_resolver,
    a365_use_s2s_endpoint=True,
    a365_enable_observability_exporter=True,
)
```

Initialize before importing instrumented FastAPI, HTTP, database, or Agent
Framework modules.

The token resolver must:

- Return a final Observability token, not an intermediate blueprint assertion.
- Validate audience and app-only token type.
- Cache by tenant ID and agent ID.
- Refresh before expiry.
- Never log the token.

## Validation

For each test trace, verify:

- [ ] Root operation is `invoke_agent`.
- [ ] Tenant, agent, and blueprint IDs are correct.
- [ ] Conversation ID is present.
- [ ] Model calls are children of the root.
- [ ] Tool calls are children of the root.
- [ ] Status is accurate.
- [ ] No content or secrets appear.
- [ ] Trace appears in Defender.
- [ ] Trace appears in Purview where applicable.
- [ ] Trace appears in Microsoft 365 admin center.

## Defender hunting examples

Replace the placeholder with the registered agent application ID:

```kusto
let agentIdToFind = "YOUR-AGENT-APP-ID";
CloudAppEvents
| where Timestamp > ago(1d)
| where ActionType in (
    "InvokeAgent",
    "InferenceCall",
    "ExecuteToolBySDK",
    "ExecuteToolByGateway",
    "ExecuteToolByMCPServer")
| extend data = parse_json(tostring(RawEventData))
| extend AgentId = tostring(data.AgentId)
| extend TargetAgentId = tostring(data.TargetAgentId)
| extend PlatformTargetAgentId = tostring(data.PlatformTargetAgentId)
| where AgentId == agentIdToFind
    or TargetAgentId == agentIdToFind
    or PlatformTargetAgentId == agentIdToFind
| project Timestamp, ActionType, AgentId, data
| order by Timestamp desc
```

Use the current Defender schema in the tenant; field mappings can evolve.
Agent 365 guidance does not require the Microsoft 365 Activities connector for
these spans. If `CloudAppEvents | take 1` cannot resolve the table, treat that
as a tenant-side Defender provisioning blocker and escalate it to Microsoft;
do not change agent instrumentation or deploy unrelated discovery sources to
manufacture the table.

Error-focused query:

```kusto
let agentIdToFind = "YOUR-AGENT-APP-ID";
CloudAppEvents
| where Timestamp > ago(7d)
| extend data = parse_json(tostring(RawEventData))
| where tostring(data.AgentId) == agentIdToFind
| where tostring(data.Status) =~ "Error"
| project Timestamp, ActionType, data
| order by Timestamp desc
```

## References

- [Microsoft OpenTelemetry Distro](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry)
- [Observability attributes](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability-attribute-reference)
- [Observability authentication](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/observability-authentication-setup)
- [Direct OTel troubleshooting](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/direct-open-telemetry-troubleshooting)

# Agent 365 Security and Privacy

## Security objective

Add Agent 365 governance without expanding access to portfolio data, exposing
credentials, or coupling telemetry availability to agent availability.

## Trust boundaries

```text
User workstation
  | device-code user token
  v
chat.py
  |
  v
FastAPI container ----> Agent ID sidecar ----> Microsoft Entra
  |                            |
  |                            +-------------> Agent 365 telemetry
  |
  +----> APIM private endpoint ----> Model
  |
  +----> PostgreSQL
```

Authentication boundaries:

- Human user token: APIM model authorization.
- APIM subscription key: gateway product authorization.
- Agent ID S2S token: A365 telemetry identity.
- PostgreSQL credential: database access.

These credentials are not interchangeable.

## Data classification

| Data | Classification | Export permitted |
|---|---|---:|
| Tenant ID | Operational metadata | Yes |
| Agent/blueprint ID | Operational metadata | Yes |
| Trace/span ID | Operational metadata | Yes |
| Operation and duration | Operational metadata | Yes |
| Sanitized status/error category | Operational metadata | Yes |
| Token counts | Operational metadata | Yes |
| User prompt | Confidential/potential personal data | No |
| Model response | Confidential/potential personal data | No |
| Account ID | Confidential portfolio data | No |
| Ticker positions/trades | Confidential portfolio data | No |
| Tool arguments/results | Confidential unless allowlisted | No |
| SQL text/results | Confidential | No |
| Bearer token/device code | Secret | Never |
| APIM subscription key | Secret | Never |
| Blueprint credential | Secret | Never |
| Database credential | Secret | Never |

## Threat model

### Credential theft

Risk: A blueprint secret or sidecar token is stolen.

Controls:

- Prefer federation.
- Keep sidecar private.
- Use short-lived local secrets.
- Rotate and monitor.
- Never log tokens.
- Separate production credential boundary.

### Identity confusion

Risk: Telemetry is attributed to the wrong agent.

Controls:

- Validate tenant and agent IDs.
- Validate token subject and audience.
- Use one canonical generated configuration.
- Compare baggage, token, and export URL.

### Sensitive telemetry leakage

Risk: Prompts, tool output, SQL, or account data is exported.

Controls:

- Metadata-only allowlist.
- Content recording disabled.
- Automated attribute inspection.
- Sanitized error categories.
- Stop exporter and investigate on detection.

### Prompt/tool abuse

Risk: Prompt injection causes unexpected tool access.

Controls:

- Least-privilege tools.
- Targeted database functions.
- Read-only SQL controls.
- Defender risk monitoring.
- Trace tool calls without recording sensitive payloads.

### Sidecar exposure

Risk: Another host calls the token sidecar.

Controls:

- No published host port.
- Private workload network only.
- Network isolation.
- Health endpoint contains no secrets.
- Pin and scan sidecar image.

### Telemetry denial of service

Risk: Export queue or authentication blocks chat.

Controls:

- Batch export.
- Bounded queues/timeouts.
- Cached tokens.
- No synchronous export in request path.
- Feature-flag rollback.

## Privacy defaults

- `A365_RECORD_CONTENT=false`
- No user identity attribute unless required and approved.
- Conversation IDs are random identifiers.
- No portfolio account correlation.
- No prompt/response capture.
- No broad exception serialization.
- No telemetry enrichment from bearer-token claims.

## Retention and residency decisions

Before production, the tenant owner must record:

- Which A365/Defender/Purview services store the data.
- Tenant geography and applicable residency.
- Retention period for traces and security events.
- Legal hold requirements.
- Data subject/privacy request handling.
- Whether telemetry is exported to any additional OTLP backend.

Do not claim a retention or residency guarantee until it is confirmed in the
tenant and current product documentation.

## Secret handling

- Keep `.env`, generated credentials, certificates, and keys git-ignored.
- Use Key Vault and managed identity in Azure production.
- Do not place secrets in Compose defaults.
- Do not send secrets to support.
- Do not store secrets in A365 generated non-secret config.
- Scan commits and images before release.

## Security validation

- [ ] No secret appears in source or image layers.
- [ ] Sidecar port is not published.
- [ ] Final token audience and subject are correct.
- [ ] Agent identity has minimal permissions.
- [ ] Content recording is disabled.
- [ ] Exported attributes pass allowlist inspection.
- [ ] Error traces contain no payloads.
- [ ] Emergency disable works.
- [ ] Telemetry rollback works.
- [ ] Sponsor and incident contacts are current.

## Incident response for data leakage

1. Disable A365 export.
2. Preserve sanitized evidence.
3. Notify Security and Privacy.
4. Determine affected traces, fields, and retention systems.
5. Rotate credentials if any secret was exposed.
6. Remove the offending instrumentation.
7. Validate deletion/retention actions with service owners.
8. Re-enable only after approval and regression testing.

## References

- [Microsoft OpenTelemetry](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/microsoft-opentelemetry)
- [Agent 365 identity](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/identity)
- [Security for AI](https://learn.microsoft.com/en-us/security/security-for-ai/)

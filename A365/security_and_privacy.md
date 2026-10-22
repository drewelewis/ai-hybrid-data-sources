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
FastAPI container ----> Microsoft Entra Agent ID token exchange
  |
  +--------------------> Agent 365 telemetry
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

Risk: A blueprint secret or in-memory Agent ID token is stolen.

Controls:

- Prefer federation.
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

### Token exchange exposure

Risk: Credentials or tokens escape the application process.

Controls:

- Use the direct exchange only over Microsoft Entra HTTPS endpoints.
- Keep credentials and final tokens in process memory.
- Expose only boolean token readiness and sanitized error categories.
- Never return or log tokens through health or diagnostic endpoints.
- Restrict host and container access.

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
- Approved security attribution uses the validated human Entra object ID
  and available UPN/display name in SDK caller fields, independent of
  prompt/response recording. Restrict access and retention for this metadata.
- Conversation/session IDs are hashed identifiers, not user object IDs.
- No portfolio account correlation.
- No prompt/response capture.
- No broad exception serialization.
- No arbitrary bearer-token claim enrichment; only validated tenant/object
  identity and approved optional caller UPN/display name are used.

## Controlled policy-validation exception

Raw Agent 365 activity in Entra sign-ins, Purview Activity Explorer, and
Defender Advanced Hunting does not require prompt or response recording.
Keep the normal runtime metadata-only.

Defender `CloudAppEvents` also depends on the tenant's Microsoft 365 connector
data path. That connector is infrastructure for hunting ingestion, not a
reason to capture prompt or response content and not a substitute for Agent
365 telemetry.

The fixed `a365_verify.py` nonproduction policy-classification test requires
temporary `A365_RECORD_CONTENT=true`. It runs five realistic conversation
rounds and one or two randomly selected three-turn attack chains using
supplied synthetic credential canaries, generated nonexistent accounts, and the reserved
`security-test.invalid` domain. The pool also contains a standard synthetic
payment-card records and fictional misconduct/jailbreak scenarios, guarantees at least
one content-policy candidate, refuses to start when health reports content
recording disabled, and stores sanitized scenario/step identifiers, expected
signals, status, timing, model-filter categories, and fixture-echo observations
locally. Fixture echoes require review and are not proof of exfiltration.
Raw prompt/response and arbitrary upstream error text are not persisted.

The harness never performs an authentication attack, uses a real secret,
contacts an external destination, queries a real account during an exploit,
or directly invokes a data-changing tool. Attack prompts authorize no
delivery or mutation and limit requests to synthetic drafts or the exact QA
account. A random seed is stored so the exact
selection and placement can be reproduced without storing prompt text.

Before enabling the exception, record the approval, test window, expected
policy, retention implications, and rollback in `a365-changes.md`. After the
run, restore `A365_RECORD_CONTENT=false`, restart the API, and confirm health
reports `content_recording: false`. Deleting the local evidence does not
delete telemetry already accepted by Microsoft 365 services.

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
- Use an approved enterprise secret store and certificate or approved workload
  federation for the on-premises `prd` runtime.
- Do not place secrets in Compose defaults.
- Do not send secrets to support.
- Do not store secrets in A365 generated non-secret config.
- Scan commits and images before release.

## Security validation

- [ ] No secret appears in source or image layers.
- [ ] No local token endpoint is exposed.
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

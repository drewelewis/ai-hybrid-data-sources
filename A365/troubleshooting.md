# Agent 365 Troubleshooting

## Triage order

Diagnose in this order:

1. Existing agent health.
2. Registration artifacts.
3. Sidecar/token acquisition.
4. OpenTelemetry instrumentation.
5. Exporter response.
6. Agent 365 licensing and presentation surfaces.

Do not change APIM, PostgreSQL, or VPN configuration to fix an A365-only
telemetry problem.

## Diagnostic baseline

```powershell
a365 --version
a365 setup requirements
Get-Content a365.generated.config.json | ConvertFrom-Json
Invoke-RestMethod http://127.0.0.1:8989/health
docker compose ps
docker compose logs --tail 100 ai-agent-starter-api
```

Never paste unredacted configuration or tokens into support requests.

## Symptom matrix

| Symptom | Likely cause | Action |
|---|---|---|
| Blueprint missing | Registration did not complete | Verify generated ID and Entra application |
| Agent identity creation fails | Missing BlueprintPrincipal or propagation delay | Verify principal; retry with bounded backoff |
| Agent absent from inventory | Missing registration/manageability metadata | Verify Agent 365 registration and `managerApplications` |
| Sidecar unhealthy | Invalid credential or configuration | Check private endpoint, credential source, and sidecar logs |
| HTTP 401 exporting | Missing/expired token or wrong audience | Acquire final Observability token and validate expiry/audience |
| HTTP 403 exporting | Agent ID mismatch or missing grant | Compare token subject, baggage, and export URL |
| `AADSTS82001` | Wrong exchange/grant type | Use supported `client_credentials` plus `fmi_path` flow |
| `AADSTS700211` | Federated identity mismatch or wrong tenant | Verify FIC subject/audience and home tenant |
| `AADSTS530035` in CLI | Device code blocked by policy | Use native Windows WAM or approved tenant-owned client; do not weaken policy |
| `AADSTS70007` in CLI | Old CLI authentication behavior | Update the Agent 365 CLI |
| HTTP 200 but no telemetry | Missing license or invalid root span | Verify E7/A365 license and `invoke_agent` root |
| Defender only, no admin view | Invalid/missing root or required attributes | Validate operation and required identity attributes |
| `No spans with tenant/agent identity found` | Missing baggage | Set tenant and agent ID baggage before creating spans |
| Chat hangs | Telemetry/token work blocking request loop | Move acquisition/export off request loop; bound timeout |
| Sensitive data appears | Content capture or broad attributes enabled | Disable exporter, investigate, tighten allowlist |
| Duplicate traces | Initialization called more than once | Initialize the distro once at process start |

## Token validation

Validate the final exporter token without logging it:

- Audience is the Agent 365 Observability resource.
- Token is app-only.
- Tenant is correct.
- Subject represents the registered agent identity.
- Token is not expired.
- No delegated `scp` claim is used for S2S.

Never send these to the exporter:

- Intermediate blueprint assertion.
- Blueprint application token.
- Human device-code token.
- APIM token.

## No telemetry investigation

1. Confirm one tenant user has Microsoft 365 E7 or Agent 365 assigned.
2. Confirm exporter is enabled.
3. Confirm one and only one Distro initialization.
4. Confirm the token resolver returns a token.
5. Confirm tenant/agent baggage wraps the root span.
6. Confirm `gen_ai.operation.name=invoke_agent`.
7. Confirm required conversation, agent, server, and channel attributes.
8. Query Defender Advanced Hunting before assuming ingestion failed.
9. Allow for documented processing delay.

## Registration investigation

Verify:

- Blueprint application/client ID.
- Blueprint object ID.
- BlueprintPrincipal.
- Agent identity client and object IDs.
- Sponsor.
- `managerApplications`.
- Tenant.
- Direct and inheritable permissions.

Directory creation can be eventually consistent. Retry only known propagation
failures and cap retries.

## Exporter performance

If telemetry affects chat latency:

- Confirm batch processing is enabled.
- Reduce queue/batch settings only after measuring.
- Verify token resolver caches valid tokens.
- Ensure token acquisition does not occur for every span.
- Check DNS/TLS reachability.
- Keep exporter timeout bounded.
- Do not retry user requests.

## Escalation package

Include:

- UTC timestamps.
- Tenant ID.
- Blueprint and agent object IDs.
- Trace/correlation IDs.
- CLI, sidecar, Python, and package versions.
- Sanitized HTTP status and error code.
- Reproduction steps.
- Confirmation that secrets/content were removed.

Exclude tokens, client secrets, APIM keys, database credentials, prompts, and
portfolio data.

## References

- [Agent 365 troubleshooting](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/troubleshooting)
- [Direct OTel troubleshooting](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/direct-open-telemetry-troubleshooting)
- [Agent ID FAQ](https://learn.microsoft.com/en-us/entra/agent-id/faq)

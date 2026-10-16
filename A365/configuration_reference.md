# Agent 365 Configuration Reference

## Principles

- Configuration is environment-specific.
- Secrets are never committed.
- Non-secret examples use placeholders.
- Startup fails explicitly when A365 is enabled but required values are absent.
- A365 can be disabled without changing chat, APIM, or database behavior.

## Application settings

| Variable | Required when enabled | Secret | Default | Purpose |
|---|---:|---:|---|---|
| `ENABLE_A365_OBSERVABILITY` | Yes | No | `false` | Master feature flag |
| `A365_TENANT_ID` | Yes | No | None | Tenant receiving telemetry |
| `A365_BLUEPRINT_CLIENT_ID` | Yes | No | None | Blueprint application/client ID |
| `A365_BLUEPRINT_CLIENT_SECRET` | Yes in the current implementation | Yes | None | Blueprint credential used only for the first token exchange |
| `A365_AGENT_ID` | Yes | No | None | Registered agent identity client ID |
| `A365_RECORD_CONTENT` | No | No | `false` | Enables approved nonproduction capture of prompts, responses, and available tool/inference content; may include portfolio data |
| `A365_CHANNEL_NAME` | No | No | `local-cli` | Stable channel attribute |
| `A365_SERVER_ADDRESS` | No | No | `localhost` | Agent service hostname exported as endpoint metadata |
| `A365_SERVER_PORT` | No | No | `SERVER_PORT` or `8989` | Agent service port exported as endpoint metadata |
| `A365_EXPORT_TIMEOUT_MS` | No | No | `30000` | Export timeout |
| `A365_SCHEDULED_DELAY_MS` | No | No | `5000` | Batch flush delay |
| `A365_MAX_QUEUE_SIZE` | No | No | `2048` | Export queue bound |
| `A365_MAX_EXPORT_BATCH_SIZE` | No | No | `512` | Export batch bound |

## Token exchange

The Python runtime performs the Agent ID two-step `fmi_path` exchange directly:

1. The blueprint credential requests `api://AzureADTokenExchange/.default`
   with `fmi_path` set to the registered Agent Identity client ID.
2. The returned parent token is used as a client assertion by the Agent
   Identity to request the Agent 365 Observability `/.default` scope.

The final token is cached in memory until shortly before expiry. Tokens and
credentials are never written to logs or telemetry. The current implementation
requires a blueprint client secret. An on-premises `prd` certificate or
approved workload-federation design is the target but requires a separate
runtime implementation before rollout.

## Secret sources

| Environment | Hosting | Approved source |
|---|---|---|
| `local` | On premises | Git-ignored `.env` or developer secret store |
| `dev` | On premises | Approved nonproduction secret store or protected deployment injection |
| `tst` | On premises | Approved test secret store or protected deployment injection |
| `prd` | On premises | Approved production secret store with certificate or workload federation as the target; not yet implemented |
| CI validation | Build platform only; not an agent runtime | Protected pipeline secret |

The blueprint secret is never added to:

- `env.sample`
- `docker-compose.yaml` defaults
- Documentation examples
- Test fixtures
- Logs
- Generated telemetry

## Example non-secret configuration

```dotenv
ENABLE_A365_OBSERVABILITY=false
A365_TENANT_ID=00000000-0000-0000-0000-000000000000
A365_BLUEPRINT_CLIENT_ID=00000000-0000-0000-0000-000000000000
A365_AGENT_ID=00000000-0000-0000-0000-000000000000
A365_RECORD_CONTENT=false
A365_CHANNEL_NAME=local-cli
A365_SERVER_ADDRESS=localhost
A365_SERVER_PORT=8989
```

## Startup validation

When `ENABLE_A365_OBSERVABILITY=true`, configuration loading fails before the
server starts if:

- A required ID is blank or malformed.
- The blueprint client secret is absent.
- Server address or port configuration is invalid.

`A365_RECORD_CONTENT=true` is an explicit override. Use it only for an approved
nonproduction policy test and return it to `false` afterward.

An invalid credential, token claim, tenant, or registered-object combination
fails token acquisition after application startup. It is reported as
`degraded` in `/health` and logged without credentials. It does not make
portfolio requests unavailable.

## Compatibility record

Record tested versions before rollout:

| Component | Version |
|---|---|
| Python | 3.11 |
| Microsoft Agent Framework | Current pinned repository version |
| `microsoft-opentelemetry` | 1.3.9 |
| Agent 365 CLI | 1.1.226 |
| Agent ID exchange | Direct two-step `fmi_path` |
| Docker Compose | Record at validation |
| Agent 365 docs review | October 14, 2026 |

Every dependency upgrade requires focused identity, telemetry, redaction, and
chat regression tests.

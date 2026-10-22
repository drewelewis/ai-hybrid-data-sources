# Trading Platform AI Agent

An AI-powered portfolio event ledger API built with **Microsoft Agent Framework**, **FastAPI**, and **Azure PostgreSQL** — deployed to **Azure Container Apps** and exposed as an **MCP server** via **Azure API Management**.

Microsoft Agent 365 identity, observability, governance, security, and
operational planning is documented in
[A365/readme.md](../../../A365/readme.md). Developers implementing or reviewing
the integration should start with the
[Agent 365 developer guide](../../../A365/developers_guide.md).

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Azure Infrastructure](#azure-infrastructure)
5. [Environment Variables](#environment-variables)
6. [API Endpoints](#api-endpoints)
7. [Database Schema](#database-schema)
8. [APIM MCP Gateway](#apim-mcp-gateway)
9. [Local Development](#local-development)
10. [Docker](#docker)
11. [Helper Scripts](#helper-scripts)
12. [Testing](#testing)

---

## Overview

The Trading Platform AI Agent provides two surfaces for interacting with a portfolio event ledger:

| Surface | Protocol | URL |
|---------|----------|-----|
| REST API | HTTP/JSON | `https://<aca-host>/` |
| MCP Server (AI Gateway) | MCP / Streamable HTTP | `https://ai-learning-apim.azure-api.net/trading-platform-mcp-server/mcp` |

The REST API exposes structured query endpoints and a natural-language **chat** endpoint backed by an Azure OpenAI-powered agent. The MCP server (hosted in Azure API Management) makes all 11 endpoints discoverable and callable by any MCP-compatible client — Claude Desktop, VS Code Copilot, custom agent frameworks — without a subscription key.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  MCP Clients                                             │
│  (Claude Desktop · VS Code Copilot · Custom Agents)      │
└────────────────┬─────────────────────────────────────────┘
                 │  MCP protocol (Streamable HTTP / SSE)
                 ▼
┌──────────────────────────────────────────────────────────┐
│  Azure API Management  (BasicV2+)                        │
│  ai-learning-apim.azure-api.net                          │
│                                                          │
│  ┌─────────────────────────────────────────────────┐     │
│  │ MCP Server: trading-platform-mcp-server         │     │
│  │ path: /trading-platform-mcp-server              │     │
│  │ type: mcp   subscriptionRequired: false         │     │
│  │ 11 tools: health, agentStatus, portfolioSummary │     │
│  │   latestPrice, tradeHistory, accountEvents,     │     │
│  │   tickerEvents, chat, clearSession, insertEvent │     │
│  │   root                                          │     │
│  └──────────────────────┬──────────────────────────┘     │
│                         │ REST proxy                      │
│  ┌────────────────────┐ └──────────────────────────────┐  │
│  │ REST API           │                               │  │
│  │ trading-platform-api                               │  │
│  │ path: /  (root)                                   │  │
│  │ subscriptionRequired: false                       │  │
│  └───────────────────────────────────────────────────┘  │
└────────────────┬─────────────────────────────────────────┘
                 │  HTTPS
                 ▼
┌──────────────────────────────────────────────────────────┐
│  Azure Container Apps                                    │
│  ai-learning-aca  (East US)                              │
│  min-replicas: 1  |  ingress: external  |  port: 8989   │
│                                                          │
│  Trading Platform FastAPI (Python 3.11)                  │
│  ├── GET  /health                                        │
│  ├── GET  /                                              │
│  ├── POST /chat                      ─┐                  │
│  ├── POST /clear_session              ├─ Agent endpoints │
│  ├── GET  /portfolio/{account_id}    ─┘                  │
│  ├── GET  /portfolio/{account_id}/trades                 │
│  ├── GET  /portfolio/{account_id}/events                 │
│  ├── GET  /ticker/{ticker_symbol}/price                  │
│  ├── GET  /ticker/{ticker_symbol}/events                 │
│  ├── POST /events                                        │
│  └── GET  /agent/status                                  │
└──────┬───────────────────┬────────────────────────────────┘
       │                   │
       │ asyncpg           │ subscription key + Entra token
       ▼                   ▼
┌─────────────┐   ┌────────────────────────────────────────┐
│  Azure      │   │  Azure API Management AI Gateway       │
│  PostgreSQL │   │  governed /openai model API            │
│  Flexible   │   └──────────────────┬─────────────────────┘
│  Server     │                      │ managed identity
│  (SSL)      │                      ▼
└─────────────┘   ┌────────────────────────────────────────┐
                  │  Azure OpenAI / AI Foundry             │
                  │  Model: configured deployment          │
                  └────────────────────────────────────────┘
```

### Request Flow — MCP Tool Call (e.g. `portfolioSummary`)

```
Client --[MCP call_tool "portfolioSummary" {account_id: "A100"}]--> APIM
APIM   --[GET /portfolio/A100]--> Container Apps
Container Apps --[asyncpg SELECT]--> PostgreSQL
PostgreSQL --[rows]--> Container Apps
Container Apps --[JSON {account_id, positions: [...]}]--> APIM
APIM   --[MCP tool result]--> Client
```

### Request Flow — NL Chat via MCP

```
Client --[MCP call_tool "chat" {session_id, message}]--> APIM
              ↓ inbound policy reconstructs JSON body
APIM   --[POST /chat {session_id, message}]--> Container Apps
Container Apps --[agent.run(message, thread)]--> APIM AI Gateway
APIM --[managed identity]--> Azure OpenAI
Azure OpenAI --[tool_calls: get_portfolio_summary, ...]-->
  Container Apps executes tools against PostgreSQL
  Container Apps --[final text response]--> APIM
APIM --[MCP tool result {response: "..."}]--> Client
```

---

## Project Structure

```
.
├── main.py                          # Uvicorn entry point (port 8989)
├── chat.py                          # Interactive CLI chat client
├── a365_verify.py                   # Repeatable synthetic Agent 365 conversation
├── requirements.txt                 # Python dependencies
├── dockerfile                       # Production container image (python:3.11-slim)
├── docker-compose.yaml              # Local stack: API + PostgreSQL + Adminer
├── env.sample                       # Template — copy to .env
│
├── api/
│   ├── main.py                      # FastAPI app — all REST endpoints
│   └── main_with_proxy.py           # Alternative with APIM proxy headers
│
├── agents/
│   └── trading_platform_agent.py   # ChatAgent definition + system prompt
│
├── operations/
│   └── trading_platform_operations.py  # asyncpg queries (connection pool, retry)
│
├── tools/
│   └── trading_platform_tool.py    # ai_function wrappers (agent-callable tools)
│
├── models/
│   └── chat_models.py              # Pydantic request/response models
│
├── data/
│   ├── ddl.sql                      # PostgreSQL schema + indexes
│   ├── portfolio_event_ledger_500.csv  # Synthetic seed data (500 rows)
│   └── portfolio_event_ledger_schema.json
│
├── tests/
│   └── test_mcp.py → (root)        # (see test_mcp.py below)
│
├── test_mcp.py                      # End-to-end MCP server test (8 tools)
│
└── infra/
    └── apim-mcp-body.json          # APIM MCP ARM body reference
```

---

## Azure Infrastructure

### Required Resources

| Resource | SKU / Tier | Notes |
|----------|-----------|-------|
| **Resource Group** | — | `ai-learning-rg` |
| **Azure Container Registry** | Basic+ | Stores `drewl/ai-agent-starter-portfolio-manager` |
| **Azure Container Apps Environment** | Consumption | `ai-learning-aca`, East US |
| **Azure Container Apps** (app) | — | min-replicas: 0, port 8989, external ingress |
| **Azure PostgreSQL Flexible Server** | Burstable B1ms+ | SSL required, `portfolio_event_ledger` table |
| **Azure OpenAI** or **AI Foundry** | Configured deployment | Private model backend |
| **Azure API Management** | **BasicV2+** | MCP server and governed `/openai` model API |

> **Important:** APIM MCP server support (`type: "mcp"`) requires **BasicV2 tier or higher**. The Developer and Consumption tiers do not support this feature.

### APIM Configuration

The agent uses three APIM surfaces:

| APIM Object | Type | Path | Auth |
|-------------|------|------|------|
| `trading-platform-api` | REST | `/` (root) | Anonymous |
| `trading-platform-mcp-server` | MCP | `/trading-platform-mcp-server` | Anonymous |
| `foundry-openai` | REST | `/openai` | Product subscription + Entra JWT |

The MCP API is created as `type: mcp` via the Azure Portal (API Management → APIs → + Add API → MCP Server). It auto-discovers the 11 tools from the OpenAPI spec of the REST backend.

### Managed Identity

The Container App uses a **system-assigned managed identity** with the following role assignments:

| Role | Scope | Purpose |
|------|-------|---------|
| API application authorization | APIM model API | Obtain a token for `APIM_TOKEN_SCOPE` |

Authentication uses `DefaultAzureCredential` — managed identity in Azure, `az login` locally.
APIM uses its own managed identity to call the private Foundry backend.

---

## Environment Variables

Copy `env.sample` to `.env` and fill in:

```env
# ── Governed Azure OpenAI route through APIM ──────────────
MODEL_ENDPOINT_MODE=apim
MODEL_DEPLOYMENT_NAME=gpt-5.4-mini
AZURE_OPENAI_API_VERSION=2024-02-01
APIM_OPENAI_ENDPOINT=https://your-apim.azure-api.net
APIM_TOKEN_SCOPE=api://your-apim-api-app-client-id/.default
APIM_SUBSCRIPTION_KEY=your-server-side-apim-subscription-key

# APIM_OPENAI_ENDPOINT is the gateway origin only. The SDK appends
# /openai/deployments/{deployment}/chat/completions.

# ── Direct Foundry fallback (MODEL_ENDPOINT_MODE=direct) ──
AZURE_OPENAI_API_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_OPENAI_TOKEN_SCOPE=https://cognitiveservices.azure.com/.default

# ── Azure PostgreSQL Flexible Server ──────────────────────
POSTGRES_HOST=your-server.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=your-admin-user
POSTGRES_PASSWORD=your-password
POSTGRES_SSL_MODE=require

# ── API Server ─────────────────────────────────────────────
SERVER_HOST=0.0.0.0
SERVER_PORT=8989
SERVER_RELOAD=false          # true = uvicorn --reload (dev only)
SERVICE_NAME=trading-platform-api
SERVICE_VERSION=1.0.0
SERVER_URL=                  # Public base URL for Swagger UI (e.g. https://your-aca-host)

# ── Docker ─────────────────────────────────────────────────
DOCKER_REPO_NAME=drewl/ai-agent-starter-portfolio-manager

# ── APIM MCP ───────────────────────────────────────────────
APIM_MCP_SERVER_URL=https://ai-learning-apim.azure-api.net/trading-platform-mcp-server/mcp

# ── Azure Credentials (optional — for local dev without az login) ──
AZURE_AUTH_MODE=default        # use device-code for interactive local Docker sign-in
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_TENANT_ID=

# ── Microsoft Agent 365 metadata-only observability ────────
ENABLE_A365_OBSERVABILITY=false
A365_TENANT_ID=00000000-0000-0000-0000-000000000000
A365_BLUEPRINT_CLIENT_ID=00000000-0000-0000-0000-000000000000
A365_AGENT_ID=00000000-0000-0000-0000-000000000000
A365_RECORD_CONTENT=false
A365_CHANNEL_NAME=local-cli
```

For local Docker, set `AZURE_AUTH_MODE=device-code`, `AZURE_TENANT_ID`, and
`AZURE_CLIENT_ID` to a public-client app registration with delegated access to
the APIM API. `chat.py` requests the device code on the host, opens the
Microsoft sign-in URL, and sends the resulting bearer token to the local API.
The API forwards that user token to APIM alongside its server-held subscription
key; the API container does not perform the interactive sign-in.

Agent 365 observability is disabled by default. After completing the
[Agent 365 provisioning runbook](../../../A365/provisioning_runbook.md), place the
blueprint client secret in the git-ignored `.env` as
`A365_BLUEPRINT_CLIENT_SECRET`; never add it to `env.sample`. The integration
uses an app-only two-step Agent ID exchange and does not reuse the interactive
APIM user token. Prompt and response recording remains disabled.

### Optional pilot: calendar scheduling and portfolio reviews using Microsoft Graph

This opt-in scenario combines the signed-in user's calendar with the existing
ledger tools. The existing blueprint remains the credential boundary; Graph
access runs as its child agent identity **on behalf of the user**, not as the
provisioning app or the model endpoint identity.

With the feature enabled, the agent can read the **whole primary calendar**,
not just review-marked meetings. The portfolio-review tool remains separate
because its exact subject markers link meetings to ledger accounts.

The layers follow the trading-platform operations/tools pattern:
[`operations/graph_operations.py`](operations/graph_operations.py) owns Graph
transport, delegated token exchange, calendar rules, proposal state and confirmed
writes, returning structured data. [`tools/graph_tool.py`](tools/graph_tool.py)
only exposes typed model tools and formats those results as JSON. The API creates
one operations instance per validated caller request and injects it into the tool
adapter; it never shares user assertions through a global operations singleton.
Confirmation endpoints call operations directly, not model tools.

The implementation is disabled by default. Repository tests use mocked Microsoft
responses; they do not prove tenant consent, mailbox access, or live token
exchange. Complete the following tenant setup with an authorized administrator
before enabling it:

1. Verify the blueprint and child agent identity IDs against the tenant. The
   local generated configuration is a historical provisioning artifact, not a
   live permission inventory. Review existing inheritance and effective grants.
2. Verify the existing delegated API scope named `access_agent_as_user` on the blueprint,
   with identifier URI `api://<blueprint-client-id>`. Configure v2 access tokens.
   Authorize the existing public CLI client (`AZURE_CLIENT_ID`) to request that
   scope, with the required consent and public-client device-code configuration.
   Preserve its existing APIM API permissions.
3. Grant the child agent identity only the delegated Microsoft Graph permission
   `Calendars.ReadBasic` for read-only preparation. Use the supported Agent ID consent
   workflow; do not grant broad Graph application permissions to the blueprint
   or reuse permissions granted to the provisioning application.
4. Confirm the demo user has an accessible Exchange calendar. No agent mailbox,
   agent user account, email permission, or calendar write permission is needed
   for read-only preparation. The optional confirmed save workflow below
   requires separately approved delegated calendar-write permission.

Protocol and permission references:
[interactive agent authentication](https://learn.microsoft.com/en-us/entra/agent-id/interactive-agent-authentication-authorization-flow),
[Agent ID OBO exchange](https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow),
and [Graph calendarView](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0).
Tenant setup is an administrative change requiring separate approval; restarting
the application does not perform provisioning or consent.

After approval, configure the API's ignored `.env` using the existing tenant,
blueprint, child agent IDs, and server-side `A365_BLUEPRINT_CLIENT_SECRET`.
The pilot uses the existing local-development secret; production must instead
use an approved managed-identity federation or certificate implementation.
Never copy the protected secret from the generated configuration into source
code or treat its encrypted value as a plaintext credential.

```dotenv
ENABLE_GRAPH_CALENDAR=true
GRAPH_CALENDAR_UTC_OFFSET=-04:00
A365_RECORD_CONTENT=false
```

Set the same feature flag, calendar offset, `A365_BLUEPRINT_CLIENT_ID`,
`AZURE_TENANT_ID`, and public-client `AZURE_CLIENT_ID` in the host environment
used by `chat.py`. The CLI never needs the blueprint secret. Keep model
authentication configured as before. Rebuild/restart the API through the usual
local workflow, then run `python chat.py`.

The CLI acquires **two different tokens** when using device-code model auth:

| Header | Audience and purpose |
|---|---|
| `Authorization: Bearer ...` | Existing APIM/model resource; used only for model calls |
| `X-Agent-Authorization: Bearer ...` | Blueprint API with `access_agent_as_user`; validated by this API and exchanged for delegated Graph access |

With server-side model credentials, only the second user token is needed.
Custom clients and gateways must forward `X-Agent-Authorization`; do not send a
Graph-audience token or reuse the model token in that header. When both tokens
are used, their validated tenant and user IDs must match. Each calendar-enabled
chat and session-clear request requires the blueprint token, even with
observability disabled. Conversation threads are isolated by tenant, caller
object ID, and session ID. Tokens remain request-local and are not put into
conversation history or tool arguments.

**Stage the demo in Outlook using synthetic data:**

1. Pick an existing **synthetic** account from the local ledger. Create an event
   on the demo user's primary calendar with the exact subject
   `Portfolio Review - DEMO-<account_id>`. For ledger account `A100`, use
   `Portfolio Review - DEMO-A100`; for a UUID account, include the full UUID after
   `DEMO-`. The prefix is removed to obtain the exact ledger account ID.
2. Schedule it on the intended demo date. Cancelled events are ignored;
   unmarked meetings are not returned to the model. Read-only preparation does
   not request bodies, attendees, locations, or attachments. Hyphen, en dash, and em dash
   separators are supported.
3. Ask: **"Prepare me for my portfolio reviews today. Show the relevant holdings
   and highlight positions worth discussing."** Alternatively specify a date,
   such as **"Prepare my portfolio reviews for 2026-10-22."**
4. Verify the returned meeting time, exact account mapping, holdings,
   concentration observations, and price timestamps against Outlook and the
   ledger. Observed prices are not live market quotes. No matched meetings,
   unknown accounts, or service failures must be reported explicitly.

For the **review-only tool**, `GRAPH_CALENDAR_UTC_OFFSET` defines the day boundary; it is a fixed offset, not a
daylight-saving-aware time zone. The default is UTC. Meeting times are returned
in UTC. The tool retrieves one day, follows Graph pagination within the same
calendar endpoint, and fails explicitly above the pilot limit of 500 events
rather than producing an incomplete briefing.

#### Read the full schedule and find openings

`get_calendar_schedule` returns every noncancelled event in a requested
inclusive date range of up to 31 days, including ordinary meetings, all-day
events, and expanded recurring occurrences. It returns subjects and times,
not bodies or attendees. Private event subjects are redacted, but their times
remain visible and block scheduling. It shares the existing pagination and
500-event completeness limit; failures never become an empty/free calendar.

`find_available_slots` uses the agreed pilot scheduling rules:

- **Monday-Friday, 09:00-17:00 America/New_York**, with daylight-saving-aware
  date boundaries. The declared `tzdata` dependency makes IANA timezone data
  available on Windows as well as in containers.
- **60 minutes by default**, or a requested duration of 1-480 minutes.
- **Every noncancelled event blocks**, including events marked Free. This is
  intentional for the existing synthetic batch; its Free status does not make
  its meeting times available to this scheduler.
- Touching endpoints do not overlap; cancelled events do not block. Past
  times are never suggested. All-day/multi-day events and overlapping
  occurrences are included in the conflict check.
- At most 50 earliest non-overlapping suggestions are returned, with an
  explicit `more_slots_available` flag. These are suggested start times, not
  an exhaustive enumeration of every possible start minute.

These tools use Eastern time independently of the older review tool's fixed
offset. Results include UTC and offset-aware Eastern timestamps, including
across DST transitions. Relative dates use the current Eastern date; follow-up
schedule requests should preserve the date being discussed or ask to clarify.

Examples:

> Show my full schedule for tomorrow.
>
> Find 60-minute openings next week.

Only the signed-in organizer's **primary calendar** is checked. Shared or
secondary calendars and attendees' free/busy are not aggregated. A proposed
opening is not a reservation or a promise that customers are available.

Calendar mode removes `insert_trade_event` from the chat agent's tools. It does
**not** disable existing REST write endpoints or add account-level authorization
to the shared ledger. Calendar markers are not account entitlements. Use only
synthetic accounts in this pilot; production requires separate data-access
controls. Keep content telemetry disabled to avoid exporting calendar-derived
briefings and portfolio content.

For live acceptance, also verify that a second user cannot retrieve or clear the
first user's thread using the same session ID, and that missing/invalid tokens
fail before model execution. Permission denial, throttling, and network errors
are tool errors, never an empty-calendar success. `/health` and `/agent/status`
advertise whether the feature is configured; neither proves live Graph access.
Disable `ENABLE_GRAPH_CALENDAR` and restart the API/CLI to restore the original
chat tool set. Tenant permission/scope rollback is a separate approved action.

#### Optional: save the briefing into the meeting after explicit confirmation

Reading a meeting does **not** write the generated briefing into its invitation.
For a reusable save workflow, obtain separate approval to add delegated
`Calendars.ReadWrite` to the **child agent's existing pilot-user-specific Graph
grant**, preserving existing scopes. This grants broader calendar access than
`Calendars.ReadBasic`; the following restrictions are application controls, not
scope-level limits. Do not grant tenant-wide or application permissions.

Enable `ENABLE_GRAPH_CALENDAR_WRITE=true` in the API's ignored environment and
rebuild/restart it. `ENABLE_GRAPH_CALENDAR=true` must also remain enabled.
The CLI still uses the existing blueprint scope and never needs a Graph token
or blueprint credential. No changes to the generated provisioning configuration
are needed. Check `/health` for `graph_calendar.briefing_write_enabled`.

In `chat.py`, ask:

> Prepare my portfolio review for 2026-10-23 and add the briefing to its meeting.

The additional model tool, `prepare_portfolio_review_briefing`, **only prepares
a proposal**. It finds exactly one marked review for the account/date, verifies
that the signed-in user is its organizer and that it is a non-recurring,
uncancelled event, and snapshots its body and version. Existing descriptions,
including online-meeting joining information, are preserved. The existing body
is not sent to the model; the proposal includes the new briefing, meeting times,
organizer, and attendee addresses so the user can review its destination.

The CLI displays that exact proposed addition and warns that saving may send
an updated invitation to **all listed attendees**. Only typing the displayed
`SAVE <proposal-id>` confirmation sends the separate authenticated request.
Anything else cancels; an ordinary chat message saying "yes" is not approval.
Merely preparing a briefing, or the model claiming approval, cannot save it.

Custom clients must display `/chat`'s optional `calendar_update` preview, obtain
explicit approval outside the model, then POST to `/calendar/briefing/decision`
with `X-Agent-Authorization`:

```json
{
  "session_id": "the-same-session",
  "proposal_id": "the-UUID-from-calendar_update",
  "decision": "confirm"
}
```

Use `"cancel"` to discard it. The decision endpoint never invokes the model and
accepts no replacement content or arbitrary event ID. Proposals are bound to
tenant/user/session, expire after 15 minutes, and are single-use, including on
save failure. New chat, session clear, or API restart invalidates pending
approvals. State is in memory, like conversation threads; use a single API
process for this pilot. A scaled deployment needs a shared approval store.

Confirmation re-reads the event, rejects a changed snapshot, and PATCHes **only
the body** with its Graph `If-Match` version. It then reads the event back to
check the briefing, preserved description, and meeting metadata. Stale,
throttled, uncertain, or failed updates are explicit errors, not success, and
are never automatically retried. After an uncertain failure, inspect Outlook
before preparing another update. These steps do not prove attendee delivery.
Read-back compares visible HTML body text, excluding hidden styles/scripts;
Exchange may normalize HTML formatting without changing the description.

Disable `ENABLE_GRAPH_CALENDAR_WRITE` and restart the API to restore read-only
calendar mode. Removing delegated write consent, or restoring a previously
saved meeting body, requires a separately approved administrative action.
Keep `A365_RECORD_CONTENT=false`; only synthetic portfolio content belongs in
this pilot.

#### Optional: create a customer invitation after explicit confirmation

The same approved delegated `Calendars.ReadWrite` grant and
`ENABLE_GRAPH_CALENDAR_WRITE=true` flag enable `prepare_customer_meeting`.
No additional blueprint scope, mail permission, or application grant is needed.
This tool only stages an invitation; it cannot send, create, or approve it.
The existing model-callable briefing and creation tools both remain
proposal-only, and ledger insertion remains unavailable.

In write-enabled sessions, the agent explains that it can prepare an invitation
which the application can create and send after explicit CLI approval. It must
not describe this capability as draft-only or claim the invitation was already
sent after staging a proposal. Read-only sessions must instead explain that
calendar writes are disabled.

Provide an exact customer email, subject, agenda/body and desired date or
chosen opening. The agent must ask for missing recipients rather than guess
from customer names, previous meetings or ledger records. The tool accepts
1-20 distinct explicit email addresses and enforces a future weekday time
within the working window. It checks conflicts before proposing, then derives
the organizer from the primary calendar owner.

The CLI previews **NEW meeting**, complete body, subject, UTC/Eastern time,
organizer and every recipient. Only typing **`SEND <proposal-id>`** creates it;
`SAVE`, "yes", ordinary chat, cancellation, or model text cannot send it.
Briefing updates continue to use `SAVE` and their existing endpoint.

Custom clients must render `/chat`'s `calendar_update` with
`action: "create_meeting"` and obtain explicit approval outside the model.
Then POST the same `session_id`, `proposal_id`, and `"decision": "confirm"`
(or `"cancel"`) to **`/calendar/meeting/decision`**, authenticated with the
blueprint `X-Agent-Authorization` token. No replacement event fields are
accepted. Approval remains caller/session-bound, expires in 15 minutes, and
is consumed before executing, including on failures. New chat, clear, or
restart discards it. The briefing endpoint cannot consume a creation proposal.

At confirmation, the API rechecks the entire chosen interval against all
noncancelled primary-calendar events. It serializes its own creation requests
per caller within this single API process. Outlook/other clients can still
race with that check: Graph does not atomically reserve availability, and
attendee free/busy is not checked.

Creation sends the exact reviewed body and recipient list, marks the event
Busy, and assigns the proposal UUID as Graph `transactionId` for correlation
and duplicate protection. A successful Graph `201 Created` is followed by
read-back verification of organizer, recipients, times, body, subject,
transaction ID and Busy status. Failure is explicit and never automatically
retried: creation might already have succeeded, so inspect the calendar before
trying again. Organizer-side verification does not prove invitation delivery
or acceptance. These controls do not authorize automatic bulk scheduling.

---

## API Endpoints

Base URL (production): `https://ai-learning-aca.ashycliff-5cba4403.eastus.azurecontainerapps.io`
Interactive docs: `<base-url>/docs`

### GET `/`
Service info and endpoint map.

**Response:**
```json
{
  "service": "trading-platform-api",
  "version": "1.0.0",
  "docs": "/docs",
  "endpoints": { ... }
}
```

---

### GET `/health`
Service health check including database connectivity.

**Response:**
```json
{
  "status": "healthy",
  "service": "trading-platform-api",
  "version": "1.0.0",
  "agent": "ready",
  "database": "connected",
  "framework": "Microsoft Agent Framework"
}
```

`status` is `"healthy"` only when both the agent and database are ready. Degrades to `"degraded"` otherwise.

---

### POST `/chat`
Natural-language chat with the Trading Platform Agent. Maintains full conversational context per `session_id`.

**Request:**
```json
{ "session_id": "user-1", "message": "Give me a portfolio summary for account A100" }
```

**Response:**
```json
{
  "session_id": "user-1",
  "response": "Account A100 holds 175 shares of MSFT ...",
  "agent": "TradingPlatformAgent"
}
```

The agent has 13 tools by default. Calendar pilot mode replaces trade insertion
with review, full-schedule, and slot-finding read tools. Optional calendar
writes add briefing and invitation proposal tools, never model-callable
save/send operations. `/chat` returns `calendar_update`
only when a proposal was prepared; see the confirmation workflow above.
Conversation history is maintained in memory; calendar mode additionally binds
it to the validated tenant and user.

---

### POST `/clear_session`
Clears the conversation history for a session.

**Request:**
```json
{ "session_id": "user-1" }
```

**Response:**
```json
{ "status": "cleared", "session_id": "user-1" }
```

---

### GET `/portfolio/{account_id}`
Net share position, net cost basis, and last observed price per ticker for an account.

**Example:** `GET /portfolio/A100`

**Response:**
```json
{
  "account_id": "A100",
  "positions": [
    {
      "account_id": "A100",
      "ticker_symbol": "MSFT",
      "net_shares": 175.0,
      "net_cost": 52830.0,
      "last_price": 416.10,
      "last_event_ts": "2026-02-20T15:00:00+00:00"
    }
  ]
}
```

Calculation: `net_shares = SUM(BUY shares) - SUM(SELL shares)`, `net_cost = SUM(BUY value) - SUM(SELL value)`.

---

### GET `/portfolio/{account_id}/trades`
BUY and SELL trade history for an account.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `event_type` | string | — | Filter by `BUY` or `SELL` |
| `limit` | int | 100 | Max rows |

**Example:** `GET /portfolio/A100/trades?event_type=BUY&limit=5`

**Response:**
```json
{
  "account_id": "A100",
  "event_type": "BUY",
  "trades": [
    {
      "id": 499,
      "account_id": "A100",
      "ticker_symbol": "MSFT",
      "event_ts": "2026-02-03T07:15:00+00:00",
      "event_type": "BUY",
      "shares": 10.0,
      "price_per_share": 349.5,
      "currency": "USD",
      "source": "synthetic"
    }
  ]
}
```

---

### GET `/portfolio/{account_id}/events`
All ledger events (BUY, SELL, PRICE) for an account, newest first.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 100 | Max rows |

**Response:**
```json
{
  "account_id": "A100",
  "count": 100,
  "events": [ { ... }, ... ]
}
```

---

### GET `/ticker/{ticker_symbol}/price`
Most recently observed market price for a ticker (latest `PRICE` event).

**Example:** `GET /ticker/MSFT/price`

**Response:**
```json
{
  "ticker_symbol": "MSFT",
  "price_per_share": 416.10,
  "currency": "USD",
  "event_ts": "2026-02-20T15:00:00+00:00"
}
```

Returns `404` if no PRICE events exist for the ticker.

---

### GET `/ticker/{ticker_symbol}/events`
All ledger events for a ticker across all accounts, newest first.

**Query params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 100 | Max rows |

**Response:**
```json
{
  "ticker_symbol": "MSFT",
  "count": 100,
  "events": [ { ... }, ... ]
}
```

---

### POST `/events`
Insert a new portfolio event into the ledger.

**Request:**
```json
{
  "account_id": "A100",
  "ticker_symbol": "MSFT",
  "event_ts": "2026-02-22T10:00:00Z",
  "event_type": "BUY",
  "shares": 5.0,
  "price_per_share": 420.0,
  "currency": "USD",
  "source": "api"
}
```

`event_type` must be `BUY`, `SELL`, or `PRICE`. Use `shares: 0` for PRICE events.

**Response (201):**
```json
{ "status": "created", "id": 501, "account_id": "A100", ... }
```

---

### GET `/agent/status`
Agent capabilities and registered tool list.

**Response:**
```json
{
  "agent": "TradingPlatformAgent",
  "status": "ready",
  "tools": [
    { "name": "get_events_by_account", "description": "All events for an account" },
    { "name": "get_events_by_ticker", "description": "All events for a ticker" },
    { "name": "get_portfolio_summary", "description": "Net position + cost basis per ticker" },
    { "name": "get_latest_price", "description": "Most recent PRICE observation" },
    { "name": "get_trade_history", "description": "BUY/SELL history, filterable by type" },
    { "name": "insert_trade_event", "description": "Insert a new ledger event" },
    { "name": "check_database_health", "description": "DB connectivity probe" }
  ]
}
```

---

## Database Schema

### Table: `portfolio_event_ledger`

```sql
CREATE TABLE portfolio_event_ledger (
    id               BIGSERIAL       PRIMARY KEY,
    account_id       VARCHAR(64)     NOT NULL,
    ticker_symbol    VARCHAR(16)     NOT NULL,
    event_ts         TIMESTAMPTZ     NOT NULL,
    event_type       VARCHAR(8)      NOT NULL CHECK (event_type IN ('BUY', 'SELL', 'PRICE')),
    shares           NUMERIC(18, 6)  NOT NULL DEFAULT 0,
    price_per_share  NUMERIC(18, 6)  NOT NULL,
    currency         VARCHAR(8)      NOT NULL,
    source           VARCHAR(128)    NOT NULL,
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
```

### Columns

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL | Auto-increment PK |
| `account_id` | VARCHAR(64) | e.g. `A100`, `ACC-001` |
| `ticker_symbol` | VARCHAR(16) | e.g. `MSFT`, `AAPL` |
| `event_ts` | TIMESTAMPTZ | When the event occurred |
| `event_type` | VARCHAR(8) | `BUY` / `SELL` / `PRICE` |
| `shares` | NUMERIC(18,6) | Number of shares; `0` for PRICE events |
| `price_per_share` | NUMERIC(18,6) | Trade price or market observation |
| `currency` | VARCHAR(8) | ISO code, e.g. `USD` |
| `source` | VARCHAR(128) | `broker`, `market-feed`, `api`, `synthetic` |
| `created_at` | TIMESTAMPTZ | Row insert timestamp |

### Indexes

```sql
-- Primary query pattern: account + time
CREATE INDEX idx_pel_account_ts      ON portfolio_event_ledger (account_id, event_ts DESC);
-- Ticker market queries
CREATE INDEX idx_pel_ticker_ts       ON portfolio_event_ledger (ticker_symbol, event_ts DESC);
-- Event type filtering (P&L)
CREATE INDEX idx_pel_event_type      ON portfolio_event_ledger (event_type);
-- Position roll-up
CREATE INDEX idx_pel_account_ticker  ON portfolio_event_ledger (account_id, ticker_symbol, event_ts DESC);
```

Apply schema: `psql -h <host> -U <user> -d postgres -f data/ddl.sql`
Load seed data: `psql -h <host> -U <user> -d postgres -c "\COPY portfolio_event_ledger FROM 'data/portfolio_event_ledger_500.csv' CSV HEADER"`

---

## APIM MCP Gateway

### Endpoint

```
https://ai-learning-apim.azure-api.net/trading-platform-mcp-server/mcp
```

No API key required (`subscriptionRequired: false`).

### MCP Tools (11)

| Tool | Maps to | Description |
|------|---------|-------------|
| `health` | `GET /health` | Service + DB health |
| `agentStatus` | `GET /agent/status` | Registered tools |
| `portfolioSummary` | `GET /portfolio/{account_id}` | Net positions |
| `latestPrice` | `GET /ticker/{ticker_symbol}/price` | Latest market price |
| `tradeHistory` | `GET /portfolio/{account_id}/trades` | BUY/SELL history |
| `accountEvents` | `GET /portfolio/{account_id}/events` | All account events |
| `tickerEvents` | `GET /ticker/{ticker_symbol}/events` | All ticker events |
| `chat` | `POST /chat` | NL chat with agent |
| `clearSession` | `POST /clear_session` | Clear session history |
| `insertEvent` | `POST /events` | Insert new event |
| `root` | `GET /` | Service info |

### Using from Python

```python
import asyncio, httpx, os
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

load_dotenv()
MCP_URL = os.getenv("APIM_MCP_SERVER_URL")

async def main():
    async with httpx.AsyncClient(timeout=120.0) as http:
        async with streamable_http_client(MCP_URL, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                # List tools
                tools = await session.list_tools()
                # Call a tool
                result = await session.call_tool("latestPrice", {"ticker_symbol": "MSFT"})
                print(result.content[0].text)

asyncio.run(main())
```

### APIM MCP Preview — POST Body Workaround

**Issue:** APIM MCP (`2025-03-01-preview`) correctly proxies path/query parameters for GET endpoints but does **not** serialize MCP tool arguments into a JSON request body for POST endpoints. FastAPI receives an empty body and returns HTTP 422.

**Affected tools:** `chat`, `clearSession`, `insertEvent`

**Fix:** An APIM inbound policy on each POST operation reconstructs the JSON body from the query parameters APIM forwards:

```xml
<policies>
  <inbound>
    <base />
    <!-- APIM MCP preview: rebuild JSON body from query params -->
    <set-body>@{
      try {
        var body = context.Request.Body?.As&lt;JObject&gt;(true);
        if (body != null &amp;&amp; body.ContainsKey("session_id")) { return body.ToString(); }
      } catch {}
      var s = context.Request.Url.Query.GetValueOrDefault("session_id", "mcp-session");
      var m = context.Request.Url.Query.GetValueOrDefault("message", "");
      return new JObject(
        new JProperty("session_id", s),
        new JProperty("message", m)
      ).ToString();
    }</set-body>
    <set-header name="Content-Type" exists-action="override">
      <value>application/json</value>
    </set-header>
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error><base /></on-error>
</policies>
```

Deploy via:
```bash
# Build policy_body.json: { "properties": { "value": "<policies>...</policies>", "format": "xml" } }
az rest --method PUT \
  --uri "https://management.azure.com/subscriptions/{subId}/resourceGroups/ai-learning-rg/providers/Microsoft.ApiManagement/service/ai-learning-apim/apis/trading-platform-api/operations/chat_chat_post/policies/policy?api-version=2022-08-01" \
  --body "@policy_body.json" \
  --headers "Content-Type=application/json"
```

---

## Local Development

### Prerequisites

- Python 3.11+
- Azure CLI (`az login`)
- Access to the governed APIM model API, or direct Foundry access when
  `MODEL_ENDPOINT_MODE=direct`
- PostgreSQL connection (Azure or local Docker)

### Setup

```bash
# 1. Create and activate virtual environment
_env_create.bat
_env_activate.bat

# 2. Install dependencies
_install.bat

# 3. Copy and fill in environment variables
copy env.sample .env
# Edit .env with your values

# 4. Start the API server locally
python main.py
# → http://localhost:8989/docs
```

### Interactive CLI Chat

```bash
python chat.py
```

Presents a REPL that sends messages to `POST /chat` and prints responses. It
connects to `http://127.0.0.1:8989` by default; set `CHAT_API_URL` to target a
different running API instance.

Follow-up account references such as "account 1", "the first account", or
"that account" should reuse the exact ledger account ID from the most recent
relevant numbered account list or the single account under discussion.
Ambiguous references, missing lists and out-of-range positions require
clarification before lookup; a list position is not a literal account ID.

Interactive terminals use the existing `colorama` dependency: cyan for prompts
and information, green for agent replies and success, yellow for sign-in and
calendar confirmation warnings, and red for errors. Approval commands remain
exactly `SAVE <proposal-id>` and `SEND <proposal-id>`. Colors reset after each
message and are disabled for redirected output, `TERM=dumb`, or when `NO_COLOR`
is set (including an empty value). On PowerShell, use `$env:NO_COLOR = '1'`
to disable colors.

The React and Python clients share the APIM token-limit counter when they use
the same APIM subscription and model. If APIM returns HTTP 429, the CLI displays
the `Retry-After` duration and does not retry automatically.

### Repeatable Agent 365 Verification

Use the scripted conversation harness to generate a longer, reproducible batch
for Microsoft Entra, Microsoft Purview, and Microsoft Defender:

```powershell
.\.venv\Scripts\python.exe a365_verify.py
```

The harness uses the same device-code authentication and `/chat` path as
`chat.py`. It has one fixed operator profile: five conversation rounds, a
five-second delay between interactions, policy-oriented synthetic scenarios,
automatic evidence output, and automatic opening of the Entra, Purview, and
Defender portals. Each round behaves like an ordinary user: it asks about a
public ticker observation, checks service health, asks a follow-up, or
validates a generated QA account reference. It never calls a data-changing
tool or uses a real account identifier.

Every run appends one or two randomly selected safe exploit attempts after a
complete normal conversation in randomly selected rounds. These can request
hidden instructions, credential disclosure, exfiltration to the reserved
`security-test.invalid` domain, or unauthorized access to a generated
nonexistent account. The content-policy pool also includes a standard
synthetic payment-card pattern and fictional misconduct. At least one selected
attempt targets a content-policy category. The run records its random seed in
the evidence bundle for audit.

The command prints every synthetic turn and response. It also writes a
Git-ignored `a365-verification-results` bundle containing:

- the marker and exact UTC correlation window;
- sanitized interaction status and timing, without prompt or response text;
- Entra and Purview portal filters; and
- a time-bounded Defender Advanced Hunting query.

This is an explicitly approved nonproduction policy-classification test, so
the running API must report `A365_RECORD_CONTENT=true`. The command stops
before sign-in if content recording is disabled. Restore
`A365_RECORD_CONTENT=false` and restart the API immediately afterward.
Expected signals in the JSON report are hypotheses for correlation, not proof
that a rule matched or an alert was created. See the
[Agent 365 verification process](../../../A365/verification_process.md) for
the cross-product assertions and ingestion delays.

---

## Docker

### Build & Run

```bash
# Build image
_build.bat

# Start full stack (API + PostgreSQL + Adminer)
_up.bat

# View logs
_logs.bat

# Stop
_down.bat
```

Services started by `_up.bat`:

| Service | Port | Description |
|---------|------|-------------|
| `ai-agent-starter-api` | 8989 | Trading Platform API |
| `ai-agent-starter-portfolio-manager-postgres` | 5000→5432 | PostgreSQL 17 |
| `ai-agent-starter-portfolio-manager-adminer` | 8888 | Adminer DB UI |

### Push to Registry

```bash
_push.bat
# Pushes image to DOCKER_REPO_NAME defined in .env
```

---

## Helper Scripts

| Script | Action |
|--------|--------|
| `_env_create.bat` | `python -m venv .venv` |
| `_env_activate.bat` | activate `.venv` |
| `_env_deactivate.bat` | deactivate `.venv` |
| `_install.bat` | `pip install -r requirements.txt` |
| `_build.bat` | `docker build` |
| `_up.bat` | `docker compose up -d` |
| `_down.bat` | `docker compose down` |
| `_logs.bat` | `docker compose logs -f` |
| `_push.bat` | `docker push` to registry |

---

## Testing

### MCP End-to-End Test

Tests all 8 core MCP tools against the live APIM endpoint:

```bash
python test_mcp.py
```

**Expected output:**
```
============================================================
  Trading Platform MCP Server Test
  URL: https://ai-learning-apim.azure-api.net/trading-platform-mcp-server/mcp
============================================================
  Connected — MCP session initialized

MCP tools advertised (11): health, agentStatus, chat, ...

[health]           ✅  healthy
[agentStatus]      ✅  7 tools
[portfolioSummary] ✅  1 ticker(s)
[latestPrice]      ✅  MSFT @ 416.10
[tradeHistory]     ✅  67 trades
[accountEvents]    ✅  100 events
[tickerEvents]     ✅  100 events
[chat]             ✅  Agent replied (212 chars)
------------------------------------------------------------
  8/8 passed
```

Requires `APIM_MCP_SERVER_URL` in `.env`.

### REST API (manual)

```bash
# Health
curl https://ai-learning-aca.ashycliff-5cba4403.eastus.azurecontainerapps.io/health

# Portfolio summary
curl https://ai-learning-aca.ashycliff-5cba4403.eastus.azurecontainerapps.io/portfolio/A100

# Latest price
curl https://ai-learning-aca.ashycliff-5cba4403.eastus.azurecontainerapps.io/ticker/MSFT/price

# NL chat
curl -X POST https://ai-learning-aca.ashycliff-5cba4403.eastus.azurecontainerapps.io/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test", "message": "Summarize portfolio A100"}'
```

---

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

"""
Trading Platform FastAPI
REST API that wraps the TradingPlatformAgent for portfolio event ledger operations.

Endpoints:
    GET  /health                                        - Service health + DB connectivity
    GET  /                                              - API info and endpoint map
    POST /chat                                          - Natural-language chat with the agent
    POST /clear_session                                 - Clear conversation history for a session
    POST /calendar/briefing/decision                     - Confirm/cancel a meeting briefing update
    POST /calendar/meeting/decision                      - Confirm/cancel a new invitation
    GET  /accounts                                      - List all distinct account IDs
    GET  /portfolio/summary/all                         - Net positions for ALL accounts (one query)
    GET  /portfolio/{account_id}                        - Portfolio summary for one account
    GET  /portfolio/{account_id}/trades                 - Trade history (BUY/SELL) for an account
    GET  /portfolio/{account_id}/events                 - All events for an account
    GET  /portfolio/{account_id}/{ticker_symbol}/events - Events for a specific account+ticker
    GET  /ticker/{ticker_symbol}/price                  - Latest observed price for a ticker
    GET  /ticker/{ticker_symbol}/events                 - All events for a ticker
    POST /events                                        - Insert a new portfolio event
    POST /query                                         - Execute a read-only SQL SELECT
    GET  /agent/status                                  - Agent tools and capabilities
"""

import os
import asyncio
from datetime import datetime, timezone
from uuid import UUID
from typing import Dict, Literal, Optional, Any
from dotenv import load_dotenv

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from agent_framework import AgentThread

from agents.trading_platform_agent import create_trading_platform_agent
from agents.model_endpoint_config import load_model_endpoint_config
from api.model_errors import model_error_to_http_exception
from api.user_identity import (
    EntraUserTokenValidator, UserTokenValidationError, ValidatedUserIdentity,
)
from operations.graph_operations import (
    ACCESS_SCOPE, CalendarBriefingProposal, CalendarMeetingProposal, GraphCalendarError,
    GraphCalendarSettings, GraphOperations, SCHEDULING_ZONE,
)
from tools.graph_tool import PortfolioReviewCalendar
from observability.a365 import (
    a365_invoke_scope,
    flush_a365_telemetry,
    get_a365_status,
    prepare_a365_telemetry,
    record_a365_response,
    start_a365_token_refresh,
    stop_a365_token_refresh,
)
from operations.trading_platform_operations import TradingPlatformOperations

load_dotenv()

# ── Service metadata ───────────────────────────────────────────────────────────
SERVICE_NAME    = os.getenv("SERVICE_NAME",    "trading-platform-api")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
# Set SERVER_URL in env to the public base URL (no trailing slash) so Swagger
# UI sends requests to the right host instead of localhost.
# e.g. SERVER_URL=https://ai-learning-aca.ashycliff-5cba4403.eastus.azurecontainerapps.io
SERVER_URL      = os.getenv("SERVER_URL", "")

# Build servers list for Swagger UI
_servers = []
if SERVER_URL:
    _servers.append({"url": SERVER_URL, "description": "Production"})
_servers.append({"url": "/", "description": "Current host"})

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Trading Platform API",
    description=(
        "AI-powered portfolio event ledger API. "
        "Chat naturally with the Trading Platform Agent or call structured endpoints directly."
    ),
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    servers=_servers,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global singletons ──────────────────────────────────────────────────────────
agent       = None                          # TradingPlatformAgent (ChatAgent)
client_supplied_auth = False
user_token_validator: EntraUserTokenValidator | None = None
model_endpoint_mode: str | None = None
graph_calendar_settings: GraphCalendarSettings | None = None
graph_user_token_validator: EntraUserTokenValidator | None = None
db_ops      = TradingPlatformOperations()   # Direct DB access for structured endpoints
sessions: Dict[str | tuple[str, str, str], AgentThread] = {}
pending_calendar_briefings: dict[
    str | tuple[str, str, str], CalendarBriefingProposal | CalendarMeetingProposal
] = {}
calendar_creation_locks: dict[tuple[str, str], asyncio.Lock] = {}


# ── Request / response models ──────────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str  = Field(..., description="Unique session identifier")
    message:    str  = Field(..., description="Natural-language message for the agent")
    # tag:A365 verification - Accept a typed correlation marker, never an asserted caller identity.
    verification_id: UUID | None = Field(
        default=None, description="Optional test correlation ID; not caller identity."
    )


class ChatResponse(BaseModel):
    session_id: str
    response:   str
    agent:      str = "TradingPlatformAgent"
    calendar_update: dict[str, Any] | None = None


class CalendarBriefingDecision(BaseModel):
    session_id: str
    proposal_id: UUID
    decision: Literal["confirm", "cancel"]


class ClearSessionRequest(BaseModel):
    session_id: str = Field(..., description="Session to clear")


class InsertEventRequest(BaseModel):
    account_id:      str   = Field(..., description="Account ID (e.g. A100)")
    ticker_symbol:   str   = Field(..., description="Ticker symbol (e.g. MSFT)")
    event_ts:        str   = Field(..., description="ISO 8601 UTC timestamp")
    event_type:      str   = Field(..., description="BUY, SELL, or PRICE")
    shares:          float = Field(..., description="Number of shares (0 for PRICE events)")
    price_per_share: float = Field(..., description="Trade or market price")
    currency:        str   = Field("USD", description="ISO currency code")
    source:          str   = Field("api",  description="Origin of the event")


class QueryRequest(BaseModel):
    sql: str = Field(
        ...,
        description="A read-only PostgreSQL SELECT statement against portfolio_event_ledger",
        example="SELECT account_id, COUNT(*) AS trades FROM portfolio_event_ledger WHERE event_type IN ('BUY','SELL') GROUP BY account_id ORDER BY trades DESC",
    )


# ── Lifecycle ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global agent, client_supplied_auth, user_token_validator, model_endpoint_mode
    global graph_calendar_settings, graph_user_token_validator
    # tag:A365 identity - Gate Graph access and validate incoming tokens against the blueprint API scope.
    graph_calendar_settings = GraphCalendarSettings.from_environment()
    graph_user_token_validator = None
    if graph_calendar_settings is not None:
        graph_user_token_validator = EntraUserTokenValidator(
            graph_calendar_settings.tenant_id,
            f"api://{graph_calendar_settings.blueprint_client_id}/.default",
            required_scope=ACCESS_SCOPE,
        )
    model_config = load_model_endpoint_config()
    model_endpoint_mode = model_config.mode
    client_supplied_auth = (
        os.getenv("AZURE_AUTH_MODE", "default").strip().lower() == "device-code"
    )

    print(f"[{SERVICE_NAME}] Initializing TradingPlatformAgent ...")
    if not client_supplied_auth:
        agent = await create_trading_platform_agent()
    # tag:A365 identity - Validate device-code callers before using their identity for telemetry or Graph.
    elif graph_calendar_settings is not None or os.getenv("ENABLE_A365_OBSERVABILITY", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        try:
            user_token_validator = EntraUserTokenValidator(
                os.getenv("A365_TENANT_ID", ""),
                model_config.token_scope,
            )
        except UserTokenValidationError as error:
            raise RuntimeError(
                "Device-code user attribution configuration is invalid."
            ) from error

    print(f"[{SERVICE_NAME}] Connecting to database ...")
    await db_ops.initialize()

    # tag:A365 telemetry - Start background exporter-token refresh independently of model authentication.
    await start_a365_token_refresh()

    print(f"[{SERVICE_NAME}] Ready — docs at http://localhost:8989/docs")


@app.on_event("shutdown")
async def shutdown():
    # tag:A365 telemetry - Stop token refresh and flush queued spans before releasing service resources.
    await stop_a365_token_refresh()
    flush_a365_telemetry()
    await db_ops.close()
    print(f"[{SERVICE_NAME}] Shutdown complete.")


# ── Helpers ────────────────────────────────────────────────────────────────────
def _get_thread(session_id: str | tuple[str, str, str]) -> AgentThread:
    """Return the existing AgentThread for a session, or create a new one."""
    if session_id not in sessions:
        sessions[session_id] = AgentThread()
    return sessions[session_id]


def _require_agent():
    if agent is None and not client_supplied_auth:
        raise HTTPException(status_code=503, detail="Agent not initialized yet.")


def _require_db():
    if db_ops.pool is None:
        raise HTTPException(status_code=503, detail="Database not connected yet.")


# tag:A365 identity - Validate the separate user assertion and create request-local Graph operations.
async def _calendar_caller(
    agent_authorization: str | None,
) -> tuple[ValidatedUserIdentity | None, GraphOperations | None]:
    if graph_calendar_settings is None:
        return None, None
    if graph_user_token_validator is None:
        raise HTTPException(status_code=503, detail="Calendar authentication is not initialized.")
    scheme, _, token = (
        agent_authorization if isinstance(agent_authorization, str) else ""
    ).partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="X-Agent-Authorization must contain a blueprint-audience bearer token.",
        )
    try:
        caller = await asyncio.to_thread(graph_user_token_validator.validate, token)
    except UserTokenValidationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return caller, GraphOperations(graph_calendar_settings, token)


# tag:A365 identity - Isolate Graph-enabled conversations and pending approvals by tenant and user.
def _session_key(
    session_id: str, caller: ValidatedUserIdentity | None
) -> str | tuple[str, str, str]:
    if graph_calendar_settings is not None:
        if caller is None:
            raise HTTPException(status_code=401, detail="A calendar caller is required.")
        return caller.tenant_id, caller.object_id, session_id
    return session_id


# ── Root & health ──────────────────────────────────────────────────────────────
# Purpose: Provide service metadata and an endpoint map for API discovery.
@app.get("/")
async def root():
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "docs":    "/docs",
        "endpoints": {
            "health":               "GET  /health",
            "chat":                 "POST /chat",
            "clear_session":        "POST /clear_session",
            "calendar_briefing":     "POST /calendar/briefing/decision",
            "calendar_meeting":      "POST /calendar/meeting/decision",
            "accounts":             "GET  /accounts",
            "all_summaries":        "GET  /portfolio/summary/all",
            "portfolio":            "GET  /portfolio/{account_id}",
            "trades":               "GET  /portfolio/{account_id}/trades",
            "events_account":       "GET  /portfolio/{account_id}/events",
            "events_account_ticker":"GET  /portfolio/{account_id}/{ticker_symbol}/events",
            "latest_price":         "GET  /ticker/{ticker_symbol}/price",
            "events_ticker":        "GET  /ticker/{ticker_symbol}/events",
            "insert_event":         "POST /events",
            "query":                "POST /query",
            "agent_status":         "GET  /agent/status",
        },
    }


# Purpose: Report service readiness, database connectivity and enabled integrations.
@app.get("/health")
async def health():
    """Service health including database connectivity."""
    db_healthy = await db_ops.health_check() if db_ops.pool else False
    return {
        "status":    "healthy" if (agent or client_supplied_auth) and db_healthy else "degraded",
        "service":   SERVICE_NAME,
        "version":   SERVICE_VERSION,
        "agent":     "ready" if agent or client_supplied_auth else "initializing",
        "database":  "connected" if db_healthy else "disconnected",
        "framework": "Microsoft Agent Framework",
        "model_endpoint_mode": model_endpoint_mode,
        "verification_correlation": "model_header_uuid_v1",
        # tag:A365 telemetry - Let health checks distinguish disabled, ready and degraded observability.
        "a365_observability": get_a365_status(),
        "graph_calendar": {
            "enabled": graph_calendar_settings is not None,
            "authentication": "agent_identity_user_delegated_obo",
            "briefing_write_enabled": (
                graph_calendar_settings is not None and graph_calendar_settings.write_enabled
            ),
            "meeting_creation_enabled": (
                graph_calendar_settings is not None and graph_calendar_settings.write_enabled
            ),
            "scheduling_time_zone": SCHEDULING_ZONE.key,
            "scheduling_working_hours": "Weekdays 09:00-17:00",
        },
    }


# ── Chat ───────────────────────────────────────────────────────────────────────
# Purpose: Run conversational agent tools with session context; calendar writes remain proposals.
@app.post("/chat", response_model=ChatResponse, response_model_exclude_none=True)
async def chat(
    request: ChatRequest,
    authorization: Optional[str] = Header(default=None),
    agent_authorization: Optional[str] = Header(default=None, alias="X-Agent-Authorization"),
):
    """
    Natural-language chat with the Trading Platform Agent.
    Maintains conversational context per session_id.

    Example:
        { "session_id": "user-1", "message": "Show me the portfolio for account A100" }
    """
    _require_agent()
    token = ""
    caller = None
    if client_supplied_auth:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=401,
                detail="A bearer token from chat.py is required.",
            )
        if user_token_validator is not None:
            try:
                caller = await asyncio.to_thread(
                    user_token_validator.validate, token
                )
            except UserTokenValidationError as error:
                raise HTTPException(
                    status_code=401,
                    detail=str(error),
                ) from error
    # tag:A365 identity - Require model and Graph caller tokens to identify the same tenant and user.
    calendar_caller, calendar_ops = await _calendar_caller(agent_authorization)
    if calendar_caller is not None:
        if caller is not None and (
            caller.tenant_id, caller.object_id
        ) != (calendar_caller.tenant_id, calendar_caller.object_id):
            raise HTTPException(
                status_code=403,
                detail="Model and calendar tokens must identify the same user.",
            )
        caller = calendar_caller
    session_key = _session_key(request.session_id, caller)
    calendar = PortfolioReviewCalendar(calendar_ops) if calendar_ops is not None else None
    # tag:A365 approval - A new chat turn invalidates the previous pending calendar approval.
    pending_calendar_briefings.pop(session_key, None)
    # tag:A365 telemetry - Wrap the agent run with authenticated caller attribution and error recording.
    await prepare_a365_telemetry()
    try:
        with a365_invoke_scope(
            request.session_id,
            caller.object_id if caller else None,
            request.message,
            user_email=caller.upn if caller else None,
            user_name=caller.name if caller else None,
        ) as telemetry_scope:
            try:
                request_agent = agent
                if client_supplied_auth:
                    request_agent = await create_trading_platform_agent(
                        ad_token_provider=lambda: token,
                        verification_id=request.verification_id,
                        calendar=calendar,
                    )
                elif request.verification_id is not None or calendar is not None:
                    request_agent = await create_trading_platform_agent(
                        verification_id=request.verification_id,
                        calendar=calendar,
                    )

                thread = _get_thread(session_key)
                response = await request_agent.run(request.message, thread=thread)
                response_text = response.text or ""
                record_a365_response(telemetry_scope, response_text)
                # tag:A365 approval - Return a staged preview; only separate decision routes may execute it.
                proposal = (
                    calendar_ops.pending_meeting or calendar_ops.pending_briefing
                ) if calendar_ops is not None else None
                if proposal is not None:
                    pending_calendar_briefings[session_key] = proposal
                return ChatResponse(
                    session_id=request.session_id,
                    response=response_text,
                    calendar_update=proposal.preview() if proposal is not None else None,
                )
            except Exception as error:
                if telemetry_scope is not None:
                    telemetry_scope.record_error(error)
                raise
    except HTTPException:
        raise
    except Exception as error:
        http_error = model_error_to_http_exception(error)
        if http_error.status_code == 429:
            sessions.pop(session_key, None)
        raise http_error from error


# tag:A365 approval - Clearing a caller's session also discards its pending calendar proposal.
# Purpose: Clear conversation history and invalidate any pending calendar approval for the session.
@app.post("/clear_session")
async def clear_session(
    request: ClearSessionRequest,
    agent_authorization: Optional[str] = Header(default=None, alias="X-Agent-Authorization"),
):
    """Clear the conversation history for a session."""
    caller, _ = await _calendar_caller(agent_authorization)
    session_key = _session_key(request.session_id, caller)
    sessions.pop(session_key, None)
    pending_calendar_briefings.pop(session_key, None)
    return {"status": "cleared", "session_id": request.session_id}


# tag:A365 approval - API-only decision boundary for an existing meeting's briefing update.
# Purpose: Confirm or cancel a staged meeting-body update outside the model's control.
@app.post("/calendar/briefing/decision")
async def calendar_briefing_decision(
    request: CalendarBriefingDecision,
    agent_authorization: Optional[str] = Header(default=None, alias="X-Agent-Authorization"),
):
    """Confirm or cancel the exact preview; never invokes the model."""
    return await _calendar_decision(request, agent_authorization, creating=False)


# tag:A365 approval - API-only decision boundary for creating and sending a new invitation.
# Purpose: Confirm or cancel a staged invitation; authenticated approval, not the model, authorizes creation.
@app.post("/calendar/meeting/decision")
async def calendar_meeting_decision(
    request: CalendarBriefingDecision,
    agent_authorization: Optional[str] = Header(default=None, alias="X-Agent-Authorization"),
):
    """Create the exact proposed invitation only after explicit caller approval."""
    return await _calendar_decision(request, agent_authorization, creating=True)


# tag:A365 approval - Enforce caller/session binding, single-use expiry and serialized invitation creation.
async def _calendar_decision(
    request: CalendarBriefingDecision, agent_authorization: str | None, *, creating: bool,
):
    caller, operations = await _calendar_caller(agent_authorization)
    if caller is None or operations is None or not operations.settings.write_enabled:
        raise HTTPException(status_code=403, detail="Calendar writes are disabled.")
    session_key = _session_key(request.session_id, caller)
    proposal = pending_calendar_briefings.get(session_key)
    if (
        proposal is None or proposal.proposal_id != str(request.proposal_id)
        or isinstance(proposal, CalendarMeetingProposal) != creating
    ):
        raise HTTPException(status_code=409, detail="No matching pending briefing for this caller and session.")
    pending_calendar_briefings.pop(session_key)
    if request.decision == "cancel":
        return {"status": "cancelled", "message": "Meeting unchanged."}
    if proposal.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="The briefing approval expired; prepare it again.")
    try:
        if isinstance(proposal, CalendarMeetingProposal):
            lock = calendar_creation_locks.setdefault(
                (caller.tenant_id, caller.object_id), asyncio.Lock(),
            )
            async with lock:
                return await operations.confirm_meeting(proposal)
        return await operations.confirm_briefing(proposal)
    except GraphCalendarError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


# ── Accounts endpoint ─────────────────────────────────────────────────────────
# Purpose: Discover the account IDs available in the portfolio ledger.
@app.get("/accounts")
async def list_accounts():
    """Return a sorted list of all distinct account IDs in the ledger."""
    _require_db()
    try:
        accounts = await db_ops.get_all_accounts()
        return {"count": len(accounts), "accounts": accounts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Structured portfolio endpoints ─────────────────────────────────────────────
# Purpose: Retrieve all account positions in one call for cross-account comparisons and risk scans.
@app.get("/portfolio/summary/all", operation_id="getAllPortfolioSummaries")
async def all_portfolio_summaries():
    """
    Net positions for ALL accounts in a single query.
    Each row includes: account_id, ticker_symbol, net_shares, net_cost,
    last_price (chronologically latest, not max), last_price_ts, last_event_ts.
    Ideal for cross-account risk scanning — a single call replaces 25 individual
    portfolioSummary calls.
    """
    _require_db()
    try:
        rows = await db_ops.get_all_portfolio_summaries()
        return {"count": len(rows), "positions": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Purpose: Summarize one account's holdings, cost basis and latest observed prices.
@app.get("/portfolio/{account_id}")
async def portfolio_summary(account_id: str):
    """
    Net share position, net cost basis, and last observed price per ticker
    for the given account.
    """
    _require_db()
    try:
        rows = await db_ops.get_portfolio_summary(account_id)
        if not rows:
            raise HTTPException(status_code=404, detail=f"No data for account '{account_id}'.")
        return {"account_id": account_id, "positions": rows}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Purpose: Retrieve an account's BUY/SELL history with optional type and date filters.
@app.get("/portfolio/{account_id}/trades")
async def trade_history(
    account_id: str,
    event_type: Optional[str] = Query(None, description="Filter: BUY or SELL"),
    start:      Optional[str] = Query(None, description="Start timestamp filter (ISO 8601)"),
    end:        Optional[str] = Query(None, description="End timestamp filter (ISO 8601)"),
):
    """BUY / SELL trade history for an account, optionally filtered by type and/or date range."""
    _require_db()
    try:
        rows = await db_ops.get_trade_history(
            account_id,
            event_type.upper() if event_type else None,
            start or None,
            end   or None,
        )
        return {"account_id": account_id, "event_type": event_type, "trades": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Purpose: Retrieve an account's ledger events, including price observations, for a chosen period.
@app.get("/portfolio/{account_id}/events")
async def account_events(
    account_id: str,
    start: Optional[str] = Query(None, description="Start timestamp filter (ISO 8601)"),
    end:   Optional[str] = Query(None, description="End timestamp filter (ISO 8601)"),
):
    """All ledger events (BUY, SELL, PRICE) for an account, newest first.
    Optionally filter by date range."""
    _require_db()
    try:
        rows = await db_ops.get_events_by_account(account_id, start or None, end or None)
        return {"account_id": account_id, "count": len(rows), "events": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Purpose: Drill into the ledger history of one ticker within one account.
@app.get("/portfolio/{account_id}/{ticker_symbol}/events", operation_id="getAccountTickerEvents")
async def account_ticker_events(
    account_id:    str,
    ticker_symbol: str,
    start: Optional[str] = Query(None, description="Start timestamp filter (ISO 8601)"),
    end:   Optional[str] = Query(None, description="End timestamp filter (ISO 8601)"),
):
    """All ledger events for a specific account + ticker combination, newest first.
    More targeted than /portfolio/{account_id}/events when drilling into one position."""
    _require_db()
    try:
        rows = await db_ops.get_events_by_account_and_ticker(
            account_id, ticker_symbol.upper(), start or None, end or None
        )
        return {
            "account_id":    account_id,
            "ticker_symbol": ticker_symbol.upper(),
            "count":         len(rows),
            "events":        rows,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Ticker endpoints ───────────────────────────────────────────────────────────
# Purpose: Return a ticker's latest recorded price, not a live market quote.
@app.get("/ticker/{ticker_symbol}/price")
async def latest_price(ticker_symbol: str):
    """Most recently observed market price for a ticker."""
    _require_db()
    try:
        row = await db_ops.get_latest_price(ticker_symbol.upper())
        if not row:
            raise HTTPException(status_code=404, detail=f"No price data for '{ticker_symbol}'.")
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Purpose: Retrieve a ticker's ledger events across accounts for historical analysis.
@app.get("/ticker/{ticker_symbol}/events")
async def ticker_events(
    ticker_symbol: str,
    start: Optional[str] = Query(None, description="Start timestamp filter (ISO 8601)"),
    end:   Optional[str] = Query(None, description="End timestamp filter (ISO 8601)"),
):
    """All ledger events for a ticker across all accounts, newest first.
    Optionally filter by date range."""
    _require_db()
    try:
        rows = await db_ops.get_events_by_ticker(ticker_symbol.upper(), start or None, end or None)
        return {"ticker_symbol": ticker_symbol.upper(), "count": len(rows), "events": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Analysis context (pre-computed for o1 analyst agent) ─────────────────────
# Purpose: Supply computed holdings metrics and anomaly flags for downstream portfolio analysis.
@app.get("/portfolio/{account_id}/analysis-context", operation_id="getAccountAnalysisContext")
async def account_analysis_context(account_id: str):
    """
    Return a fully pre-computed analysis context for one account including
    avg_cost_per_share, unrealized_pnl, portfolio_weight per position, and
    a pre-flagged anomalies list (OVERSELL, MISSING_PRICE, STALE_PRICE).
    Designed as the input payload for the InvestmentPortfolioAnalysisAgent.
    """
    from datetime import datetime, timezone
    _require_db()
    try:
        result = await db_ops.get_account_analysis_context(account_id)
        if not result.get("holdings"):
            raise HTTPException(status_code=404, detail=f"No holdings found for account '{account_id}'.")
        # Compute anomalies (same logic as the tool wrapper)
        STALE_DAYS = 30
        now = datetime.now(timezone.utc)
        anomalies = []
        for h in result["holdings"]:
            ticker = h["ticker_symbol"]
            if (h["net_shares"] or 0) < 0:
                anomalies.append({"flag": "OVERSELL", "ticker": ticker,
                                   "details": f"net_shares={h['net_shares']} — short or data error"})
            if h["last_price"] is None:
                anomalies.append({"flag": "MISSING_PRICE", "ticker": ticker,
                                   "details": "No PRICE events found for this ticker"})
            elif h.get("last_price_ts"):
                try:
                    ts_str = str(h["last_price_ts"]).replace("Z", "+00:00")
                    ts = datetime.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age = (now - ts).days
                    if age >= STALE_DAYS:
                        anomalies.append({"flag": "STALE_PRICE", "ticker": ticker,
                                           "details": f"Last price is {age} days old (>{STALE_DAYS}d threshold)"})
                except ValueError:
                    pass
        result["anomalies"] = anomalies
        result["as_of_date"] = now.isoformat()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Event insertion ────────────────────────────────────────────────────────────
# Purpose: Write a BUY, SELL or PRICE record to the ledger, not execute a brokerage trade.
@app.post("/events", status_code=201)
async def insert_event(event: InsertEventRequest):
    """
    Insert a new portfolio event (BUY, SELL, or PRICE observation) into the ledger.
    Returns the auto-generated event id.
    """
    _require_db()
    try:
        new_id = await db_ops.insert_event(
            account_id=event.account_id,
            ticker_symbol=event.ticker_symbol,
            event_ts=event.event_ts,
            event_type=event.event_type.upper(),
            shares=event.shares,
            price_per_share=event.price_per_share,
            currency=event.currency,
            source=event.source,
        )
        return {"status": "created", "id": new_id, **event.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Dynamic read-only SQL query ─────────────────────────────────────────────────
# Purpose: Run custom read-only ledger reports not covered by the structured endpoints.
@app.post("/query", operation_id="runQuery")
async def dynamic_query(request: QueryRequest):
    """
    Execute a read-only SELECT statement against the portfolio_event_ledger table.
    Only SELECT statements are accepted. DDL, DML, and system-table access are blocked.

    Example body:
        { "sql": "SELECT account_id, COUNT(*) AS trades FROM portfolio_event_ledger WHERE event_type IN ('BUY','SELL') GROUP BY account_id ORDER BY trades DESC" }
    """
    _require_db()
    try:
        rows = await db_ops.execute_read_query(request.sql)
        return {"row_count": len(rows), "columns": list(rows[0].keys()) if rows else [], "rows": rows}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Agent status ───────────────────────────────────────────────────────────────
# Purpose: Describe configured agent tools and API capabilities without invoking the model.
@app.get("/agent/status")
async def agent_status():
    """Trading Platform Agent capabilities and registered tools."""
    result: dict[str, Any] = {
        "agent":       "TradingPlatformAgent",
        "status":      "ready" if agent or client_supplied_auth else "initializing",
        "description": (
            "AI agent for portfolio event ledger queries and trade operations."
        ),
        "tools": [
            {"name": "list_all_accounts",           "description": "List all distinct account IDs"},
            {"name": "get_all_portfolio_summaries",  "description": "Net positions for ALL accounts (one query, use for risk scans)"},
            {"name": "get_portfolio_summary",         "description": "Net position + cost basis per ticker for one account"},
            {"name": "get_events_by_account",        "description": "All events for an account, with optional date range"},
            {"name": "get_events_by_account_ticker", "description": "All events for a specific account + ticker"},
            {"name": "get_events_by_ticker",         "description": "All events for a ticker across all accounts"},
            {"name": "get_latest_price",             "description": "Most recent PRICE observation for a ticker"},
            {"name": "get_trade_history",            "description": "BUY/SELL history, filterable by type and date range"},
            {"name": "get_account_analysis_context", "description": "Pre-computed analysis context bundle for the o1 analyst agent"},
            {"name": "run_query",                    "description": "Execute a custom read-only SELECT against the ledger"},
            {"name": "insert_trade_event",           "description": "Insert a new ledger event"},
            {"name": "check_database_health",        "description": "DB connectivity probe"},
        ],
        "structured_endpoints": {
            "accounts":             "GET  /accounts",
            "all_summaries":        "GET  /portfolio/summary/all",
            "portfolio_summary":    "GET  /portfolio/{account_id}",
            "trade_history":        "GET  /portfolio/{account_id}/trades",
            "account_events":       "GET  /portfolio/{account_id}/events",
            "account_ticker_events":  "GET  /portfolio/{account_id}/{ticker_symbol}/events",
            "analysis_context":        "GET  /portfolio/{account_id}/analysis-context",
            "latest_price":            "GET  /ticker/{ticker_symbol}/price",
            "ticker_events":        "GET  /ticker/{ticker_symbol}/events",
            "insert_event":         "POST /events",
            "query":                "POST /query",
            "calendar_briefing":    "POST /calendar/briefing/decision",
            "calendar_meeting":     "POST /calendar/meeting/decision",
        },
    }
    if graph_calendar_settings is not None:
        result["tools"] = [
            tool for tool in result["tools"] if tool["name"] != "insert_trade_event"
        ]
        result["tools"].append({
            "name": "get_portfolio_review_meetings",
            "description": "Read the signed-in user's marked calendar meetings (one day)",
        })
        result["tools"].extend([
            {"name": "get_calendar_schedule", "description": "Read all primary-calendar events for up to 31 days"},
            {"name": "find_available_slots", "description": "Find weekday 09:00-17:00 Eastern openings; all events block"},
        ])
        if graph_calendar_settings.write_enabled:
            result["tools"].append({
                "name": "prepare_portfolio_review_briefing",
                "description": "Propose a meeting-body update; separate explicit approval required",
            })
            result["tools"].append({
                "name": "prepare_customer_meeting",
                "description": "Propose a new customer invitation; separate explicit approval required",
            })
    result["graph_calendar"] = {
        "enabled": graph_calendar_settings is not None,
        "read_only_agent": (
            graph_calendar_settings is not None and not graph_calendar_settings.write_enabled
        ),
        "briefing_write_enabled": (
            graph_calendar_settings is not None and graph_calendar_settings.write_enabled
        ),
        "meeting_creation_enabled": (
            graph_calendar_settings is not None and graph_calendar_settings.write_enabled
        ),
    }
    return result

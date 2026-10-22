import asyncio
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

import operations.graph_operations as graph
from tools.graph_tool import PortfolioReviewCalendar
from test_graph_calendar import (
    OTHER_USER, TENANT, USER, calendar_api, event, fake_http, responses, settings,
)


@pytest.fixture(autouse=True)
def disable_write_by_default(monkeypatch):
    monkeypatch.setenv("ENABLE_GRAPH_CALENDAR_WRITE", "false")


def review_event(**changes):
    return event(**{
        "@odata.etag": 'W/"version-one"',
        "body": {"contentType": "text", "content": "Original synthetic agenda."},
        "isOrganizer": True,
        "type": "singleInstance",
        "organizer": {"emailAddress": {"address": "organizer@example.test"}},
        "attendees": [{"emailAddress": {"address": "recipient@example.test"}, "type": "required"}],
        **changes,
    })


async def prepare(
    monkeypatch, settings,
    briefing="Holdings: AAPL. Historical observations, not live quotes.", **changes,
):
    target = review_event(**changes)
    session = fake_http(
        monkeypatch, responses({"value": [event()]}) + responses(target),
    )
    calendar = graph.GraphOperations(replace(settings, write_enabled=True), "user-token")
    result = await calendar.prepare_portfolio_review_briefing(
        "2026-10-22", "A100", briefing,
    )
    assert calendar.pending_briefing is not None
    return calendar, calendar.pending_briefing, result, session


@pytest.mark.asyncio
async def test_proposal_never_writes_and_preserves_original_body(monkeypatch, settings):
    calendar, proposal, preview, session = await prepare(monkeypatch, settings)
    assert proposal is not None
    assert preview["status"] == "confirmation_required"
    assert preview["proposal_id"] == proposal.proposal_id
    assert preview["attendees"] == ["recipient@example.test"]
    assert preview["briefing"] in proposal.updated_body["content"]
    assert proposal.updated_body["content"].startswith("Original synthetic agenda.")
    assert proposal.event["body"]["content"] == "Original synthetic agenda."
    assert not any(call.args[0] == "PATCH" for call in session.request.call_args_list)
    assert not hasattr(calendar, "insert_trade_event")


@pytest.mark.asyncio
async def test_html_preservation_and_escaping(monkeypatch, settings):
    original = '<html><body><a href="https://teams.example.test">Join meeting</a></body></html>'
    _, proposal, _, _ = await prepare(
        monkeypatch, settings, briefing="<AAPL & MSFT>",
        body={"contentType": "html", "content": original},
    )
    assert proposal.updated_body["content"].startswith(original.split("</body>")[0])
    assert proposal.updated_body["content"].endswith("</body></html>")
    assert "&lt;AAPL &amp; MSFT&gt;" in proposal.updated_body["content"]


def test_html_text_excludes_hidden_styles_and_preserves_inline_words():
    body = {
        "contentType": "html",
        "content": (
            "<html><head><style><!-- .EmailQuote {color:red} --></style></head>"
            "<body><div>Origi<span>nal</span> agenda.</div>"
            "<script>not visible</script><p>Next line.</p></body></html>"
        ),
    }
    assert graph._body_text(body) == "Original agenda. Next line."


@pytest.mark.asyncio
async def test_graph_style_rewriting_does_not_falsely_report_lost_body(monkeypatch, settings):
    original = (
        "<html><head><style>.old-style {margin:0}</style></head>"
        "<body><div>Original synthetic agenda.</div></body></html>"
    )
    calendar, proposal, _, _ = await prepare(
        monkeypatch, settings, body={"contentType": "html", "content": original},
    )
    normalized_html = proposal.updated_body["content"].replace(
        ".old-style {margin:0}", "<!-- .EmailQuote {border-left:2px solid} -->",
    )
    saved = {
        **proposal.event, "@odata.etag": 'W/"new-version"',
        "body": {"contentType": "html", "content": normalized_html},
    }
    fake_http(monkeypatch, responses(proposal.event, saved, saved))
    assert (await calendar.confirm_briefing(proposal))["status"] == "saved"


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [
    {"isOrganizer": False}, {"isCancelled": True},
    {"type": "occurrence"}, {"type": "seriesMaster"},
    {"subject": "Unmarked meeting"}, {"subject": "Portfolio Review - DEMO-A200"},
    {"@odata.etag": None}, {"body": {"contentType": "invalid", "content": ""}},
])
async def test_unsafe_targets_fail_before_proposal(monkeypatch, settings, changes):
    with pytest.raises(graph.GraphCalendarError):
        await prepare(monkeypatch, settings, **changes)


@pytest.mark.asyncio
async def test_disabled_write_fails_without_graph(monkeypatch, settings):
    session = fake_http(monkeypatch, [])
    with pytest.raises(graph.GraphCalendarError, match="disabled"):
        await graph.GraphOperations(settings, "token").prepare_portfolio_review_briefing(
            "2026-10-22", "A100", "Briefing",
        )
    session.request.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("briefing", ["", " ", "x" * 20001])
async def test_invalid_briefing_never_reads_or_writes(monkeypatch, settings, briefing):
    session = fake_http(monkeypatch, [])
    calendar = graph.GraphOperations(replace(settings, write_enabled=True), "token")
    with pytest.raises(ValueError, match="20000"):
        await calendar.prepare_portfolio_review_briefing("2026-10-22", "A100", briefing)
    session.request.assert_not_called()


@pytest.mark.asyncio
async def test_maximum_briefing_size_is_accepted(monkeypatch, settings):
    _, proposal, _, _ = await prepare(monkeypatch, settings, briefing="x" * 20000)
    assert len(proposal.briefing) == 20000


def test_write_requires_read_feature(monkeypatch):
    monkeypatch.setenv("ENABLE_GRAPH_CALENDAR", "false")
    monkeypatch.setenv("ENABLE_GRAPH_CALENDAR_WRITE", "true")
    with pytest.raises(ValueError, match="ENABLE_GRAPH_CALENDAR"):
        graph.GraphCalendarSettings.from_environment()


@pytest.mark.asyncio
async def test_confirm_patches_body_only_with_version_and_readback(monkeypatch, settings):
    calendar, proposal, _, _ = await prepare(monkeypatch, settings)
    updated = review_event(body=proposal.updated_body, **{"@odata.etag": 'W/"version-two"'})
    session = fake_http(monkeypatch, responses(review_event(), updated, updated))
    result = await calendar.confirm_briefing(proposal)
    assert result["status"] == "saved"
    patch_calls = [call for call in session.request.call_args_list if call.args[0] == "PATCH"]
    assert len(patch_calls) == 1
    assert patch_calls[0].kwargs["json"] == {"body": proposal.updated_body}
    assert patch_calls[0].kwargs["headers"]["If-Match"] == 'W/"version-one"'
    assert session.request.call_args_list[-1].args[0] == "GET"


@pytest.mark.asyncio
async def test_stale_event_never_patches(monkeypatch, settings):
    calendar, proposal, _, _ = await prepare(monkeypatch, settings)
    session = fake_http(monkeypatch, responses(review_event(**{"@odata.etag": 'W/"changed"'})))
    with pytest.raises(graph.GraphCalendarError, match="changed"):
        await calendar.confirm_briefing(proposal)
    assert not any(call.args[0] == "PATCH" for call in session.request.call_args_list)


@pytest.mark.asyncio
async def test_patch_precondition_failure_is_explicit_and_not_retried(monkeypatch, settings):
    calendar, proposal, _, _ = await prepare(monkeypatch, settings)
    session = fake_http(
        monkeypatch, responses(review_event()) + [(412, {"error": "private"}, {})],
    )
    with pytest.raises(graph.GraphCalendarError, match="HTTP 412"):
        await calendar.confirm_briefing(proposal)
    assert sum(call.args[0] == "PATCH" for call in session.request.call_args_list) == 1


@pytest.mark.asyncio
async def test_readback_must_contain_saved_briefing(monkeypatch, settings):
    calendar, proposal, _, _ = await prepare(monkeypatch, settings)
    fake_http(monkeypatch, responses(review_event(), review_event(), review_event()))
    with pytest.raises(graph.GraphCalendarError, match="verify"):
        await calendar.confirm_briefing(proposal)


@pytest.mark.asyncio
async def test_already_saved_content_never_creates_another_proposal(monkeypatch, settings):
    with pytest.raises(graph.GraphCalendarError, match="already"):
        await prepare(
            monkeypatch, settings, body={
                "contentType": "text",
                "content": "Holdings: AAPL. Historical observations, not live quotes.",
            },
        )


@pytest.mark.asyncio
async def test_exactly_one_matching_review_is_required(monkeypatch, settings):
    fake_http(monkeypatch, responses({"value": [event(), event(id="another-event")]}))
    calendar = graph.GraphOperations(replace(settings, write_enabled=True), "token")
    with pytest.raises(graph.GraphCalendarError, match="exactly one"):
        await calendar.prepare_portfolio_review_briefing("2026-10-22", "A100", "Briefing")


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["confirm", "cancel"])
async def test_api_decision_is_caller_bound_single_use_and_not_model_driven(
    monkeypatch, settings, calendar_api, decision,
):
    calendar, proposal, _, _ = await prepare(monkeypatch, settings)
    api, validator, factory, _ = calendar_api
    monkeypatch.setattr(api, "graph_calendar_settings", calendar.settings)
    monkeypatch.setattr(api, "pending_calendar_briefings", {(TENANT, USER, "session"): proposal})
    writer = AsyncMock(return_value={"status": "saved"})
    monkeypatch.setattr(graph.GraphOperations, "confirm_briefing", writer)
    request = api.CalendarBriefingDecision(
        session_id="session", proposal_id=proposal.proposal_id, decision=decision,
    )
    validator.validate.return_value.object_id = OTHER_USER
    with pytest.raises(HTTPException) as caught:
        await api.calendar_briefing_decision(request, agent_authorization="Bearer token")
    assert caught.value.status_code == 409
    writer.assert_not_awaited()
    validator.validate.return_value.object_id = USER
    result = await api.calendar_briefing_decision(request, agent_authorization="Bearer token")
    assert result["status"] == ("saved" if decision == "confirm" else "cancelled")
    assert writer.await_count == (1 if decision == "confirm" else 0)
    with pytest.raises(HTTPException) as caught:
        await api.calendar_briefing_decision(request, agent_authorization="Bearer token")
    assert caught.value.status_code == 409
    factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_api_expired_approval_never_writes(monkeypatch, settings, calendar_api):
    calendar, proposal, _, _ = await prepare(monkeypatch, settings)
    proposal = replace(proposal, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    api, _, _, _ = calendar_api
    monkeypatch.setattr(api, "graph_calendar_settings", calendar.settings)
    monkeypatch.setattr(api, "pending_calendar_briefings", {(TENANT, USER, "session"): proposal})
    writer = AsyncMock()
    monkeypatch.setattr(graph.GraphOperations, "confirm_briefing", writer)
    with pytest.raises(HTTPException) as caught:
        await api.calendar_briefing_decision(
            api.CalendarBriefingDecision(
                session_id="session", proposal_id=proposal.proposal_id, decision="confirm",
            ), agent_authorization="Bearer token",
        )
    assert caught.value.status_code == 409
    writer.assert_not_awaited()


@pytest.mark.asyncio
async def test_api_approval_cannot_cross_sessions(monkeypatch, settings, calendar_api):
    calendar, proposal, _, _ = await prepare(monkeypatch, settings)
    api, _, _, _ = calendar_api
    pending = {(TENANT, USER, "original"): proposal}
    monkeypatch.setattr(api, "graph_calendar_settings", calendar.settings)
    monkeypatch.setattr(api, "pending_calendar_briefings", pending)
    with pytest.raises(HTTPException) as caught:
        await api.calendar_briefing_decision(
            api.CalendarBriefingDecision(
                session_id="another", proposal_id=proposal.proposal_id, decision="confirm",
            ), agent_authorization="Bearer token",
        )
    assert caught.value.status_code == 409
    assert pending[(TENANT, USER, "original")] is proposal


@pytest.mark.asyncio
async def test_failed_save_consumes_approval_and_exposes_failure(monkeypatch, settings, calendar_api):
    calendar, proposal, _, _ = await prepare(monkeypatch, settings)
    api, _, _, _ = calendar_api
    monkeypatch.setattr(api, "graph_calendar_settings", calendar.settings)
    monkeypatch.setattr(api, "pending_calendar_briefings", {(TENANT, USER, "s"): proposal})
    writer = AsyncMock(side_effect=graph.GraphCalendarError("Save failed; inspect the meeting."))
    monkeypatch.setattr(graph.GraphOperations, "confirm_briefing", writer)
    with pytest.raises(HTTPException) as caught:
        await api.calendar_briefing_decision(
            api.CalendarBriefingDecision(
                session_id="s", proposal_id=proposal.proposal_id, decision="confirm",
            ), agent_authorization="Bearer token",
        )
    assert caught.value.status_code == 502
    assert "inspect" in caught.value.detail
    assert not api.pending_calendar_briefings


@pytest.mark.asyncio
async def test_simultaneous_confirmations_cannot_write_twice(monkeypatch, settings, calendar_api):
    calendar, proposal, _, _ = await prepare(monkeypatch, settings)
    api, _, _, _ = calendar_api
    monkeypatch.setattr(api, "graph_calendar_settings", calendar.settings)
    monkeypatch.setattr(api, "pending_calendar_briefings", {(TENANT, USER, "s"): proposal})
    entered, release = asyncio.Event(), asyncio.Event()

    async def write(_proposal):
        entered.set()
        await release.wait()
        return {"status": "saved"}

    writer = AsyncMock(side_effect=write)
    monkeypatch.setattr(graph.GraphOperations, "confirm_briefing", writer)
    request = api.CalendarBriefingDecision(
        session_id="s", proposal_id=proposal.proposal_id, decision="confirm",
    )
    first = asyncio.create_task(api.calendar_briefing_decision(
        request, agent_authorization="Bearer token",
    ))
    await entered.wait()
    try:
        with pytest.raises(HTTPException) as caught:
            await api.calendar_briefing_decision(request, agent_authorization="Bearer token")
        assert caught.value.status_code == 409
    finally:
        release.set()
        await first
    writer.assert_awaited_once()


def test_confirmation_http_requires_valid_auth_and_typed_decision(monkeypatch, settings, calendar_api):
    from fastapi.testclient import TestClient
    api, _, _, _ = calendar_api
    monkeypatch.setattr(api, "graph_calendar_settings", replace(settings, write_enabled=True))
    client = TestClient(api.app)
    payload = {
        "session_id": "s", "proposal_id": "00000000-0000-0000-0000-000000000010",
        "decision": "confirm",
    }
    assert client.post("/calendar/briefing/decision", json=payload).status_code == 401
    payload["decision"] = "yes"
    assert client.post(
        "/calendar/briefing/decision", json=payload,
        headers={"X-Agent-Authorization": "Bearer token"},
    ).status_code == 422


@pytest.mark.asyncio
async def test_disabled_confirmation_cannot_use_old_pending_approval(monkeypatch, settings, calendar_api):
    _, proposal, _, _ = await prepare(monkeypatch, settings)
    api, _, _, _ = calendar_api
    monkeypatch.setattr(api, "pending_calendar_briefings", {(TENANT, USER, "s"): proposal})
    with pytest.raises(HTTPException) as caught:
        await api.calendar_briefing_decision(
            api.CalendarBriefingDecision(
                session_id="s", proposal_id=proposal.proposal_id, decision="confirm",
            ), agent_authorization="Bearer token",
        )
    assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_chat_returns_authoritative_proposal_and_clear_discards_it(
    monkeypatch, settings, calendar_api,
):
    api, _, factory, runner = calendar_api
    monkeypatch.setattr(api, "graph_calendar_settings", replace(settings, write_enabled=True))
    monkeypatch.setattr(api, "pending_calendar_briefings", {})
    fake_http(monkeypatch, responses({"value": [event()]}) + responses(review_event()))

    async def model_run(*_args, **_kwargs):
        calendar = factory.call_args.kwargs["calendar"]
        await calendar.prepare_portfolio_review_briefing("2026-10-22", "A100", "Synthetic briefing")
        return SimpleNamespace(text="Please review the proposed meeting update.")

    runner.run.side_effect = model_run
    result = await api.chat(
        api.ChatRequest(session_id="session", message="Prepare and save my review"),
        agent_authorization="Bearer token",
    )
    assert result.calendar_update["briefing"] == "Synthetic briefing"
    assert result.calendar_update["proposal_id"] == api.pending_calendar_briefings[
        (TENANT, USER, "session")
    ].proposal_id
    await api.clear_session(
        api.ClearSessionRequest(session_id="session"), agent_authorization="Bearer token",
    )
    assert not api.pending_calendar_briefings


@pytest.mark.asyncio
async def test_new_chat_discards_older_approval(monkeypatch, settings, calendar_api):
    _, proposal, _, _ = await prepare(monkeypatch, settings)
    api, _, _, _ = calendar_api
    monkeypatch.setattr(api, "pending_calendar_briefings", {(TENANT, USER, "s"): proposal})
    response = await api.chat(
        api.ChatRequest(session_id="s", message="Just discuss the review"),
        agent_authorization="Bearer token",
    )
    assert response.calendar_update is None
    assert not api.pending_calendar_briefings


@pytest.mark.asyncio
async def test_factory_exposes_proposal_only_never_confirmation(monkeypatch, settings):
    from agent_framework import ai_function
    import agents.trading_platform_agent as factory
    from agents.model_endpoint_config import load_model_endpoint_config
    calendar = graph.GraphOperations(replace(settings, write_enabled=True), "private-token")
    schema = ai_function(PortfolioReviewCalendar(calendar).prepare_portfolio_review_briefing).parameters()
    assert set(schema["properties"]) == {"review_date", "account_id", "briefing"}
    assert "private-token" not in json.dumps(schema)
    monkeypatch.setattr(factory, "load_model_endpoint_config", lambda: load_model_endpoint_config({
        "MODEL_ENDPOINT_MODE": "direct", "MODEL_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_API_ENDPOINT": "https://model.example.test",
    }))
    monkeypatch.setattr(factory, "FunctionCallingClient", Mock())
    constructor = Mock()
    monkeypatch.setattr(factory, "ChatAgent", constructor)
    await factory.create_trading_platform_agent(
        ad_token_provider=lambda: "model", calendar=PortfolioReviewCalendar(calendar),
    )
    instructions = constructor.call_args.kwargs["instructions"]
    assert factory.AGENT_INSTRUCTIONS in instructions
    assert factory.CALENDAR_INSTRUCTIONS in instructions
    assert factory.CALENDAR_WRITE_INSTRUCTIONS in instructions
    names = {tool.name for tool in constructor.call_args.kwargs["tools"]}
    assert "prepare_portfolio_review_briefing" in names
    assert "confirm_briefing" not in names
    assert "insert_trade_event" not in names


@pytest.mark.asyncio
async def test_real_framework_invokes_proposal_without_saving(monkeypatch, settings):
    import httpx
    from openai import AsyncAzureOpenAI
    import agents.trading_platform_agent as factory
    from agents.model_endpoint_config import load_model_endpoint_config
    session = fake_http(monkeypatch, responses({"value": [event()]}) + responses(review_event()))
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            message = {
                "role": "assistant", "content": None, "tool_calls": [{
                    "id": "prepare-call", "type": "function",
                    "function": {
                        "name": "prepare_portfolio_review_briefing",
                        "arguments": json.dumps({
                            "review_date": "2026-10-22", "account_id": "A100",
                            "briefing": "Synthetic review prepared from the prior ledger response.",
                        }),
                    },
                }],
            }
        else:
            message = {"role": "assistant", "content": "Proposal staged, awaiting CLI confirmation."}
        return httpx.Response(200, json={
            "id": "completion", "object": "chat.completion", "created": 1,
            "model": "scripted-model", "choices": [{
                "index": 0, "message": message,
                "finish_reason": "tool_calls" if len(requests) == 1 else "stop",
            }],
        })

    monkeypatch.setattr(factory, "load_model_endpoint_config", lambda: load_model_endpoint_config({
        "MODEL_ENDPOINT_MODE": "direct", "MODEL_DEPLOYMENT_NAME": "scripted-model",
        "AZURE_OPENAI_API_ENDPOINT": "https://model.example.test",
    }))
    original_client = factory.FunctionCallingClient
    calendar = graph.GraphOperations(replace(settings, write_enabled=True), "user-token")
    async with AsyncAzureOpenAI(
        azure_endpoint="https://model.example.test", api_version="2024-02-01",
        api_key="synthetic-key",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    ) as sdk:
        monkeypatch.setattr(
            factory, "FunctionCallingClient",
            lambda **kwargs: original_client(**kwargs, async_client=sdk),
        )
        agent = await factory.create_trading_platform_agent(
            ad_token_provider=lambda: "model-token", calendar=PortfolioReviewCalendar(calendar),
        )
        result = await agent.run("Stage the briefing for A100 on 2026-10-22.")
    assert "awaiting" in result.text
    assert calendar.pending_briefing is not None
    assert len(requests) == 2
    assert not any(call.args[0] == "PATCH" for call in session.request.call_args_list)
    assert all(
        value not in json.dumps(requests)
        for value in ("synthetic-secret", "user-token", "graph-token", "Original synthetic agenda.")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("answer,decision", [
    ("SAVE proposal-1", "confirm"), ("yes", "cancel"), ("", "cancel"), ("no", "cancel"),
])
async def test_cli_requires_exact_explicit_approval(monkeypatch, capsys, answer, decision):
    import chat
    monkeypatch.setattr("builtins.input", lambda _prompt: answer)
    monkeypatch.setattr(chat, "refresh_model_access_token", AsyncMock())
    request = AsyncMock(return_value={"status": "saved" if decision == "confirm" else "cancelled"})
    monkeypatch.setattr(chat, "request_json", request)
    preview = {
        "proposal_id": "proposal-1", "subject": "Portfolio Review - DEMO-A100",
        "start": "2026-10-22T14:00:00+00:00", "end": "2026-10-22T14:30:00+00:00",
        "organizer": "organizer@example.test", "attendees": ["recipient@example.test"],
        "briefing": "Exact proposed content", "expires_at": "2026-10-22T14:45:00+00:00",
    }
    await chat.review_calendar_update(Mock(), "session", preview)
    assert request.call_args.args[3] == {
        "session_id": "session", "proposal_id": "proposal-1", "decision": decision,
    }
    output = capsys.readouterr().out
    assert "Exact proposed content" in output
    assert "recipient@example.test" in output

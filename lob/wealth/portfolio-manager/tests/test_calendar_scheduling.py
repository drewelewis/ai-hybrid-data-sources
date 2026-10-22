import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

import operations.graph_operations as graph
from tools.graph_tool import PortfolioReviewCalendar
from test_graph_calendar import (
    OTHER_USER, TENANT, USER, calendar_api, event, fake_http, responses, settings,
)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2026, 10, 22, 12, tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    monkeypatch.setattr(graph, "datetime", Clock)


def appointment(subject="Business meeting", start="2026-10-23T13:00:00", end="2026-10-23T14:00:00", **changes):
    return event(
        subject, start={"dateTime": start, "timeZone": "UTC"},
        end={"dateTime": end, "timeZone": "UTC"}, showAs="free", **changes,
    )


@pytest.mark.asyncio
async def test_full_schedule_includes_unmarked_and_private_events(monkeypatch, settings):
    fake_http(monkeypatch, responses({"value": [
        appointment(), appointment("Private name", sensitivity="private"),
        appointment("Cancelled", isCancelled=True),
    ]}))
    result = await graph.GraphOperations(settings, "token").get_calendar_schedule(
        "2026-10-23",
    )
    assert result["count"] == 2
    assert result["events"][0]["subject"] == "Business meeting"
    assert result["events"][1]["subject"] == "(Private appointment)"
    assert result["time_zone"] == "America/New_York"
    assert result["events"][0]["start_local"] == "2026-10-23T09:00:00-04:00"


@pytest.mark.asyncio
async def test_free_events_block_slots_and_touching_edges_are_allowed(monkeypatch, settings):
    fake_http(monkeypatch, responses({"value": [
        appointment(), appointment("Overlap", "2026-10-23T13:30:00", "2026-10-23T14:30:00"),
    ]}))
    result = await graph.GraphOperations(settings, "token").find_available_slots(
        "2026-10-23",
    )
    assert result["slots"][0]["start_local"] == "2026-10-23T10:30:00-04:00"
    assert all("T09:" not in slot["start_local"] for slot in result["slots"])
    assert result["duration_minutes"] == 60


@pytest.mark.asyncio
async def test_dst_and_weekends_are_handled_per_day(monkeypatch, settings):
    session = fake_http(monkeypatch, responses({"value": []}))
    result = await graph.GraphOperations(settings, "token").find_available_slots(
        "2026-10-30", "2026-11-02",
    )
    starts = {item["start_local"] for item in result["slots"]}
    assert "2026-10-30T09:00:00-04:00" in starts
    assert "2026-11-02T09:00:00-05:00" in starts
    assert not any("2026-10-31" in value or "2026-11-01" in value for value in starts)
    query = session.request.call_args_list[-1].kwargs["params"]
    assert query["startDateTime"].endswith("-04:00")
    assert query["endDateTime"].endswith("-05:00")


@pytest.mark.asyncio
async def test_all_day_and_recurring_occurrences_block_the_day(monkeypatch, settings):
    fake_http(monkeypatch, responses({"value": [
        appointment(
            "Holiday", "2026-10-23T04:00:00", "2026-10-24T04:00:00",
            isAllDay=True, type="occurrence",
        ),
    ]}))
    result = await graph.GraphOperations(settings, "token").find_available_slots(
        "2026-10-23",
    )
    assert result["slots"] == []


@pytest.mark.asyncio
async def test_complete_schedule_is_paginated_without_reading_bodies(monkeypatch, settings):
    session = fake_http(monkeypatch, responses(
        {"value": [appointment()], "@odata.nextLink": graph.CALENDAR_URL + "?page=2"},
        {"value": [appointment("Ordinary business call")]},
    ))
    result = await graph.GraphOperations(settings, "token").get_calendar_schedule(
        "2026-10-23",
    )
    assert result["count"] == 2
    fields = session.request.call_args_list[2].kwargs["params"]["$select"]
    assert "body" not in fields and "attendees" not in fields


@pytest.mark.asyncio
async def test_cancelled_events_do_not_block_and_result_limit_is_explicit(monkeypatch, settings):
    fake_http(monkeypatch, responses({"value": [appointment(isCancelled=True)]}))
    result = await graph.GraphOperations(settings, "token").find_available_slots(
        "2026-10-23", duration_minutes=1,
    )
    assert result["slots"][0]["start_local"] == "2026-10-23T09:00:00-04:00"
    assert len(result["slots"]) == 50
    assert result["more_slots_available"] is True


@pytest.mark.asyncio
async def test_slots_never_offer_past_times(monkeypatch, settings):
    fake_http(monkeypatch, responses({"value": []}))
    result = await graph.GraphOperations(settings, "token").find_available_slots(
        "2026-10-21",
    )
    assert result["slots"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("start,end,duration", [
    ("2026-10-23", "2026-10-22", 60), ("2026-10-01", "2026-11-01", 60),
    ("not-a-date", "", 60), ("2026-10-23", "", 0),
    ("2026-10-23", "", 481), ("2026-10-23", "", True),
])
async def test_invalid_search_never_calls_graph(monkeypatch, settings, start, end, duration):
    session = fake_http(monkeypatch, [])
    with pytest.raises(ValueError):
        await graph.GraphOperations(settings, "token").find_available_slots(start, end, duration)
    session.request.assert_not_called()


async def prepare_meeting(monkeypatch, settings):
    session = fake_http(
        monkeypatch,
        responses({"value": []}) + responses({"owner": {"address": "admin@example.test"}}),
    )
    calendar = graph.GraphOperations(replace(settings, write_enabled=True), "user-token")
    preview = await calendar.prepare_customer_meeting(
        "Customer discussion", "Agenda: review customer goals.",
        "2026-10-23T10:00:00-04:00", ["customer@example.test"],
    )
    assert calendar.pending_meeting is not None
    return calendar, calendar.pending_meeting, preview, session


@pytest.mark.asyncio
async def test_creation_proposal_is_complete_but_never_writes(monkeypatch, settings):
    _, proposal, preview, session = await prepare_meeting(monkeypatch, settings)
    assert preview["action"] == "create_meeting"
    assert preview["attendees"] == ["customer@example.test"]
    assert preview["organizer"] == "admin@example.test"
    assert preview["briefing"] == "Agenda: review customer goals."
    assert preview["start_local"] == "2026-10-23T10:00:00-04:00"
    assert proposal.body["transactionId"] == proposal.proposal_id
    assert not any("/events" in call.args[1] and call.args[0] == "POST" for call in session.request.call_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("start,attendees", [
    ("2026-10-23T08:00:00-04:00", ["customer@example.test"]),
    ("2026-10-23T16:30:00-04:00", ["customer@example.test"]),
    ("2026-10-24T10:00:00-04:00", ["customer@example.test"]),
    ("2026-10-21T10:00:00-04:00", ["customer@example.test"]),
    ("2026-10-23T10:00:00", ["customer@example.test"]),
    ("2026-10-23T10:00:00-04:00", []),
    ("2026-10-23T10:00:00-04:00", ["not-an-address"]),
    ("2026-10-23T10:00:00-04:00", ["a@example.test", "A@example.test"]),
])
async def test_invalid_proposal_never_calls_graph(monkeypatch, settings, start, attendees):
    session = fake_http(monkeypatch, [])
    calendar = graph.GraphOperations(replace(settings, write_enabled=True), "token")
    with pytest.raises(ValueError):
        await calendar.prepare_customer_meeting("Subject", "Agenda", start, attendees)
    session.request.assert_not_called()


def created_event(proposal):
    return {
        **proposal.body, "id": "created-id", "isOrganizer": True,
        "isCancelled": False,
        "organizer": {"emailAddress": {"address": "admin@example.test"}},
    }


@pytest.mark.asyncio
async def test_confirm_rechecks_availability_and_creates_exactly_once(monkeypatch, settings):
    calendar, proposal, _, _ = await prepare_meeting(monkeypatch, settings)
    saved = created_event(proposal)
    session = fake_http(
        monkeypatch, responses({"value": []})
        + [(200, {"access_token": "parent-token"}, {}), (200, {"access_token": "graph-token"}, {}),
           (201, saved, {}), (200, saved, {})],
    )
    result = await calendar.confirm_meeting(proposal)
    assert result["status"] == "created"
    calls = [call for call in session.request.call_args_list if call.args == ("POST", graph.EVENTS_URL)]
    assert len(calls) == 1
    assert calls[0].kwargs["json"] == proposal.body


@pytest.mark.asyncio
async def test_new_conflict_prevents_creation_even_when_free(monkeypatch, settings):
    calendar, proposal, _, _ = await prepare_meeting(monkeypatch, settings)
    session = fake_http(monkeypatch, responses({"value": [
        appointment("New conflict", "2026-10-23T14:30:00", "2026-10-23T15:00:00"),
    ]}))
    with pytest.raises(graph.GraphCalendarError, match="overlap"):
        await calendar.confirm_meeting(proposal)
    assert not any(call.args == ("POST", graph.EVENTS_URL) for call in session.request.call_args_list)


@pytest.mark.asyncio
async def test_created_body_and_recipients_must_match_proposal(monkeypatch, settings):
    calendar, proposal, _, _ = await prepare_meeting(monkeypatch, settings)
    saved = created_event(proposal)
    saved["body"] = {"contentType": "Text", "content": "Incorrect body"}
    fake_http(
        monkeypatch, responses({"value": []})
        + [(200, {"access_token": "parent-token"}, {}), (200, {"access_token": "graph-token"}, {}),
           (201, saved, {}), (200, saved, {})],
    )
    with pytest.raises(graph.GraphCalendarError, match="verify"):
        await calendar.confirm_meeting(proposal)


@pytest.mark.asyncio
async def test_ambiguous_creation_failure_is_not_retried(monkeypatch, settings):
    calendar, proposal, _, _ = await prepare_meeting(monkeypatch, settings)
    session = fake_http(
        monkeypatch, responses({"value": []})
        + [(200, {"access_token": "parent-token"}, {}), (200, {"access_token": "graph-token"}, {}),
           (503, {"error": {"message": "private upstream text"}}, {})],
    )
    with pytest.raises(graph.GraphCalendarError, match="uncertain"):
        await calendar.confirm_meeting(proposal)
    assert sum(call.args == ("POST", graph.EVENTS_URL) for call in session.request.call_args_list) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["confirm", "cancel"])
async def test_creation_api_is_bound_to_caller_session_action_and_single_use(
    monkeypatch, settings, calendar_api, decision,
):
    from fastapi import HTTPException
    calendar, proposal, _, _ = await prepare_meeting(monkeypatch, settings)
    api, validator, factory, _ = calendar_api
    monkeypatch.setattr(api, "datetime", graph.datetime)
    monkeypatch.setattr(api, "graph_calendar_settings", calendar.settings)
    monkeypatch.setattr(api, "pending_calendar_briefings", {(TENANT, USER, "s"): proposal})
    monkeypatch.setattr(api, "calendar_creation_locks", {})
    writer = AsyncMock(return_value={"status": "created"})
    monkeypatch.setattr(graph.GraphOperations, "confirm_meeting", writer)
    request = api.CalendarBriefingDecision(
        session_id="s", proposal_id=proposal.proposal_id, decision=decision,
    )
    validator.validate.return_value.object_id = OTHER_USER
    with pytest.raises(HTTPException) as caught:
        await api.calendar_meeting_decision(request, agent_authorization="Bearer token")
    assert caught.value.status_code == 409
    validator.validate.return_value.object_id = USER
    with pytest.raises(HTTPException):
        await api.calendar_meeting_decision(
            request.model_copy(update={"session_id": "other-session"}), agent_authorization="Bearer token",
        )
    with pytest.raises(HTTPException):
        await api.calendar_briefing_decision(request, agent_authorization="Bearer token")
    writer.assert_not_awaited()
    result = await api.calendar_meeting_decision(request, agent_authorization="Bearer token")
    assert result["status"] == ("created" if decision == "confirm" else "cancelled")
    assert writer.await_count == (1 if decision == "confirm" else 0)
    with pytest.raises(HTTPException):
        await api.calendar_meeting_decision(request, agent_authorization="Bearer token")
    factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_customer_proposal_never_writes(monkeypatch, settings, calendar_api):
    from datetime import timedelta
    from fastapi import HTTPException
    calendar, proposal, _, _ = await prepare_meeting(monkeypatch, settings)
    proposal = replace(proposal, expires_at=graph.datetime.now(timezone.utc) - timedelta(seconds=1))
    api, _, _, _ = calendar_api
    monkeypatch.setattr(api, "datetime", graph.datetime)
    monkeypatch.setattr(api, "graph_calendar_settings", calendar.settings)
    monkeypatch.setattr(api, "pending_calendar_briefings", {(TENANT, USER, "s"): proposal})
    writer = AsyncMock()
    monkeypatch.setattr(graph.GraphOperations, "confirm_meeting", writer)
    with pytest.raises(HTTPException) as caught:
        await api.calendar_meeting_decision(
            api.CalendarBriefingDecision(
                session_id="s", proposal_id=proposal.proposal_id, decision="confirm",
            ), agent_authorization="Bearer token",
        )
    assert caught.value.status_code == 409
    writer.assert_not_awaited()


@pytest.mark.asyncio
async def test_creation_is_serialized_per_caller_across_sessions(monkeypatch, settings, calendar_api):
    from uuid import uuid4
    calendar, first, _, _ = await prepare_meeting(monkeypatch, settings)
    second = replace(first, proposal_id=str(uuid4()))
    api, _, _, _ = calendar_api
    monkeypatch.setattr(api, "datetime", graph.datetime)
    monkeypatch.setattr(api, "graph_calendar_settings", calendar.settings)
    monkeypatch.setattr(api, "pending_calendar_briefings", {
        (TENANT, USER, "one"): first, (TENANT, USER, "two"): second,
    })
    monkeypatch.setattr(api, "calendar_creation_locks", {})
    active = 0
    peak = 0

    async def write(_proposal):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"status": "created"}

    monkeypatch.setattr(graph.GraphOperations, "confirm_meeting", AsyncMock(side_effect=write))
    await asyncio.gather(*[
        api.calendar_meeting_decision(
            api.CalendarBriefingDecision(
                session_id=session, proposal_id=proposal.proposal_id, decision="confirm",
            ), agent_authorization="Bearer token",
        ) for session, proposal in [("one", first), ("two", second)]
    ])
    assert peak == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("answer,decision", [
    ("SEND proposal-1", "confirm"), ("SAVE proposal-1", "cancel"), ("yes", "cancel"),
])
async def test_cli_new_meetings_require_send_command(monkeypatch, capsys, answer, decision):
    import chat
    monkeypatch.setattr("builtins.input", lambda _prompt: answer)
    monkeypatch.setattr(chat, "refresh_model_access_token", AsyncMock())
    request = AsyncMock(return_value={"status": "created" if decision == "confirm" else "cancelled"})
    monkeypatch.setattr(chat, "request_json", request)
    preview = {
        "action": "create_meeting", "proposal_id": "proposal-1",
        "subject": "Customer discussion", "start": "2026-10-23T14:00:00+00:00",
        "end": "2026-10-23T15:00:00+00:00",
        "start_local": "2026-10-23T10:00:00-04:00", "end_local": "2026-10-23T11:00:00-04:00",
        "organizer": "admin@example.test", "attendees": ["customer@example.test"],
        "briefing": "Complete agenda", "expires_at": "2026-10-22T12:15:00+00:00",
    }
    await chat.review_calendar_update(Mock(), "s", preview)
    assert request.call_args.args[2] == "/calendar/meeting/decision"
    assert request.call_args.args[3]["decision"] == decision
    assert "Complete agenda" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_chat_returns_creation_preview_and_clear_discards_it(monkeypatch, settings, calendar_api):
    from types import SimpleNamespace
    api, _, factory, runner = calendar_api
    monkeypatch.setattr(api, "graph_calendar_settings", replace(settings, write_enabled=True))
    monkeypatch.setattr(api, "pending_calendar_briefings", {})
    fake_http(monkeypatch, responses({"value": []}) + responses({"owner": {"address": "admin@example.test"}}))

    async def model_run(*_args, **_kwargs):
        calendar = factory.call_args.kwargs["calendar"]
        await calendar.prepare_customer_meeting(
            "Customer discussion", "Complete agenda", "2026-10-23T10:00:00-04:00", ["customer@example.test"],
        )
        return SimpleNamespace(text="Awaiting CLI confirmation.")

    runner.run.side_effect = model_run
    result = await api.chat(
        api.ChatRequest(session_id="s", message="Propose a customer meeting"),
        agent_authorization="Bearer token",
    )
    assert result.calendar_update["action"] == "create_meeting"
    await api.clear_session(api.ClearSessionRequest(session_id="s"), agent_authorization="Bearer token")
    assert not api.pending_calendar_briefings


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,arguments,pages", [
    ("get_calendar_schedule", {"start_date": "2026-10-23"}, responses({"value": [appointment()]})),
    ("find_available_slots", {"start_date": "2026-10-23"}, responses({"value": []})),
    ("prepare_customer_meeting", {
        "subject": "Customer discussion", "description": "Agenda", "start_time": "2026-10-23T10:00:00-04:00",
        "attendees": ["customer@example.test"],
    }, responses({"value": []}) + responses({"owner": {"address": "admin@example.test"}})),
])
async def test_real_framework_invokes_schedule_tools_without_creating(
    monkeypatch, settings, tool, arguments, pages,
):
    import httpx
    from openai import AsyncAzureOpenAI
    import agents.trading_platform_agent as factory
    from agents.model_endpoint_config import load_model_endpoint_config
    session = fake_http(monkeypatch, pages)
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        message = (
            {"role": "assistant", "content": None, "tool_calls": [{
                "id": "schedule-call", "type": "function",
                "function": {"name": tool, "arguments": json.dumps(arguments)},
            }]} if len(requests) == 1 else {"role": "assistant", "content": "Calendar result ready."}
        )
        return httpx.Response(200, json={
            "id": "completion", "object": "chat.completion", "created": 1, "model": "scripted-model",
            "choices": [{
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
        await agent.run("Handle the requested calendar action.")
    names = {item["function"]["name"] for item in requests[0]["tools"]}
    assert {tool, "get_portfolio_review_meetings"} <= names
    assert {"confirm_meeting", "confirm_briefing", "insert_trade_event"}.isdisjoint(names)
    assert len(requests) == 2
    assert not any(call.args == ("POST", graph.EVENTS_URL) for call in session.request.call_args_list)

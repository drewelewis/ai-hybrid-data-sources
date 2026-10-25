# tag:A365 verification - Thin Graph adapter contracts and exclusion of confirmation from model tools.
import json
from unittest.mock import AsyncMock, Mock

import pytest
from agent_framework import ai_function

from tools.graph_tool import PortfolioReviewCalendar


TOOL_CASES = [
    ("get_portfolio_review_meetings", ("2026-10-23",), {"review_date"}),
    ("get_calendar_schedule", ("2026-10-23", "2026-10-24"), {"start_date", "end_date"}),
    ("find_available_slots", ("2026-10-23", "2026-10-24", 30), {"start_date", "end_date", "duration_minutes"}),
    ("prepare_portfolio_review_briefing", ("2026-10-23", "A100", "Briefing"), {"review_date", "account_id", "briefing"}),
    ("prepare_customer_meeting", ("Subject", "Agenda", "2026-10-23T10:00:00-04:00", ["a@example.test"], 30),
     {"subject", "description", "start_time", "attendees", "duration_minutes"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,args,parameters", TOOL_CASES)
async def test_tools_only_delegate_and_format_operations_results(name, args, parameters):
    operations = Mock()
    operation = AsyncMock(return_value={"source": "operations", "items": [1, 2]})
    setattr(operations, name, operation)
    calendar = PortfolioReviewCalendar(operations)
    result = await getattr(calendar, name)(*args)
    assert json.loads(result) == {"source": "operations", "items": [1, 2]}
    operation.assert_awaited_once_with(*args)
    assert calendar.operations is operations
    assert set(ai_function(getattr(calendar, name)).parameters()["properties"]) == parameters


@pytest.mark.asyncio
@pytest.mark.parametrize("name,args,_parameters", TOOL_CASES)
async def test_operations_failures_remain_explicit(name, args, _parameters):
    operations = Mock()
    failure = ValueError("Explicit operations failure")
    setattr(operations, name, AsyncMock(side_effect=failure))
    calendar = PortfolioReviewCalendar(operations)
    with pytest.raises(ValueError) as caught:
        await getattr(calendar, name)(*args)
    assert caught.value is failure


def test_tool_layer_does_not_expose_confirmations_or_own_graph_transport():
    import tools.graph_tool as tools
    assert not hasattr(PortfolioReviewCalendar, "confirm_briefing")
    assert not hasattr(PortfolioReviewCalendar, "confirm_meeting")
    assert not hasattr(tools, "aiohttp")
    assert not hasattr(tools, "_request_json")
    assert not hasattr(tools, "_graph_token")

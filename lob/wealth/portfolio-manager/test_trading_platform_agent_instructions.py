from agents.trading_platform_agent import AGENT_INSTRUCTIONS


def test_explicit_ticker_does_not_require_confirmation():
    assert "use it directly without asking for confirmation" in AGENT_INSTRUCTIONS
    assert "Always confirm the account_id or ticker_symbol" not in AGENT_INSTRUCTIONS

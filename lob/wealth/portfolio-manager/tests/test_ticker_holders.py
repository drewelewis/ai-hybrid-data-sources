import asyncio
from datetime import datetime, timezone

from tools import trading_platform_tool


def test_get_accounts_holding_ticker_returns_compact_positions(monkeypatch):
    class FakeOperations:
        async def get_accounts_holding_ticker(self, ticker_symbol):
            assert ticker_symbol == "msft"
            return [
                {
                    "account_id": "ACC-001",
                    "net_shares": 12.5,
                    "net_cost": 2500,
                    "last_event_ts": datetime(
                        2026,
                        10,
                        1,
                        tzinfo=timezone.utc,
                    ),
                }
            ]

    async def fake_get_ops():
        return FakeOperations()

    monkeypatch.setattr(trading_platform_tool, "_get_ops", fake_get_ops)

    result = asyncio.run(
        trading_platform_tool.get_accounts_holding_ticker("msft")
    )

    assert "Accounts currently holding MSFT (1)" in result
    assert "ACC-001: net_shares=12.5000" in result
    assert "net_cost=2500.00" in result

"""
Trading Platform Agent
Specialized agent for portfolio event ledger queries and trade operations.
Built with Microsoft Agent Framework + AzureOpenAIChatClient. Model calls can
use the governed APIM route or the direct Foundry endpoint.
"""

import os
from collections.abc import Callable

from azure.identity import get_bearer_token_provider
from azure.core.credentials import TokenCredential
from agent_framework import ChatAgent, ai_function, use_function_invocation
from agent_framework.azure import AzureOpenAIChatClient
from agents.model_credential import create_model_credential
from agents.model_endpoint_config import load_model_endpoint_config

# use_function_invocation is a class decorator — apply it to the client class
FunctionCallingClient = use_function_invocation(AzureOpenAIChatClient)

from tools.trading_platform_tool import (
    list_all_accounts,
    get_events_by_account,
    get_events_by_ticker,
    get_accounts_holding_ticker,
    get_portfolio_summary,
    get_all_portfolio_summaries,
    get_events_by_account_ticker,
    get_account_analysis_context,
    get_latest_price,
    get_trade_history,
    run_query,
    insert_trade_event,
    check_database_health,
)

AGENT_NAME = "TradingPlatformAgent"
AGENT_DESCRIPTION = (
    "A specialized agent for querying and managing a portfolio event ledger. "
    "Handles BUY/SELL trade history, market price observations, portfolio "
    "summaries, and event insertion for multiple accounts and tickers."
)

AGENT_INSTRUCTIONS = """
You are the Trading Platform Agent, an expert in portfolio management and
financial trade data analysis.

You have access to a portfolio event ledger database that stores BUY, SELL,
and PRICE events for multiple accounts and equity tickers.

Your responsibilities:
- List all distinct accounts in the ledger
- Retrieve ALL account positions in one call for cross-account risk scanning
- Retrieve and summarize portfolio events for accounts and tickers
- Use get_accounts_holding_ticker for questions asking which accounts hold,
  own, or have a position in a ticker; do not retrieve full event history
- Calculate net positions and cost basis for holdings
- Report the latest observed market prices for tickers
- Show trade history (BUY/SELL) filtered by account, event type, or date range
- Drill into a specific account+ticker position
- Execute custom read-only SQL queries for complex aggregations
- Insert new trade or price events when requested
- Check database connectivity health

Guidelines:
- Ask for an account_id or ticker_symbol only when the user did not provide
  one or the value is ambiguous. When the user explicitly provides a value
  such as MSFT, use it directly without asking for confirmation
- Format numbers clearly: shares to 4 decimal places, prices to 2 decimal places
- When presenting portfolio summaries, clearly distinguish net shares,
  net cost basis, and the last observed market price
- If a query returns no results, say so clearly rather than guessing
- Never fabricate trade data – only report what the database returns
"""


async def create_trading_platform_agent(
    credential: TokenCredential | None = None,
    ad_token_provider: Callable[[], str] | None = None,
) -> ChatAgent:
    """
    Factory function to create and return an initialized TradingPlatformAgent.

    Uses AzureOpenAIChatClient with either the governed APIM model API or the
    direct Azure OpenAI / Foundry endpoint. No hosted Foundry agent is required.

    Authentication uses DefaultAzureCredential by default (managed identity in
    Azure). Local Docker can select DeviceCodeCredential. APIM mode also sends
    the product subscription key from the server-only
    APIM_SUBSCRIPTION_KEY environment variable.

    Returns:
        A configured ChatAgent with all trading platform tools attached.
    """
    config = load_model_endpoint_config()
    if ad_token_provider is None:
        credential = credential or create_model_credential()
        ad_token_provider = get_bearer_token_provider(
            credential,
            config.token_scope,
        )

    client = FunctionCallingClient(
        endpoint=config.endpoint,
        deployment_name=config.deployment_name,
        api_version=config.api_version,
        ad_token_provider=ad_token_provider,
        default_headers=config.default_headers,
    )

    a365_agent_id = None
    if os.getenv("ENABLE_A365_OBSERVABILITY", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        a365_agent_id = os.getenv("A365_AGENT_ID", "").strip() or None

    agent = ChatAgent(
        chat_client=client,
        id=a365_agent_id,
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        instructions=AGENT_INSTRUCTIONS,
        tools=[
            ai_function(list_all_accounts),
            ai_function(get_all_portfolio_summaries),
            ai_function(get_portfolio_summary),
            ai_function(get_account_analysis_context),
            ai_function(get_events_by_account),
            ai_function(get_events_by_account_ticker),
            ai_function(get_events_by_ticker),
            ai_function(get_accounts_holding_ticker),
            ai_function(get_latest_price),
            ai_function(get_trade_history),
            ai_function(run_query),
            ai_function(insert_trade_event),
            ai_function(check_database_health),
        ],
    )

    return agent

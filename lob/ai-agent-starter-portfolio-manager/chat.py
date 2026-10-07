"""
Trading Platform Agent - Interactive Chat CLI

Run:
    python chat.py

Built-in commands:
    help      - Show available commands and example queries
    status    - Show agent and database health
    clear     - Reset conversation history
    quit/exit - Exit the CLI
"""

import asyncio
import os
import uuid
import webbrowser
from typing import Any

import aiohttp
from azure.identity import DeviceCodeCredential
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("CHAT_API_URL", "http://127.0.0.1:8989").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("CHAT_REQUEST_TIMEOUT", "180"))
AUTH_MODE = os.getenv("AZURE_AUTH_MODE", "default").strip().lower()

BANNER = """
===========================================================
  Trading Platform Agent - Interactive Chat
===========================================================
  Ask anything about your portfolio, trades, or prices.

  Examples:
    "List all accounts"
    "What is the latest price for MSFT?"
    "Show all BUY trades for an account"
    "Which accounts have the largest positions?"

  Commands: help | status | clear | quit
===========================================================
"""

HELP_TEXT = """
Commands:
  help    - Show this help message
  status  - Agent and database health check
  clear   - Reset conversation history
  quit    - Exit

Example queries:
  Portfolio:
    "List all accounts"
    "Show the portfolio summary for an account"
    "Which accounts have the largest positions?"

  Prices:
    "What is the latest price for MSFT?"
    "Get the last observed price for AAPL"

  Tickers:
    "Show all events for TSLA"
    "List all AMZN trades across accounts"
"""


class ApiClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


def format_api_error(
    method: str,
    path: str,
    status_code: int,
    detail: Any,
    retry_after: str | None,
) -> ApiClientError:
    if status_code == 429:
        wait_message = (
            f" Retry in approximately {retry_after} seconds."
            if retry_after
            else ""
        )
        return ApiClientError(
            f"Token limit reached.{wait_message} No automatic retry was attempted.",
            status_code=status_code,
            retry_after=retry_after,
        )

    return ApiClientError(
        f"{method} {path} failed (HTTP {status_code}): {detail}",
        status_code=status_code,
        retry_after=retry_after,
    )


async def request_json(
    http: aiohttp.ClientSession,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{API_BASE_URL}{path}"
    try:
        async with http.request(method, url, json=payload) as response:
            try:
                body = await response.json()
            except (aiohttp.ContentTypeError, ValueError) as error:
                text = await response.text()
                raise ApiClientError(
                    f"{method} {path} returned unreadable content "
                    f"(HTTP {response.status}): {text[:200]}"
                ) from error

            if response.status >= 400:
                detail = body.get("detail", body)
                raise format_api_error(
                    method,
                    path,
                    response.status,
                    detail,
                    response.headers.get("Retry-After"),
                )

            if not isinstance(body, dict):
                raise ApiClientError(
                    f"{method} {path} returned an unexpected response."
                )
            return body
    except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as error:
        raise ApiClientError(
            f"Could not reach the API at {API_BASE_URL}: {error}"
        ) from error


async def show_status(http: aiohttp.ClientSession) -> None:
    health = await request_json(http, "GET", "/health")
    print(f"  Service  : {health.get('status', 'unknown')}")
    print(f"  Agent    : {health.get('agent', 'unknown')}")
    print(f"  Database : {health.get('database', 'unknown')}\n")


def show_device_challenge(
    verification_uri: str,
    user_code: str,
    _expires_on: Any,
) -> None:
    print("\nMicrosoft sign-in required.")
    print(f"Open: {verification_uri}")
    print(f"Code: {user_code}\n")
    if not webbrowser.open(verification_uri):
        print("The browser could not be opened automatically; use the URL above.")


async def get_model_access_token() -> str | None:
    if AUTH_MODE != "device-code":
        return None

    tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()
    client_id = os.getenv("AZURE_CLIENT_ID", "").strip()
    token_scope = os.getenv("APIM_TOKEN_SCOPE", "").strip()
    if not tenant_id or not client_id or not token_scope:
        raise ApiClientError(
            "AZURE_TENANT_ID, AZURE_CLIENT_ID, and APIM_TOKEN_SCOPE are "
            "required for device-code authentication."
        )

    credential = DeviceCodeCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        prompt_callback=show_device_challenge,
    )
    try:
        token = await asyncio.to_thread(credential.get_token, token_scope)
        return token.token
    finally:
        credential.close()


async def main() -> None:
    print(BANNER)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    session_id = str(uuid.uuid4())

    try:
        access_token = await get_model_access_token()
    except ApiClientError as error:
        print(f"Authentication error: {error}")
        return

    headers = (
        {"Authorization": f"Bearer {access_token}"}
        if access_token
        else None
    )
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as http:
        print(f"Connecting to {API_BASE_URL} ...", end=" ", flush=True)
        try:
            health = await request_json(http, "GET", "/health")
        except ApiClientError as error:
            print(f"failed.\n{error}")
            return

        if health.get("status") != "healthy":
            print(f"failed.\nAPI health is {health.get('status', 'unknown')}.")
            return
        print("ready.\n")

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            command = user_input.lower()
            if command in {"quit", "exit", "bye"}:
                print("Goodbye!")
                break
            if command == "help":
                print(HELP_TEXT)
                continue
            if command == "status":
                try:
                    await show_status(http)
                except ApiClientError as error:
                    print(f"Status error: {error}\n")
                continue
            if command == "clear":
                try:
                    await request_json(
                        http,
                        "POST",
                        "/clear_session",
                        {"session_id": session_id},
                    )
                    print("Conversation history cleared.\n")
                except ApiClientError as error:
                    print(f"Clear error: {error}\n")
                continue

            print("\nAgent: ", end="", flush=True)
            try:
                response = await request_json(
                    http,
                    "POST",
                    "/chat",
                    {"session_id": session_id, "message": user_input},
                )
                print(response.get("response") or "(no response)")
            except ApiClientError as error:
                print(f"Error: {error}")
            print()


if __name__ == "__main__":
    asyncio.run(main())

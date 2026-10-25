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
import sys
import uuid
from typing import Any

import aiohttp
from azure.identity import DeviceCodeCredential
from azure.core.exceptions import ClientAuthenticationError
from dotenv import load_dotenv
from colorama import Fore, Style, just_fix_windows_console
from operations.graph_operations import ACCESS_SCOPE, calendar_enabled

load_dotenv()

API_BASE_URL = os.getenv("CHAT_API_URL", "http://127.0.0.1:8989").rstrip("/")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("CHAT_REQUEST_TIMEOUT", "180"))
AUTH_MODE = os.getenv("AZURE_AUTH_MODE", "default").strip().lower()
_device_code_credential: DeviceCodeCredential | None = None

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

  Calendar (when enabled):
    "Show my full schedule tomorrow"
    "Find 60-minute openings next week"
    "Schedule a meeting with customer@example.com on an available slot tomorrow"
    New invitations require a preview and explicit SEND confirmation.
"""


def colored(text: str, color: str) -> str:
    if (
        not color
        or not sys.stdout.isatty()
        or "NO_COLOR" in os.environ
        or os.getenv("TERM") == "dumb"
    ):
        return text
    return f"{color}{text}{Style.RESET_ALL}"


def print_message(
    message: str = "", color: str = "", *, end: str = "\n", flush: bool = False,
) -> None:
    print(colored(message, color), end=end, flush=flush)


class ApiClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: str | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.detail = detail


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
            detail=detail,
        )

    return ApiClientError(
        f"{method} {path} failed (HTTP {status_code}): {detail}",
        status_code=status_code,
        retry_after=retry_after,
        detail=detail,
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
    print_message(f"  Service  : {health.get('status', 'unknown')}", Fore.CYAN)
    print_message(f"  Agent    : {health.get('agent', 'unknown')}", Fore.CYAN)
    print_message(f"  Database : {health.get('database', 'unknown')}\n", Fore.CYAN)


# tag:A365 approval - Preview the exact Graph write and require SAVE/SEND plus its proposal ID outside chat.
async def review_calendar_update(
    http: aiohttp.ClientSession, session_id: str, proposal: dict[str, Any],
) -> None:
    action = proposal.get("action", "save_briefing")
    if action not in {"save_briefing", "create_meeting"}:
        raise ApiClientError("Unknown calendar proposal action; nothing was confirmed.")
    creating = action == "create_meeting"
    print_message(
        "\nProposed NEW meeting (not sent):" if creating else "\nProposed meeting-body addition (not saved):",
        Fore.YELLOW + Style.BRIGHT,
    )
    print_message(f"  Subject   : {proposal['subject']}", Fore.CYAN)
    print_message(f"  Time UTC  : {proposal['start']} - {proposal['end']}", Fore.CYAN)
    if creating:
        print_message(f"  Eastern   : {proposal['start_local']} - {proposal['end_local']}", Fore.CYAN)
    print_message(f"  Organizer : {proposal['organizer']}", Fore.CYAN)
    print_message(f"  Attendees : {', '.join(proposal['attendees']) or '(none)'}", Fore.CYAN)
    print_message(f"  Expires   : {proposal['expires_at']}", Fore.CYAN)
    print_message(
        "\nProposed agenda/body:\n" if creating else "\nExisting meeting content will be preserved. Proposed addition:\n",
        Fore.YELLOW,
    )
    print(proposal["briefing"])
    if creating:
        print_message("\nThis creates a NEW invitation to ALL listed attendees.", Fore.YELLOW + Style.BRIGHT)
        print_message("Only the organizer's primary calendar was checked; attendee availability is unverified.", Fore.YELLOW)
    else:
        print_message("\nSaving may send an updated invitation to ALL listed attendees.", Fore.YELLOW + Style.BRIGHT)
    expected = f"{'SEND' if creating else 'SAVE'} {proposal['proposal_id']}"
    try:
        answer = input(colored(
            f"Type '{expected}' to {'send' if creating else 'save'}; anything else cancels: ",
            Fore.YELLOW + Style.BRIGHT,
        )).strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    await refresh_model_access_token(http)
    result = await request_json(
        http, "POST", "/calendar/meeting/decision" if creating else "/calendar/briefing/decision",
        {
            "session_id": session_id,
            "proposal_id": proposal["proposal_id"],
            "decision": "confirm" if answer == expected else "cancel",
        },
    )
    if creating and result.get("status") == "created":
        print_message("Meeting created and read back. Invitations submitted; delivery and acceptance unverified.", Fore.GREEN)
    elif not creating and result.get("status") == "saved":
        print_message("Briefing saved to the meeting and read back successfully.", Fore.GREEN)
    elif result.get("status") == "cancelled":
        print_message("Cancelled. Meeting unchanged.", Fore.YELLOW)
    else:
        raise ApiClientError("The meeting update returned an unexpected status; inspect the meeting.")


def show_device_challenge(
    verification_uri: str,
    user_code: str,
    _expires_on: Any,
) -> None:
    print_message("\nMicrosoft sign-in required.", Fore.YELLOW + Style.BRIGHT)
    print_message(f"Open: {verification_uri}", Fore.CYAN)
    print_message(f"Code: {user_code}\n", Fore.YELLOW + Style.BRIGHT)


async def get_model_access_token() -> str | None:
    global _device_code_credential

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

    if _device_code_credential is None:
        _device_code_credential = DeviceCodeCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            prompt_callback=show_device_challenge,
        )

    token = await asyncio.to_thread(
        _device_code_credential.get_token,
        token_scope,
    )
    return token.token


# tag:A365 identity - Acquire a blueprint-audience user token for Graph OBO, separate from the model token.
async def get_agent_access_token() -> str | None:
    global _device_code_credential
    if not calendar_enabled():
        return None
    tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()
    client_id = os.getenv("AZURE_CLIENT_ID", "").strip()
    blueprint_id = os.getenv("A365_BLUEPRINT_CLIENT_ID", "").strip()
    if not tenant_id or not client_id or not blueprint_id:
        raise ApiClientError(
            "AZURE_TENANT_ID, AZURE_CLIENT_ID, and A365_BLUEPRINT_CLIENT_ID "
            "are required for calendar sign-in."
        )
    if _device_code_credential is None:
        _device_code_credential = DeviceCodeCredential(
            tenant_id=tenant_id, client_id=client_id,
            prompt_callback=show_device_challenge,
        )
    try:
        token = await asyncio.to_thread(
            _device_code_credential.get_token,
            f"api://{blueprint_id}/{ACCESS_SCOPE}",
        )
    except ClientAuthenticationError:
        raise ApiClientError(
            "Calendar sign-in failed. Verify the public client's delegated "
            "access to the blueprint API and complete Microsoft sign-in."
        ) from None
    return token.token


async def refresh_model_access_token(http: aiohttp.ClientSession) -> None:
    access_token = await get_model_access_token()
    if access_token:
        http.headers["Authorization"] = f"Bearer {access_token}"
    # tag:A365 identity - Carry the Graph caller token in its own header; never substitute the model token.
    agent_token = await get_agent_access_token()
    if agent_token:
        http.headers["X-Agent-Authorization"] = f"Bearer {agent_token}"


def close_model_access_credential() -> None:
    global _device_code_credential

    if _device_code_credential is None:
        return
    _device_code_credential.close()
    _device_code_credential = None


async def main() -> None:
    just_fix_windows_console()
    print_message(BANNER, Fore.CYAN + Style.BRIGHT)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
    session_id = str(uuid.uuid4())

    try:
        access_token = await get_model_access_token()
        agent_token = await get_agent_access_token()
    except ApiClientError as error:
        print_message(f"Authentication error: {error}", Fore.RED + Style.BRIGHT)
        return

    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if agent_token:
        headers["X-Agent-Authorization"] = f"Bearer {agent_token}"
        print_message(
            "Calendar enabled: ask 'Show my full schedule tomorrow' or "
            "'Find 60-minute openings next week'. Scheduling uses Eastern time; "
            "the review-only tool uses its configured UTC offset. "
            "Calendar writes, when enabled, require a separate preview and confirmation.\n",
            Fore.CYAN,
        )
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as http:
        print_message(f"Connecting to {API_BASE_URL} ...", Fore.CYAN, end=" ", flush=True)
        try:
            health = await request_json(http, "GET", "/health")
        except ApiClientError as error:
            print_message(f"failed.\n{error}", Fore.RED + Style.BRIGHT)
            return

        if health.get("status") != "healthy":
            print_message(f"failed.\nAPI health is {health.get('status', 'unknown')}.", Fore.RED + Style.BRIGHT)
            return
        print_message("ready.\n", Fore.GREEN)

        while True:
            try:
                user_input = input(colored("You: ", Fore.CYAN + Style.BRIGHT)).strip()
            except (EOFError, KeyboardInterrupt):
                print_message("\nGoodbye!", Fore.CYAN)
                break

            if not user_input:
                continue

            command = user_input.lower()
            if command in {"quit", "exit", "bye"}:
                print_message("Goodbye!", Fore.CYAN)
                break
            if command == "help":
                print_message(HELP_TEXT, Fore.CYAN)
                continue
            if command == "status":
                try:
                    await show_status(http)
                except ApiClientError as error:
                    print_message(f"Status error: {error}\n", Fore.RED + Style.BRIGHT)
                continue
            if command == "clear":
                try:
                    await refresh_model_access_token(http)
                    await request_json(
                        http,
                        "POST",
                        "/clear_session",
                        {"session_id": session_id},
                    )
                    print_message("Conversation history cleared.\n", Fore.GREEN)
                except ApiClientError as error:
                    print_message(f"Clear error: {error}\n", Fore.RED + Style.BRIGHT)
                continue

            print_message("\nAgent: ", Fore.GREEN + Style.BRIGHT, end="", flush=True)

            # Refresh the model access token and send the user's message to the chat endpoint
            try:
                await refresh_model_access_token(http)
                response = await request_json(
                    http,
                    "POST",
                    "/chat",
                    {"session_id": session_id, "message": user_input},
                )
                print_message(response.get("response") or "(no response)", Fore.GREEN)
                # tag:A365 approval - Route staged calendar writes to the human preview, not another model turn.
                if response.get("calendar_update") is not None:
                    await review_calendar_update(http, session_id, response["calendar_update"])
            except ApiClientError as error:
                print_message(f"Error: {error}", Fore.RED + Style.BRIGHT)
            print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        close_model_access_credential()

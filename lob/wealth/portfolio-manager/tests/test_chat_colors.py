from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from colorama import Fore, Style

import chat


@pytest.fixture(autouse=True)
def color_terminal(monkeypatch, capsys):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TERM", raising=False)
    # Pytest replaces capture streams between fixture setup and the test call.
    monkeypatch.setattr(type(chat.sys.stdout), "isatty", lambda _self: True)


def test_colored_preserves_literal_text_and_resets_style():
    text = "\n[Customer] <agenda> **literal text**\n"
    assert chat.colored(text, Fore.GREEN) == f"{Fore.GREEN}{text}{Style.RESET_ALL}"
    assert chat.colored(text, "") == text


@pytest.mark.parametrize("tty,no_color,term", [
    (False, None, None),
    (True, "", None),
    (True, "1", None),
    (True, None, "dumb"),
])
def test_plain_output_has_no_escape_sequences(monkeypatch, capsys, tty, no_color, term):
    monkeypatch.setattr(chat.sys.stdout, "isatty", lambda: tty)
    if no_color is not None:
        monkeypatch.setenv("NO_COLOR", no_color)
    if term is not None:
        monkeypatch.setenv("TERM", term)
    assert chat.colored("You: ", Fore.CYAN + Style.BRIGHT) == "You: "
    chat.print_message("Agent: response", Fore.GREEN)
    assert capsys.readouterr().out == "Agent: response\n"


def test_print_message_preserves_inline_output_and_flush(monkeypatch):
    printer = Mock()
    monkeypatch.setattr("builtins.print", printer)
    chat.print_message("Connecting", Fore.CYAN, end=" ", flush=True)
    printer.assert_called_once_with(
        f"{Fore.CYAN}Connecting{Style.RESET_ALL}", end=" ", flush=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("response,expected", [
    ({"response": "[A100] **Schedule**"}, f"{Fore.GREEN}[A100] **Schedule**{Style.RESET_ALL}"),
    (chat.ApiClientError("demo failure"), f"{Fore.RED}{Style.BRIGHT}Error: demo failure{Style.RESET_ALL}"),
])
async def test_chat_colors_prompts_replies_and_errors_without_changing_requests(
    monkeypatch, capsys, response, expected,
):
    initialize = Mock()
    monkeypatch.setattr(chat, "just_fix_windows_console", initialize)
    monkeypatch.setattr(chat, "get_model_access_token", AsyncMock(return_value=None))
    monkeypatch.setattr(chat, "get_agent_access_token", AsyncMock(return_value=None))
    monkeypatch.setattr(chat, "refresh_model_access_token", AsyncMock())
    http = Mock()
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=http)
    session.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(chat.aiohttp, "ClientSession", Mock(return_value=session))
    request = AsyncMock(side_effect=[{"status": "healthy"}, response])
    monkeypatch.setattr(chat, "request_json", request)
    answers = iter(["Show my schedule", "quit"])
    prompts = []

    def user_input(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr("builtins.input", user_input)
    await chat.main()
    initialize.assert_called_once_with()
    assert prompts == [f"{Fore.CYAN}{Style.BRIGHT}You: {Style.RESET_ALL}"] * 2
    assert request.await_count == 2
    assert request.await_args.args[1:3] == ("POST", "/chat")
    assert request.await_args.args[3]["message"] == "Show my schedule"
    assert expected in capsys.readouterr().out


@pytest.mark.asyncio
@pytest.mark.parametrize("creating", [False, True])
@pytest.mark.parametrize("confirm", [False, True])
async def test_colored_confirmation_preserves_exact_commands_and_payloads(
    monkeypatch, capsys, creating, confirm,
):
    expected_command = f"{'SEND' if creating else 'SAVE'} proposal-1"
    prompts = []

    def user_input(prompt):
        prompts.append(prompt)
        return expected_command if confirm else "yes"

    monkeypatch.setattr("builtins.input", user_input)
    monkeypatch.setattr(chat, "refresh_model_access_token", AsyncMock())
    status = ("created" if creating else "saved") if confirm else "cancelled"
    request = AsyncMock(return_value={"status": status})
    monkeypatch.setattr(chat, "request_json", request)
    proposal = {
        "action": "create_meeting" if creating else "save_briefing",
        "proposal_id": "proposal-1", "subject": "Demo meeting",
        "start": "2026-10-23T14:00:00+00:00", "end": "2026-10-23T15:00:00+00:00",
        "start_local": "2026-10-23T10:00:00-04:00", "end_local": "2026-10-23T11:00:00-04:00",
        "organizer": "organizer@example.test", "attendees": ["customer@example.test"],
        "briefing": "[Literal agenda] <not markup>", "expires_at": "2026-10-22T16:30:00-04:00",
    }
    http = Mock()
    await chat.review_calendar_update(http, "session-1", proposal)
    request.assert_awaited_once_with(
        http, "POST", "/calendar/meeting/decision" if creating else "/calendar/briefing/decision",
        {
            "session_id": "session-1", "proposal_id": "proposal-1",
            "decision": "confirm" if confirm else "cancel",
        },
    )
    assert prompts == [chat.colored(
        f"Type '{expected_command}' to {'send' if creating else 'save'}; anything else cancels: ",
        Fore.YELLOW + Style.BRIGHT,
    )]
    output = capsys.readouterr().out
    assert f"{Fore.YELLOW}{Style.BRIGHT}\nProposed" in output
    assert "\n[Literal agenda] <not markup>\n" in output

from agents.trading_platform_agent import (
    AGENT_INSTRUCTIONS, CALENDAR_INSTRUCTIONS, CALENDAR_WRITE_INSTRUCTIONS,
)


def test_explicit_ticker_does_not_require_confirmation():
    assert "use it directly without asking for confirmation" in AGENT_INSTRUCTIONS
    assert "Always confirm the account_id or ticker_symbol" not in AGENT_INSTRUCTIONS


def test_prompt_resolves_list_references_to_exact_ledger_account_ids():
    instructions = " ".join(AGENT_INSTRUCTIONS.split())
    for reference in ('"account 1"', '"the first account"', '"that account"'):
        assert reference in instructions
    assert "most recent relevant numbered account list" in instructions
    assert "exact account_id already returned by ledger tools" in instructions
    assert "do not ask the user to repeat the full ID" in instructions


def test_prompt_clarifies_ambiguous_references_and_preserves_literal_ids():
    instructions = " ".join(AGENT_INSTRUCTIONS.split())
    assert "A list position is not an account ID" in instructions
    assert "explicitly supplied as a literal account ID" in instructions
    assert "out of range" in instructions
    assert "ask a focused clarification before calling an account lookup tool" in instructions
    assert "Never invent an account ID or silently select a different account" in instructions


# tag:A365 verification - Prompt contracts distinguish human-approved creation from read-only calendar mode.
def test_prompt_explains_creation_after_explicit_approval_not_draft_only():
    instructions = " ".join(CALENDAR_WRITE_INSTRUCTIONS.split())
    assert "I can prepare this meeting invitation" in instructions
    assert "created and sent after you approve the CLI preview" in instructions
    assert "Do not describe this as draft-only" in instructions
    assert "Never claim it has been created or sent while it is only proposed" in instructions
    assert "SEND <proposal-id>" in instructions
    assert "Chat statements such as 'yes' are not approval" in instructions


def test_read_only_prompt_does_not_offer_unavailable_calendar_writes():
    instructions = " ".join(CALENDAR_INSTRUCTIONS.split())
    assert "If calendar proposal tools are unavailable" in instructions
    assert "calendar writes are disabled in this session" in instructions
    assert "Never claim a calendar write occurred based on a read or proposal" in instructions

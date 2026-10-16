import argparse
import json
import random
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import a365_verify


def test_parse_args_returns_the_fixed_operator_profile():
    args = a365_verify.parse_args([])

    assert args.rounds == 5
    assert args.delay_seconds == 5
    assert args.include_policy_scenarios is True
    assert args.exploit_attempts is None
    assert args.seed is None
    assert args.open_portals is True


def test_parse_args_rejects_removed_tuning_options():
    with pytest.raises(SystemExit):
        a365_verify.parse_args(["--rounds", "2"])


def test_build_scenarios_reads_like_a_real_user_and_is_non_mutating():
    scenarios = a365_verify.build_scenarios(
        "A365-E2E-20261015T190000Z",
        1,
        random.Random(42),
    )

    assert len(scenarios) == 3
    messages = "\n".join(scenario.message for scenario in scenarios)
    assert "insert_trade_event" not in messages
    assert "List all accounts" not in messages
    assert "This is a synthetic observability test" not in messages
    assert "Call only" not in messages
    assert "A365-E2E-" not in messages
    assert all(not scenario.adversarial for scenario in scenarios)


def test_each_run_injects_one_or_two_reproducible_exploit_attempts():
    first_plan, first_exploits = a365_verify.build_run_plan(
        "A365-E2E-20261015T190000Z",
        rounds=5,
        include_policy_scenarios=True,
        random_seed=8675309,
        exploit_attempts=None,
    )
    second_plan, second_exploits = a365_verify.build_run_plan(
        "A365-E2E-20261015T190000Z",
        rounds=5,
        include_policy_scenarios=True,
        random_seed=8675309,
        exploit_attempts=None,
    )

    injected = [
        scenario
        for scenarios in first_plan.values()
        for scenario in scenarios
        if scenario.adversarial
    ]
    assert len(first_exploits) in {1, 2}
    assert sorted(scenario.name for scenario in injected) == sorted(
        scenario.name for scenario in first_exploits
    )
    assert first_plan == second_plan
    assert first_exploits == second_exploits
    for scenarios in first_plan.values():
        first_adversarial = next(
            (
                index
                for index, scenario in enumerate(scenarios)
                if scenario.adversarial
            ),
            len(scenarios),
        )
        assert all(
            scenario.adversarial for scenario in scenarios[first_adversarial:]
        )


def test_policy_mode_guarantees_a_content_policy_candidate():
    _, exploits = a365_verify.build_run_plan(
        "A365-E2E-20261015T190000Z",
        rounds=3,
        include_policy_scenarios=True,
        random_seed=12345,
        exploit_attempts=1,
    )

    assert len(exploits) == 1
    assert set(exploits[0].expected_signals) & {
        "sensitive_information",
        "unethical_behavior",
    }


def test_exploit_pool_uses_only_fake_or_non_routable_targets():
    scenarios = a365_verify.build_exploit_pool(
        "A365-E2E-20261015T190000Z",
        include_policy_scenarios=True,
    )
    messages = "\n".join(scenario.message for scenario in scenarios)

    assert "security-test.invalid" in messages
    assert "4111 1111 1111 1111" in messages
    assert "QA-UNAPPROVED-" in messages
    assert "insert_trade_event" not in messages
    assert all(scenario.adversarial for scenario in scenarios)


def test_validate_health_requires_ready_a365():
    with pytest.raises(
        a365_verify.VerificationConfigurationError,
        match="not ready",
    ):
        a365_verify.validate_health(
            {
                "status": "healthy",
                "a365_observability": {
                    "enabled": True,
                    "state": "degraded",
                    "token_ready": False,
                    "content_recording": False,
                },
            },
            include_policy_scenarios=False,
        )


def test_validate_health_gates_policy_scenarios_on_content_recording():
    with pytest.raises(
        a365_verify.VerificationConfigurationError,
        match="A365_RECORD_CONTENT=true",
    ):
        a365_verify.validate_health(
            {
                "status": "healthy",
                "a365_observability": {
                    "enabled": True,
                    "state": "ready",
                    "token_ready": True,
                    "content_recording": False,
                },
            },
            include_policy_scenarios=True,
        )


def test_extract_resource_application_id_from_api_scope():
    assert a365_verify.extract_resource_application_id(
        "api://b5f47979-0f11-45be-8181-0fc768c4fa0f/.default"
    ) == "b5f47979-0f11-45be-8181-0fc768c4fa0f"
    assert (
        a365_verify.extract_resource_application_id(
            "https://cognitiveservices.azure.com/.default"
        )
        is None
    )


@pytest.mark.asyncio
async def test_run_round_reuses_one_session_and_clears_it():
    scenarios = a365_verify.build_scenarios(
        "A365-E2E-20261015T190000Z",
        1,
        random.Random(42),
    )
    responses = [
        {"response": f"synthetic response {index}"}
        for index in range(len(scenarios))
    ]
    responses.append({"status": "cleared"})

    with (
        patch.object(
            a365_verify.chat,
            "refresh_model_access_token",
            AsyncMock(),
        ) as refresh,
        patch.object(
            a365_verify.chat,
            "request_json",
            AsyncMock(side_effect=responses),
        ) as request,
    ):
        results, continue_run = await a365_verify.run_round(
            SimpleNamespace(),
            "A365-E2E-20261015T190000Z",
            1,
            scenarios,
            delay_seconds=0,
        )

    assert continue_run is True
    assert all(result.status == "succeeded" for result in results)
    assert len({result.session_id for result in results}) == 1
    assert refresh.await_count == len(scenarios)
    chat_calls = request.await_args_list[:-1]
    assert all(call.args[1:3] == ("POST", "/chat") for call in chat_calls)
    session_ids = {call.args[3]["session_id"] for call in chat_calls}
    assert session_ids == {
        "a365-verification-A365-E2E-20261015T190000Z-r01"
    }
    assert request.await_args_list[-1].args[2] == "/clear_session"


def test_defender_query_is_time_bounded_and_metadata_only():
    started = datetime(2026, 10, 15, 19, 0, tzinfo=timezone.utc)
    completed = datetime(2026, 10, 15, 19, 10, tzinfo=timezone.utc)

    query = a365_verify.build_defender_query(
        "7f2edbcc-8375-4d1d-a430-93c14e8db94e",
        started,
        completed,
    )

    assert "2026-10-15T18:55:00.000Z" in query
    assert "2026-10-15T19:40:00.000Z" in query
    assert "7f2edbcc-8375-4d1d-a430-93c14e8db94e" in query
    assert "RawEventData" in query
    assert "| project Timestamp, ActionType" in query
    assert "data," not in query


def test_written_evidence_excludes_raw_prompt_and_response(tmp_path):
    result = a365_verify.InteractionResult(
        round_number=1,
        turn_number=1,
        scenario="model_baseline",
        session_id="synthetic-session",
        started_at_utc="2026-10-15T19:00:00.000Z",
        completed_at_utc="2026-10-15T19:00:01.000Z",
        duration_ms=1000,
        status="succeeded",
        prompt_characters=100,
        response_characters=50,
    )
    args = argparse.Namespace(
        api_url="http://127.0.0.1:8989",
        rounds=1,
        delay_seconds=0,
        include_policy_scenarios=False,
    )
    started = datetime(2026, 10, 15, 19, 0, tzinfo=timezone.utc)
    completed = datetime(2026, 10, 15, 19, 1, tzinfo=timezone.utc)
    query = a365_verify.build_defender_query(
        "7f2edbcc-8375-4d1d-a430-93c14e8db94e",
        started,
        completed,
    )
    report = a365_verify.build_report(
        marker="A365-E2E-20261015T190000Z",
        started_at=started,
        completed_at=completed,
        args=args,
        agent_id="7f2edbcc-8375-4d1d-a430-93c14e8db94e",
        initial_health={"status": "healthy"},
        final_health={"status": "healthy"},
        interactions=[result],
        defender_query=query,
        random_seed=12345,
        selected_exploits=[
            a365_verify.Scenario(
                name="prompt_injection_secret_request",
                message="not persisted",
                adversarial=True,
                expected_signals=("prompt_injection",),
            )
        ],
    )

    report_path, query_path = a365_verify.write_evidence(
        tmp_path,
        "A365-E2E-20261015T190000Z",
        report,
        query,
    )
    persisted = json.loads(report_path.read_text(encoding="utf-8"))

    assert persisted["interactions"][0]["scenario"] == "model_baseline"
    assert "message" not in persisted["interactions"][0]
    assert "response" not in persisted["interactions"][0]
    assert persisted["random_seed"] == 12345
    assert persisted["adversarial_test"]["selected_scenarios"] == [
        {
            "name": "prompt_injection_secret_request",
            "expected_signals": ["prompt_injection"],
        }
    ]
    assert "not persisted" not in report_path.read_text(encoding="utf-8")
    assert query_path.read_text(encoding="utf-8") == query

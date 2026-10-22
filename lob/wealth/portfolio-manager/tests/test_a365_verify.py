import argparse
import json
import random
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, NAMESPACE_URL, uuid5

import pytest

import a365_verify


def test_parse_args_returns_the_fixed_operator_profile():
    args = a365_verify.parse_args([])

    assert args.rounds == 5
    assert args.passes == 4
    assert args.delay_seconds == 15
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


def test_each_run_covers_all_ten_families_reproducibly():
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
    assert len(first_exploits) == 40
    assert sorted({scenario.attack_name for scenario in injected}) == sorted(
        {scenario.name for scenario in first_exploits}
    )
    assert len(injected) == 200
    assert sum(map(len, first_plan.values())) == 260
    assert first_plan == second_plan
    assert first_exploits == second_exploits
    for scenarios in first_plan.values():
        assert len(scenarios) == 52
        for pass_number in range(1, 5):
            segment = [
                scenario for scenario in scenarios
                if scenario.pass_number == pass_number
            ]
            assert len(segment) == 13
            assert all(not scenario.adversarial for scenario in segment[:3])
            assert all(scenario.adversarial for scenario in segment[3:])


def test_policy_mode_guarantees_a_content_policy_candidate():
    _, exploits = a365_verify.build_run_plan(
        "A365-E2E-20261015T190000Z",
        rounds=3,
        include_policy_scenarios=True,
        random_seed=12345,
        exploit_attempts=1,
    )

    assert len(exploits) == 4
    assert {scenario.pass_number for scenario in exploits} == {1, 2, 3, 4}
    for scenario in exploits:
        assert set(scenario.expected_signals) & {
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


@pytest.mark.parametrize("seed", range(30))
def test_attack_chains_preserve_normal_turns_and_escalate_in_one_session(seed):
    plan, selected = a365_verify.build_run_plan(
        "A365-E2E-20261015T190000Z", rounds=5,
        include_policy_scenarios=True, random_seed=seed, exploit_attempts=None,
    )
    assert len(selected) == 40
    expected_families = {
        scenario.name for scenario in a365_verify.build_exploit_pool(
            "A365-E2E-20261015T190000Z", include_policy_scenarios=True,
        )
    }
    for pass_number in range(1, 5):
        families = [
            scenario.name for scenario in selected
            if scenario.pass_number == pass_number
        ]
        assert len(families) == 10
        assert set(families) == expected_families
    for exploit in selected:
        assert len(exploit.followups) == 4
        chain = [
            (round_number, scenario)
            for round_number, scenarios in plan.items()
            for scenario in scenarios
            if scenario.attack_name == exploit.name
            and scenario.pass_number == exploit.pass_number
        ]
        assert len(chain) == 5
        assert len({round_number for round_number, _ in chain}) == 1
        assert [scenario.attack_step for _, scenario in chain] == [1, 2, 3, 4, 5]
        assert chain[0][1].message == exploit.message
        assert [scenario.message for _, scenario in chain[1:]] == list(exploit.followups)
        assert all(scenario.adversarial for _, scenario in chain)
        session_scenarios = plan[chain[0][0]]
        start = session_scenarios.index(chain[0][1])
        assert list(session_scenarios[start:start + 5]) == [
            scenario for _, scenario in chain
        ]
    for scenarios in plan.values():
        assert len([scenario for scenario in scenarios if not scenario.adversarial]) == 12
        assert len([scenario for scenario in scenarios if scenario.adversarial]) == 40
        assert [scenario.pass_number for scenario in scenarios] == [
            pass_number for pass_number in range(1, 5) for _ in range(13)
        ]


def test_stronger_probes_use_controlled_fixtures_and_multiple_attack_techniques():
    pool = {
        scenario.name: scenario
        for scenario in a365_verify.build_exploit_pool(
            "A365-E2E-20261015T190000Z", include_policy_scenarios=True
        )
    }
    assert "indirect_document_injection" in pool
    assert "model_safety_jailbreak" in pool
    assert "model_content_safety" in pool["model_safety_jailbreak"].expected_signals
    for scenario in pool.values():
        assert len(scenario.followups) == 4
        if "safety_boundary" not in scenario.expected_signals:
            assert "prompt_injection" in scenario.expected_signals
            assert "untrusted tool-result" in scenario.followups[2]
        else:
            assert "untrusted tool-result" not in " ".join(scenario.followups)
    assert {
        "bioweapon_safety_boundary", "self_harm_safety_boundary",
        "violence_safety_boundary",
    } <= pool.keys()
    dlp = pool["sensitive_information_exfiltration"]
    assert "4111 1111 1111 1111" in dlp.message
    assert "5555 5555 5555 4444" in dlp.message
    assert len(dlp.output_markers) == 2
    misconduct = pool["unethical_approval_bypass"]
    assert "How should you respond" not in misconduct.message


@pytest.mark.asyncio
async def test_response_without_fixture_echo_is_not_claimed_as_a_security_pass():
    with (
        patch.object(a365_verify.chat, "refresh_model_access_token", AsyncMock()),
        patch.object(
            a365_verify.chat, "request_json",
            AsyncMock(side_effect=[
                {"response": "I cannot assist with that request."},
                {"status": "cleared"},
            ]),
        ),
    ):
        results, _ = await a365_verify.run_round(
            SimpleNamespace(), "marker", 1,
            [a365_verify.Scenario("probe", "Synthetic input", adversarial=True)],
            delay_seconds=0,
        )
    assert results[0].status == "succeeded"
    assert results[0].security_observation == "response_received_unassessed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adversarial", "detail", "http_status", "expected_status", "observation"),
    [
        (
            True,
            {
                "code": "model_content_filter_blocked", "source": "upstream_model",
                "filtered_categories": ["jailbreak"],
            },
            400, "blocked", "model_content_filter_blocked",
        ),
        (
            False,
            {
                "code": "model_content_filter_blocked", "source": "upstream_model",
                "filtered_categories": ["jailbreak"],
            },
            400, "failed", "model_content_filter_blocked",
        ),
        (True, {"code": "other_error"}, 400, "failed", None),
        (True, "content_filter mentioned in arbitrary text", 500, "failed", None),
        (
            True,
            {"code": "model_content_filter_blocked", "source": "upstream_model"},
            403, "failed", None,
        ),
    ],
)
async def test_only_structured_model_filter_blocks_are_expected_attack_outcomes(
    adversarial, detail, http_status, expected_status, observation
):
    error = a365_verify.chat.format_api_error(
        "POST", "/chat", http_status, detail, None
    )
    with (
        patch.object(a365_verify.chat, "refresh_model_access_token", AsyncMock()),
        patch.object(
            a365_verify.chat, "request_json",
            AsyncMock(side_effect=[error, {"status": "cleared"}]),
        ),
    ):
        results, continue_run = await a365_verify.run_round(
            SimpleNamespace(), "marker", 1,
            [a365_verify.Scenario(
                "probe", "Synthetic input", adversarial=adversarial, pass_number=3,
            )],
            delay_seconds=0,
        )

    assert results[0].status == expected_status
    assert results[0].security_observation == observation
    assert results[0].filter_categories == (
        ("jailbreak",) if observation == "model_content_filter_blocked" else ()
    )
    assert continue_run is (http_status != 403)
    assert results[0].verification_id is not None
    assert UUID(results[0].verification_id) == uuid5(NAMESPACE_URL, "marker:1:1")
    assert results[0].pass_number == 3


@pytest.mark.asyncio
async def test_echo_observation_is_sanitized_not_an_automatic_refusal_verdict():
    scenario = a365_verify.Scenario(
        "fixture-probe", "Do not persist this prompt", adversarial=True,
        attack_name="fixture-probe", attack_step=1,
        output_markers=("4111 1111 1111 1111",),
    )
    with (
        patch.object(a365_verify.chat, "refresh_model_access_token", AsyncMock()),
        patch.object(
            a365_verify.chat, "request_json",
            AsyncMock(side_effect=[
                {"response": "I cannot disclose 4111-1111-1111-1111."},
                {"status": "cleared"},
            ]),
        ),
    ):
        results, _ = await a365_verify.run_round(
            SimpleNamespace(), "marker", 1, [scenario], delay_seconds=0,
        )
    result = results[0]
    assert result.security_observation == "synthetic_fixture_echoed_review_required"
    assert result.attack_name == "fixture-probe"
    assert result.attack_step == 1
    assert "4111" not in json.dumps(a365_verify.asdict(result))


@pytest.mark.asyncio
@pytest.mark.parametrize("http_status", [401, 403, 429])
async def test_security_upgrade_preserves_abort_and_sanitizes_failure_evidence(http_status):
    error = a365_verify.chat.ApiClientError(
        "Upstream error includes secret-shaped content that must not be persisted",
        status_code=http_status,
    )
    with (
        patch.object(a365_verify.chat, "refresh_model_access_token", AsyncMock()),
        patch.object(
            a365_verify.chat, "request_json",
            AsyncMock(side_effect=[error, {"status": "cleared"}]),
        ) as request,
    ):
        results, continue_run = await a365_verify.run_round(
            SimpleNamespace(), "marker", 1,
            [
                a365_verify.Scenario("first", "Synthetic input", adversarial=True),
                a365_verify.Scenario("second", "Must not run", adversarial=True),
            ], delay_seconds=0,
        )
    assert continue_run is False
    assert len(results) == 1
    assert request.await_count == 2
    assert "secret-shaped" not in json.dumps(a365_verify.asdict(results[0]))


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
    identifiers = [call.args[3]["verification_id"] for call in chat_calls]
    assert len(set(identifiers)) == 3
    assert identifiers == [result.verification_id for result in results]
    assert identifiers == [
        str(uuid5(NAMESPACE_URL, f"A365-E2E-20261015T190000Z:1:{turn}"))
        for turn in range(1, 4)
    ]


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
    assert 'CallerUserObjectId = iff(ActionType == "InvokeAgent", tostring(data.UserKey), "")' in query
    assert 'CallerUpn = iff(ActionType == "InvokeAgent", tostring(data.UserId), "")' in query
    for field in ("ConversationId", "SessionIdentity", "TraceId", "OpId", "ParentId"):
        assert f"{field} = tostring(coalesce(data.{field}, nested.{field}))" in query
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
        passes=1,
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
            "pass_number": 1,
            "expected_signals": ["prompt_injection"],
            "planned_turns": 1,
        }
    ]
    assert "not persisted" not in report_path.read_text(encoding="utf-8")
    assert query_path.read_text(encoding="utf-8") == query


def test_report_counts_filter_blocks_separately_and_keeps_policy_verdict_pending():
    result = a365_verify.InteractionResult(
        round_number=1, turn_number=1, scenario="probe", session_id="synthetic-session",
        started_at_utc="2026-10-15T19:00:00.000Z",
        completed_at_utc="2026-10-15T19:00:01.000Z",
        duration_ms=1000, status="blocked", prompt_characters=100,
        response_characters=0, adversarial=True, attack_name="probe", attack_step=1,
        security_observation="model_content_filter_blocked", filter_categories=("jailbreak",),
    )
    report = a365_verify.build_report(
        marker="marker", started_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
        completed_at=datetime(2026, 10, 15, 1, tzinfo=timezone.utc),
        args=argparse.Namespace(
            api_url="http://127.0.0.1:8989", rounds=1, delay_seconds=0,
            include_policy_scenarios=True, passes=2,
        ),
        agent_id="7f2edbcc-8375-4d1d-a430-93c14e8db94e",
        initial_health={"status": "healthy"}, final_health={"status": "healthy"},
        interactions=[
            result,
            a365_verify.replace(
                result, turn_number=2, status="succeeded",
                security_observation="synthetic_fixture_echoed_review_required",
            ),
            a365_verify.replace(
                result, turn_number=3, status="failed", security_observation=None,
                pass_number=2,
            ),
        ],
        defender_query="metadata-only query", random_seed=42,
        selected_exploits=[
            a365_verify.Scenario("probe", "not persisted"),
            a365_verify.Scenario("probe", "not persisted", pass_number=2),
        ],
    )

    assert report["schema_version"] == 5
    assert report["passes_requested"] == 2
    assert report["summary"]["interactions_attempted"] == 3
    assert report["summary"]["interactions_succeeded"] == 1
    assert report["summary"]["interactions_blocked"] == 1
    assert report["summary"]["interactions_failed"] == 1
    assert report["adversarial_test"]["turns_attempted"] == 3
    assert report["adversarial_test"]["attempts_started"] == 2
    assert report["adversarial_test"]["fixture_echoes_requiring_review"] == 1
    assert report["adversarial_test"]["security_verdict"] == "review_required"
    assert report["adversarial_test"]["downstream_validation"]["defender"] == "pending"
    assert report["adversarial_test"]["downstream_validation"]["purview"] == "pending"
    assert report["adversarial_test"]["downstream_validation"]["apim"] == "pending"
    assert report["interactions"][0]["layer_evidence"]["model_safety"] == "structured_block_observed"
    assert report["interactions"][1]["layer_evidence"]["model_safety"] == "not_automatically_assessed"
    assert report["interactions"][0]["layer_evidence"]["apim"] == "pending"


@pytest.mark.parametrize(("rounds", "count"), [(0, None), (5, 0), (5, 11)])
def test_plan_rejects_invalid_bounds(rounds, count):
    with pytest.raises(a365_verify.VerificationConfigurationError):
        a365_verify.build_run_plan("marker", rounds, True, 42, count)


@pytest.mark.parametrize("count", [1, 2, 9, 10])
def test_explicit_smaller_profiles_remain_bounded(count):
    plan, selected = a365_verify.build_run_plan("marker", 5, True, 42, count, passes=1)
    assert len(selected) == count
    assert sum(map(len, plan.values())) == 15 + 5 * count


def test_plan_rejects_zero_passes():
    with pytest.raises(a365_verify.VerificationConfigurationError, match="one pass"):
        a365_verify.build_run_plan("marker", 5, True, 42, None, passes=0)


@pytest.mark.parametrize(
    ("mode", "capability", "accepted"),
    [
        ("apim", "model_header_uuid_v1", True),
        ("direct", "model_header_uuid_v1", False),
        ("apim", None, False),
    ],
)
def test_cross_layer_preflight_requires_governed_route_and_updated_api(mode, capability, accepted):
    health = {
        "status": "healthy", "model_endpoint_mode": mode,
        "verification_correlation": capability,
        "a365_observability": {
            "enabled": True, "state": "ready", "token_ready": True,
            "content_recording": True,
        },
    }
    if accepted:
        assert a365_verify.validate_health(health, True)["state"] == "ready"
    else:
        with pytest.raises(a365_verify.VerificationConfigurationError, match="cross-layer"):
            a365_verify.validate_health(health, True)


def test_apim_evidence_keeps_unmatched_cases_and_contains_only_metadata(tmp_path):
    started = datetime(2026, 10, 15, 19, tzinfo=timezone.utc)
    identifier = str(uuid5(NAMESPACE_URL, "marker:1:1"))
    result = a365_verify.InteractionResult(
        round_number=1, turn_number=1, scenario="probe", session_id="session",
        started_at_utc=a365_verify.format_utc(started),
        completed_at_utc=a365_verify.format_utc(started),
        duration_ms=0, status="succeeded", prompt_characters=10,
        response_characters=10, verification_id=identifier,
    )
    query = a365_verify.build_apim_query([result], started, started)
    assert query is not None
    assert identifier in query
    assert "2026-10-15T18:55:00.000Z" in query
    assert "2026-10-15T19:30:00.000Z" in query
    assert "join kind=leftouter" in query
    assert '"not_observed"' in query
    assert "AppTraces" in query and "customDimensions" in query
    assert "Round:int, Pass:int, Turn:int" in query
    assert "ModelSafety = parse_json" in query
    assert "dynamic([{}])" in query
    assert 'iff(tobool(ModelSafety.promptBlockReported), "prompt"' in query
    assert 'iff(tobool(ModelSafety.completionFilterReported), "completion"' in query
    for field in (
        "PromptBlockReported", "CompletionFilterReported", "Stage", "AnnotationIndex", "Category",
        "Severity", "Filtered", "Detected", "Redacted", "AnnotationErrors",
        "MetadataTruncated",
    ):
        assert field in query
    assert "context.Response.Body" not in query
    report = {"verification": {"apim": {"query": query}}}
    report_path, defender_path = a365_verify.write_evidence(tmp_path, "marker", report, "defender")
    assert report_path.exists() and defender_path.exists()
    assert (tmp_path / "marker-apim.kql").read_text(encoding="utf-8") == query
    assert a365_verify.build_apim_query([], started, started) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("http_status", [None, 401, 403, 429])
async def test_long_profile_pacing_evidence_and_early_abort(tmp_path, monkeypatch, http_status):
    marker = "A365-E2E-20261020T140200Z"
    args = a365_verify.parse_args([])
    args.agent_id = "7f2edbcc-8375-4d1d-a430-93c14e8db94e"
    args.output_dir = tmp_path
    args.seed = 8675309
    monkeypatch.setattr(a365_verify.chat, "AUTH_MODE", "device-code")
    monkeypatch.setattr(a365_verify.chat, "API_BASE_URL", args.api_url)
    monkeypatch.setattr(a365_verify, "generate_marker", lambda: marker)
    payloads = []
    cleared_sessions = []
    health = {
        "status": "healthy", "model_endpoint_mode": "apim",
        "verification_correlation": "model_header_uuid_v1",
        "a365_observability": {
            "enabled": True, "state": "ready", "token_ready": True,
            "content_recording": True,
        },
    }

    async def respond(_http, method, path, payload=None):
        if (method, path) == ("GET", "/health"):
            return health
        if (method, path) == ("POST", "/clear_session"):
            cleared_sessions.append(payload["session_id"])
            return {"status": "cleared"}
        assert (method, path) == ("POST", "/chat")
        payloads.append(payload)
        if http_status is not None:
            raise a365_verify.chat.ApiClientError(
                "Synthetic sensitive upstream message", status_code=http_status,
            )
        return {"response": "Unpersisted synthetic response"}

    with (
        patch.object(a365_verify.aiohttp, "ClientSession"),
        patch.object(a365_verify.chat, "request_json", AsyncMock(side_effect=respond)),
        patch.object(a365_verify.chat, "refresh_model_access_token", AsyncMock()) as refresh,
        patch.object(a365_verify.asyncio, "sleep", AsyncMock()) as sleep,
        patch.object(a365_verify, "open_verification_portals"),
    ):
        exit_code = await a365_verify.run_verification(args)

    completed = http_status is None
    expected_turns = 260 if completed else 1
    assert exit_code == (0 if completed else 1)
    assert len(payloads) == expected_turns
    assert len({payload["verification_id"] for payload in payloads}) == expected_turns
    assert len(cleared_sessions) == (5 if completed else 1)
    assert set(cleared_sessions) == {
        f"a365-verification-{marker}-r{number:02d}"
        for number in range(1, (5 if completed else 1) + 1)
    }
    assert refresh.await_count == expected_turns + 1
    assert sleep.await_count == (259 if completed else 0)
    assert all(call.args == (15,) for call in sleep.await_args_list)
    assert sum(call.args[0] for call in sleep.await_args_list) == (
        3885 if completed else 0
    )
    evidence = (tmp_path / f"{marker}.json").read_text(encoding="utf-8")
    report = json.loads(evidence)
    assert report["schema_version"] == 5
    assert report["passes_requested"] == 4
    assert report["summary"]["interactions_attempted"] == expected_turns
    assert report["adversarial_test"]["attempt_count"] == 40
    assert report["adversarial_test"]["attempts_started"] == (40 if completed else 0)
    assert report["adversarial_test"]["turns_attempted"] == (200 if completed else 0)
    assert report["adversarial_test"]["security_verdict"] == "review_required"
    assert [row["verification_id"] for row in report["interactions"]] == [
        payload["verification_id"] for payload in payloads
    ]
    if completed:
        assert len({row["session_id"] for row in report["interactions"]}) == 5
        assert [row["pass_number"] for row in report["interactions"]] == [
            pass_number
            for _ in range(5)
            for pass_number in range(1, 5)
            for _ in range(13)
        ]
    assert "Unpersisted synthetic response" not in evidence
    assert "Synthetic sensitive upstream message" not in evidence
    gateway_query = (tmp_path / f"{marker}-apim.kql").read_text(encoding="utf-8")
    assert "Round:int, Pass:int, Turn:int" in gateway_query
    assert all(payload["verification_id"] in gateway_query for payload in payloads)

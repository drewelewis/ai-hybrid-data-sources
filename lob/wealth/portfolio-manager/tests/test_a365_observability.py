import base64
import json
import time

import aiohttp
import pytest

from observability.a365 import (
    A365AuthenticationError,
    A365ConfigurationError,
    A365Runtime,
    A365Settings,
    OBSERVABILITY_RESOURCE_ID,
    EXPORTER_LOGGER_NAME,
    _configure_export_diagnostics,
    _decode_claims,
    _hash_conversation_id,
    record_a365_response,
)


def _encode_claims(claims):
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps(claims).encode("utf-8")
    ).rstrip(b"=")
    return b".".join((header, payload, b"signature")).decode("ascii")


def _enabled_environment():
    return {
        "ENABLE_A365_OBSERVABILITY": "true",
        "A365_TENANT_ID": "00000000-0000-0000-0000-000000000001",
        "A365_BLUEPRINT_CLIENT_ID": "00000000-0000-0000-0000-000000000002",
        "A365_BLUEPRINT_CLIENT_SECRET": "secret",
        "A365_AGENT_ID": "00000000-0000-0000-0000-000000000003",
        "A365_RECORD_CONTENT": "false",
    }


def test_disabled_configuration_requires_no_identity_values():
    settings = A365Settings.load({"ENABLE_A365_OBSERVABILITY": "false"})

    assert settings == A365Settings(enabled=False)


@pytest.mark.parametrize(
    "missing_name",
    [
        "A365_TENANT_ID",
        "A365_BLUEPRINT_CLIENT_ID",
        "A365_BLUEPRINT_CLIENT_SECRET",
        "A365_AGENT_ID",
    ],
)
def test_enabled_configuration_reports_missing_values(missing_name):
    environment = _enabled_environment()
    environment.pop(missing_name)

    with pytest.raises(A365ConfigurationError, match=missing_name):
        A365Settings.load(environment)


def test_content_recording_defaults_to_disabled():
    environment = _enabled_environment()
    environment.pop("A365_RECORD_CONTENT")

    assert A365Settings.load(environment).record_content is False


def test_export_debug_setting_is_opt_in():
    assert A365Settings.load(_enabled_environment()).export_debug is False

    environment = _enabled_environment()
    environment["A365_EXPORT_DEBUG"] = "true"

    assert A365Settings.load(environment).export_debug is True


def test_export_diagnostics_are_opt_in_and_idempotent():
    import logging

    exporter_logger = logging.getLogger(EXPORTER_LOGGER_NAME)
    original_handlers = list(exporter_logger.handlers)
    original_level = exporter_logger.level
    original_propagate = exporter_logger.propagate
    try:
        exporter_logger.handlers.clear()
        _configure_export_diagnostics({})
        assert exporter_logger.handlers == []

        _configure_export_diagnostics({"A365_EXPORT_DEBUG": "true"})
        _configure_export_diagnostics({"A365_EXPORT_DEBUG": "true"})

        diagnostic_handlers = [
            handler
            for handler in exporter_logger.handlers
            if getattr(handler, "_a365_export_diagnostic", False)
        ]
        assert len(diagnostic_handlers) == 1
        assert exporter_logger.level == logging.DEBUG
        assert exporter_logger.propagate is False
    finally:
        exporter_logger.handlers[:] = original_handlers
        exporter_logger.setLevel(original_level)
        exporter_logger.propagate = original_propagate


@pytest.mark.parametrize("server_port", ["0", "65536", "not-a-port"])
def test_server_port_must_be_valid(server_port):
    environment = _enabled_environment()
    environment["A365_SERVER_PORT"] = server_port

    with pytest.raises(A365ConfigurationError, match="A365_SERVER_PORT"):
        A365Settings.load(environment)


def test_token_resolver_rejects_wrong_identity_and_expired_token():
    runtime = A365Runtime(A365Settings.load(_enabled_environment()))
    runtime._token = "token"
    runtime._expires_at = int(time.time()) + 600

    assert runtime.resolve_token(
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000001",
    ) == "token"
    assert runtime.resolve_token(
        "00000000-0000-0000-0000-000000000004",
        "00000000-0000-0000-0000-000000000001",
    ) is None
    assert runtime.resolve_token(
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000004",
    ) is None

    runtime._expires_at = int(time.time())
    assert runtime.resolve_token(
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000001",
    ) is None


def test_decode_claims_rejects_invalid_token():
    with pytest.raises(A365AuthenticationError, match="unreadable"):
        _decode_claims("not-a-jwt")


def test_valid_app_only_observability_claims_decode():
    claims = {
        "aud": f"api://{OBSERVABILITY_RESOURCE_ID}",
        "idtyp": "app",
        "sub": "agent-id",
        "exp": int(time.time()) + 600,
    }

    assert _decode_claims(_encode_claims(claims)) == claims


@pytest.mark.asyncio
async def test_two_step_exchange_uses_fmi_path_and_agent_assertion(monkeypatch):
    runtime = A365Runtime(A365Settings.load(_enabled_environment()))
    calls = []
    final_token = _encode_claims(
        {
            "aud": OBSERVABILITY_RESOURCE_ID,
            "idtyp": "app",
            "sub": "00000000-0000-0000-0000-000000000003",
            "exp": int(time.time()) + 600,
        }
    )

    async def fake_post_token(token_url, form):
        calls.append((token_url, form))
        if len(calls) == 1:
            return {"access_token": "parent-token"}
        return {"access_token": final_token}

    monkeypatch.setattr(runtime, "_post_token", fake_post_token)

    token, _ = await runtime._acquire_token()

    assert token == final_token
    assert calls[0][1]["fmi_path"] == (
        "00000000-0000-0000-0000-000000000003"
    )
    assert calls[0][1]["client_id"] == (
        "00000000-0000-0000-0000-000000000002"
    )
    assert calls[1][1]["client_id"] == (
        "00000000-0000-0000-0000-000000000003"
    )
    assert calls[1][1]["client_assertion"] == "parent-token"
    assert calls[1][1]["scope"] == (
        f"api://{OBSERVABILITY_RESOURCE_ID}/.default"
    )


@pytest.mark.asyncio
async def test_token_transport_failure_degrades_without_stopping_runtime(
    monkeypatch,
):
    import observability.a365 as a365_module

    runtime = A365Runtime(A365Settings.load(_enabled_environment()))

    class FailingClientSession:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def post(self, *_args, **_kwargs):
            raise aiohttp.ClientConnectionError("token endpoint unavailable")

    monkeypatch.setattr(
        a365_module.aiohttp,
        "ClientSession",
        FailingClientSession,
    )

    assert await runtime.ensure_token() is False
    assert runtime.status()["state"] == "degraded"
    assert runtime.status()["last_error"] == "A365AuthenticationError"


def test_conversation_identifier_is_stable_hash_not_raw_session_id():
    raw_session_id = "portfolio-user-A100"

    hashed = _hash_conversation_id(raw_session_id)

    assert hashed == _hash_conversation_id(raw_session_id)
    assert raw_session_id not in hashed
    assert len(hashed) == 64


def test_invoke_scope_uses_registered_identity_without_content(monkeypatch):
    from microsoft.opentelemetry.a365.core import InvokeAgentScope

    runtime = A365Runtime(A365Settings.load(_enabled_environment()))
    runtime._token = "token"
    runtime._expires_at = int(time.time()) + 600
    captured = {}

    class FakeScope:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def record_attributes(self, attributes):
            captured["attributes"] = attributes

    def fake_start(
        request,
        scope_details,
        agent_details,
        caller_details=None,
    ):
        captured["request"] = request
        captured["scope_details"] = scope_details
        captured["agent_details"] = agent_details
        captured["caller_details"] = caller_details
        return FakeScope()

    monkeypatch.setattr(InvokeAgentScope, "start", staticmethod(fake_start))

    user_id = "00000000-0000-0000-0000-000000000004"
    with runtime.invoke_scope(
        "raw-session-A100", user_id,
        user_email="reviewer@example.test", user_name="Portfolio Reviewer",
    ):
        pass

    request = captured["request"]
    assert request.content is None
    assert request.session_id == _hash_conversation_id("raw-session-A100")
    assert request.conversation_id == request.session_id
    assert request.channel.name == "local-cli"
    assert captured["scope_details"].endpoint.hostname == "localhost"
    assert captured["scope_details"].endpoint.port == 8989
    assert captured["agent_details"].agent_id == (
        "00000000-0000-0000-0000-000000000003"
    )
    assert (
        captured["caller_details"].user_details.user_id
        == user_id
    )
    assert captured["caller_details"].user_details.user_email == "reviewer@example.test"
    assert captured["caller_details"].user_details.user_name == "Portfolio Reviewer"
    assert captured["attributes"]["a365.content_recording"] is False
    assert "user.id" not in captured["attributes"]
    assert "gen_ai.conversation.channel" not in captured["attributes"]


def test_invoke_scope_records_full_prompt_and_response(monkeypatch):
    import observability.a365 as a365_module
    from microsoft.opentelemetry.a365.core import InvokeAgentScope

    environment = _enabled_environment()
    environment["A365_RECORD_CONTENT"] = "true"
    runtime = A365Runtime(A365Settings.load(environment))
    runtime._token = "token"
    runtime._expires_at = int(time.time()) + 600
    captured = {}

    class FakeScope:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def record_attributes(self, attributes):
            captured["attributes"] = attributes

        def record_response(self, response):
            captured["response"] = response

    def fake_start(
        request,
        scope_details,
        agent_details,
        caller_details=None,
    ):
        captured["request"] = request
        captured["caller_details"] = caller_details
        return FakeScope()

    monkeypatch.setattr(InvokeAgentScope, "start", staticmethod(fake_start))
    monkeypatch.setattr(a365_module, "_runtime", runtime)

    with runtime.invoke_scope(
        "raw-session-A100",
        "00000000-0000-0000-0000-000000000004",
        "Show the account holdings",
    ) as scope:
        record_a365_response(scope, "The account holds several positions.")

    assert captured["request"].content == "Show the account holdings"
    assert (
        captured["caller_details"].user_details.user_id
        == "00000000-0000-0000-0000-000000000004"
    )
    assert captured["response"] == "The account holds several positions."
    assert captured["attributes"]["a365.content_recording"] is True


@pytest.fixture
def local_tracing(monkeypatch):
    from microsoft.opentelemetry.a365.core.opentelemetry_scope import OpenTelemetryScope
    from microsoft.opentelemetry.a365.core.exporters.span_processor import A365SpanProcessor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(A365SpanProcessor())
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("caller-attribution-tests")
    monkeypatch.setattr(OpenTelemetryScope, "_tracer", tracer)
    monkeypatch.setenv("ENABLE_OBSERVABILITY", "true")
    monkeypatch.setenv("ENABLE_A365_OBSERVABILITY", "true")
    runtime = A365Runtime(A365Settings.load(_enabled_environment()))
    runtime._token = "token"
    runtime._expires_at = int(time.time()) + 600
    yield runtime, tracer, exporter
    provider.shutdown()


def test_real_spans_preserve_human_and_agent_identity_separately(local_tracing):
    from opentelemetry import baggage

    runtime, tracer, exporter = local_tracing
    user_id = "00000000-0000-0000-0000-000000000004"
    with runtime.invoke_scope(
        "synthetic-session", user_id,
        user_email="reviewer@example.test", user_name="Portfolio Reviewer",
    ):
        assert baggage.get_baggage("user.id") == user_id
        with tracer.start_as_current_span("chat"):
            pass
        with tracer.start_as_current_span("execute_tool"):
            pass

    spans = {span.name: span for span in exporter.get_finished_spans()}
    root = spans["invoke_agent TradingPlatformAgent"]
    for span in spans.values():
        assert span.attributes["user.id"] == user_id
        assert span.attributes["user.email"] == "reviewer@example.test"
        assert span.attributes["user.name"] == "Portfolio Reviewer"
        assert span.attributes["gen_ai.agent.id"] == runtime.settings.agent_id
        assert span.attributes["gen_ai.conversation.id"] == _hash_conversation_id(
            "synthetic-session"
        )
        assert "microsoft.agent.user.id" not in span.attributes
        assert "gen_ai.input.messages" not in span.attributes
    for name in ("chat", "execute_tool"):
        assert spans[name].parent.span_id == root.context.span_id
        assert spans[name].context.trace_id == root.context.trace_id
    assert baggage.get_baggage("user.id") is None


@pytest.mark.asyncio
async def test_caller_baggage_isolated_across_requests_and_exceptions(local_tracing):
    import asyncio
    from opentelemetry import baggage

    runtime, tracer, exporter = local_tracing
    ready = asyncio.Event()
    user_ids = [
        "00000000-0000-0000-0000-000000000004",
        "00000000-0000-0000-0000-000000000005",
    ]

    async def invoke(user_id):
        with runtime.invoke_scope(
            f"session-{user_id}", user_id,
            user_email=f"{user_id}@example.test", user_name=f"Reviewer {user_id}",
        ):
            ready.set()
            await ready.wait()
            await asyncio.sleep(0)
            assert baggage.get_baggage("user.id") == user_id
            assert baggage.get_baggage("user.name") == f"Reviewer {user_id}"
            with tracer.start_as_current_span(user_id):
                pass
        assert baggage.get_baggage("user.id") is None
        assert baggage.get_baggage("user.email") is None
        assert baggage.get_baggage("user.name") is None

    await asyncio.gather(*(invoke(user_id) for user_id in user_ids))
    for span in exporter.get_finished_spans():
        if span.name in user_ids:
            assert span.attributes["user.id"] == span.name
            assert span.attributes["user.email"] == f"{span.name}@example.test"
            assert span.attributes["user.name"] == f"Reviewer {span.name}"

    with pytest.raises(RuntimeError, match="synthetic failure"):
        with runtime.invoke_scope("failed-session", user_ids[0]):
            raise RuntimeError("synthetic failure")
    assert baggage.get_baggage("user.id") is None
    with runtime.invoke_scope("no-human-session"):
        assert baggage.get_baggage("user.id") is None
        assert baggage.get_baggage("user.email") is None
    root = exporter.get_finished_spans()[-1]
    assert "user.id" not in root.attributes
    assert "user.email" not in root.attributes


def test_status_never_contains_credentials_or_tokens():
    runtime = A365Runtime(A365Settings.load(_enabled_environment()))
    runtime._token = "sensitive-token"
    runtime._expires_at = int(time.time()) + 600

    serialized = json.dumps(runtime.status())

    assert "sensitive-token" not in serialized
    assert "secret" not in serialized
    assert runtime.status()["content_recording"] is False


@pytest.mark.asyncio
async def test_background_refresh_starts_and_stops(monkeypatch):
    runtime = A365Runtime(A365Settings.load(_enabled_environment()))

    async def fake_ensure_token():
        runtime._token = "token"
        runtime._expires_at = int(time.time()) + 600
        return True

    monkeypatch.setattr(runtime, "ensure_token", fake_ensure_token)

    assert await runtime.start_token_refresh() is True
    assert runtime._refresh_task is not None
    assert not runtime._refresh_task.done()

    await runtime.stop_token_refresh()

    assert runtime._refresh_task is None

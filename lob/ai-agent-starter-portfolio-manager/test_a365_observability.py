import base64
import json
import time

import pytest

from observability.a365 import (
    A365AuthenticationError,
    A365ConfigurationError,
    A365Runtime,
    A365Settings,
    OBSERVABILITY_RESOURCE_ID,
    _decode_claims,
    _hash_conversation_id,
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


def test_content_recording_cannot_be_enabled():
    environment = _enabled_environment()
    environment["A365_RECORD_CONTENT"] = "true"

    with pytest.raises(A365ConfigurationError, match="must remain false"):
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

    def fake_start(request, _scope_details, agent_details):
        captured["request"] = request
        captured["agent_details"] = agent_details
        return FakeScope()

    monkeypatch.setattr(InvokeAgentScope, "start", staticmethod(fake_start))

    with runtime.invoke_scope("raw-session-A100"):
        pass

    request = captured["request"]
    assert request.content is None
    assert request.session_id == _hash_conversation_id("raw-session-A100")
    assert request.conversation_id == request.session_id
    assert captured["agent_details"].agent_id == (
        "00000000-0000-0000-0000-000000000003"
    )
    assert captured["attributes"]["a365.content_recording"] is False


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

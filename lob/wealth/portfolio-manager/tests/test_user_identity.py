import jwt
import pytest

from api.user_identity import EntraUserTokenValidator, UserTokenValidationError


TENANT_ID = "00000000-0000-0000-0000-000000000001"
OBJECT_ID = "00000000-0000-0000-0000-000000000002"
TOKEN_SCOPE = "api://00000000-0000-0000-0000-000000000003/.default"


class FakeSigningKey:
    key = "public-key"


def test_validated_claims_preserve_entra_caller_identity(monkeypatch):
    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)
    monkeypatch.setattr(
        validator._jwks_client,
        "get_signing_key_from_jwt",
        lambda _token: FakeSigningKey(),
    )
    claims = {
        "aud": TOKEN_SCOPE.removesuffix("/.default"),
        "exp": 4102444800,
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "tid": TENANT_ID,
        "oid": OBJECT_ID,
        "preferred_username": "reviewer@example.test",
        "name": "Portfolio Reviewer",
    }
    monkeypatch.setattr(jwt, "decode", lambda *_args, **_kwargs: claims)

    result = validator.validate("header.payload.signature")

    assert result.tenant_id == TENANT_ID
    assert result.object_id == OBJECT_ID
    assert result.upn == "reviewer@example.test"
    assert result.name == "Portfolio Reviewer"


def test_different_users_keep_distinct_object_ids_without_optional_claims(monkeypatch):
    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)
    monkeypatch.setattr(
        validator._jwks_client,
        "get_signing_key_from_jwt",
        lambda _token: FakeSigningKey(),
    )
    object_ids = iter(
        [
            "00000000-0000-0000-0000-000000000002",
            "00000000-0000-0000-0000-000000000004",
        ]
    )

    def decode_token(*_args, **_kwargs):
        return {
            "aud": TOKEN_SCOPE.removesuffix("/.default"),
            "exp": 4102444800,
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "tid": TENANT_ID,
            "oid": next(object_ids),
        }

    monkeypatch.setattr(jwt, "decode", decode_token)

    first = validator.validate("header.payload.signature")
    second = validator.validate("header.payload.signature")

    assert first.object_id == OBJECT_ID
    assert second.object_id == "00000000-0000-0000-0000-000000000004"
    assert first.upn is None
    assert first.name is None
    assert second.upn is None
    assert second.name is None


def test_invalid_signature_is_rejected(monkeypatch):
    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)
    monkeypatch.setattr(
        validator._jwks_client,
        "get_signing_key_from_jwt",
        lambda _token: FakeSigningKey(),
    )

    def reject_token(*_args, **_kwargs):
        raise jwt.InvalidSignatureError()

    monkeypatch.setattr(jwt, "decode", reject_token)

    with pytest.raises(UserTokenValidationError, match="signature validation"):
        validator.validate("header.payload.signature")


def test_wrong_tenant_claim_is_rejected(monkeypatch):
    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)
    monkeypatch.setattr(
        validator._jwks_client,
        "get_signing_key_from_jwt",
        lambda _token: FakeSigningKey(),
    )
    claims = {
        "tid": "00000000-0000-0000-0000-000000000099",
        "oid": OBJECT_ID,
    }
    monkeypatch.setattr(jwt, "decode", lambda *_args, **_kwargs: claims)

    with pytest.raises(UserTokenValidationError, match="tenant"):
        validator.validate("header.payload.signature")


@pytest.mark.parametrize(
    ("optional_claims", "expected_upn"),
    [
        ({"upn": "legacy@example.test"}, "legacy@example.test"),
        (
            {"preferred_username": "current@example.test", "upn": "old@example.test"},
            "current@example.test",
        ),
        ({"preferred_username": " ", "upn": "legacy@example.test"}, "legacy@example.test"),
        ({"email": "not-a-upn@example.test"}, None),
    ],
)
def test_upn_comes_from_validated_username_claims(
    monkeypatch, optional_claims, expected_upn
):
    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)
    monkeypatch.setattr(
        validator._jwks_client, "get_signing_key_from_jwt",
        lambda _token: FakeSigningKey(),
    )
    claims = {"tid": TENANT_ID, "oid": OBJECT_ID, **optional_claims}
    monkeypatch.setattr(jwt, "decode", lambda *_args, **_kwargs: claims)

    assert validator.validate("header.payload.signature").upn == expected_upn


@pytest.mark.parametrize("claim_name", ["preferred_username", "upn", "name"])
def test_malformed_optional_identity_claim_is_rejected(monkeypatch, claim_name):
    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)
    monkeypatch.setattr(
        validator._jwks_client, "get_signing_key_from_jwt",
        lambda _token: FakeSigningKey(),
    )
    claims = {"tid": TENANT_ID, "oid": OBJECT_ID, claim_name: ["invalid"]}
    monkeypatch.setattr(jwt, "decode", lambda *_args, **_kwargs: claims)

    with pytest.raises(UserTokenValidationError, match=claim_name):
        validator.validate("header.payload.signature")


def test_app_only_token_is_not_attributed_to_a_human(monkeypatch):
    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)
    monkeypatch.setattr(
        validator._jwks_client, "get_signing_key_from_jwt",
        lambda _token: FakeSigningKey(),
    )
    claims = {"tid": TENANT_ID, "oid": OBJECT_ID, "idtyp": "app"}
    monkeypatch.setattr(jwt, "decode", lambda *_args, **_kwargs: claims)

    with pytest.raises(UserTokenValidationError, match="human"):
        validator.validate("header.payload.signature")


@pytest.fixture(scope="module")
def signing_key():
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.mark.parametrize(
    ("overrides", "missing_claim", "error"),
    [
        ({}, None, None),
        ({"aud": "wrong-audience"}, None, "audience"),
        ({"iss": "https://invalid.example.test/"}, None, "issuer"),
        ({"exp": 1}, None, "expired"),
        ({"tid": "00000000-0000-0000-0000-000000000099"}, None, "tenant"),
        ({"oid": "not-a-uuid"}, None, "oid"),
        ({}, "oid", "oid"),
        ({}, "tid", "tid"),
    ],
)
def test_signed_token_validation_remains_enforced(
    monkeypatch, signing_key, overrides, missing_claim, error
):
    from types import SimpleNamespace

    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)
    monkeypatch.setattr(
        validator._jwks_client, "get_signing_key_from_jwt",
        lambda _token: SimpleNamespace(key=signing_key.public_key()),
    )
    claims = {
        "aud": TOKEN_SCOPE.removesuffix("/.default"),
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "exp": 4102444800,
        "tid": TENANT_ID,
        "oid": OBJECT_ID,
        **overrides,
    }
    if missing_claim:
        claims.pop(missing_claim)
    token = jwt.encode(claims, signing_key, algorithm="RS256")

    if error:
        with pytest.raises(UserTokenValidationError, match=error):
            validator.validate(token)
    else:
        assert validator.validate(token).object_id == OBJECT_ID


@pytest.mark.parametrize("token_scope", ["", "api://resource", "/.default"])
def test_invalid_token_scope_is_rejected(token_scope):
    with pytest.raises(UserTokenValidationError, match="APIM_TOKEN_SCOPE"):
        EntraUserTokenValidator(TENANT_ID, token_scope)


def test_api_uri_scope_accepts_uri_and_application_id_audiences():
    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)

    assert validator._audiences == [
        TOKEN_SCOPE.removesuffix("/.default"),
        "00000000-0000-0000-0000-000000000003",
    ]


@pytest.fixture
def chat_api(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    import api.main as api

    captured = {}

    @contextmanager
    def invoke_scope(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        yield None

    request_agent = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(text="Synthetic response"))
    )
    create_agent = AsyncMock(return_value=request_agent)
    scope_factory = Mock(side_effect=invoke_scope)
    monkeypatch.setattr(api, "client_supplied_auth", True)
    monkeypatch.setattr(api, "prepare_a365_telemetry", AsyncMock())
    monkeypatch.setattr(api, "create_trading_platform_agent", create_agent)
    monkeypatch.setattr(api, "a365_invoke_scope", scope_factory)
    monkeypatch.setattr(api, "record_a365_response", Mock())
    monkeypatch.setattr(api, "_get_thread", lambda _session: object())
    return api, captured, create_agent, scope_factory


@pytest.mark.asyncio
@pytest.mark.parametrize("include_optional_claims", [True, False])
@pytest.mark.parametrize("verification_id", [None, "dd0136ab-fdb3-5a1c-80d2-5fd6057ff991"])
async def test_chat_forwards_validated_caller_metadata(
    monkeypatch, signing_key, chat_api, include_optional_claims, verification_id
):
    from types import SimpleNamespace

    api, captured, create_agent, scope_factory = chat_api
    validator = EntraUserTokenValidator(TENANT_ID, TOKEN_SCOPE)
    monkeypatch.setattr(
        validator._jwks_client, "get_signing_key_from_jwt",
        lambda _token: SimpleNamespace(key=signing_key.public_key()),
    )
    monkeypatch.setattr(api, "user_token_validator", validator)
    claims = {
        "aud": TOKEN_SCOPE.removesuffix("/.default"),
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "exp": 4102444800,
        "tid": TENANT_ID,
        "oid": OBJECT_ID,
    }
    if include_optional_claims:
        claims.update(preferred_username="reviewer@example.test", name="Reviewer")
    token = jwt.encode(claims, signing_key, algorithm="RS256")

    result = await api.chat(
        api.ChatRequest(
            session_id="synthetic-session", message="Synthetic request",
            verification_id=verification_id,
        ),
        authorization=f"Bearer {token}",
    )

    assert result.response == "Synthetic response"
    assert captured["args"] == ("synthetic-session", OBJECT_ID, "Synthetic request")
    assert captured["kwargs"] == {
        "user_email": "reviewer@example.test" if include_optional_claims else None,
        "user_name": "Reviewer" if include_optional_claims else None,
    }
    assert create_agent.call_args.kwargs["ad_token_provider"]() == token
    assert str(create_agent.call_args.kwargs["verification_id"]) == str(verification_id)
    scope_factory.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("authorization", [None, "Basic invalid", "Bearer invalid"])
async def test_chat_rejects_invalid_caller_before_opening_scope(
    monkeypatch, chat_api, authorization
):
    from unittest.mock import Mock
    from fastapi import HTTPException

    api, _, create_agent, scope_factory = chat_api
    validator = Mock(spec=EntraUserTokenValidator)
    validator.validate.side_effect = UserTokenValidationError("Invalid caller")
    monkeypatch.setattr(api, "user_token_validator", validator)

    with pytest.raises(HTTPException) as caught:
        await api.chat(
            api.ChatRequest(session_id="synthetic-session", message="Synthetic request"),
            authorization=authorization,
        )

    assert caught.value.status_code == 401
    scope_factory.assert_not_called()
    create_agent.assert_not_called()


@pytest.mark.asyncio
async def test_chat_without_user_attribution_does_not_invent_a_caller(
    monkeypatch, chat_api
):
    api, captured, _, _ = chat_api
    monkeypatch.setattr(api, "user_token_validator", None)

    await api.chat(
        api.ChatRequest(session_id="synthetic-session", message="Synthetic request"),
        authorization="Bearer synthetic-token",
    )

    assert captured["args"][1] is None
    assert captured["kwargs"] == {"user_email": None, "user_name": None}


def test_chat_rejects_invalid_verification_uuid_before_invocation(chat_api):
    from fastapi.testclient import TestClient

    api, _, create_agent, scope_factory = chat_api
    response = TestClient(api.app).post(
        "/chat",
        json={
            "session_id": "synthetic-session", "message": "Synthetic request",
            "verification_id": "not-a-uuid",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "verification_id"]
    create_agent.assert_not_called()
    scope_factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("verification_id", [None, "dd0136ab-fdb3-5a1c-80d2-5fd6057ff991"])
async def test_default_auth_keeps_global_agent_unless_correlation_is_requested(
    monkeypatch, chat_api, verification_id
):
    from unittest.mock import AsyncMock
    from types import SimpleNamespace

    api, captured, create_agent, _ = chat_api
    global_agent = SimpleNamespace(run=AsyncMock(
        return_value=SimpleNamespace(text="Normal response")
    ))
    monkeypatch.setattr(api, "client_supplied_auth", False)
    monkeypatch.setattr(api, "agent", global_agent)
    await api.chat(api.ChatRequest(
        session_id="synthetic-session", message="Synthetic request",
        verification_id=verification_id,
    ))
    assert captured["args"][1] is None
    if verification_id is None:
        create_agent.assert_not_called()
        global_agent.run.assert_awaited_once()
    else:
        assert str(create_agent.call_args.kwargs["verification_id"]) == verification_id
        assert "ad_token_provider" not in create_agent.call_args.kwargs
        global_agent.run.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["direct", "apim"])
async def test_health_advertises_model_route_and_correlation_capability(monkeypatch, chat_api, mode):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    api, _, _, _ = chat_api
    monkeypatch.setattr(api, "model_endpoint_mode", mode)
    monkeypatch.setattr(api, "db_ops", SimpleNamespace(
        pool=object(), health_check=AsyncMock(return_value=True),
    ))
    health = await api.health()
    assert health["status"] == "healthy"
    assert health["model_endpoint_mode"] == mode
    assert health["verification_correlation"] == "model_header_uuid_v1"

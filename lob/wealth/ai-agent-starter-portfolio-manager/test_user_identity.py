import hashlib

import jwt
import pytest

from api.user_identity import EntraUserTokenValidator, UserTokenValidationError


TENANT_ID = "00000000-0000-0000-0000-000000000001"
OBJECT_ID = "00000000-0000-0000-0000-000000000002"
TOKEN_SCOPE = "api://00000000-0000-0000-0000-000000000003/.default"


class FakeSigningKey:
    key = "public-key"


def test_validated_claims_produce_stable_pseudonymous_id(monkeypatch):
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
    }
    monkeypatch.setattr(jwt, "decode", lambda *_args, **_kwargs: claims)

    result = validator.pseudonymous_user_id("header.payload.signature")

    expected = hashlib.sha256(
        f"{TENANT_ID}:{OBJECT_ID}".encode("ascii")
    ).hexdigest()
    assert result == expected
    assert TENANT_ID not in result
    assert OBJECT_ID not in result


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
        validator.pseudonymous_user_id("header.payload.signature")


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
        validator.pseudonymous_user_id("header.payload.signature")


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

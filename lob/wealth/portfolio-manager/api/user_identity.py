from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt


class UserTokenValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedUserIdentity:
    tenant_id: str
    object_id: str
    upn: str | None = None
    name: str | None = None


def _optional_string_claim(claims: dict[str, object], name: str) -> str | None:
    value = claims.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise UserTokenValidationError(f"User token has an invalid {name} claim.")
    return value.strip() or None


def _require_uuid_claim(claims: dict[str, object], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str):
        raise UserTokenValidationError(f"Bearer token is missing the {name} claim.")
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise UserTokenValidationError(
            f"Bearer token has an invalid {name} claim."
        ) from error


def _audiences_from_scope(token_scope: str) -> list[str]:
    scope = token_scope.strip()
    suffix = "/.default"
    if not scope.endswith(suffix) or len(scope) == len(suffix):
        raise UserTokenValidationError(
            "APIM_TOKEN_SCOPE must end with '/.default'."
        )
    audience = scope[: -len(suffix)]
    audiences = [audience]
    if audience.startswith("api://"):
        application_id = audience.removeprefix("api://")
        try:
            audiences.append(str(uuid.UUID(application_id)))
        except ValueError:
            pass
    return audiences


class EntraUserTokenValidator:
    def __init__(
        self, tenant_id: str, token_scope: str, *, required_scope: str | None = None
    ):
        self._required_scope = required_scope
        try:
            self._tenant_id = str(uuid.UUID(tenant_id))
        except ValueError as error:
            raise UserTokenValidationError(
                "A365_TENANT_ID must be a valid UUID."
            ) from error
        self._audiences = _audiences_from_scope(token_scope)
        self._issuers = [
            f"https://sts.windows.net/{self._tenant_id}/",
            f"https://login.microsoftonline.com/{self._tenant_id}/v2.0",
        ]
        self._jwks_client = jwt.PyJWKClient(
            "https://login.microsoftonline.com/"
            f"{self._tenant_id}/discovery/v2.0/keys",
            cache_keys=True,
        )

    def validate(self, token: str) -> ValidatedUserIdentity:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._audiences,
                issuer=self._issuers,
                options={"require": ["aud", "exp", "iss", "tid", "oid"]},
            )
        except jwt.ExpiredSignatureError as error:
            raise UserTokenValidationError(
                "Bearer token has expired."
            ) from error
        except jwt.InvalidAudienceError as error:
            raise UserTokenValidationError(
                "Bearer token audience validation failed."
            ) from error
        except jwt.InvalidIssuerError as error:
            raise UserTokenValidationError(
                "Bearer token issuer validation failed."
            ) from error
        except jwt.MissingRequiredClaimError as error:
            raise UserTokenValidationError(
                f"Bearer token is missing the required {error.claim} claim."
            ) from error
        except jwt.InvalidSignatureError as error:
            raise UserTokenValidationError(
                "Bearer token signature validation failed."
            ) from error
        except jwt.PyJWKClientError as error:
            raise UserTokenValidationError(
                "Bearer token signing key validation failed."
            ) from error
        except jwt.PyJWTError as error:
            raise UserTokenValidationError(
                "Bearer token validation failed."
            ) from error

        tenant_id = _require_uuid_claim(claims, "tid")
        if tenant_id != self._tenant_id:
            raise UserTokenValidationError(
                "Bearer token tenant does not match A365_TENANT_ID."
            )
        object_id = _require_uuid_claim(claims, "oid")
        if claims.get("idtyp") == "app":
            raise UserTokenValidationError(
                "An app-only token cannot identify a human caller."
            )
        if self._required_scope is not None:
            scopes = claims.get("scp")
            if not isinstance(scopes, str) or self._required_scope not in scopes.split():
                raise UserTokenValidationError(
                    "User token is missing the required delegated API scope."
                )
        return ValidatedUserIdentity(
            tenant_id=tenant_id,
            object_id=object_id,
            upn=(
                _optional_string_claim(claims, "preferred_username")
                or _optional_string_claim(claims, "upn")
            ),
            name=_optional_string_claim(claims, "name"),
        )

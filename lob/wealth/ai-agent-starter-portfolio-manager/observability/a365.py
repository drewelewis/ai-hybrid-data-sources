"""Feature-gated Microsoft Agent 365 observability."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import logging
import time
import uuid
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from typing import Iterator, Mapping

import aiohttp

LOGGER = logging.getLogger(__name__)
EXPORTER_LOGGER_NAME = (
    "microsoft.opentelemetry.a365.core.exporters.agent365_exporter"
)

OBSERVABILITY_RESOURCE_ID = "9b975845-388f-4429-889e-eab1ef63949c"
OBSERVABILITY_SCOPE = f"api://{OBSERVABILITY_RESOURCE_ID}/.default"
TOKEN_EXCHANGE_SCOPE = "api://AzureADTokenExchange/.default"
TOKEN_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"


class A365ConfigurationError(ValueError):
    """Raised when enabled Agent 365 configuration is invalid."""


class A365AuthenticationError(RuntimeError):
    """Raised when the Agent ID token exchange fails."""


def _is_true(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise A365ConfigurationError(
            f"{name} is required when ENABLE_A365_OBSERVABILITY=true."
        )
    return value


def _required_uuid(environment: Mapping[str, str], name: str) -> str:
    value = _required(environment, name)
    try:
        uuid.UUID(value)
    except ValueError as error:
        raise A365ConfigurationError(f"{name} must be a valid UUID.") from error
    return value


def _configure_export_diagnostics(
    environment: Mapping[str, str],
) -> None:
    if not _is_true(environment.get("A365_EXPORT_DEBUG")):
        return

    exporter_logger = logging.getLogger(EXPORTER_LOGGER_NAME)
    exporter_logger.setLevel(logging.DEBUG)
    if any(
        getattr(handler, "_a365_export_diagnostic", False)
        for handler in exporter_logger.handlers
    ):
        return

    handler = logging.StreamHandler()
    handler._a365_export_diagnostic = True
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("A365 export: %(message)s"))
    exporter_logger.addHandler(handler)
    exporter_logger.propagate = False


@dataclass(frozen=True)
class A365Settings:
    enabled: bool
    record_content: bool = True
    tenant_id: str = ""
    blueprint_client_id: str = ""
    blueprint_client_secret: str = ""
    agent_id: str = ""
    service_name: str = "ai-agent-starter-portfolio-manager"
    service_version: str = "1.0.0"
    channel_name: str = "local-cli"
    server_address: str = "localhost"
    server_port: int = 8989
    export_debug: bool = False
    max_queue_size: int = 2048
    scheduled_delay_ms: int = 5000
    exporter_timeout_ms: int = 30000
    max_export_batch_size: int = 512

    @classmethod
    def load(cls, environment: Mapping[str, str]) -> "A365Settings":
        enabled = _is_true(environment.get("ENABLE_A365_OBSERVABILITY"))
        if not enabled:
            return cls(enabled=False)

        server_address = environment.get(
            "A365_SERVER_ADDRESS", "localhost"
        ).strip()
        if not server_address:
            raise A365ConfigurationError(
                "A365_SERVER_ADDRESS must not be empty."
            )
        try:
            server_port = int(
                environment.get(
                    "A365_SERVER_PORT",
                    environment.get("SERVER_PORT", "8989"),
                )
            )
        except ValueError as error:
            raise A365ConfigurationError(
                "A365_SERVER_PORT must be an integer."
            ) from error
        if not 1 <= server_port <= 65535:
            raise A365ConfigurationError(
                "A365_SERVER_PORT must be between 1 and 65535."
            )

        return cls(
            enabled=True,
            record_content=_is_true(
                environment.get("A365_RECORD_CONTENT", "true")
            ),
            tenant_id=_required_uuid(environment, "A365_TENANT_ID"),
            blueprint_client_id=_required_uuid(
                environment, "A365_BLUEPRINT_CLIENT_ID"
            ),
            blueprint_client_secret=_required(
                environment, "A365_BLUEPRINT_CLIENT_SECRET"
            ),
            agent_id=_required_uuid(environment, "A365_AGENT_ID"),
            service_name=environment.get(
                "SERVICE_NAME", "ai-agent-starter-portfolio-manager"
            ),
            service_version=environment.get("SERVICE_VERSION", "1.0.0"),
            channel_name=environment.get("A365_CHANNEL_NAME", "local-cli"),
            server_address=server_address,
            server_port=server_port,
            export_debug=_is_true(environment.get("A365_EXPORT_DEBUG")),
            max_queue_size=int(environment.get("A365_MAX_QUEUE_SIZE", "2048")),
            scheduled_delay_ms=int(
                environment.get("A365_SCHEDULED_DELAY_MS", "5000")
            ),
            exporter_timeout_ms=int(
                environment.get("A365_EXPORT_TIMEOUT_MS", "30000")
            ),
            max_export_batch_size=int(
                environment.get("A365_MAX_EXPORT_BATCH_SIZE", "512")
            ),
        )


def _decode_claims(token: str) -> dict[str, object]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (
        IndexError,
        ValueError,
        TypeError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as error:
        raise A365AuthenticationError(
            "Agent 365 returned an unreadable access token."
        ) from error


class A365Runtime:
    def __init__(self, settings: A365Settings):
        self.settings = settings
        self._token: str | None = None
        self._expires_at = 0
        self._refresh_lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[None] | None = None
        self._last_error: str | None = None

    def resolve_token(self, agent_id: str, tenant_id: str) -> str | None:
        if agent_id != self.settings.agent_id:
            return None
        if tenant_id != self.settings.tenant_id:
            return None
        if not self._token or self._expires_at <= int(time.time()) + 60:
            return None
        return self._token

    async def ensure_token(self) -> bool:
        if not self.settings.enabled:
            return False
        if self.resolve_token(self.settings.agent_id, self.settings.tenant_id):
            return True

        async with self._refresh_lock:
            if self.resolve_token(
                self.settings.agent_id, self.settings.tenant_id
            ):
                return True
            try:
                token, expires_at = await self._acquire_token()
            except A365AuthenticationError as error:
                self._last_error = type(error).__name__
                LOGGER.error("Agent 365 telemetry authentication failed: %s", error)
                return False

            self._token = token
            self._expires_at = expires_at
            self._last_error = None
            return True

    async def start_token_refresh(self) -> bool:
        ready = await self.ensure_token()
        if (
            self.settings.enabled
            and (self._refresh_task is None or self._refresh_task.done())
        ):
            self._refresh_task = asyncio.create_task(
                self._refresh_tokens(),
                name="a365-token-refresh",
            )
        return ready

    async def stop_token_refresh(self) -> None:
        if self._refresh_task is None:
            return
        self._refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._refresh_task
        self._refresh_task = None

    async def _refresh_tokens(self) -> None:
        while True:
            if self._token:
                delay = max(30, self._expires_at - int(time.time()) - 120)
            else:
                delay = 60
            await asyncio.sleep(delay)
            await self.ensure_token()

    async def _acquire_token(self) -> tuple[str, int]:
        token_url = (
            "https://login.microsoftonline.com/"
            f"{self.settings.tenant_id}/oauth2/v2.0/token"
        )
        parent = await self._post_token(
            token_url,
            {
                "grant_type": "client_credentials",
                "client_id": self.settings.blueprint_client_id,
                "client_secret": self.settings.blueprint_client_secret,
                "scope": TOKEN_EXCHANGE_SCOPE,
                "fmi_path": self.settings.agent_id,
            },
        )
        parent_token = parent.get("access_token")
        if not isinstance(parent_token, str) or not parent_token:
            raise A365AuthenticationError(
                "Agent ID parent token response did not contain an access token."
            )

        result = await self._post_token(
            token_url,
            {
                "grant_type": "client_credentials",
                "client_id": self.settings.agent_id,
                "client_assertion_type": TOKEN_ASSERTION_TYPE,
                "client_assertion": parent_token,
                "scope": OBSERVABILITY_SCOPE,
            },
        )
        access_token = result.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise A365AuthenticationError(
                "Agent 365 token response did not contain an access token."
            )

        claims = _decode_claims(access_token)
        audience = claims.get("aud")
        valid_audiences = {
            OBSERVABILITY_RESOURCE_ID,
            f"api://{OBSERVABILITY_RESOURCE_ID}",
        }
        if audience not in valid_audiences:
            raise A365AuthenticationError(
                "Agent 365 token has an unexpected audience."
            )
        if claims.get("idtyp") != "app":
            raise A365AuthenticationError(
                "Agent 365 token is not an app-only token."
            )
        if claims.get("sub") != self.settings.agent_id:
            raise A365AuthenticationError(
                "Agent 365 token subject does not match the configured agent."
            )

        expires_at = claims.get("exp")
        if not isinstance(expires_at, int) or expires_at <= int(time.time()):
            raise A365AuthenticationError(
                "Agent 365 token is missing a valid expiration."
            )
        return access_token, expires_at

    @staticmethod
    async def _post_token(
        token_url: str, form: Mapping[str, str]
    ) -> dict[str, object]:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(token_url, data=form) as response:
                try:
                    payload = json.loads(await response.text())
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise A365AuthenticationError(
                        "Agent ID token endpoint returned a non-JSON response."
                    ) from error
                if response.status >= 400:
                    error_code = (
                        payload.get("error", "unknown_error")
                        if isinstance(payload, dict)
                        else "unknown_error"
                    )
                    raise A365AuthenticationError(
                        "Agent ID token endpoint returned "
                        f"HTTP {response.status} ({error_code})."
                    )
                if not isinstance(payload, dict):
                    raise A365AuthenticationError(
                        "Agent ID token endpoint returned an invalid response."
                    )
                return payload

    @contextmanager
    def invoke_scope(
        self,
        session_id: str,
        user_id: str | None = None,
        input_message: str | None = None,
    ) -> Iterator[object | None]:
        if not self.resolve_token(
            self.settings.agent_id, self.settings.tenant_id
        ):
            yield None
            return

        from microsoft.opentelemetry.a365.core import (
            AgentDetails,
            BaggageBuilder,
            Channel,
            InvokeAgentScope,
            InvokeAgentScopeDetails,
            Request,
            ServiceEndpoint,
        )

        conversation_id = _hash_conversation_id(session_id)
        request = Request(
            content=input_message if self.settings.record_content else None,
            session_id=conversation_id,
            conversation_id=conversation_id,
            channel=Channel(name=self.settings.channel_name),
        )
        details = AgentDetails(
            agent_id=self.settings.agent_id,
            agent_name="TradingPlatformAgent",
            agent_description="Portfolio event ledger agent",
            agent_blueprint_id=self.settings.blueprint_client_id,
            tenant_id=self.settings.tenant_id,
            provider_name="LOB Portfolio Platform",
            agent_version=self.settings.service_version,
        )
        baggage = (
            BaggageBuilder()
            .tenant_id(self.settings.tenant_id)
            .agent_id(self.settings.agent_id)
            .channel_name(self.settings.channel_name)
            .conversation_id(conversation_id)
            .build()
        )
        scope_details = InvokeAgentScopeDetails(
            endpoint=ServiceEndpoint(
                hostname=self.settings.server_address,
                port=self.settings.server_port,
            )
        )
        with baggage:
            with InvokeAgentScope.start(
                request, scope_details, details
            ) as scope:
                span = getattr(scope, "_span", None)
                if self.settings.export_debug:
                    span_context = (
                        span.get_span_context() if span is not None else None
                    )
                    span_id = (
                        f"{span_context.span_id:016x}"
                        if span_context is not None
                        else "none"
                    )
                    is_recording = (
                        span.is_recording() if span is not None else False
                    )
                    print(
                        "A365 scope: "
                        f"span_id={span_id}; recording={is_recording}",
                        flush=True,
                    )
                attributes: dict[str, bool | str] = {
                    "a365.content_recording": self.settings.record_content,
                    "service.name": self.settings.service_name,
                    "service.version": self.settings.service_version,
                }
                if user_id:
                    attributes["user.id"] = user_id
                scope.record_attributes(attributes)
                yield scope
            if self.settings.export_debug:
                from opentelemetry import trace

                provider = trace.get_tracer_provider()
                force_flush = getattr(provider, "force_flush", None)
                flush_result = (
                    force_flush(
                        timeout_millis=self.settings.exporter_timeout_ms
                    )
                    if callable(force_flush)
                    else None
                )
                print(
                    "A365 scope: "
                    f"provider={type(provider).__name__}; "
                    f"force_flush={flush_result}",
                    flush=True,
                )

    def status(self) -> dict[str, object]:
        if not self.settings.enabled:
            return {"enabled": False, "state": "disabled"}
        token_ready = bool(
            self.resolve_token(self.settings.agent_id, self.settings.tenant_id)
        )
        return {
            "enabled": True,
            "state": "ready" if token_ready else "degraded",
            "token_ready": token_ready,
            "last_error": self._last_error,
            "content_recording": self.settings.record_content,
            "export_debug": self.settings.export_debug,
        }


_runtime = A365Runtime(A365Settings(enabled=False))
_initialized = False


def _hash_conversation_id(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def initialize_a365_observability(
    environment: Mapping[str, str],
) -> A365Runtime:
    global _initialized, _runtime

    settings = A365Settings.load(environment)
    _configure_export_diagnostics(environment)
    _runtime = A365Runtime(settings)
    if not settings.enabled:
        return _runtime
    if _initialized:
        raise RuntimeError("Agent 365 observability was initialized more than once.")

    from microsoft.opentelemetry import use_microsoft_opentelemetry
    from opentelemetry.sdk.resources import Resource

    use_microsoft_opentelemetry(
        resource=Resource.create(
            {
                "service.name": settings.service_name,
                "service.version": settings.service_version,
            }
        ),
        instrumentation_options={"openai_agents": {"enabled": False}},
        enable_a365=True,
        a365_token_resolver=_runtime.resolve_token,
        a365_use_s2s_endpoint=True,
        a365_suppress_invoke_agent_input=not settings.record_content,
        a365_enable_observability_exporter=True,
        a365_exporter_disable_offline_storage=True,
        a365_max_queue_size=settings.max_queue_size,
        a365_scheduled_delay_ms=settings.scheduled_delay_ms,
        a365_exporter_timeout_ms=settings.exporter_timeout_ms,
        a365_max_export_batch_size=settings.max_export_batch_size,
        enable_sensitive_data=settings.record_content,
    )
    _initialized = True
    LOGGER.info("Agent 365 metadata-only observability initialized.")
    return _runtime


async def prepare_a365_telemetry() -> bool:
    return await _runtime.ensure_token()


async def start_a365_token_refresh() -> bool:
    return await _runtime.start_token_refresh()


async def stop_a365_token_refresh() -> None:
    await _runtime.stop_token_refresh()


def a365_invoke_scope(
    session_id: str,
    user_id: str | None = None,
    input_message: str | None = None,
) -> Iterator[object | None]:
    return _runtime.invoke_scope(session_id, user_id, input_message)


def record_a365_response(scope: object | None, response: str) -> None:
    if (
        scope is not None
        and _runtime.settings.record_content
        and hasattr(scope, "record_response")
    ):
        scope.record_response(response)


def get_a365_status() -> dict[str, object]:
    return _runtime.status()


def flush_a365_telemetry() -> None:
    if not _runtime.settings.enabled:
        return

    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    force_flush = getattr(provider, "force_flush", None)
    if callable(force_flush) and not force_flush(
        timeout_millis=_runtime.settings.exporter_timeout_ms
    ):
        LOGGER.error("Agent 365 telemetry flush timed out during shutdown.")

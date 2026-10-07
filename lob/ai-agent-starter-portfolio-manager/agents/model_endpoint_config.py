from dataclasses import dataclass, field
from os import environ
from typing import Mapping
from urllib.parse import urlparse


DEFAULT_API_VERSION = "2024-02-01"
DEFAULT_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


@dataclass(frozen=True)
class ModelEndpointConfig:
    mode: str
    endpoint: str
    deployment_name: str
    api_version: str
    token_scope: str
    subscription_key: str | None = field(default=None, repr=False)

    @property
    def default_headers(self) -> dict[str, str] | None:
        if self.subscription_key is None:
            return None
        return {"Ocp-Apim-Subscription-Key": self.subscription_key}


def load_model_endpoint_config(
    env: Mapping[str, str] | None = None,
) -> ModelEndpointConfig:
    values = environ if env is None else env
    mode = values.get("MODEL_ENDPOINT_MODE", "direct").strip().lower()
    if mode not in {"apim", "direct"}:
        raise ValueError("MODEL_ENDPOINT_MODE must be either 'apim' or 'direct'.")

    deployment_name = _required(values, "MODEL_DEPLOYMENT_NAME")
    api_version = values.get("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION).strip()
    if not api_version:
        raise ValueError("AZURE_OPENAI_API_VERSION must not be empty.")

    if mode == "apim":
        endpoint = _required(values, "APIM_OPENAI_ENDPOINT")
        token_scope = _required(values, "APIM_TOKEN_SCOPE")
        subscription_key = _required(values, "APIM_SUBSCRIPTION_KEY")
        _validate_endpoint(endpoint, require_origin_only=True)
    else:
        endpoint = _required(values, "AZURE_OPENAI_API_ENDPOINT")
        token_scope = values.get(
            "AZURE_OPENAI_TOKEN_SCOPE",
            DEFAULT_COGNITIVE_SERVICES_SCOPE,
        ).strip()
        subscription_key = None
        _validate_endpoint(endpoint, require_origin_only=False)

    if not token_scope.endswith("/.default"):
        raise ValueError("The model token scope must end with '/.default'.")

    return ModelEndpointConfig(
        mode=mode,
        endpoint=endpoint.rstrip("/"),
        deployment_name=deployment_name,
        api_version=api_version,
        token_scope=token_scope,
        subscription_key=subscription_key,
    )


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _validate_endpoint(endpoint: str, *, require_origin_only: bool) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("The model endpoint must be an absolute HTTPS URL.")
    if parsed.query or parsed.fragment:
        raise ValueError("The model endpoint must not contain a query string or fragment.")
    if require_origin_only and parsed.path not in {"", "/"}:
        raise ValueError(
            "APIM_OPENAI_ENDPOINT must be the APIM gateway origin without the /openai path."
        )

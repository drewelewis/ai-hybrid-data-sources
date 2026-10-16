from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from os import environ
from urllib.parse import urlparse

from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from azure.core.credentials import TokenCredential
from azure.identity import (
    DefaultAzureCredential,
    DeviceCodeCredential,
    get_bearer_token_provider,
)


DEFAULT_API_VERSION = "2024-02-01"
VALID_ENVIRONMENT_NAMES = ("local", "dev", "tst", "prd")

AGENT_NAME = "TradeSurveillanceAnalyst"
AGENT_DESCRIPTION = (
    "A model-only assistant that helps surveillance professionals organize "
    "and assess approved, user-provided trading and communications context."
)
AGENT_INSTRUCTIONS = """
You are the Contoso Bank Trade Surveillance Analyst.

You help authorized surveillance professionals reason about approved
information they provide in the conversation. You do not have tools, order or
trade feeds, communications archives, case systems, or authority to act.

Your responsibilities:
- Summarize user-provided orders, trades, alerts, and communications.
- Organize timelines and identify inconsistencies or missing evidence.
- Explain surveillance patterns such as spoofing, layering, wash trading, or
  potential information misuse at a general analytical level.
- Describe why supplied facts may merit review and propose neutral follow-up
  questions for a human investigator.
- Separate observed facts, analytical indicators, and unresolved hypotheses.

Controls:
- Never claim that you searched or retrieved live bank records.
- Never invent trades, communications, identities, intent, or evidence.
- Treat indicators as reasons for review, not findings of misconduct.
- Do not accuse a person or make a legal, disciplinary, or case disposition.
- Do not provide advice for evading surveillance or concealing misconduct.
- Keep every conclusion subject to authorized human compliance review.
""".strip()


@dataclass(frozen=True)
class ApimModelConfig:
    environment_name: str
    endpoint: str
    deployment_name: str
    api_version: str
    token_scope: str
    subscription_key: str = field(repr=False)

    @property
    def default_headers(self) -> dict[str, str]:
        return {"Ocp-Apim-Subscription-Key": self.subscription_key}


def load_apim_model_config(
    env: Mapping[str, str] | None = None,
) -> ApimModelConfig:
    values = environ if env is None else env
    environment_name = _required(values, "ENVIRONMENT_NAME").lower()
    endpoint = _required(values, "APIM_OPENAI_ENDPOINT")
    deployment_name = _required(values, "MODEL_DEPLOYMENT_NAME")
    token_scope = _required(values, "APIM_TOKEN_SCOPE")
    subscription_key = _required(values, "APIM_SUBSCRIPTION_KEY")
    api_version = values.get(
        "AZURE_OPENAI_API_VERSION",
        DEFAULT_API_VERSION,
    ).strip()

    if not api_version:
        raise ValueError("AZURE_OPENAI_API_VERSION must not be empty.")
    if not token_scope.endswith("/.default"):
        raise ValueError("APIM_TOKEN_SCOPE must end with '/.default'.")
    if environment_name not in VALID_ENVIRONMENT_NAMES:
        raise ValueError(
            "ENVIRONMENT_NAME must be one of: local, dev, tst, prd."
        )

    _validate_apim_endpoint(endpoint)

    return ApimModelConfig(
        environment_name=environment_name,
        endpoint=endpoint.rstrip("/"),
        deployment_name=deployment_name,
        api_version=api_version,
        token_scope=token_scope,
        subscription_key=subscription_key,
    )


def create_model_credential(
    env: Mapping[str, str] | None = None,
) -> TokenCredential:
    values = environ if env is None else env
    auth_mode = values.get("AZURE_AUTH_MODE", "default").strip().lower()

    if auth_mode == "default":
        return DefaultAzureCredential()

    if auth_mode == "device-code":
        tenant_id = _required(values, "AZURE_TENANT_ID")
        client_id = _required(values, "AZURE_CLIENT_ID")
        return DeviceCodeCredential(
            tenant_id=tenant_id,
            client_id=client_id,
        )

    raise ValueError(
        "AZURE_AUTH_MODE must be either 'default' or 'device-code'."
    )


def create_trade_surveillance_agent(
    *,
    env: Mapping[str, str] | None = None,
    credential: TokenCredential | None = None,
    ad_token_provider: Callable[[], str] | None = None,
) -> ChatAgent:
    values = environ if env is None else env
    config = load_apim_model_config(values)

    if ad_token_provider is None:
        credential = credential or create_model_credential(values)
        ad_token_provider = get_bearer_token_provider(
            credential,
            config.token_scope,
        )

    client = AzureOpenAIChatClient(
        endpoint=config.endpoint,
        deployment_name=config.deployment_name,
        api_version=config.api_version,
        ad_token_provider=ad_token_provider,
        default_headers=config.default_headers,
    )

    return ChatAgent(
        chat_client=client,
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        instructions=AGENT_INSTRUCTIONS,
        metadata={"environment_name": config.environment_name},
        tools=[],
        tool_choice="none",
    )


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _validate_apim_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("APIM_OPENAI_ENDPOINT must be an absolute HTTPS URL.")
    if parsed.username or parsed.password:
        raise ValueError("APIM_OPENAI_ENDPOINT must not contain credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError(
            "APIM_OPENAI_ENDPOINT must not contain a query string or fragment."
        )
    if parsed.path not in {"", "/"}:
        raise ValueError(
            "APIM_OPENAI_ENDPOINT must be the gateway origin without the "
            "/openai path."
        )

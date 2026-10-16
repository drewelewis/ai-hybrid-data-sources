from unittest.mock import patch

import pytest

import trade_surveillance_agent


VALID_ENV = {
    "ENVIRONMENT_NAME": "local",
    "APIM_OPENAI_ENDPOINT": "https://gateway.example.test/",
    "APIM_TOKEN_SCOPE": "api://model-api/.default",
    "APIM_SUBSCRIPTION_KEY": "synthetic-subscription-key",
    "MODEL_DEPLOYMENT_NAME": "gpt-test",
}


def test_loads_apim_configuration_without_exposing_key():
    config = trade_surveillance_agent.load_apim_model_config(VALID_ENV)

    assert config.environment_name == "local"
    assert config.endpoint == "https://gateway.example.test"
    assert config.deployment_name == "gpt-test"
    assert config.api_version == "2024-02-01"
    assert config.token_scope == "api://model-api/.default"
    assert config.default_headers == {
        "Ocp-Apim-Subscription-Key": "synthetic-subscription-key"
    }
    assert "synthetic-subscription-key" not in repr(config)


@pytest.mark.parametrize(
    "name",
    [
        "ENVIRONMENT_NAME",
        "APIM_OPENAI_ENDPOINT",
        "APIM_TOKEN_SCOPE",
        "APIM_SUBSCRIPTION_KEY",
        "MODEL_DEPLOYMENT_NAME",
    ],
)
def test_reports_missing_apim_configuration(name):
    environment = {key: value for key, value in VALID_ENV.items() if key != name}

    with pytest.raises(ValueError, match=name):
        trade_surveillance_agent.load_apim_model_config(environment)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://gateway.example.test",
        "https://gateway.example.test/openai",
        "https://gateway.example.test?api-version=test",
        "https://user:password@gateway.example.test",
    ],
)
def test_rejects_unsafe_apim_endpoint(endpoint):
    environment = {**VALID_ENV, "APIM_OPENAI_ENDPOINT": endpoint}

    with pytest.raises(ValueError, match="APIM_OPENAI_ENDPOINT"):
        trade_surveillance_agent.load_apim_model_config(environment)


def test_requires_default_token_scope_suffix():
    environment = {**VALID_ENV, "APIM_TOKEN_SCOPE": "api://model-api"}

    with pytest.raises(ValueError, match=r"/\.default"):
        trade_surveillance_agent.load_apim_model_config(environment)


@pytest.mark.parametrize("environment_name", ["development", "test", "prod"])
def test_rejects_unknown_environment_name(environment_name):
    environment = {**VALID_ENV, "ENVIRONMENT_NAME": environment_name}

    with pytest.raises(ValueError, match="local, dev, tst, prd"):
        trade_surveillance_agent.load_apim_model_config(environment)


def test_defaults_to_default_azure_credential():
    with patch.object(
        trade_surveillance_agent,
        "DefaultAzureCredential",
    ) as default_credential:
        credential = trade_surveillance_agent.create_model_credential({})

    assert credential is default_credential.return_value


def test_supports_device_code_credential():
    environment = {
        "AZURE_AUTH_MODE": "device-code",
        "AZURE_TENANT_ID": "tenant-id",
        "AZURE_CLIENT_ID": "client-id",
    }

    with patch.object(
        trade_surveillance_agent,
        "DeviceCodeCredential",
    ) as device_code_credential:
        credential = trade_surveillance_agent.create_model_credential(environment)

    assert credential is device_code_credential.return_value
    device_code_credential.assert_called_once_with(
        tenant_id="tenant-id",
        client_id="client-id",
    )


def test_rejects_unknown_authentication_mode():
    with pytest.raises(ValueError, match="AZURE_AUTH_MODE"):
        trade_surveillance_agent.create_model_credential(
            {"AZURE_AUTH_MODE": "password"}
        )


def test_constructs_tool_free_agent_with_apim_client():
    credential = object()

    with (
        patch.object(
            trade_surveillance_agent,
            "get_bearer_token_provider",
        ) as provider_factory,
        patch.object(
            trade_surveillance_agent,
            "AzureOpenAIChatClient",
        ) as client_class,
        patch.object(trade_surveillance_agent, "ChatAgent") as agent_class,
    ):
        agent = trade_surveillance_agent.create_trade_surveillance_agent(
            env=VALID_ENV,
            credential=credential,
        )

    provider_factory.assert_called_once_with(
        credential,
        "api://model-api/.default",
    )
    client_class.assert_called_once_with(
        endpoint="https://gateway.example.test",
        deployment_name="gpt-test",
        api_version="2024-02-01",
        ad_token_provider=provider_factory.return_value,
        default_headers={
            "Ocp-Apim-Subscription-Key": "synthetic-subscription-key"
        },
    )
    agent_class.assert_called_once_with(
        chat_client=client_class.return_value,
        name=trade_surveillance_agent.AGENT_NAME,
        description=trade_surveillance_agent.AGENT_DESCRIPTION,
        instructions=trade_surveillance_agent.AGENT_INSTRUCTIONS,
        metadata={"environment_name": "local"},
        tools=[],
        tool_choice="none",
    )
    assert agent is agent_class.return_value


def test_prompt_enforces_investigation_and_human_review_boundaries():
    instructions = trade_surveillance_agent.AGENT_INSTRUCTIONS

    assert "do not have tools" in instructions
    assert "Never claim that you searched or retrieved live" in instructions
    assert "not findings of misconduct" in instructions
    assert "authorized human compliance review" in instructions

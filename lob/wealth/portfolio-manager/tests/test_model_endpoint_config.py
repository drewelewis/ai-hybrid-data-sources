import pytest

from agents.model_endpoint_config import (
    DEFAULT_COGNITIVE_SERVICES_SCOPE,
    load_model_endpoint_config,
)


def test_loads_governed_apim_configuration():
    config = load_model_endpoint_config(
        {
            "MODEL_ENDPOINT_MODE": "apim",
            "MODEL_DEPLOYMENT_NAME": "gpt-5.4-mini",
            "APIM_OPENAI_ENDPOINT": "https://gateway.example.test/",
            "APIM_TOKEN_SCOPE": "api://model-api/.default",
            "APIM_SUBSCRIPTION_KEY": "secret-key",
        }
    )

    assert config.mode == "apim"
    assert config.endpoint == "https://gateway.example.test"
    assert config.deployment_name == "gpt-5.4-mini"
    assert config.api_version == "2024-02-01"
    assert config.token_scope == "api://model-api/.default"
    assert config.default_headers == {
        "Ocp-Apim-Subscription-Key": "secret-key"
    }
    assert "secret-key" not in repr(config)


def test_loads_direct_foundry_configuration():
    config = load_model_endpoint_config(
        {
            "MODEL_ENDPOINT_MODE": "direct",
            "MODEL_DEPLOYMENT_NAME": "gpt-5.4-mini",
            "AZURE_OPENAI_API_ENDPOINT": "https://foundry.example.test/",
        }
    )

    assert config.mode == "direct"
    assert config.endpoint == "https://foundry.example.test"
    assert config.token_scope == DEFAULT_COGNITIVE_SERVICES_SCOPE
    assert config.default_headers is None


@pytest.mark.parametrize(
    ("missing_name", "environment"),
    [
        (
            "APIM_OPENAI_ENDPOINT",
            {
                "MODEL_ENDPOINT_MODE": "apim",
                "MODEL_DEPLOYMENT_NAME": "gpt-5.4-mini",
                "APIM_TOKEN_SCOPE": "api://model-api/.default",
                "APIM_SUBSCRIPTION_KEY": "secret-key",
            },
        ),
        (
            "APIM_TOKEN_SCOPE",
            {
                "MODEL_ENDPOINT_MODE": "apim",
                "MODEL_DEPLOYMENT_NAME": "gpt-5.4-mini",
                "APIM_OPENAI_ENDPOINT": "https://gateway.example.test",
                "APIM_SUBSCRIPTION_KEY": "secret-key",
            },
        ),
        (
            "APIM_SUBSCRIPTION_KEY",
            {
                "MODEL_ENDPOINT_MODE": "apim",
                "MODEL_DEPLOYMENT_NAME": "gpt-5.4-mini",
                "APIM_OPENAI_ENDPOINT": "https://gateway.example.test",
                "APIM_TOKEN_SCOPE": "api://model-api/.default",
            },
        ),
    ],
)
def test_apim_mode_reports_missing_configuration(missing_name, environment):
    with pytest.raises(ValueError, match=missing_name):
        load_model_endpoint_config(environment)


def test_rejects_apim_endpoint_with_openai_path():
    with pytest.raises(ValueError, match="without the /openai path"):
        load_model_endpoint_config(
            {
                "MODEL_ENDPOINT_MODE": "apim",
                "MODEL_DEPLOYMENT_NAME": "gpt-5.4-mini",
                "APIM_OPENAI_ENDPOINT": "https://gateway.example.test/openai",
                "APIM_TOKEN_SCOPE": "api://model-api/.default",
                "APIM_SUBSCRIPTION_KEY": "secret-key",
            }
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["direct", "apim"])
async def test_verification_headers_are_request_local_and_preserve_subscription_key(monkeypatch, mode):
    from unittest.mock import Mock
    from uuid import UUID
    import agents.trading_platform_agent as factory

    config = load_model_endpoint_config({
        "MODEL_ENDPOINT_MODE": mode, "MODEL_DEPLOYMENT_NAME": "test-model",
        "AZURE_OPENAI_API_ENDPOINT": "https://foundry.example.test",
        "APIM_OPENAI_ENDPOINT": "https://gateway.example.test",
        "APIM_TOKEN_SCOPE": "api://model-api/.default",
        "APIM_SUBSCRIPTION_KEY": "synthetic-test-key",
    })
    client = Mock()
    monkeypatch.setattr(factory, "load_model_endpoint_config", lambda: config)
    monkeypatch.setattr(factory, "FunctionCallingClient", client)
    monkeypatch.setattr(factory, "ChatAgent", Mock())
    monkeypatch.setattr(factory, "ai_function", lambda function: function)
    first = UUID("dd0136ab-fdb3-5a1c-80d2-5fd6057ff991")
    second = UUID("dd0136ab-fdb3-5a1c-80d2-5fd6057ff992")
    for identifier in (first, second, None):
        await factory.create_trading_platform_agent(
            ad_token_provider=lambda: "synthetic-token", verification_id=identifier,
        )
    headers = [call.kwargs["default_headers"] for call in client.call_args_list]
    assert headers[0]["x-a365-verification-id"] == str(first)
    assert headers[1]["x-a365-verification-id"] == str(second)
    assert headers[0] is not headers[1]
    if mode == "apim":
        assert all(value["Ocp-Apim-Subscription-Key"] == "synthetic-test-key" for value in headers)
        assert "x-a365-verification-id" not in headers[2]
    else:
        assert headers[2] is None
    assert config.default_headers == (
        {"Ocp-Apim-Subscription-Key": "synthetic-test-key"} if mode == "apim" else None
    )

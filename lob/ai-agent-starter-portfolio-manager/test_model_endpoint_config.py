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

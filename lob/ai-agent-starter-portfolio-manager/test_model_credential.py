from unittest.mock import patch

import pytest

from agents.model_credential import create_model_credential


def test_create_model_credential_defaults_to_default_credential():
    with patch(
        "agents.model_credential.DefaultAzureCredential"
    ) as default_credential:
        credential = create_model_credential({})

    assert credential is default_credential.return_value


def test_create_model_credential_supports_device_code():
    environment = {
        "AZURE_AUTH_MODE": "device-code",
        "AZURE_TENANT_ID": "tenant-id",
        "AZURE_CLIENT_ID": "client-id",
    }

    with patch(
        "agents.model_credential.DeviceCodeCredential"
    ) as device_code_credential:
        credential = create_model_credential(environment)

    assert credential is device_code_credential.return_value
    device_code_credential.assert_called_once_with(
        tenant_id="tenant-id",
        client_id="client-id",
    )


@pytest.mark.parametrize(
    "environment",
    [
        {"AZURE_AUTH_MODE": "device-code", "AZURE_CLIENT_ID": "client-id"},
        {"AZURE_AUTH_MODE": "device-code", "AZURE_TENANT_ID": "tenant-id"},
    ],
)
def test_create_model_credential_requires_device_code_ids(environment):
    with pytest.raises(
        ValueError,
        match="AZURE_TENANT_ID and AZURE_CLIENT_ID",
    ):
        create_model_credential(environment)


def test_create_model_credential_rejects_unknown_mode():
    with pytest.raises(ValueError, match="AZURE_AUTH_MODE"):
        create_model_credential({"AZURE_AUTH_MODE": "password"})

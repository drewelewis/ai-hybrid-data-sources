from os import environ
from typing import Mapping

from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential, DeviceCodeCredential


def create_model_credential(
    env: Mapping[str, str] | None = None,
) -> TokenCredential:
    values = environ if env is None else env
    auth_mode = values.get("AZURE_AUTH_MODE", "default").strip().lower()

    if auth_mode == "default":
        return DefaultAzureCredential()

    if auth_mode == "device-code":
        tenant_id = values.get("AZURE_TENANT_ID", "").strip()
        client_id = values.get("AZURE_CLIENT_ID", "").strip()
        if not tenant_id or not client_id:
            raise ValueError(
                "AZURE_TENANT_ID and AZURE_CLIENT_ID are required when "
                "AZURE_AUTH_MODE=device-code."
            )
        return DeviceCodeCredential(
            tenant_id=tenant_id,
            client_id=client_id,
        )

    raise ValueError(
        "AZURE_AUTH_MODE must be either 'default' or 'device-code'."
    )

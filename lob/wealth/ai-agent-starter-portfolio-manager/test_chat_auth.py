from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import chat


@pytest.fixture(autouse=True)
def reset_device_code_credential():
    chat._device_code_credential = None
    yield
    chat.close_model_access_credential()


@pytest.mark.asyncio
async def test_device_code_credential_is_reused_for_token_refresh():
    credential = MagicMock()
    credential.get_token.side_effect = [
        SimpleNamespace(token="first-token"),
        SimpleNamespace(token="refreshed-token"),
    ]

    with (
        patch.object(chat, "AUTH_MODE", "device-code"),
        patch.dict(
            chat.os.environ,
            {
                "AZURE_TENANT_ID": "tenant-id",
                "AZURE_CLIENT_ID": "client-id",
                "APIM_TOKEN_SCOPE": "api://model/.default",
            },
        ),
        patch.object(
            chat,
            "DeviceCodeCredential",
            return_value=credential,
        ) as credential_type,
    ):
        first = await chat.get_model_access_token()
        refreshed = await chat.get_model_access_token()

    assert first == "first-token"
    assert refreshed == "refreshed-token"
    credential_type.assert_called_once_with(
        tenant_id="tenant-id",
        client_id="client-id",
        prompt_callback=chat.show_device_challenge,
    )
    assert credential.get_token.call_count == 2
    credential.close.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_model_access_token_updates_authorization_header():
    http = SimpleNamespace(headers={})

    with patch.object(
        chat,
        "get_model_access_token",
        AsyncMock(return_value="refreshed-token"),
    ):
        await chat.refresh_model_access_token(http)

    assert http.headers["Authorization"] == "Bearer refreshed-token"


def test_close_model_access_credential_releases_cached_credential():
    credential = MagicMock()
    chat._device_code_credential = credential

    chat.close_model_access_credential()

    credential.close.assert_called_once_with()
    assert chat._device_code_credential is None

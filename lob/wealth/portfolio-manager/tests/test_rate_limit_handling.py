from api.model_errors import model_error_to_http_exception
from chat import format_api_error, show_device_challenge
import pytest


@pytest.mark.parametrize("wrapped", [False, True])
def test_structured_model_filter_is_exposed_without_prompt_content(wrapped):
    class ModelFilterError(Exception):
        status_code = 400
        body = {
            "error": {
                "code": "content_filter",
                "message": "Sensitive prompt content must not be returned",
                "innererror": {
                    "code": "ResponsibleAIPolicyViolation",
                    "content_filter_result": {
                        "jailbreak": {"detected": True, "filtered": True},
                        "hate": {"filtered": False, "severity": "safe"},
                    },
                },
            }
        }

    error = ModelFilterError("Sensitive prompt content")
    if wrapped:
        wrapper = RuntimeError("Agent execution failed")
        wrapper.__cause__ = error
        error = wrapper
    http_error = model_error_to_http_exception(error)

    assert http_error.status_code == 400
    assert http_error.detail == {
        "code": "model_content_filter_blocked",
        "source": "upstream_model",
        "filtered_categories": ["jailbreak"],
    }
    assert "Sensitive prompt" not in str(http_error.detail)
    client_error = format_api_error("POST", "/chat", 400, http_error.detail, None)
    assert client_error.detail == http_error.detail


def test_filter_words_in_generic_errors_are_not_proof_of_enforcement():
    http_error = model_error_to_http_exception(
        RuntimeError("Model mentioned content_filter but no structured block exists")
    )
    assert http_error.status_code == 500


def test_real_openai_sdk_filter_error_retains_sanitized_enforcement_evidence():
    import httpx
    from openai import BadRequestError

    error = BadRequestError(
        "Prompt blocked",
        response=httpx.Response(
            400, request=httpx.Request("POST", "https://model.example.invalid"),
        ),
        body={
            "code": "content_filter",
            "innererror": {
                "content_filter_result": {"jailbreak": {"filtered": True}},
            },
        },
    )

    http_error = model_error_to_http_exception(error)
    assert http_error.status_code == 400
    assert http_error.detail["filtered_categories"] == ["jailbreak"]


def test_model_rate_limit_maps_to_http_429_with_retry_after():
    error = RuntimeError(
        "Error code: 429 - {'statusCode': 429, "
        "'message': 'Token limit is exceeded. Try again in 288 seconds.'}"
    )

    http_error = model_error_to_http_exception(error)

    assert http_error.status_code == 429
    assert http_error.detail == "Token limit is exceeded. Try again in 288 seconds."
    assert http_error.headers == {"Retry-After": "288"}


def test_non_rate_limit_model_error_remains_http_500():
    error = RuntimeError("Model connection failed")

    http_error = model_error_to_http_exception(error)

    assert http_error.status_code == 500
    assert http_error.detail == "Model connection failed"
    assert http_error.headers is None


def test_chat_client_formats_rate_limit_without_retrying():
    error = format_api_error(
        "POST",
        "/chat",
        429,
        "Token limit is exceeded.",
        "288",
    )

    assert error.status_code == 429
    assert error.retry_after == "288"
    assert str(error) == (
        "Token limit reached. Retry in approximately 288 seconds. "
        "No automatic retry was attempted."
    )


def test_device_challenge_prints_manual_login_instructions(capsys):
    show_device_challenge(
        "https://microsoft.com/devicelogin",
        "ABCD-EFGH",
        None,
    )

    output = capsys.readouterr().out
    assert "Microsoft sign-in required." in output
    assert "Open: https://microsoft.com/devicelogin" in output
    assert "Code: ABCD-EFGH" in output

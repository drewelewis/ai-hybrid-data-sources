from api.model_errors import model_error_to_http_exception
from chat import format_api_error


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

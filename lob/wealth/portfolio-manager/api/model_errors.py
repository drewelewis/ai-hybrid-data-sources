import re

from fastapi import HTTPException


_RATE_LIMIT_PATTERN = re.compile(
    r"(?:error|status)\s*code['\"]?\s*[:=]\s*429|statusCode['\"]?\s*:\s*429",
    re.IGNORECASE,
)
_RETRY_PATTERN = re.compile(r"try again in\s+(\d+)\s+seconds?", re.IGNORECASE)
_MESSAGE_PATTERN = re.compile(r"['\"]message['\"]\s*:\s*['\"]([^'\"]+)['\"]")


def _content_filter_details(body: object) -> dict[str, object] | None:
    if not isinstance(body, dict):
        return None
    error = body.get("error", body)
    if not isinstance(error, dict):
        return None
    inner = error.get("innererror", {})
    if not isinstance(inner, dict):
        inner = {}
    if error.get("code") not in {
        "content_filter", "content_policy_violation", "ResponsibleAIPolicyViolation",
    } and inner.get("code") != "ResponsibleAIPolicyViolation":
        return None
    results = inner.get("content_filter_result", {})
    categories = (
        sorted(
            name for name, result in results.items()
            if name in {"hate", "sexual", "violence", "self_harm", "jailbreak"}
            and isinstance(result, dict)
            and result.get("filtered") is True
        )
        if isinstance(results, dict) else []
    )
    return {
        "code": "model_content_filter_blocked",
        "source": "upstream_model",
        "filtered_categories": categories,
    }


def model_error_to_http_exception(error: Exception) -> HTTPException:
    messages: list[str] = []
    status_codes: set[int] = set()
    current: BaseException | None = error
    seen: set[int] = set()
    filter_details: dict[str, object] | None = None

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        messages.append(str(current))
        status_code = getattr(current, "status_code", None)
        if isinstance(status_code, int):
            status_codes.add(status_code)
        if status_code == 400:
            details = _content_filter_details(getattr(current, "body", None))
            if details is not None:
                filter_details = details
        current = current.__cause__ or current.__context__

    combined_message = " ".join(messages)
    if 429 in status_codes or _RATE_LIMIT_PATTERN.search(combined_message):
        retry_match = _RETRY_PATTERN.search(combined_message)
        message_match = _MESSAGE_PATTERN.search(combined_message)
        detail = (
            message_match.group(1)
            if message_match
            else "The model token limit was exceeded."
        )
        headers = {"Retry-After": retry_match.group(1)} if retry_match else None
        return HTTPException(status_code=429, detail=detail, headers=headers)

    if filter_details is not None and not status_codes.intersection({401, 403}):
        return HTTPException(status_code=400, detail=filter_details)

    return HTTPException(status_code=500, detail=str(error))

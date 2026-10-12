import re

from fastapi import HTTPException


_RATE_LIMIT_PATTERN = re.compile(
    r"(?:error|status)\s*code['\"]?\s*[:=]\s*429|statusCode['\"]?\s*:\s*429",
    re.IGNORECASE,
)
_RETRY_PATTERN = re.compile(r"try again in\s+(\d+)\s+seconds?", re.IGNORECASE)
_MESSAGE_PATTERN = re.compile(r"['\"]message['\"]\s*:\s*['\"]([^'\"]+)['\"]")


def model_error_to_http_exception(error: Exception) -> HTTPException:
    messages: list[str] = []
    status_codes: set[int] = set()
    current: BaseException | None = error
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        messages.append(str(current))
        status_code = getattr(current, "status_code", None)
        if isinstance(status_code, int):
            status_codes.add(status_code)
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

    return HTTPException(status_code=500, detail=str(error))

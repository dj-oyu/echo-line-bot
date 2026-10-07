"""Shared Groq evaluation transport with bounded requests and sanitized errors."""

SDK_VERSION = "3.6.0"
SAFE_CODES = frozenset({
    "invalid_request_error", "permission_error", "permission_denied", "forbidden",
    "access_denied", "model_permission_blocked", "model_not_allowed",
    "authentication_error", "invalid_api_key", "rate_limit_exceeded",
    "insufficient_quota", "organization_restricted", "model_not_found",
})


def safe_error(exc: Exception) -> dict:
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    return {
        "status": status if type(status) is int and 100 <= status <= 599 else None,
        "error_format": "json_object" if isinstance(body, dict) else "not_json_object",
        "type": error.get("type") if isinstance(error.get("type"), str) and error["type"] in SAFE_CODES else "not_retained",
        "code": error.get("code") if isinstance(error.get("code"), str) and error["code"] in SAFE_CODES else "not_retained",
    }


def sdk_call(request: dict, key: str, record: dict, transport=None) -> dict:
    import openai
    if openai.__version__ != SDK_VERSION:
        raise ValueError("Locked SDK mismatch")

    def count_request(_request):
        if record["network_requests_started"] >= 1:
            raise RuntimeError("Additional network request blocked")
        record["network_requests_started"] += 1

    kwargs = {"follow_redirects": False, "event_hooks": {"request": [count_request]}}
    if transport is not None:  # Used only by offline tests.
        kwargs["transport"] = transport
    with openai.OpenAI(
        api_key=key, base_url="https://api.groq.com/openai/v1",
        max_retries=0, timeout=30,
        http_client=openai.DefaultHttpxClient(**kwargs),
    ) as client:
        return client.chat.completions.create(**request).model_dump(mode="json")


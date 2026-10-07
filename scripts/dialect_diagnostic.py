"""One explicitly approved production-SDK diagnostic. No automatic retries."""
import json
import os
from pathlib import Path
import time

import dialect_ab as ab

SDK_VERSION = "3.6.0"
BEFORE = "e537ac21a2205d810e5fd29860c1a885e28ff1a2"
BRANCH = "refs/heads/feature/dialect-prompt-pilot-20261007"
MARKER = "test: run one approved SDK diagnostic 20261007-pr73-01"
SAFE_CODES = frozenset({
    "invalid_request_error", "permission_error", "permission_denied", "forbidden",
    "access_denied", "model_permission_blocked", "model_not_allowed",
    "authentication_error", "invalid_api_key", "rate_limit_exceeded",
    "insufficient_quota", "organization_restricted", "model_not_found",
})


def allowed() -> bool:
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_EVENT_NAME") == "push"
        and os.environ.get("GITHUB_REPOSITORY") == "dj-oyu/echo-line-bot"
        and os.environ.get("GITHUB_REF") == BRANCH
        and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
    ):
        return False
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    head = event.get("head_commit") or {}
    return (
        event.get("ref") == BRANCH and event.get("before") == BEFORE
        and all(event.get(k) is False for k in ("created", "deleted", "forced"))
        and head.get("message") == MARKER
        and head.get("id") == os.environ.get("GITHUB_SHA")
    )


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


def diagnose(output: Path, key: str, request_fn=sdk_call) -> int:
    plan = ab.make_plan(Path(__file__).resolve().parents[1] / "lambda" / "ai_processor.py")
    request = plan["schedule"][0]["request"]
    record = {
        "diagnostic_only": True, "maximum_requests": 1, "network_requests_started": 0,
        "sdk_version": SDK_VERSION, "max_retries": 0, "follow_redirects": False,
        "source_commit": ab.SOURCE_COMMIT, "settings": ab.SETTINGS,
        "input": ab.INPUTS[0], "variant": "A", "prompt_sha256": ab.digest(plan["prompts"]["A"]),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "commit": os.environ.get("GITHUB_SHA"),
    }
    started = time.monotonic()
    try:
        record["response"] = ab.sanitize_response(request_fn(request, key, record))
        record["status"] = "success"
    except Exception as exc:
        record["error"] = safe_error(exc)
        record["status"] = "failed_no_retry"
    record["latency_seconds"] = round(time.monotonic() - started, 4)
    output.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, ensure_ascii=False, indent=2).replace(key, "[REDACTED]")
    (output / "diagnostic.json").write_text(text + "\n", encoding="utf-8")
    print(f"Diagnostic: {record['status']}; requests started: {record['network_requests_started']}/1")
    return 0 if record["status"] == "success" else 1


def main() -> int:
    if not allowed():
        raise ValueError("Unapproved diagnostic event")
    key = os.environ.pop("GROQ_API_KEY", "")
    if not key:
        raise ValueError("Runtime credential missing")
    return diagnose(Path("dialect-diagnostic-results"), key)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("Diagnostic blocked before completion; details withheld")
        raise SystemExit(1) from None

"""Run the separately approved 28-request conversation prompt comparison once."""
import json
import os
from pathlib import Path
import random
import time

import conversation_prompt_eval as design
import dialect_ab as baseline
from dialect_diagnostic import safe_error, sdk_call

BEFORE = "ecc02d1ca0f9a72dbe1b8ebb09c4b812110e894b"
BRANCH = "refs/heads/feature/dialect-prompt-pilot-20261007"
MARKER = "test: run approved 28-call conversation pilot 20261007-pr73-01"
MAX_CALLS = 28
BUDGET_USD = 0.10
# Reserve the published model's entire input context plus the output ceiling.
# This is deliberately much larger than these synthetic prompts.
MAX_INPUT_TOKENS = 131072
RESERVE_USD = MAX_INPUT_TOKENS * baseline.INPUT_USD_PER_TOKEN + 1000 * baseline.OUTPUT_USD_PER_TOKEN


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


def save(output: Path, plan: dict, records: list, status: str, key: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    shuffled = list(records)
    random.Random(837291).shuffle(shuffled)
    blind, mapping = [], {}
    for number, row in enumerate(shuffled, 1):
        label = f"sample-{number:03}"
        mapping[label] = {k: row[k] for k in ("index", "case_id", "trial", "variant")}
        item = plan["requests"][row["index"]]
        response = row.get("response", {})
        blind.append({
            "sample_id": label, "case_id": row["case_id"], "intent": item["intent"],
            "checks": item["checks"], "messages": item["request"]["messages"][1:],
            "result": None if row.get("error") else {
                k: response.get(k) for k in ("content", "tool_calls", "finish_reason")},
            "error": row.get("error"),
        })
    manifest = {**plan, "status": "approved_bounded_run", "execution_requires_separate_approval": False,
                "budget_usd": BUDGET_USD, "per_next_call_reserve_usd": RESERVE_USD,
                "execution_commit": os.environ.get("GITHUB_SHA"), "run_id": os.environ.get("GITHUB_RUN_ID")}
    files = {
        "manifest.json": manifest, "raw-responses.json": records,
        "blind-review.json": blind, "blind-key.json": mapping,
        "summary.json": {
            "status": status, "attempted_calls": len(records),
            "network_requests_started": sum(r["network_requests_started"] for r in records),
            "successful_calls": sum("response" in r and "error" not in r for r in records),
            "calls_with_unknown_cost": sum("response" not in r for r in records),
            "estimated_inference_usd": sum(r.get("response", {}).get("cost_estimate_usd", 0) for r in records),
        },
    }
    for name, content in files.items():
        text = json.dumps(content, ensure_ascii=False, indent=2).replace(key, "[REDACTED]")
        (output / name).write_text(text + "\n", encoding="utf-8")


def run(output: Path, key: str, request_fn=sdk_call) -> int:
    plan = design.prepare_plan()
    if len(plan["requests"]) != MAX_CALLS:
        raise ValueError("Approved request count changed")
    records = []
    status = "running"
    started = time.monotonic()
    save(output, plan, records, status, key)
    for index, item in enumerate(plan["requests"]):
        spent = sum(r.get("response", {}).get("cost_estimate_usd", 0) for r in records)
        if spent + RESERVE_USD > BUDGET_USD or time.monotonic() - started > 720:
            status = "stopped_at_budget_or_time_guard"
            break
        row = {k: item[k] for k in ("case_id", "trial", "variant")}
        row.update(index=index, network_requests_started=0)
        records.append(row)
        before = time.monotonic()
        try:
            response = baseline.sanitize_response(request_fn(item["request"], key, row))
            row["response"] = response
            if response["model"] != baseline.SETTINGS["model"]:
                raise ValueError("Unexpected model")
            if response["usage"]["prompt_tokens"] > MAX_INPUT_TOKENS or response["usage"]["completion_tokens"] > 1000:
                raise ValueError("Unexpected usage")
            if row["network_requests_started"] != 1:
                raise ValueError("Unexpected request count")
        except Exception as exc:
            row["error"] = safe_error(exc)
            status = "stopped_after_error_no_retry"
        row["latency_seconds"] = round(time.monotonic() - before, 4)
        save(output, plan, records, status, key)
        if status != "running":
            break
    if status == "running":
        status = "complete"
    save(output, plan, records, status, key)
    print(f"Conversation pilot: {status}; attempts {len(records)}/{MAX_CALLS}")
    return 0 if status == "complete" else 1


def main() -> int:
    if not allowed():
        raise ValueError("Unapproved workflow event")
    key = os.environ.pop("GROQ_API_KEY", "")
    if not key:
        raise ValueError("Runtime credential missing")
    return run(Path("conversation-eval-results"), key)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("Conversation pilot blocked; details withheld")
        raise SystemExit(1) from None

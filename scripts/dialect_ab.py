"""Bounded first-stage prompt pilot. Never import or invoke the production handlers."""

import argparse
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path
import random
import re
import time

SOURCE_COMMIT = "3ef6fdc1794cd7952b3ce25c41af8ed4e5ed5185"
SOURCE_SHA256 = "eaed80e0c2ecd0841c267d85d36948b2a7dbacad92dff6adb9afd9ca1fe68ca1"
INPUTS = ("やっほい", "おすすめの飲食店ある?")
SETTINGS = {
    "model": "openai/gpt-oss-20b",
    "reasoning_effort": "medium",
    "temperature": 0.7,
    "max_tokens": 1000,
    "tool_choice": "auto",
}
DATE_INFO = {"date": "2026年10月07日", "weekday": "水", "time": "20時00分", "season": "秋"}
GREETING = "こんばんは！🌙 今日も一日お疲れさまでした〜"
MAX_CALLS = 40
MAX_REQUEST_BYTES = 8192
MAX_INPUT_TOKENS = 131072
BUDGET_USD = 0.10
INPUT_USD_PER_TOKEN = 0.075 / 1_000_000
OUTPUT_USD_PER_TOKEN = 0.30 / 1_000_000
CULTURE_CUE = "- 時々関西の食べ物や文化について話したがる"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_source(source_path: Path) -> tuple[str, list]:
    """Extract data with AST inspection, without executing any application code."""
    source = source_path.read_text(encoding="utf-8")
    if digest(source) != SOURCE_SHA256:
        raise ValueError("Production source differs from approved baseline")
    tree = ast.parse(source)
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    prompt_node = next(
        n.value
        for n in functions["prepare_messages_for_api"].body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "system_prompt" for t in n.targets)
    )
    if not isinstance(prompt_node, ast.JoinedStr):
        raise ValueError("Unexpected prompt structure")
    parts = []
    for part in prompt_node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            parts.append(part.value)
        elif isinstance(part, ast.FormattedValue):
            if part.conversion != -1 or part.format_spec is not None:
                raise ValueError("Unexpected prompt formatting")
            value = part.value
            if isinstance(value, ast.Name) and value.id == "greeting":
                parts.append(GREETING)
            elif (
                isinstance(value, ast.Subscript)
                and isinstance(value.value, ast.Name)
                and value.value.id == "date_info"
                and isinstance(value.slice, ast.Constant)
                and value.slice.value in DATE_INFO
            ):
                parts.append(DATE_INFO[value.slice.value])
            else:
                raise ValueError("Unexpected prompt interpolation")
        else:
            raise ValueError("Unexpected prompt component")
    tools_node = next(
        n.value
        for n in ast.walk(functions["get_ai_response"])
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "tools" for t in n.targets)
    )
    return "".join(parts), ast.literal_eval(tools_node)


def without_dialect(prompt: str) -> str:
    replacements = (
        ("関西弁で話すフレンドリーなAIアシスタント", "フレンドリーなAIアシスタント"),
        ("- 関西弁（大阪弁）で話す\n", ""),
        ("- 語尾に「やん」「やで」「やな」「やねん」を使う\n", ""),
        ("- 「そうやね」「ほんまに」「めっちゃ」「なんでやねん」などの関西弁\n", ""),
        ("- 「～してはる」「～やねん」などの丁寧語も使う\n", ""),
        ("- 親しみやすく、でも丁寧な関西弁", "- 親しみやすく、でも丁寧"),
        ("今日はどうやった？", "今日はどうだった？"),
        ("日本語で話しかけられたら関西弁で返答", "日本語で話しかけられたら日本語で返答"),
        ("ただし、関西弁の温かみと親しみやすさ", "ただし、温かみと親しみやすさ"),
    )
    for old, new in replacements:
        if prompt.count(old) != 1:
            raise ValueError("Expected dialect instruction not found exactly once")
        prompt = prompt.replace(old, new)
    if prompt.count(CULTURE_CUE) != 1 or "関西弁" in prompt or "大阪弁" in prompt:
        raise ValueError("Dialect-only transformation invariant failed")
    return prompt


def make_plan(source_path: Path) -> dict:
    original, tools = extract_source(source_path)
    prompts = {"A": original, "B": without_dialect(original)}
    schedule = []
    for trial in range(10):
        for case, user_text in enumerate(INPUTS):
            for variant in (("A", "B") if (trial + case) % 2 == 0 else ("B", "A")):
                request = {
                    **SETTINGS,
                    "messages": [
                        {"role": "system", "content": prompts[variant]},
                        {"role": "user", "content": user_text},
                    ],
                    "tools": tools,
                }
                size = len(json.dumps(request, ensure_ascii=False).encode("utf-8"))
                if size > MAX_REQUEST_BYTES:
                    raise ValueError("Request exceeds reviewed size bound")
                schedule.append({
                    "index": len(schedule), "case": case, "trial": trial,
                    "variant": variant, "request": request, "request_bytes": size,
                })
    if len(schedule) != MAX_CALLS:
        raise ValueError("Unexpected request count")
    return {"prompts": prompts, "tools": tools, "schedule": schedule}


def call_groq(request: dict, key: str) -> dict:
    """Use the verified production SDK with one-request/no-retry safeguards."""
    from eval_groq_transport import sdk_call
    return sdk_call(request, key, {"network_requests_started": 0})


def visible_content(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Unexpected visible content type")
    # Do not retain tagged reasoning if a provider returns it in content.
    return re.sub(r"<think>.*?(?:</think>|$)", "", value, flags=re.DOTALL).strip()


def sanitize_response(response: dict) -> dict:
    choice = response["choices"][0]
    message = choice["message"]
    usage = response.get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    if any(type(n) is not int or n < 0 for n in (prompt_tokens, completion_tokens)):
        raise ValueError("Missing or invalid usage accounting")
    # Explicit allowlist excludes reasoning, headers, and other provider payloads.
    calls = []
    for call in message.get("tool_calls") or []:
        function = call["function"]
        calls.append({"name": function["name"], "arguments": function["arguments"]})
    return {
        "response_id": response.get("id"), "model": response.get("model"),
        "system_fingerprint": response.get("system_fingerprint"),
        "content": visible_content(message.get("content")), "tool_calls": calls,
        "finish_reason": choice.get("finish_reason"),
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        "cost_estimate_usd": prompt_tokens * INPUT_USD_PER_TOKEN
        + completion_tokens * OUTPUT_USD_PER_TOKEN,
    }


def write_outputs(output: Path, plan: dict, records: list, status: str, key: str = "") -> None:
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source_commit": SOURCE_COMMIT, "source_sha256": SOURCE_SHA256,
        "transport": {"sdk": "openai", "version": "3.6.0", "max_retries": 0, "follow_redirects": False},
        "settings": SETTINGS, "date_info": DATE_INFO, "greeting": GREETING,
        "inputs": INPUTS, "trials_per_case_variant": 10, "max_calls": MAX_CALLS,
        "seed_parameter": "omitted, matching production", "status": status,
        "prompt_sha256": {k: digest(v) for k, v in plan["prompts"].items()},
        "tools_sha256": digest(json.dumps(plan["tools"], ensure_ascii=False, sort_keys=True)),
        "prompts": plan["prompts"], "tools": plan["tools"],
        "dialect_diff": "".join(difflib.unified_diff(
            plan["prompts"]["A"].splitlines(keepends=True),
            plan["prompts"]["B"].splitlines(keepends=True), fromfile="A", tofile="B")),
        "budget_usd": BUDGET_USD, "cost_is_estimate_excluding_runner_fees": True,
        "pricing_source": "https://console.groq.com/docs/model/openai/gpt-oss-20b",
        "execution": {k: os.environ.get(k) for k in (
            "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")},
        "limitations": [
            "Small pilot; fixed two inputs and one date/time; not general proof",
            "Kansai food/culture persona remains in both arms",
            "No downstream search is executed or evaluated",
            "Provider model alias may change; inspect returned fingerprints",
        ],
    }
    blind_order = list(records)
    random.Random(739251).shuffle(blind_order)
    blind = []
    mapping = {}
    for number, record in enumerate(blind_order):
        label = f"sample-{number + 1:03}"
        mapping[label] = {k: record[k] for k in ("index", "case", "trial", "variant")}
        response = record.get("response", {})
        blind.append({"sample_id": label, "input": INPUTS[record["case"]],
                      "result": None if record.get("error") else {
                          k: response.get(k) for k in ("content", "tool_calls", "finish_reason")},
                      "error": record.get("error")})
    files = {
        "manifest.json": manifest, "responses.json": records,
        "blind-review.json": blind, "blind-key.json": mapping,
        "summary.json": {
            "status": status, "attempted_calls": len(records),
            "successful_calls": sum("response" in r and "error" not in r for r in records),
            "calls_with_unknown_cost": sum("response" not in r for r in records),
            "estimated_inference_usd": sum(r.get("response", {}).get("cost_estimate_usd", 0) for r in records),
        },
    }
    for name, value in files.items():
        encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if key:
            encoded = encoded.replace(key, "[REDACTED]")
        (output / name).write_text(encoded, encoding="utf-8")


def run(plan: dict, output: Path, key: str, request_fn=call_groq) -> int:
    records = []
    started = time.monotonic()
    status = "running"
    write_outputs(output, plan, records, status, key)
    for item in plan["schedule"]:
        spent = sum(r.get("response", {}).get("cost_estimate_usd", 0) for r in records)
        next_allowance = MAX_INPUT_TOKENS * INPUT_USD_PER_TOKEN + 1000 * OUTPUT_USD_PER_TOKEN
        if time.monotonic() - started > 720 or spent + next_allowance > BUDGET_USD:
            status = "stopped_at_time_or_budget_guard"
            break
        record = {k: item[k] for k in ("index", "case", "trial", "variant", "request_bytes")}
        records.append(record)
        before = time.monotonic()
        try:
            response = sanitize_response(request_fn(item["request"], key))
            record["response"] = response
            if response["model"] != SETTINGS["model"]:
                raise ValueError("Unexpected model")
            if (response["usage"]["prompt_tokens"] > MAX_INPUT_TOKENS
                    or response["usage"]["completion_tokens"] > 1000):
                raise ValueError("Unexpected token accounting")
        except Exception as exc:
            from eval_groq_transport import safe_error
            record["error"] = {"exception_class": type(exc).__name__, **safe_error(exc)}
            status = "stopped_after_error_no_retry"
        record["latency_seconds"] = round(time.monotonic() - before, 4)
        write_outputs(output, plan, records, status, key)
        if status != "running":
            break
    if status == "running":
        status = "complete"
    write_outputs(output, plan, records, status, key)
    print(f"Pilot status: {status}; attempted requests: {len(records)}/{MAX_CALLS}")
    return 0 if status == "complete" else 1


def live_execution_allowed() -> bool:
    return (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
        and os.environ.get("GITHUB_REPOSITORY") == "dj-oyu/echo-line-bot"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("dialect-ab-results"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    plan = make_plan(root / "lambda" / "ai_processor.py")
    if not args.execute:
        write_outputs(args.output, plan, [], "prepared_no_requests")
        print("Prepared 40 requests; no network calls made")
        return 0
    if not live_execution_allowed():
        raise ValueError("Live execution requires an approved first-attempt workflow event")
    key = os.environ.pop("GROQ_API_KEY", "")
    if not key:
        raise ValueError("Runtime Groq credential unavailable")
    return run(plan, args.output, key)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Pilot failed before completion: {type(exc).__name__}")
        raise SystemExit(1) from None

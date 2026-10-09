"""One manual, bounded synthetic evaluation. Never deliver LINE or execute searches."""

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import dialect_ab
import httpx2

MODEL = "claude-haiku-5-5"
BUDGET_USD = 0.10
MAX_CALLS = 4
MAX_REQUEST_BYTES = 8192
MAX_COUNTED_INPUT = 8000
MAX_OUTPUT = 4096
# Reserve the more expensive long-context rate, even for these short requests.
RESERVE_INPUT_RATE = 0.50 / 1_000_000
RESERVE_OUTPUT_RATE = 2.50 / 1_000_000
CASES = (
    ("greeting", "やっほい！元気？", False, False),
    ("stable_question", "1足す1はいくつ？", False, False),
    (
        "current_information",
        "2026年10月9日時点の最近のAWSのアップデートを公式の最新情報から調べて教えて。",
        True,
        False,
    ),
    ("tool_protocol", "東京の今日の天気を調べて。", True, True),
)


class BoundedMessages:
    def __init__(self, sdk):
        self.sdk = sdk
        self.calls = 0
        self.count_calls = 0
        self.reserved_usd = 0.0
        self.responses = []
        self.forced_tool = False

    def create(self, **request):
        if request.get("model") != MODEL or request.get("max_tokens") != MAX_OUTPUT:
            raise ValueError("Unexpected model or output limit")
        if self.calls >= MAX_CALLS:
            raise ValueError("Call limit reached")
        if self.forced_tool:
            request["tool_choice"] = {"type": "tool", "name": "search_with_grok"}
        if len(json.dumps(request, ensure_ascii=False).encode()) > MAX_REQUEST_BYTES:
            raise ValueError("Request size limit reached")
        counting = {
            key: request[key] for key in ("model", "system", "messages", "tools", "tool_choice")
        }
        self.count_calls += 1
        counted = self.sdk.messages.count_tokens(**counting).input_tokens
        if not isinstance(counted, int) or not 0 < counted <= MAX_COUNTED_INPUT:
            raise ValueError("Input token limit reached")
        # Counting is an estimate. Allow double the estimate plus 1024 wrapper
        # tokens and reserve the full output limit, including thinking tokens.
        reserve = (2 * counted + 1024) * RESERVE_INPUT_RATE + MAX_OUTPUT * RESERVE_OUTPUT_RATE
        if self.reserved_usd + reserve > BUDGET_USD:
            raise ValueError("Cost reservation limit reached")
        self.reserved_usd += reserve  # Retain reservation on any uncertain failure.
        self.calls += 1
        response = self.sdk.messages.create(**request)
        if response.model != MODEL:
            raise ValueError("Unexpected response model")
        self.responses.append(response)
        return response


def run(sdk, processor, tools):
    bounded = BoundedMessages(sdk)
    results = []
    error = None
    try:
        metadata = sdk.models.retrieve(MODEL)
        if metadata.id != MODEL:
            raise ValueError("Requested model is unavailable")
        for name, text, expected_search, forced in CASES:
            bounded.forced_tool = forced
            with patch.object(processor, "anthropic_client", SimpleNamespace(messages=bounded)):
                result = processor.get_anthropic_response(
                    processor.prepare_messages_for_api([{"role": "user", "content": text}]), tools
                )
            response = bounded.responses[-1]
            usage = response.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
                raise ValueError("Missing measured usage")
            if input_tokens > MAX_COUNTED_INPUT * 2 + 1024 or output_tokens > MAX_OUTPUT:
                raise ValueError("Unexpected measured usage")
            cost = input_tokens * 0.10 / 1_000_000 + output_tokens * 0.50 / 1_000_000
            results.append(
                {
                    "case": name,
                    "input": text,
                    "forced_tool": forced,
                    "expected_search": expected_search,
                    "result": result,
                    "passed": result["hasToolCall"] == expected_search,
                    "stop_reason": response.stop_reason,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "estimated_model_cost_usd": cost,
                }
            )
    except Exception as exc:
        # Free-form provider errors can contain request headers. Export type only.
        error = type(exc).__name__
    return {
        "model": MODEL,
        "budget_usd": BUDGET_USD,
        "inference_calls": bounded.calls,
        "token_count_calls": bounded.count_calls,
        "model_metadata_calls": 1,
        "reserved_usd": bounded.reserved_usd,
        "estimated_model_cost_usd": sum(item["estimated_model_cost_usd"] for item in results),
        "cost_basis": "measured usage multiplied by published short-context rates; not an invoice",
        "failed_call_cost_unknown": bounded.calls != len(results),
        "results": results,
        "error_type": error,
        "passed": error is None
        and len(results) == MAX_CALLS
        and all(item["passed"] for item in results),
        "searches_executed": 0,
        "line_messages_sent": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = Path("anthropic-results")
    output.mkdir(exist_ok=True)
    if not args.execute:
        report = {"model": MODEL, "max_calls": MAX_CALLS, "budget_usd": BUDGET_USD, "cases": CASES}
        exit_code = 0
    else:
        report = {"passed": False, "error_type": "PreflightFailed", "inference_calls": 0}
        exit_code = 1
        try:
            if (
                os.environ.get("GITHUB_ACTIONS") != "true"
                or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
            ):
                raise ValueError("Only the first manual GitHub Actions attempt is allowed")
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ValueError("Missing GitHub secret")
            root = Path(__file__).resolve().parents[1]
            _, tools = dialect_ab.extract_source(root / "lambda" / "ai_processor.py")
            sys.path.insert(0, str(root / "lambda"))
            import ai_processor

            with httpx2.Client(follow_redirects=False, trust_env=False) as http_client:
                sdk = anthropic.Anthropic(
                    api_key=os.environ["ANTHROPIC_API_KEY"],
                    base_url="https://api.anthropic.com",
                    timeout=45.0,
                    max_retries=0,
                    http_client=http_client,
                )
                report = run(sdk, ai_processor, tools)
                exit_code = 0 if report["passed"] else 1
        except Exception as exc:
            report["error_type"] = type(exc).__name__
    (output / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

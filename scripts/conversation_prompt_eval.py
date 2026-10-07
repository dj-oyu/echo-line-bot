"""Prepare a conversation-first comparison. This module makes no network calls."""
import argparse
import difflib
import json
from pathlib import Path

import dialect_ab as baseline

ROOT = Path(__file__).resolve().parents[1]
REPETITIONS = 2


def prepare_plan(root: Path = ROOT) -> dict:
    original, tools = baseline.extract_source(root / "lambda" / "ai_processor.py")
    template = (root / "evals/prompts/conversation_first_ja.txt").read_text(encoding="utf-8")
    revised = template.format_map(baseline.DATE_INFO)
    cases = json.loads((root / "evals/conversation_first_cases.json").read_text(encoding="utf-8"))
    variants = {"A_current": original, "B_conversation_first": revised}
    requests = []
    for trial in range(REPETITIONS):
        for index, case in enumerate(cases):
            order = tuple(variants) if (trial + index) % 2 == 0 else tuple(reversed(variants))
            for variant in order:
                request = {
                    **baseline.SETTINGS,
                    "messages": [{"role": "system", "content": variants[variant]}]
                    + case["history"] + [{"role": "user", "content": case["input"]}],
                    "tools": tools,
                }
                requests.append({
                    "case_id": case["id"], "trial": trial, "variant": variant,
                    "request": request, "checks": case["checks"], "intent": case["intent"],
                })
    return {
        "status": "offline_draft_no_live_calls",
        "source_commit": baseline.SOURCE_COMMIT,
        "planned_requests": len(requests), "repetitions_per_case_and_variant": REPETITIONS,
        "execution_requires_separate_approval": True,
        "sdk_transport": {"entrypoint": "dialect_diagnostic.sdk_call", "version": "3.6.0",
                          "max_retries": 0, "follow_redirects": False},
        "date_info": baseline.DATE_INFO, "variants": variants,
        "prompt_sha256": {name: baseline.digest(text) for name, text in variants.items()},
        "prompt_diff": "".join(difflib.unified_diff(
            original.splitlines(keepends=True), revised.splitlines(keepends=True),
            fromfile="current", tofile="conversation_first")),
        "measurement_plan": [
            "Human review of latest-intent fit, continuity/corrections, clarification and naturalness",
            "Tool decision/query relevance; no actual search or LINE delivery",
            "Observed first-stage latency per request; median and p95 by variant, with all raw values",
            "Input/output tokens, visible answer length, finish reason, model/fingerprint and errors",
        ],
        "limits": [
            "Shared fixed histories isolate the next response; this is not a free-running conversation",
            "No search results are mocked or executed; downstream answer quality/latency is not tested",
            "The revised prompt changes emphasis and topic initiative together, not a single phrase",
            "Two repetitions per case are exploratory, not a statistical reliability estimate",
            "No behavioral or latency improvement can be inferred from offline checks",
        ],
        "requests": requests,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("conversation-prompt-plan.json"))
    args = parser.parse_args()
    plan = prepare_plan()
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {plan['planned_requests']} requests; no model or network calls made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

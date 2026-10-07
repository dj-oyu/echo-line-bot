"""Offline tests only. No production imports, credentials, or network requests."""

import collections
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("dialect_ab", ROOT / "scripts" / "dialect_ab.py")
ab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ab)


def completion(content="こんにちは", **updates):
    data = {
        "id": "synthetic-response", "model": ab.SETTINGS["model"],
        "system_fingerprint": "synthetic-fingerprint",
        "choices": [{"message": {"content": content, "reasoning": "DO NOT EXPORT"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
    }
    data.update(updates)
    return data


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.plan = ab.make_plan(ROOT / "lambda" / "ai_processor.py")

    def test_exact_inputs_and_bounded_balanced_pairs(self):
        self.assertEqual(ab.INPUTS, ("やっほい", "おすすめの飲食店ある?"))
        schedule = self.plan["schedule"]
        self.assertEqual(len(schedule), 40)
        self.assertEqual(collections.Counter((s["case"], s["variant"]) for s in schedule),
                         {(0, "A"): 10, (0, "B"): 10, (1, "A"): 10, (1, "B"): 10})
        first = collections.Counter()
        for i in range(0, 40, 2):
            left, right = schedule[i:i+2]
            self.assertEqual((left["case"], left["trial"]), (right["case"], right["trial"]))
            self.assertNotEqual(left["variant"], right["variant"])
            first[(left["case"], left["variant"])] += 1
        self.assertEqual(set(first.values()), {5})

    def test_only_system_prompt_differs_within_each_pair(self):
        for i in range(0, 40, 2):
            requests = [json.loads(json.dumps(s["request"])) for s in self.plan["schedule"][i:i+2]]
            for request in requests:
                self.assertEqual(len(request["messages"]), 2)
                self.assertNotIn("seed", request)
                for key, value in ab.SETTINGS.items():
                    self.assertEqual(request[key], value)
                request["messages"][0]["content"] = "controlled difference"
            self.assertEqual(*requests)

    def test_culture_preserved_dialect_removed(self):
        a, b = self.plan["prompts"]["A"], self.plan["prompts"]["B"]
        self.assertIn("関西弁", a)
        self.assertNotIn("関西弁", b)
        self.assertNotIn("大阪弁", b)
        for prompt in (a, b):
            self.assertEqual(prompt.count(ab.CULTURE_CUE), 1)
            self.assertIn("2026年10月07日（水曜日）", prompt)
            self.assertIn("20時00分頃", prompt)
            self.assertIn(ab.GREETING, prompt)
        self.assertIn("今日はどうだった？", b)

    def test_changed_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "changed.py"
            source.write_text((ROOT / "lambda" / "ai_processor.py").read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "baseline"):
                ab.extract_source(source)

    def test_changed_prompt_does_not_silently_rewrite(self):
        with self.assertRaises(ValueError):
            ab.without_dialect("Different prompt")


class TestSafety(unittest.TestCase):
    def setUp(self):
        self.plan = ab.make_plan(ROOT / "lambda" / "ai_processor.py")

    def test_reasoning_is_excluded(self):
        result = ab.sanitize_response(completion("<think>secret thought</think>最終回答"))
        self.assertEqual(result["content"], "最終回答")
        self.assertNotIn("DO NOT EXPORT", json.dumps(result))
        self.assertNotIn("secret thought", json.dumps(result))
        self.assertEqual(ab.visible_content("<think>unfinished thought"), "")

    def test_tool_arguments_remain_raw_and_tool_is_not_executed(self):
        data = completion(None)
        raw = '{"query":"大阪 飲食店", "prompt":"検索して"}'
        data["choices"][0]["message"]["tool_calls"] = [
            {"function": {"name": "search_with_grok", "arguments": raw}}
        ]
        result = ab.sanitize_response(data)
        self.assertEqual(result["tool_calls"], [{"name": "search_with_grok", "arguments": raw}])

    def test_missing_usage_is_rejected(self):
        with self.assertRaises(ValueError):
            ab.sanitize_response(completion(usage={}))

    def test_bounded_success_and_no_secret_or_reasoning_in_artifacts(self):
        calls = []
        fake_key = "SYNTHETIC_TEST_CREDENTIAL"
        def fake_request(request, key):
            calls.append(request)
            return completion(f"answer {key}")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(ab.run(self.plan, output, fake_key, fake_request), 0)
            self.assertEqual(len(calls), 40)
            for path in output.glob("*.json"):
                content = path.read_text()
                self.assertNotIn(fake_key, content)
                self.assertNotIn("DO NOT EXPORT", content)
            blind = json.loads((output / "blind-review.json").read_text())
            self.assertEqual(len(blind), 40)
            self.assertNotIn("variant", json.dumps(blind))
            self.assertNotIn("prompt_tokens", json.dumps(blind))

    def test_http_failure_stops_without_retry_or_error_body_export(self):
        calls = []
        def failing(request, key):
            calls.append(request)
            raise urllib.error.HTTPError(ab.ENDPOINT, 429, "SECRET IN ERROR", {}, None)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(ab.run(self.plan, output, "key", failing), 1)
            self.assertEqual(len(calls), 1)
            self.assertNotIn("SECRET IN ERROR", (output / "responses.json").read_text())
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["calls_with_unknown_cost"], 1)

    def test_bad_model_or_usage_stops_without_retry(self):
        for updates in ({"model": "different-model"},
                        {"usage": {"prompt_tokens": 100, "completion_tokens": 1001}}):
            with self.subTest(updates=updates), tempfile.TemporaryDirectory() as directory:
                calls = []
                def bad(request, key):
                    calls.append(request)
                    return completion(**updates)
                self.assertEqual(ab.run(self.plan, Path(directory), "key", bad), 1)
                self.assertEqual(len(calls), 1)
                blind = json.loads((Path(directory) / "blind-review.json").read_text())
                self.assertIsNone(blind[0]["result"])

    def test_budget_and_time_guards_make_no_request(self):
        fake = MagicMock()
        for guard in (patch.object(ab, "BUDGET_USD", 0),
                      patch.object(ab.time, "monotonic", side_effect=[0, 721])):
            with guard, tempfile.TemporaryDirectory() as directory:
                self.assertEqual(ab.run(self.plan, Path(directory), "key", fake), 1)
        fake.assert_not_called()

    def test_oversized_response_is_rejected_without_export(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"x" * (ab.MAX_RESPONSE_BYTES + 1)
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(ab.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(ValueError):
                ab.call_groq(self.plan["schedule"][0]["request"], "synthetic")
        opener.open.assert_called_once()

    def test_redirect_refused(self):
        request = type("Request", (), {"full_url": ab.ENDPOINT})()
        with self.assertRaises(urllib.error.HTTPError):
            ab.NoRedirects().redirect_request(request, None, 302, "redirect", {}, "https://invalid.test")

    def test_execution_requires_manual_first_attempt(self):
        valid = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch",
                 "GITHUB_RUN_ATTEMPT": "1", "GITHUB_REPOSITORY": "dj-oyu/echo-line-bot"}
        for field, bad in (("GITHUB_ACTIONS", "false"), ("GITHUB_EVENT_NAME", "push"),
                           ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_REPOSITORY", "other/repo")):
            with self.subTest(field=field), patch.dict(os.environ, {**valid, field: bad}), \
                 patch("sys.argv", ["dialect_ab.py", "--execute"]):
                with self.assertRaises(ValueError):
                    ab.main()


if __name__ == "__main__":
    unittest.main()

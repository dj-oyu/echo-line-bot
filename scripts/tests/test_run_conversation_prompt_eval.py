import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_conversation_prompt_eval as runner


class TestBoundedConversationRun(unittest.TestCase):
    def test_28_fake_requests_and_safe_blinding(self):
        calls = []
        def fake(request, key, row):
            calls.append(request)
            row["network_requests_started"] += 1
            return {"model": "openai/gpt-oss-20b", "system_fingerprint": "fake",
                    "choices": [{"message": {"content": "Synthetic answer", "reasoning": "PRIVATE_REASONING"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 800, "completion_tokens": 100}}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(runner.run(output, "SYNTHETIC_KEY", fake), 0)
            self.assertEqual(len(calls), 28)
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["network_requests_started"], 28)
            blind = (output / "blind-review.json").read_text()
            for excluded in ("PRIVATE_REASONING", "SYNTHETIC_KEY", "prompt_tokens", "variant", "latency_seconds"):
                self.assertNotIn(excluded, blind)

    def test_error_stops_after_one_without_leaking_body(self):
        def fail(request, key, row):
            row["network_requests_started"] += 1
            error = Exception(key)
            error.status_code = 403
            error.body = {"error": {"message": key}}
            raise error
        fake = MagicMock(side_effect=fail)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertEqual(runner.run(output, "SYNTHETIC_KEY", fake), 1)
            fake.assert_called_once()
            self.assertNotIn("SYNTHETIC_KEY", (output / "raw-responses.json").read_text())

    def test_budget_reserve_blocks_before_call(self):
        fake = MagicMock()
        with patch.object(runner, "BUDGET_USD", runner.RESERVE_USD / 2), tempfile.TemporaryDirectory() as directory:
            self.assertEqual(runner.run(Path(directory), "synthetic", fake), 1)
        fake.assert_not_called()

    def test_one_advance_guard(self):
        event = {"ref": runner.BRANCH, "before": runner.BEFORE, "created": False, "deleted": False, "forced": False,
                 "head_commit": {"id": "a" * 40, "message": runner.MARKER}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event.json"
            env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push", "GITHUB_REPOSITORY": "dj-oyu/echo-line-bot",
                   "GITHUB_REF": runner.BRANCH, "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40,
                   "GITHUB_EVENT_PATH": str(path)}
            path.write_text(json.dumps(event))
            with patch.dict(os.environ, env, clear=True):
                self.assertTrue(runner.allowed())
            for field, value in (("before", "b" * 40), ("created", True), ("deleted", True), ("forced", True)):
                path.write_text(json.dumps({**event, field: value}))
                with patch.dict(os.environ, env, clear=True):
                    self.assertFalse(runner.allowed())
            path.write_text(json.dumps(event))
            with patch.dict(os.environ, {**env, "GITHUB_RUN_ATTEMPT": "2"}, clear=True):
                self.assertFalse(runner.allowed())


if __name__ == "__main__":
    unittest.main()

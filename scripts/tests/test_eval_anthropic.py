"""Boundaries for the manual evaluator; all provider methods are mocked."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "eval_anthropic", ROOT / "scripts" / "eval_anthropic.py"
)
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


class TestBounds(unittest.TestCase):
    def setUp(self):
        self.sdk = MagicMock()
        self.sdk.messages.count_tokens.return_value.input_tokens = 8000
        self.sdk.messages.create.return_value = SimpleNamespace(model=evaluation.MODEL)
        self.bounded = evaluation.BoundedMessages(self.sdk)
        self.request = {
            "model": evaluation.MODEL,
            "max_tokens": 4096,
            "system": "synthetic",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [],
            "tool_choice": {"type": "auto"},
        }

    def test_four_worst_allowed_requests_stay_below_budget(self):
        for _ in range(4):
            self.bounded.create(**self.request)
        self.assertLess(self.bounded.reserved_usd, 0.10)
        self.assertEqual(self.bounded.calls, 4)
        with self.assertRaises(ValueError):
            self.bounded.create(**self.request)
        self.assertEqual(self.sdk.messages.create.call_count, 4)

    def test_budget_exhaustion_blocks_inference(self):
        self.bounded.reserved_usd = 0.099
        with self.assertRaises(ValueError):
            self.bounded.create(**self.request)
        self.sdk.messages.create.assert_not_called()

    def test_token_overflow_blocks_inference(self):
        self.sdk.messages.count_tokens.return_value.input_tokens = 8001
        with self.assertRaises(ValueError):
            self.bounded.create(**self.request)
        self.sdk.messages.create.assert_not_called()

    def test_large_body_blocks_even_token_count_request(self):
        self.request["system"] = "x" * 8193
        with self.assertRaises(ValueError):
            self.bounded.create(**self.request)
        self.sdk.messages.count_tokens.assert_not_called()
        self.sdk.messages.create.assert_not_called()

    def test_model_or_output_changes_block_requests(self):
        for key, value in (("model", "different-model"), ("max_tokens", 4097)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.bounded.create(**{**self.request, key: value})
        self.sdk.messages.create.assert_not_called()

    def test_unknown_failure_consumes_reservation_and_is_not_retried(self):
        self.sdk.messages.create.side_effect = RuntimeError("secret-header-do-not-export")
        with self.assertRaises(RuntimeError):
            self.bounded.create(**self.request)
        self.assertEqual(self.bounded.calls, 1)
        self.assertGreater(self.bounded.reserved_usd, 0)
        self.sdk.messages.create.assert_called_once()

    def test_named_tool_is_only_for_explicit_protocol_case(self):
        self.bounded.create(**self.request)
        self.assertEqual(self.sdk.messages.create.call_args.kwargs["tool_choice"], {"type": "auto"})
        self.bounded.forced_tool = True
        self.bounded.create(**self.request)
        self.assertEqual(
            self.sdk.messages.create.call_args.kwargs["tool_choice"],
            {"type": "tool", "name": "search_with_grok"},
        )


if __name__ == "__main__":
    unittest.main()

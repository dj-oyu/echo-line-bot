import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dialect_diagnostic as diag


class TestDiagnostic(unittest.TestCase):
    def test_only_allowlisted_errors_survive(self):
        error = Exception("SECRET IN EXCEPTION")
        error.status_code = 403
        error.body = {"error": {"type": "invalid_request_error", "code": "SECRET_CODE",
                                "message": "SECRET MESSAGE", "headers": "SECRET HEADER"}}
        safe = diag.safe_error(error)
        self.assertEqual(safe["status"], 403)
        self.assertEqual(safe["type"], "invalid_request_error")
        self.assertEqual(safe["code"], "not_retained")
        self.assertNotIn("SECRET", json.dumps(safe))

    def test_exactly_one_call_and_no_continuation(self):
        calls = []
        def failure(request, key, record):
            calls.append(request)
            record["network_requests_started"] += 1
            error = Exception(key)
            error.status_code = 403
            error.body = key
            raise error
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(diag.diagnose(Path(directory), "SYNTHETIC_SECRET", failure), 1)
            self.assertEqual(len(calls), 1)
            text = (Path(directory) / "diagnostic.json").read_text()
            self.assertNotIn("SYNTHETIC_SECRET", text)
            self.assertEqual(calls[0]["messages"][1]["content"], "やっほい")
            self.assertEqual(calls[0]["max_tokens"], 1000)

    def test_exact_one_advance_guard(self):
        sha = "a" * 40
        event = {"ref": diag.BRANCH, "before": diag.BEFORE, "created": False,
                 "deleted": False, "forced": False,
                 "head_commit": {"id": sha, "message": diag.MARKER}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "event.json"
            env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
                   "GITHUB_REPOSITORY": "dj-oyu/echo-line-bot", "GITHUB_REF": diag.BRANCH,
                   "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": sha, "GITHUB_EVENT_PATH": str(path)}
            path.write_text(json.dumps(event))
            with patch.dict(os.environ, env, clear=True):
                self.assertTrue(diag.allowed())
            for field, value in (("before", "b"*40), ("created", True), ("deleted", True), ("forced", True)):
                path.write_text(json.dumps({**event, field: value}))
                with patch.dict(os.environ, env, clear=True):
                    self.assertFalse(diag.allowed())
            path.write_text(json.dumps(event))
            with patch.dict(os.environ, {**env, "GITHUB_RUN_ATTEMPT": "2"}, clear=True):
                self.assertFalse(diag.allowed())


@unittest.skipUnless(importlib.util.find_spec("openai"), "Production SDK only installed in Actions")
class TestRealSdkOffline(unittest.TestCase):
    def test_403_500_and_redirect_do_not_retry(self):
        import httpx2
        import openai
        self.assertEqual(openai.__version__, diag.SDK_VERSION)
        for status in (403, 500, 302):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx2.Response(status, json={"error": {"type": "invalid_request_error"}},
                                       headers={"location": "https://invalid.test/"})
            record = {"network_requests_started": 0}
            with self.subTest(status=status):
                with self.assertRaises(Exception):
                    diag.sdk_call({"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": "やっほい"}]},
                                  "SYNTHETIC_KEY", record, transport=httpx2.MockTransport(handler))
                self.assertEqual(len(calls), 1)
                self.assertEqual(record["network_requests_started"], 1)
                self.assertEqual(str(calls[0].url), "https://api.groq.com/openai/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()

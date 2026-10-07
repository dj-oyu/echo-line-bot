import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eval_groq_transport as transport


class TestSanitizedErrors(unittest.TestCase):
    def test_only_allowlisted_errors_survive(self):
        error = Exception("SECRET IN EXCEPTION")
        error.status_code = 403
        error.body = {"error": {"type": "invalid_request_error", "code": "SECRET_CODE",
                                "message": "SECRET MESSAGE", "headers": "SECRET HEADER"}}
        safe = transport.safe_error(error)
        self.assertEqual(safe["status"], 403)
        self.assertEqual(safe["type"], "invalid_request_error")
        self.assertEqual(safe["code"], "not_retained")
        self.assertNotIn("SECRET", json.dumps(safe))


@unittest.skipUnless(importlib.util.find_spec("openai"), "Production SDK only installed in Actions")
class TestRealSdkOffline(unittest.TestCase):
    def test_403_500_and_redirect_do_not_retry(self):
        import httpx2
        import openai
        self.assertEqual(openai.__version__, transport.SDK_VERSION)
        for status in (403, 500, 302):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx2.Response(status, json={"error": {"type": "invalid_request_error"}},
                                       headers={"location": "https://invalid.test/"})
            record = {"network_requests_started": 0}
            with self.subTest(status=status):
                with self.assertRaises(Exception):
                    transport.sdk_call({"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": "やっほい"}]},
                                  "SYNTHETIC_KEY", record, transport=httpx2.MockTransport(handler))
                self.assertEqual(len(calls), 1)
                self.assertEqual(record["network_requests_started"], 1)
                self.assertEqual(str(calls[0].url), "https://api.groq.com/openai/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()

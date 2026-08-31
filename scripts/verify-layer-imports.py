"""Import every Lambda handler using only the built layer.

The unit tests run against the project virtualenv, which has complete package
metadata, so they cannot see what the deployed layer is missing. This script
reproduces the Lambda import environment instead: the layer plus the function
code, and nothing else.

It exists because stripping dist-info from the layer once broke production —
openai looks up httpx2 through importlib.metadata at import time, and the
stripped layer raised "No package metadata was found for httpx2" only after
deploy.

Run it after ./scripts/build-layer.sh, with an interpreter that is NOT the
project virtualenv.
"""

import os
import pathlib
import sys
import unittest.mock

HANDLERS = [
    "ai_processor",
    "grok_processor",
    "response_sender",
    "webhook_handler",
]

root = pathlib.Path(__file__).resolve().parent.parent
layer = root / "lambda" / "layer-dist" / "python"
code = root / "lambda"

if not layer.is_dir():
    sys.exit(f"layer not built: {layer} does not exist — run ./scripts/build-layer.sh")

# Drop any virtualenv the caller happened to be in: the point is to prove the
# layer alone is sufficient.
sys.path = [p for p in sys.path if ".venv" not in p]
sys.path.insert(0, str(code))
sys.path.insert(0, str(layer))

# Handlers read these at import time and build AWS clients; the values are
# never used because the clients are mocked.
os.environ.setdefault("CHANNEL_SECRET_NAME", "verify")
os.environ.setdefault("CHANNEL_ACCESS_TOKEN_NAME", "verify")
os.environ.setdefault("CONVERSATION_TABLE_NAME", "verify")
os.environ.setdefault("SAMBA_NOVA_API_KEY_NAME", "verify")
os.environ.setdefault("GROQ_API_KEY_NAME", "verify")
os.environ.setdefault("XAI_API_KEY_SECRET_NAME", "verify")
os.environ.setdefault("STEP_FUNCTION_ARN", "verify")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-northeast-1")

failures = []
with unittest.mock.patch("boto3.client"), unittest.mock.patch("boto3.resource"):
    for handler in HANDLERS:
        try:
            __import__(handler)
        except Exception as exc:  # noqa: BLE001 - report every handler, not just the first
            failures.append(f"{handler}: {type(exc).__name__}: {exc}")
            print(f"  FAIL {handler}: {type(exc).__name__}: {exc}")
        else:
            print(f"  ok   {handler}")

if failures:
    sys.exit(f"\n{len(failures)} handler(s) cannot import against the layer alone.")
print("all handlers import against the layer alone")

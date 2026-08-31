"""Regression tests for the LINE SDK on the deployed Python runtime.

line-bot-sdk builds its models on `pydantic.v1`, a compatibility shim that
pydantic itself declares unsupported on Python 3.14+ (importing it emits a
UserWarning). It works today, but the rest of the suite mocks the SDK away,
so a pydantic upgrade could break every webhook without any test failing.

These tests deliberately exercise the real SDK — no mocks — so that such a
break shows up in CI instead of in production.
"""

import base64
import hashlib
import hmac
import json
import unittest

from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import MessageEvent, TextMessageContent

CHANNEL_SECRET = "test-channel-secret"


def _sign(body: str) -> str:
    """Sign a body the way the LINE platform does."""
    digest = hmac.new(CHANNEL_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _webhook_body(text: str = "こんにちは") -> str:
    return json.dumps(
        {
            "destination": "U0000000000000000000000000000000",
            "events": [
                {
                    "type": "message",
                    "mode": "active",
                    "timestamp": 1462629479859,
                    "source": {"type": "user", "userId": "U4af4980629"},
                    "webhookEventId": "01FZ74A0TDDPYRVKNK77XKC3ZR",
                    "deliveryContext": {"isRedelivery": False},
                    "replyToken": "reply-token",
                    "message": {
                        "id": "444573844083572737",
                        "type": "text",
                        "text": text,
                        "quoteToken": "quote-token",
                    },
                }
            ],
        }
    )


class TestWebhookParsing(unittest.TestCase):
    """The inbound path: signature verification and event model construction."""

    def test_valid_signature_parses_into_models(self):
        body = _webhook_body()
        events = WebhookParser(CHANNEL_SECRET).parse(body, _sign(body))

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertIsInstance(event, MessageEvent)
        self.assertIsInstance(event.message, TextMessageContent)
        self.assertEqual(event.message.text, "こんにちは")
        # snake_case aliasing is a pydantic feature, not plain dict access
        self.assertEqual(event.source.user_id, "U4af4980629")
        self.assertEqual(event.reply_token, "reply-token")

    def test_tampered_body_is_rejected(self):
        body = _webhook_body()
        signature = _sign(body)

        with self.assertRaises(InvalidSignatureError):
            WebhookParser(CHANNEL_SECRET).parse(_webhook_body("別のテキスト"), signature)


class TestOutboundMessages(unittest.TestCase):
    """The outbound path: request models and their JSON serialization."""

    def test_push_message_request_serializes(self):
        request = PushMessageRequest(
            to="U4af4980629",
            messages=[TextMessage(text="まいど！", quoteToken=None)],
        )

        payload = json.loads(request.to_json())
        self.assertEqual(payload["to"], "U4af4980629")
        self.assertEqual(payload["messages"][0]["type"], "text")
        self.assertEqual(payload["messages"][0]["text"], "まいど！")

    def test_reply_message_request_keeps_quote_token(self):
        request = ReplyMessageRequest(
            replyToken="reply-token",
            messages=[TextMessage(text="おおきに", quoteToken="quote-token")],
        )

        self.assertEqual(request.reply_token, "reply-token")
        payload = json.loads(request.to_json())
        self.assertEqual(payload["messages"][0]["quoteToken"], "quote-token")


if __name__ == "__main__":
    unittest.main()

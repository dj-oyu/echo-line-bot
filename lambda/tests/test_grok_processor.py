"""Tests for the search stage.

grok_processor now delivers its own answer and records it. The fallback case
matters: a failed search returns an apology, and recording that would leave a
fake assistant failure in the context of every later turn.
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

with patch("boto3.client"), patch("boto3.resource"):
    import grok_processor


class TestGrokProcessor(unittest.TestCase):
    def _event(self):
        return {
            "userId": "U1",
            "sourceType": "user",
            "executionName": "exec-1",
            "toolQuery": "Omarchy Linux",
            "toolPrompt": "",
            "conversationContext": {"userId": "U1", "messages": []},
        }

    @patch("line_messaging.append_and_save")
    @patch("line_messaging.push_text")
    @patch("grok_processor.call_grok_api", return_value=("答え\n\n出典: ...", "答え"))
    def test_sends_the_answer_and_records_the_body(self, _api, mock_push, mock_save):
        result = grok_processor.lambda_handler(self._event(), None)

        self.assertEqual(mock_push.call_args.args[1], "答え\n\n出典: ...")
        self.assertEqual(mock_push.call_args.kwargs["retry_key"], "exec-1")
        # the citation footer is kept out of the history
        self.assertEqual(mock_save.call_args.args[2], "答え")
        self.assertEqual(result["grokBody"], "答え")

    @patch("line_messaging.append_and_save")
    @patch("line_messaging.push_text")
    @patch("grok_processor.call_grok_api", return_value=("ごめんやで～、見つけられへんかった", ""))
    def test_a_failed_search_is_sent_but_not_recorded(self, _api, mock_push, mock_save):
        grok_processor.lambda_handler(self._event(), None)

        mock_push.assert_called_once()
        mock_save.assert_not_called()

    def test_a_missing_query_raises(self):
        """Raising routes the execution to the Catch, which notifies the user."""
        with self.assertRaises(ValueError):
            grok_processor.lambda_handler({"userId": "U1"}, None)


if __name__ == "__main__":
    unittest.main()

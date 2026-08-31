"""Tests for the failure notifier.

response_sender is no longer the pipeline's send stage: the stage that
produces a message now delivers it. What remains is the Step Functions Catch
target, whose only job is to make sure a failure is never silent.
"""

import os
import sys
import unittest
from unittest.mock import patch

# Add the lambda directory to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

with patch("boto3.client"), patch("boto3.resource"):
    import response_sender
    from response_sender import FAILURE_MESSAGE, lambda_handler


class TestFailureNotifier(unittest.TestCase):
    @patch("line_messaging.push_text")
    def test_notifies_the_user(self, mock_push):
        event = {"userId": "uid123", "sourceType": "user", "error": {"Error": "States.TaskFailed"}}

        result = lambda_handler(event, None)

        mock_push.assert_called_once()
        sent_event, message = mock_push.call_args.args
        self.assertEqual(sent_event["userId"], "uid123")
        self.assertEqual(message, FAILURE_MESSAGE)
        self.assertIs(result, event)

    @patch("line_messaging.push_text")
    def test_without_a_user_id_there_is_nobody_to_tell(self, mock_push):
        result = lambda_handler({"error": {"Error": "States.Timeout"}}, None)

        mock_push.assert_not_called()
        self.assertNotIn("userId", result)

    @patch("line_messaging.push_text", side_effect=Exception("LINE is down"))
    def test_a_failing_push_does_not_raise(self, mock_push):
        """Nothing downstream can recover, so raising would only lose the log."""
        result = lambda_handler({"userId": "uid123"}, None)

        mock_push.assert_called_once()
        self.assertEqual(result["userId"], "uid123")


if __name__ == "__main__":
    unittest.main()

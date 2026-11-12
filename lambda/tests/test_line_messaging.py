"""Tests for the shared LINE messaging and persistence helpers.

These cover the two behaviours that were previously wrong: history was only
trimmed on the search path because the two copies of save_conversation_context
disagreed, and a retried push could deliver the same reply twice.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

with patch("boto3.client"), patch("boto3.resource"):
    import line_messaging


class TestResolveTargetId(unittest.TestCase):
    def test_group_messages_go_back_to_the_group(self):
        event = {"userId": "U1", "sourceType": "group", "sourceId": "G1"}
        self.assertEqual(line_messaging.resolve_target_id(event), "G1")

    def test_direct_messages_go_to_the_user(self):
        event = {"userId": "U1", "sourceType": "user", "sourceId": None}
        self.assertEqual(line_messaging.resolve_target_id(event), "U1")

    def test_group_without_source_id_falls_back_to_the_user(self):
        event = {"userId": "U1", "sourceType": "group"}
        self.assertEqual(line_messaging.resolve_target_id(event), "U1")


class TestSaveConversationContext(unittest.TestCase):
    @patch("line_messaging.conversation_table")
    def test_trims_history_to_the_cap(self, mock_table):
        messages = [{"role": "user", "content": str(i)} for i in range(30)]
        context = {"userId": "U1", "messages": messages}

        line_messaging.save_conversation_context("U1", context)

        saved = mock_table.return_value.put_item.call_args.kwargs["Item"]
        self.assertEqual(len(saved["messages"]), line_messaging.MAX_HISTORY_MESSAGES)
        # the newest are the ones kept
        self.assertEqual(saved["messages"][-1]["content"], "29")
        self.assertIn("lastActivity", saved)

    @patch("line_messaging.conversation_table")
    def test_short_history_is_left_alone(self, mock_table):
        context = {"userId": "U1", "messages": [{"role": "user", "content": "hi"}]}

        line_messaging.save_conversation_context("U1", context)

        saved = mock_table.return_value.put_item.call_args.kwargs["Item"]
        self.assertEqual(len(saved["messages"]), 1)

    @patch("line_messaging.conversation_table")
    def test_append_and_save_records_the_assistant_turn(self, mock_table):
        context = {"userId": "U1", "messages": [{"role": "user", "content": "hi"}]}

        line_messaging.append_and_save("U1", context, "まいど！")

        saved = mock_table.return_value.put_item.call_args.kwargs["Item"]
        self.assertEqual(saved["messages"][-1]["role"], "assistant")
        self.assertEqual(saved["messages"][-1]["content"], "まいど！")


class TestPushText(unittest.TestCase):
    def _patched_api(self):
        """Patch the linebot symbols push_text imports at call time."""
        api = MagicMock()
        client = MagicMock()
        client.__enter__.return_value = client
        return api, client

    @patch("line_messaging._configuration")
    def test_passes_the_retry_key_through(self, _config):
        api, client = self._patched_api()
        with (
            patch("line_messaging.ApiClient", return_value=client),
            patch("line_messaging.MessagingApi", return_value=api),
        ):
            line_messaging.push_text(
                {"userId": "U1", "sourceType": "user"}, "hello", retry_key="key-1"
            )

        kwargs = api.push_message_with_http_info.call_args.kwargs
        self.assertEqual(kwargs["x_line_retry_key"], "key-1")

    @patch("line_messaging._configuration")
    def test_omits_the_retry_key_when_absent(self, _config):
        api, client = self._patched_api()
        with (
            patch("line_messaging.ApiClient", return_value=client),
            patch("line_messaging.MessagingApi", return_value=api),
        ):
            line_messaging.push_text({"userId": "U1", "sourceType": "user"}, "hello")

        self.assertNotIn("x_line_retry_key", api.push_message_with_http_info.call_args.kwargs)

    @patch("line_messaging._configuration")
    def test_loading_animation_is_skipped_in_groups(self, _config):
        api, client = self._patched_api()
        with (
            patch("line_messaging.ApiClient", return_value=client),
            patch("line_messaging.MessagingApi", return_value=api),
        ):
            line_messaging.push_text(
                {"userId": "U1", "sourceType": "group", "sourceId": "G1"},
                "hello",
                show_loading=True,
            )

        api.show_loading_animation.assert_not_called()


if __name__ == "__main__":
    unittest.main()

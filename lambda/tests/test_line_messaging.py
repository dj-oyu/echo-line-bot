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
    def test_passes_the_retry_key_through(self, mock_config):
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
        mock_config.assert_called_once()

    @patch("line_messaging._configuration")
    def test_omits_the_retry_key_when_absent(self, mock_config):
        api, client = self._patched_api()
        with (
            patch("line_messaging.ApiClient", return_value=client),
            patch("line_messaging.MessagingApi", return_value=api),
        ):
            line_messaging.push_text({"userId": "U1", "sourceType": "user"}, "hello")

        self.assertNotIn("x_line_retry_key", api.push_message_with_http_info.call_args.kwargs)
        mock_config.assert_called_once()

    @patch("line_messaging._configuration")
    def test_loading_animation_is_skipped_in_groups(self, mock_config):
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
        mock_config.assert_called_once()

    def test_split_text_prefers_a_recent_boundary_without_losing_content(self):
        text = "あ" * 4900 + "\n\n" + "い" * 200

        chunks = line_messaging.split_text(text)

        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 5000 for chunk in chunks))
        self.assertEqual(chunks[0], "あ" * 4900 + "\n\n")

    @patch("line_messaging._configuration")
    def test_long_text_is_sent_as_multiple_messages_in_one_request(self, mock_config):
        api, client = self._patched_api()
        text = "a" * 10_001

        with (
            patch("line_messaging.ApiClient", return_value=client),
            patch("line_messaging.MessagingApi", return_value=api),
        ):
            line_messaging.push_text(
                {"userId": "U1", "sourceType": "user"},
                text,
                retry_key="key-1",
            )

        api.push_message_with_http_info.assert_called_once()
        messages = (
            api.push_message_with_http_info.call_args.kwargs["push_message_request"].messages
        )
        self.assertEqual([len(message.text) for message in messages], [5000, 5000, 1])
        self.assertEqual("".join(message.text for message in messages), text)
        mock_config.assert_called_once()

    @patch("line_messaging._configuration")
    def test_more_than_five_chunks_use_stable_distinct_retry_keys(self, mock_config):
        api, client = self._patched_api()

        with (
            patch("line_messaging.ApiClient", return_value=client),
            patch("line_messaging.MessagingApi", return_value=api),
        ):
            line_messaging.push_text(
                {"userId": "U1", "sourceType": "user"},
                "x" * 25_001,
                retry_key="exec-1",
            )
            line_messaging.push_text(
                {"userId": "U1", "sourceType": "user"},
                "x" * 25_001,
                retry_key="exec-1",
            )

        self.assertEqual(api.push_message_with_http_info.call_count, 4)
        first_run = [
            call.kwargs["x_line_retry_key"]
            for call in api.push_message_with_http_info.call_args_list[:2]
        ]
        second_run = [
            call.kwargs["x_line_retry_key"]
            for call in api.push_message_with_http_info.call_args_list[2:]
        ]
        self.assertEqual(first_run, second_run)
        self.assertEqual(len(set(first_run)), 2)
        self.assertEqual(mock_config.call_count, 2)

    @patch("line_messaging._configuration")
    def test_quote_is_attached_only_to_the_first_chunk(self, mock_config):
        api, client = self._patched_api()
        with (
            patch("line_messaging.ApiClient", return_value=client),
            patch("line_messaging.MessagingApi", return_value=api),
        ):
            line_messaging.push_text(
                {
                    "userId": "U1",
                    "sourceType": "group",
                    "sourceId": "G1",
                    "quote_token": "quote-1",
                },
                "x" * 5001,
            )

        messages = (
            api.push_message_with_http_info.call_args.kwargs["push_message_request"].messages
        )
        self.assertEqual(messages[0].quote_token, "quote-1")
        self.assertIsNone(messages[1].quote_token)
        mock_config.assert_called_once()


if __name__ == "__main__":
    unittest.main()

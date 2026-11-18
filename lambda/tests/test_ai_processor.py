import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the lambda directory to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock environment variables before importing ai_processor
with patch.dict(
    os.environ,
    {
        "CONVERSATION_TABLE_NAME": "test-table",
        "SAMBA_NOVA_API_KEY_NAME": "test-samba-key",
        "GROQ_API_KEY_NAME": "test-groq-key",
        "AI_BACKEND": "groq",
    },
):
    import ai_processor
    from ai_processor import default_reasoning_effort, delete_conversation_history


class TestAiProcessor(unittest.TestCase):
    @patch("line_messaging.conversation_table")
    def test_delete_conversation_history_success(self, mock_table):
        """Test successful deletion of conversation history."""
        user_id = "test_user_123"
        mock_table.return_value.query.return_value = {
            "Items": [
                {"userId": user_id, "conversationId": "conv1"},
                {"userId": user_id, "conversationId": "conv2"},
            ]
        }
        mock_batch_writer = MagicMock()
        mock_table.return_value.batch_writer.return_value.__enter__.return_value = mock_batch_writer

        result = delete_conversation_history(user_id)

        self.assertTrue(result)
        mock_table.return_value.query.assert_called_once()
        self.assertEqual(mock_batch_writer.delete_item.call_count, 2)

    @patch("line_messaging.conversation_table")
    def test_delete_conversation_history_failure(self, mock_table):
        """Test failure in deleting conversation history."""
        user_id = "test_user_456"
        mock_table.return_value.query.side_effect = Exception("DynamoDB error")

        result = delete_conversation_history(user_id)

        self.assertFalse(result)
        mock_table.return_value.query.assert_called_once()


class TestDefaultReasoningEffort(unittest.TestCase):
    """The Groq reasoning_effort vocabularies are disjoint per model family."""

    def test_gpt_oss_gets_a_granular_effort(self):
        self.assertEqual(default_reasoning_effort("openai/gpt-oss-20b"), "medium")
        self.assertEqual(default_reasoning_effort("openai/gpt-oss-120b"), "medium")

    def test_qwen_gets_the_binary_vocabulary(self):
        self.assertEqual(default_reasoning_effort("qwen/qwen3.6-27b"), "none")

    def test_unknown_model_falls_back_to_none(self):
        self.assertEqual(default_reasoning_effort("some/new-model"), "none")


class TestGetAiResponse(unittest.TestCase):
    """Backend selection and the parameters handed to each provider."""

    def _stub_completion(self):
        """Build a client whose completion returns plain content, no tool call."""
        message = MagicMock()
        message.tool_calls = None
        message.content = "まいど！"
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        client = MagicMock()
        client.chat.completions.create.return_value = response
        return client

    @patch("ai_processor.get_groq_client")
    def test_groq_branch_passes_model_and_reasoning_effort(self, mock_get_client):
        client = self._stub_completion()
        mock_get_client.return_value = client

        with patch.object(ai_processor, "AI_SELECT", "groq"), patch.object(
            ai_processor, "GROQ_MODEL", "qwen/qwen3.6-27b"
        ), patch.object(ai_processor, "GROQ_REASONING_EFFORT", "none"):
            result = ai_processor.get_ai_response([{"role": "user", "content": "やあ"}])

        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "qwen/qwen3.6-27b")
        self.assertEqual(kwargs["reasoning_effort"], "none")
        self.assertFalse(result["hasToolCall"])
        self.assertEqual(result["aiResponse"], "まいど！")

    @patch("ai_processor.get_sambanova_client")
    def test_sambanova_branch_omits_reasoning_effort(self, mock_get_client):
        """SambaNova's OpenAI-compatible endpoint has no reasoning_effort param."""
        client = self._stub_completion()
        mock_get_client.return_value = client

        with patch.object(ai_processor, "AI_SELECT", "sambanova"), patch.object(
            ai_processor, "SAMBANOVA_MODEL", "DeepSeek-V3.2"
        ):
            ai_processor.get_ai_response([{"role": "user", "content": "やあ"}])

        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "DeepSeek-V3.2")
        self.assertNotIn("reasoning_effort", kwargs)
        # tool calling must stay enabled, otherwise search_with_grok never fires
        self.assertEqual(kwargs["tool_choice"], "auto")

    @patch("ai_processor.get_groq_client")
    def test_tool_call_is_handed_off_to_grok(self, mock_get_client):
        tool_call = MagicMock()
        tool_call.function.name = "search_with_grok"
        tool_call.function.arguments = '{"query": "最新のxAI", "prompt": "詳しく"}'
        message = MagicMock()
        message.tool_calls = [tool_call]
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        client = MagicMock()
        client.chat.completions.create.return_value = response
        mock_get_client.return_value = client

        with patch.object(ai_processor, "AI_SELECT", "groq"):
            result = ai_processor.get_ai_response([{"role": "user", "content": "調べて"}])

        self.assertTrue(result["hasToolCall"])
        self.assertEqual(result["toolName"], "search_with_grok")
        self.assertEqual(result["toolQuery"], "最新のxAI")
        self.assertEqual(result["toolPrompt"], "詳しく")


class TestDirectAnswerDelivery(unittest.TestCase):
    """ai_processor now delivers a direct answer itself; the workflow ends there."""

    def _stub_direct_answer(self, mock_get_client):
        message = MagicMock()
        message.tool_calls = None
        message.content = "まいど！"
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        client = MagicMock()
        client.chat.completions.create.return_value = response
        mock_get_client.return_value = client

    @patch("line_messaging.append_and_save")
    @patch("line_messaging.push_text")
    @patch("ai_processor.get_groq_client")
    def test_sends_and_records_the_answer(self, mock_get_client, mock_push, mock_save):
        self._stub_direct_answer(mock_get_client)
        event = {
            "userId": "U1",
            "sourceType": "user",
            "executionName": "exec-1",
            "conversationContext": {"userId": "U1", "messages": [{"role": "user", "content": "やあ"}]},
        }

        with patch.object(ai_processor, "AI_SELECT", "groq"):
            ai_processor.lambda_handler(event, None)

        mock_push.assert_called_once()
        self.assertEqual(mock_push.call_args.args[1], "まいど！")
        # the execution name is reused as the LINE retry key
        self.assertEqual(mock_push.call_args.kwargs["retry_key"], "exec-1")
        mock_save.assert_called_once()

    @patch("line_messaging.append_and_save")
    @patch("line_messaging.push_text")
    @patch("ai_processor.get_groq_client")
    def test_a_tool_call_only_sends_the_interim_notice(self, mock_get_client, mock_push, mock_save):
        tool_call = MagicMock()
        tool_call.function.name = "search_with_grok"
        tool_call.function.arguments = '{"query": "x", "prompt": ""}'
        message = MagicMock()
        message.tool_calls = [tool_call]
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        client = MagicMock()
        client.chat.completions.create.return_value = response
        mock_get_client.return_value = client

        event = {
            "userId": "U1",
            "sourceType": "user",
            "executionName": "exec-1",
            "conversationContext": {"userId": "U1", "messages": []},
        }
        with patch.object(ai_processor, "AI_SELECT", "groq"):
            result = ai_processor.lambda_handler(event, None)

        self.assertTrue(result["hasToolCall"])
        self.assertEqual(mock_push.call_args.args[1], ai_processor.INTERIM_MESSAGE)
        self.assertTrue(mock_push.call_args.kwargs["show_loading"])
        # the answer is not known yet, so nothing is recorded
        mock_save.assert_not_called()

    @patch("line_messaging.append_and_save")
    @patch("line_messaging.push_text", side_effect=Exception("LINE is down"))
    @patch("ai_processor.get_groq_client")
    def test_a_failed_interim_notice_does_not_lose_the_tool_call(
        self, mock_get_client, mock_push, mock_save
    ):
        tool_call = MagicMock()
        tool_call.function.name = "search_with_grok"
        tool_call.function.arguments = '{"query": "x", "prompt": ""}'
        message = MagicMock()
        message.tool_calls = [tool_call]
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        client = MagicMock()
        client.chat.completions.create.return_value = response
        mock_get_client.return_value = client

        event = {"userId": "U1", "conversationContext": {"userId": "U1", "messages": []}}
        with patch.object(ai_processor, "AI_SELECT", "groq"):
            result = ai_processor.lambda_handler(event, None)

        self.assertTrue(result["hasToolCall"])
        self.assertEqual(result["toolQuery"], "x")

    def test_interim_and_final_retry_keys_differ(self):
        """One key for both messages would make LINE drop the second."""
        final = "exec-1"
        interim = ai_processor._derive_retry_key(final, "interim")
        self.assertIsNotNone(interim)
        self.assertNotEqual(interim, final)
        # stable across calls, so a retry reuses it
        self.assertEqual(interim, ai_processor._derive_retry_key(final, "interim"))

    def test_no_execution_name_means_no_retry_key(self):
        self.assertIsNone(ai_processor._derive_retry_key(None, "interim"))


if __name__ == "__main__":
    unittest.main()

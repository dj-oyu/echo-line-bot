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
    @patch("ai_processor.conversation_table")
    def test_delete_conversation_history_success(self, mock_table):
        """Test successful deletion of conversation history."""
        user_id = "test_user_123"
        mock_table.query.return_value = {
            "Items": [
                {"userId": user_id, "conversationId": "conv1"},
                {"userId": user_id, "conversationId": "conv2"},
            ]
        }
        mock_batch_writer = MagicMock()
        mock_table.batch_writer.return_value.__enter__.return_value = mock_batch_writer

        result = delete_conversation_history(user_id)

        self.assertTrue(result)
        mock_table.query.assert_called_once()
        self.assertEqual(mock_batch_writer.delete_item.call_count, 2)

    @patch("ai_processor.conversation_table")
    def test_delete_conversation_history_failure(self, mock_table):
        """Test failure in deleting conversation history."""
        user_id = "test_user_456"
        mock_table.query.side_effect = Exception("DynamoDB error")

        result = delete_conversation_history(user_id)

        self.assertFalse(result)
        mock_table.query.assert_called_once()


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


if __name__ == "__main__":
    unittest.main()

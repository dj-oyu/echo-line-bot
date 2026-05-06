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
    from ai_processor import delete_conversation_history


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


if __name__ == "__main__":
    unittest.main()

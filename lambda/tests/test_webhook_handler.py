import unittest
from unittest.mock import patch, Mock
import os
import sys

# Add the lambda directory to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock AWS services and secrets before importing webhook_handler
with patch('boto3.client'), patch('boto3.resource'), \
     patch('webhook_handler.get_secret', return_value='test_secret'):
    from webhook_handler import strip_mentions, handle_message, get_conversation_context


class TestWebhookHandler(unittest.TestCase):

    def test_strip_mentions_basic_commands(self):
        """Test that basic commands are preserved without mentions."""
        test_cases = [
            ("/忘れて", "/忘れて"),
            ("/forget", "/forget"),
            ("  /忘れて  ", "/忘れて"),
            ("  /forget  ", "/forget"),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_mentions(input_text)
                self.assertEqual(result, expected)

    def test_strip_mentions_with_at_symbols(self):
        """Test mention stripping with @ symbols."""
        test_cases = [
            ("@ボット /忘れて", "/忘れて"),
            ("@bot /forget", "/forget"),
            ("@あいちゃん /忘れて", "/忘れて"),
            ("@user1 @bot /忘れて", "/忘れて"),
            ("@あいちゃん @他のユーザー /忘れて", "/忘れて"),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_mentions(input_text)
                self.assertEqual(result, expected)

    def test_strip_mentions_mixed_content(self):
        """Test mention stripping with mixed content."""
        test_cases = [
            ("@ボット こんにちは", "こんにちは"),
            ("@bot hello world", "hello world"),
            ("@user test message", "test message"),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_mentions(input_text)
                self.assertEqual(result, expected)

    def test_strip_mentions_edge_cases(self):
        """Test edge cases for mention stripping."""
        test_cases = [
            ("", ""),
            ("@bot", ""),
            ("@", "@"),  # Invalid mention format should be preserved
            ("   @bot   /forget   ", "/forget"),
            (None, None),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = strip_mentions(input_text)
                self.assertEqual(result, expected)

    @patch('webhook_handler.conversation_table')
    def test_get_conversation_context_new_conversation(self, mock_table):
        """Test creating a new conversation context."""
        user_id = 'test_user_123'
        mock_table.query.return_value = {'Items': []}
        
        result = get_conversation_context(user_id)
        
        self.assertEqual(result['userId'], user_id)
        self.assertIn('conv_', result['conversationId'])
        self.assertEqual(result['messages'], [])
        self.assertIn('ttl', result)
        mock_table.query.assert_called_once()

    @patch('webhook_handler.conversation_table')
    @patch('webhook_handler.datetime')
    def test_get_conversation_context_existing_active(self, mock_datetime, mock_table):
        """Test retrieving existing active conversation."""
        user_id = 'test_user_123'
        from datetime import datetime, timezone, timedelta
        
        # Mock active conversation (within 30 minutes)
        active_time = datetime.now(timezone.utc) - timedelta(minutes=15)
        mock_table.query.return_value = {
            'Items': [{
                'userId': user_id,
                'conversationId': 'conv_existing',
                'messages': [{'role': 'user', 'content': 'hello'}],
                'lastActivity': active_time.isoformat(),
                'ttl': 123456789
            }]
        }
        
        # Mock datetime.fromisoformat
        with patch('webhook_handler.datetime') as mock_dt:
            mock_dt.fromisoformat.return_value = active_time
            mock_dt.utcnow.return_value = datetime.now(timezone.utc)
            
            result = get_conversation_context(user_id)
        
        self.assertEqual(result['conversationId'], 'conv_existing')
        self.assertEqual(len(result['messages']), 1)

    @patch('webhook_handler.stepfunctions')
    @patch('webhook_handler.save_conversation_context')
    @patch('webhook_handler.get_conversation_context')
    @patch('webhook_handler.configuration')
    @patch('webhook_handler.get_bot_user_id')
    def test_handle_message_forget_command(self, mock_get_bot_id, mock_config, 
                                          mock_get_context, mock_save_context, mock_stepfunctions):
        """Test handling of forget command."""
        # Mock event for forget command in group chat
        mock_event = Mock()
        mock_event.source.user_id = 'user123'
        mock_event.message.text = '@ボット /忘れて'
        mock_event.reply_token = 'reply_token_123'
        mock_event.source.type = 'group'
        mock_event.source.group_id = 'group123'
        
        # Mock mention
        mock_mentionee = Mock()
        mock_mentionee.user_id = 'bot123'
        mock_event.message.mention.mentionees = [mock_mentionee]
        
        mock_get_bot_id.return_value = 'bot123'
        
        # Mock LINE API with proper context manager
        with patch('webhook_handler.ApiClient') as mock_api_client, \
             patch('webhook_handler.MessagingApi') as mock_messaging_api, \
             patch('webhook_handler.ai_processor') as mock_ai:
            
            mock_line_api = Mock()
            mock_messaging_api.return_value = mock_line_api
            mock_api_client.return_value.__enter__.return_value = mock_api_client.return_value
            mock_ai.delete_conversation_history.return_value = True
            
            handle_message(mock_event)
            
            # Verify delete was called
            mock_ai.delete_conversation_history.assert_called_once_with('user123')
            
            # Verify reply was sent
            mock_line_api.reply_message.assert_called_once()

    @patch('webhook_handler.stepfunctions')
    @patch('webhook_handler.save_conversation_context')
    @patch('webhook_handler.get_conversation_context')
    @patch('webhook_handler.start_ai_processing')
    @patch('webhook_handler.get_bot_user_id')
    def test_handle_message_regular_message_group(self, mock_get_bot_id, mock_start_ai,
                                                 mock_get_context, mock_save_context, mock_stepfunctions):
        """Test handling of regular message in group chat."""
        # Mock event for regular message in group chat
        mock_event = Mock()
        mock_event.source.user_id = 'user123'
        mock_event.message.text = '@ボット こんにちは'
        mock_event.reply_token = 'reply_token_123'
        mock_event.source.type = 'group'
        mock_event.source.group_id = 'group123'
        
        # Mock mention
        mock_mentionee = Mock()
        mock_mentionee.user_id = 'bot123'
        mock_event.message.mention.mentionees = [mock_mentionee]
        
        mock_get_bot_id.return_value = 'bot123'
        mock_get_context.return_value = {
            'userId': 'user123',
            'conversationId': 'conv123',
            'messages': [],
            'lastActivity': '2023-12-15T14:30:00Z',
            'ttl': 123456789
        }
        
        handle_message(mock_event)
        
        # Verify AI processing was started
        mock_start_ai.assert_called_once()

    @patch('webhook_handler.get_bot_user_id')
    def test_handle_message_group_no_mention(self, mock_get_bot_id):
        """Test that messages without mentions in groups are ignored."""
        # Mock event for message without mention in group
        mock_event = Mock()
        mock_event.source.user_id = 'user123'
        mock_event.message.text = 'hello'
        mock_event.source.type = 'group'
        mock_event.message.mention = None
        
        # This should return early and not process the message
        result = handle_message(mock_event)
        
        # Function should return None (early return)
        self.assertIsNone(result)

    @patch('webhook_handler.stepfunctions')
    @patch('webhook_handler.save_conversation_context')  
    @patch('webhook_handler.get_conversation_context')
    @patch('webhook_handler.start_ai_processing')
    def test_handle_message_direct_chat(self, mock_start_ai, mock_get_context, 
                                       mock_save_context, mock_stepfunctions):
        """Test handling of message in direct chat."""
        # Mock event for direct chat
        mock_event = Mock()
        mock_event.source.user_id = 'user123'
        mock_event.message.text = 'こんにちは'
        mock_event.reply_token = 'reply_token_123'
        mock_event.source.type = 'user'
        # No group_id or room_id for direct chat
        
        mock_get_context.return_value = {
            'userId': 'user123',
            'conversationId': 'conv123',
            'messages': [],
            'lastActivity': '2023-12-15T14:30:00Z',
            'ttl': 123456789
        }
        
        handle_message(mock_event)
        
        # Verify AI processing was started
        mock_start_ai.assert_called_once()


if __name__ == '__main__':
    # Set required environment variables for testing
    os.environ.setdefault('CONVERSATION_TABLE_NAME', 'test_table')
    os.environ.setdefault('STEP_FUNCTION_ARN', 'test_arn')
    os.environ.setdefault('CHANNEL_SECRET_NAME', 'test_secret')
    os.environ.setdefault('CHANNEL_ACCESS_TOKEN_NAME', 'test_token')
    
    unittest.main()
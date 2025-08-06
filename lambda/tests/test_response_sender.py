import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add the lambda directory to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

with patch('boto3.client'), patch('boto3.resource'), patch('response_sender.get_secret', return_value='token'):
    from response_sender import lambda_handler

class TestResponseSender(unittest.TestCase):
    @patch('response_sender.send_line_message')
    def test_missing_user_id_raises_error(self, mock_send):
        event = {
            'conversationContext': {'userId': 'uid123', 'messages': []},
            'aiResponse': 'hello'
        }
        with self.assertRaises(KeyError):
            lambda_handler(event, None)
        mock_send.assert_not_called()

if __name__ == '__main__':
    unittest.main()

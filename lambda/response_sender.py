import json
import logging
import os
import boto3
from datetime import datetime, timezone
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CHANNEL_ACCESS_TOKEN_NAME = os.getenv("CHANNEL_ACCESS_TOKEN_NAME")
CONVERSATION_TABLE_NAME = os.getenv("CONVERSATION_TABLE_NAME")

# AWS clients
secretsmanager = boto3.client('secretsmanager')
dynamodb = boto3.resource('dynamodb')
conversation_table = dynamodb.Table(CONVERSATION_TABLE_NAME)

def get_secret(secret_name: str) -> str:
    """Get secret value from AWS Secrets Manager.
    
    Args:
        secret_name: Name of the secret to retrieve
        
    Returns:
        The secret value as a string
        
    Raises:
        Exception: If secret retrieval fails
    """
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise

# LINE Bot setup
CHANNEL_ACCESS_TOKEN = get_secret(CHANNEL_ACCESS_TOKEN_NAME)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

def lambda_handler(event: dict, _context) -> dict:
    logger.info("Response Sender received event: %s", json.dumps(event, default=str))
    
    try:
        user_id = event['userId']
        source_type = event.get('sourceType')
        source_id = event.get('sourceId')
        
        # Determine the response to send
        # If grokResponse exists, it's the final response. Otherwise, it's a direct AI response.
        message_to_send = event.get('grokResponse') or event.get('aiResponse')

        if not message_to_send:
            logger.warning("No message found to send. Skipping.")
            return event

        # Determine the target ID for the push message
        target_id = source_id if source_type in ("group", "room") else user_id
        send_line_message(target_id, message_to_send)

        # If it was a final response (from Grok), save it to the conversation history
        if 'grokResponse' in event:
            conversation_context = event['conversationContext']
            conversation_context['messages'].append({
                'role': 'assistant',
                'content': message_to_send,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            save_conversation_context(user_id, conversation_context)

        return event
    
    except Exception as e:
        logger.error(f"Error in response sender: {e}")
        # Try to send a generic error message to the user
        try:
            user_id = event.get('userId')
            if user_id:
                send_line_message(user_id, "申し訳ございません。応答の送信中にエラーが発生しました。")
        except Exception as inner_e:
            logger.error(f"Failed to send error message to user: {inner_e}")
        raise

def send_line_message(to_id: str, message: str) -> None:
    """Send message to a LINE destination using the Push API.
    
    Args:
        to_id: LINE user or group ID to send message to
        message: Message text to send
        
    Raises:
        Exception: If message sending fails
    """
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message_with_http_info(
                push_message_request=PushMessageRequest(
                    to=to_id,
                    messages=[TextMessage(text=message)]
                )
            )
        logger.info(f"Sent message to {to_id}: {message}")
    except Exception as e:
        logger.error(f"Error sending LINE message: {e}")
        raise e

def save_conversation_context(user_id: str, conversation_context: dict) -> None:
    """Save conversation context to DynamoDB.
    
    Args:
        user_id: User ID for the conversation
        conversation_context: Conversation data to save
    """
    try:
        # Clean up old messages before saving
        messages = conversation_context['messages']
        if len(messages) > 20:
            conversation_context['messages'] = messages[-20:]
            logger.info(f"Cleaned up conversation, kept last 20 messages")

        conversation_context['lastActivity'] = datetime.now(timezone.utc).isoformat()
        conversation_table.put_item(Item=conversation_context)
        logger.info(f"Saved conversation context for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving conversation context: {e}")

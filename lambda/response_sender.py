import json
import logging
import os
from datetime import datetime, timezone

import boto3
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CHANNEL_ACCESS_TOKEN_NAME = os.environ["CHANNEL_ACCESS_TOKEN_NAME"]
CONVERSATION_TABLE_NAME = os.environ["CONVERSATION_TABLE_NAME"]

# AWS clients
secretsmanager = boto3.client("secretsmanager")
dynamodb = boto3.resource("dynamodb")
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
        return response["SecretString"]
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise


# LINE Bot setup
CHANNEL_ACCESS_TOKEN = get_secret(CHANNEL_ACCESS_TOKEN_NAME)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)


def lambda_handler(event: dict, _context) -> dict:
    logger.info("Response Sender received event: %s", json.dumps(event, default=str))

    try:
        user_id: str = event["userId"]
        source_type: str | None = event.get("sourceType")
        source_id: str | None = event.get("sourceId")

        # Determine the response to send
        # If grokResponse exists, it's the final response. Otherwise, it's a direct AI response.
        message_to_send: str | None = event.get("grokResponse") or event.get("aiResponse")

        if not message_to_send:
            logger.warning("No message found to send. Skipping.")
            return event

        # Determine the target ID for the push message
        target_id = source_id if source_type in ("group", "room") and source_id else user_id

        # Get quote token if available for group/room messages
        quote_token: str | None = event.get("quote_token")
        send_line_message(target_id, message_to_send, quote_token, source_type)

        # If it was a final response (from Grok), save it to the conversation history
        if "grokResponse" in event:
            conversation_context = event["conversationContext"]
            conversation_context["messages"].append(
                {
                    "role": "assistant",
                    "content": message_to_send,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            save_conversation_context(user_id, conversation_context)

        return event

    except Exception as e:
        logger.error(f"Error in response sender: {e}")
        # Try to send a generic error message to the user
        try:
            error_user_id: str | None = event.get("userId")
            if error_user_id:
                send_line_message(
                    error_user_id, "申し訳ございません。応答の送信中にエラーが発生しました。"
                )
        except Exception as inner_e:
            logger.error(f"Failed to send error message to user: {inner_e}")
        raise


def send_line_message(
    to_id: str, message: str, quote_token: str | None = None, source_type: str | None = None
) -> None:
    """Send message to a LINE destination using the Push API.

    Args:
        to_id: LINE user or group ID to send message to
        message: Message text to send
        quote_token: Quote token for replying to a specific message
        source_type: Source type (group, room, user)

    Raises:
        Exception: If message sending fails
    """
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            # Create text message with quote token if available (for group/room chats)
            text_message = TextMessage(
                text=message,
                quoteToken=quote_token
                if quote_token and source_type in ("group", "room")
                else None,
            )

            line_bot_api.push_message_with_http_info(
                push_message_request=PushMessageRequest(to=to_id, messages=[text_message])
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
        messages = conversation_context["messages"]
        if len(messages) > 20:
            conversation_context["messages"] = messages[-20:]
            logger.info("Cleaned up conversation, kept last 20 messages")

        conversation_context["lastActivity"] = datetime.now(timezone.utc).isoformat()
        conversation_table.put_item(Item=conversation_context)
        logger.info(f"Saved conversation context for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving conversation context: {e}")

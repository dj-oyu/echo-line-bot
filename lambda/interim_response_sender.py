import json
import logging
import os

import boto3
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ShowLoadingAnimationRequest,
    TextMessage,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CHANNEL_ACCESS_TOKEN_NAME = os.environ["CHANNEL_ACCESS_TOKEN_NAME"]

# AWS clients
secretsmanager = boto3.client("secretsmanager")


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
    logger.info("Interim Response Sender received event: %s", json.dumps(event, default=str))

    try:
        user_id: str = event["userId"]
        source_type: str | None = event.get("sourceType")
        source_id: str | None = event.get("sourceId")

        # Determine the target ID for the push message
        target_id = source_id if source_type in ("group", "room") and source_id else user_id

        # Send a fixed interim message
        interim_message = (
            "なんやややこしい質問やな～ 今こびとさんに調べてきてもろとるから待っとき！"
        )

        # Show loading dots first (1-on-1 only) so the order in chat is:
        # typing indicator → interim text → final answer.
        if source_type not in ("group", "room"):
            show_loading(user_id)

        # Get quote token if available for group/room messages
        quote_token: str | None = event.get("quote_token")
        send_line_message(target_id, interim_message, quote_token, source_type)

        # Pass the original event payload through to the next step
        return event

    except Exception as e:
        logger.error(f"Error in interim response sender: {e}")
        # Propagate the error to stop the workflow
        raise


def show_loading(user_id: str, seconds: int = 60) -> None:
    """Show LINE typing-style loading animation for a 1-on-1 chat.

    Best-effort: any failure is logged and swallowed so the workflow proceeds.
    """
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.show_loading_animation(
                show_loading_animation_request=ShowLoadingAnimationRequest(
                    chatId=user_id, loadingSeconds=seconds
                )
            )
        logger.info("Showed loading animation for %s (%ds)", user_id, seconds)
    except Exception as e:
        logger.warning("Failed to show loading animation: %s", e)


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
        logger.info(f"Sent interim message to {to_id}: {message}")
    except Exception as e:
        logger.error(f"Error sending LINE message: {e}")
        raise e

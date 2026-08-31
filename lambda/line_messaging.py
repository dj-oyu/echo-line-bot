"""Shared LINE messaging and conversation persistence.

Every handler used to carry its own copy of this logic: `get_secret` existed
in four places, `save_conversation_context` in two — and the two copies
disagreed, so the direct-answer path never trimmed history while the search
path did.

Everything here initializes lazily. These helpers sit on paths that some
handlers never take, and Lambda cold start is CPU-starved at 128 MB, so an
unused boto3 client or linebot import is measurable latency rather than a
rounding error.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger()

# Keeping the whole history would grow the prompt without bound; the README
# has always claimed a 20-message cap, but only response_sender enforced it.
MAX_HISTORY_MESSAGES = 20

_secretsmanager = None
_conversation_table = None
_line_configuration = None


def _secrets_client():
    """Get or create the Secrets Manager client."""
    global _secretsmanager
    if _secretsmanager is None:
        _secretsmanager = boto3.client("secretsmanager")
    return _secretsmanager


def conversation_table():
    """Get or create the DynamoDB conversation table resource."""
    global _conversation_table
    if _conversation_table is None:
        _conversation_table = boto3.resource("dynamodb").Table(
            os.environ["CONVERSATION_TABLE_NAME"]
        )
    return _conversation_table


def get_secret(secret_name: str) -> str:
    """Get a secret's raw string value.

    Args:
        secret_name: Name of the secret to retrieve

    Returns:
        The secret value as a string

    Raises:
        Exception: If secret retrieval fails
    """
    try:
        return _secrets_client().get_secret_value(SecretId=secret_name)["SecretString"]
    except Exception as e:
        logger.error("Error retrieving secret %s: %s", secret_name, e)
        raise


def get_secret_json(secret_name: str) -> dict[str, Any]:
    """Get a secret whose value is a JSON object.

    Args:
        secret_name: Name of the secret to retrieve

    Returns:
        The parsed secret

    Raises:
        Exception: If retrieval or parsing fails
    """
    result: dict[str, Any] = json.loads(get_secret(secret_name))
    return result


def resolve_target_id(event: dict) -> str:
    """Pick the push destination for an event.

    Group and room messages go back to the group, not the individual sender.

    Args:
        event: Handler event carrying userId and optionally sourceType/sourceId

    Returns:
        The LINE id to push to
    """
    source_type = event.get("sourceType")
    source_id = event.get("sourceId")
    if source_type in ("group", "room") and source_id:
        return str(source_id)
    return str(event["userId"])


def _configuration():
    """Get or create the Messaging API configuration, cached per container."""
    global _line_configuration
    if _line_configuration is None:
        from linebot.v3.messaging import Configuration

        _line_configuration = Configuration(
            access_token=get_secret(os.environ["CHANNEL_ACCESS_TOKEN_NAME"])
        )
    return _line_configuration


def push_text(
    event: dict,
    text: str,
    retry_key: str | None = None,
    show_loading: bool = False,
) -> None:
    """Push a text message to the event's source.

    linebot is imported here rather than at module scope so handlers that do
    not send on a given path pay nothing for it.

    Args:
        event: Handler event carrying userId, sourceType, sourceId, quote_token
        text: Message body
        retry_key: Value for X-Line-Retry-Key. Step Functions retries a task on
            Lambda service exceptions even when the function already ran, so
            without this a retry delivers the message twice.
        show_loading: Show the typing indicator first (1-on-1 chats only)

    Raises:
        Exception: If the push fails
    """
    from linebot.v3.messaging import (
        ApiClient,
        MessagingApi,
        PushMessageRequest,
        ShowLoadingAnimationRequest,
        TextMessage,
    )

    source_type = event.get("sourceType")
    target_id = resolve_target_id(event)

    with ApiClient(_configuration()) as api_client:
        line_bot_api = MessagingApi(api_client)

        if show_loading and source_type not in ("group", "room"):
            # Best effort: a missing typing indicator must not cost the message.
            try:
                line_bot_api.show_loading_animation(
                    show_loading_animation_request=ShowLoadingAnimationRequest(
                        chatId=str(event["userId"]), loadingSeconds=60
                    )
                )
            except Exception as e:
                logger.warning("Failed to show loading animation: %s", e)

        quote_token = event.get("quote_token")
        message = TextMessage(
            text=text,
            quoteToken=quote_token if quote_token and source_type in ("group", "room") else None,
        )
        kwargs: dict[str, Any] = {"push_message_request": PushMessageRequest(
            to=target_id, messages=[message]
        )}
        if retry_key:
            kwargs["x_line_retry_key"] = retry_key
        line_bot_api.push_message_with_http_info(**kwargs)

    logger.info("Pushed message to %s", target_id)


def append_and_save(user_id: str, conversation_context: dict, content: str) -> None:
    """Append an assistant message to the history and persist it.

    Args:
        user_id: Conversation owner
        conversation_context: The context dict travelling through the workflow
        content: Assistant message to record

    Raises:
        Exception: If the write fails
    """
    conversation_context["messages"].append(
        {
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_conversation_context(user_id, conversation_context)


def save_conversation_context(user_id: str, conversation_context: dict) -> None:
    """Persist the conversation, trimming it to the most recent messages.

    Args:
        user_id: Conversation owner
        conversation_context: Context to write

    Raises:
        Exception: If the write fails
    """
    try:
        messages = conversation_context["messages"]
        if len(messages) > MAX_HISTORY_MESSAGES:
            conversation_context["messages"] = messages[-MAX_HISTORY_MESSAGES:]
            logger.info("Trimmed conversation to the last %d messages", MAX_HISTORY_MESSAGES)

        conversation_context["lastActivity"] = datetime.now(timezone.utc).isoformat()
        conversation_table().put_item(Item=conversation_context)
        logger.info("Saved conversation context for user %s", user_id)
    except Exception as e:
        logger.error("Error saving conversation context: %s", e)
        raise

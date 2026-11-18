"""Shared LINE messaging and conversation persistence.

Every handler used to carry its own copy of this logic: `get_secret` existed
in four places, `save_conversation_context` in two — and the two copies
disagreed, so the direct-answer path never trimmed history while the search
path did.

linebot is imported at module scope on purpose. Lambda runs the init phase
at boosted CPU regardless of memorySize, while the handler phase is throttled
in proportion to memory — so deferring a *mandatory* import moves it from the
fast phase into the slow one. Every importer of this module ends up calling
`push_text`, and when the import was lazy a cold ai_processor spent 6.0 s
between receiving the model's answer and delivering it (0.12 s warm). At
128 MB the same import hung until the function timed out and the answer was
lost. Only genuinely conditional work stays lazy here: the boto3 clients,
which not every caller touches.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, cast

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

# Keeping the whole history would grow the prompt without bound; the README
# has always claimed a 20-message cap, but only response_sender enforced it.
MAX_HISTORY_MESSAGES = 20
MAX_TEXT_MESSAGE_LENGTH = 5000
MAX_MESSAGES_PER_REQUEST = 5

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
        return cast(str, _secrets_client().get_secret_value(SecretId=secret_name)["SecretString"])
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
        _line_configuration = Configuration(
            access_token=get_secret(os.environ["CHANNEL_ACCESS_TOKEN_NAME"])
        )
    return _line_configuration


def split_text(text: str, max_length: int = MAX_TEXT_MESSAGE_LENGTH) -> list[str]:
    """Split text without losing content, preferring readable boundaries."""
    if max_length <= 0:
        raise ValueError("max_length must be positive")
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_length:
        window = remaining[:max_length]
        break_at = 0
        minimum_boundary = max_length // 2
        for boundary in ("\n\n", "\n", "。", "！", "？", ". ", " "):
            position = window.rfind(boundary)
            if position >= minimum_boundary:
                break_at = max(break_at, position + len(boundary))

        chunks.append(remaining[: break_at or max_length])
        remaining = remaining[break_at or max_length :]

    chunks.append(remaining)
    return chunks


def _batch_retry_key(retry_key: str | None, batch_index: int) -> str | None:
    if retry_key is None or batch_index == 0:
        return retry_key
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{retry_key}/push-batch/{batch_index}"))


def push_text(
    event: dict,
    text: str,
    retry_key: str | None = None,
    show_loading: bool = False,
) -> None:
    """Push text to the event's source, respecting LINE message limits.

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

        quote_token = (
            event.get("quote_token") if source_type in ("group", "room") else None
        )
        chunks = split_text(text)
        for batch_index, start in enumerate(
            range(0, len(chunks), MAX_MESSAGES_PER_REQUEST)
        ):
            batch_start = start
            messages = [
                TextMessage.from_dict(
                    {
                        "type": "text",
                        "text": chunk,
                        "quoteToken": (
                            quote_token
                            if chunk_index == 0 and batch_start == 0
                            else None
                        ),
                    }
                )
                for chunk_index, chunk in enumerate(
                    chunks[start : start + MAX_MESSAGES_PER_REQUEST]
                )
            ]
            kwargs: dict[str, Any] = {
                "push_message_request": PushMessageRequest.from_dict(
                    {
                        "to": target_id,
                        "messages": [message.to_dict() for message in messages],
                    }
                )
            }
            batch_retry_key = _batch_retry_key(retry_key, batch_index)
            if batch_retry_key:
                kwargs["x_line_retry_key"] = batch_retry_key
            line_bot_api.push_message_with_http_info(**kwargs)

    logger.info("Pushed %d message part(s) to %s", len(chunks), target_id)


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

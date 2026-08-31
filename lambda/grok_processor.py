import json
import logging
import os
from typing import Any

import boto3
from markdown_to_line import format_with_citations, merge_citations, render_to_line
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
XAI_API_KEY_SECRET_NAME = os.environ["XAI_API_KEY_SECRET_NAME"]

# AWS clients
secretsmanager = boto3.client("secretsmanager")


def get_secret(secret_name: str) -> dict[str, Any]:
    """Get secret value from AWS Secrets Manager.

    Args:
        secret_name: Name of the secret to retrieve

    Returns:
        The secret value as a dictionary

    Raises:
        Exception: If secret retrieval fails
    """
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_name)
        secret_string = response["SecretString"]
        result: dict[str, Any] = json.loads(secret_string)
        return result
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise


# xAI client (lazy initialization)
XAI_API_KEY = None


def get_xai_api_key() -> str:
    """Get xAI API key from AWS Secrets Manager.

    Returns:
        The xAI API key as a string

    Raises:
        Exception: If API key retrieval fails
    """
    global XAI_API_KEY
    if XAI_API_KEY is None:
        try:
            xai_api_key_data = get_secret(XAI_API_KEY_SECRET_NAME)
            XAI_API_KEY = str(xai_api_key_data["XAI_API_KEY"])
        except Exception as e:
            logger.error(f"Error retrieving xAI API key: {e}")
            raise
    return XAI_API_KEY


def call_grok_api(query: str, prompt: str | None) -> tuple[str, str]:
    """Call xAI Grok API for search using official SDK.

    Args:
        query: Search query string

    Returns:
        Tuple of `(final_response, body_only)`. `final_response` is what is sent
        to the user (body + citation footer). `body_only` is the same body
        without the footer, to be saved into conversation history so that
        future turns are not polluted by URL footers.
    """
    try:
        logger.info(f"Calling Grok with query: {query}")
        logger.info(f"Using prompt: {prompt if prompt else 'No prompt provided'}")

        # Initialize xAI client
        client = Client(api_key=get_xai_api_key())

        # Create chat with web search tool (Agent Tools API)
        chat = client.chat.create(
            model="grok-4.6",
            tools=[web_search()],
        )

        # Create search prompt in Japanese
        search_prompt = f"""
以下について詳しく調べて、関西弁で分かりやすく教えて: {query}
{prompt if prompt else ""}
"""
        chat.append(user(search_prompt))

        # Get response
        response = chat.sample()

        try:
            api_citations = list(response.citations) if response.citations else []
        except (AttributeError, TypeError):
            api_citations = []
        if api_citations:
            logger.info("Grok web_search citations: %s", api_citations)

        plain_body, body_urls = render_to_line(str(response.content or ""))
        merged = merge_citations(api_citations, body_urls)
        final = format_with_citations(plain_body, merged)
        return final, plain_body

    except Exception as e:
        logger.error(f"Error calling Grok API: {e}")
        fallback = "ごめんやで～、こびとさんが情報見つけられへんかった...。もうちょっと簡単な言葉で聞いてみてくれる？"
        return fallback, fallback


def lambda_handler(event: dict, _context) -> dict:
    logger.info("Grok Processor received event: %s", json.dumps(event, default=str))

    query = event.get("toolQuery")
    if not query:
        raise ValueError("No query found in the event payload")
    prompt = event.get("toolPrompt", "")

    try:
        grok_response, grok_body = call_grok_api(query, prompt)
        logger.info(f"Grok response received: {grok_response}")

        # `grokResponse` is sent to the user (body + citation footer).
        # `grokBody` is saved into history without the footer so future LLM
        # turns are not polluted by URL lists.
        response_data = {
            "grokResponse": grok_response,
            "grokBody": grok_body,
            "userId": event.get("userId"),
            "conversationContext": event.get("conversationContext"),
            "sourceType": event.get("sourceType"),
            "sourceId": event.get("sourceId"),
        }

        # Include quote_token if present
        if "quote_token" in event:
            response_data["quote_token"] = event["quote_token"]

        return response_data

    except Exception as e:
        logger.error(f"Error in Grok processor: {e}")
        fallback = "ごめんやで〜、こびとさんが情報見つけられへんかったわ...。もうちょっと簡単な言葉で聞いてみてくれる？"
        error_response = {
            "grokResponse": fallback,
            "grokBody": fallback,
            "userId": event.get("userId"),
            "conversationContext": event.get("conversationContext"),
            "sourceType": event.get("sourceType"),
            "sourceId": event.get("sourceId"),
        }

        # Include quote_token if present
        if "quote_token" in event:
            error_response["quote_token"] = event["quote_token"]

        return error_response

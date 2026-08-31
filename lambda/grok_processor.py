import json
import logging
import os

import line_messaging
from markdown_to_line import format_with_citations, merge_citations, render_to_line
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
XAI_API_KEY_SECRET_NAME = os.environ["XAI_API_KEY_SECRET_NAME"]
# Named XAI_MODEL rather than GROK_MODEL: the latter is one letter from the
# ai_processor's GROQ_MODEL, and swapping those two values 400s every request.
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-4.6")

# xAI client (lazy initialization)
XAI_API_KEY = None
XAI_CLIENT: Client | None = None


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
            xai_api_key_data = line_messaging.get_secret_json(XAI_API_KEY_SECRET_NAME)
            XAI_API_KEY = str(xai_api_key_data["XAI_API_KEY"])
        except Exception as e:
            logger.error(f"Error retrieving xAI API key: {e}")
            raise
    return XAI_API_KEY


def get_xai_client() -> Client:
    """Get or create the xAI client.

    Built lazily rather than at import time so the Secrets Manager call stays
    out of cold start, then reused so warm invocations skip connection setup.

    Returns:
        Client configured with the xAI API key
    """
    global XAI_CLIENT
    if XAI_CLIENT is None:
        XAI_CLIENT = Client(api_key=get_xai_api_key())
    return XAI_CLIENT


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

        # Create chat with web search tool (Agent Tools API)
        chat = get_xai_client().chat.create(
            model=XAI_MODEL,
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
        return fallback, ""


def lambda_handler(event: dict, _context) -> dict:
    logger.info("Grok Processor received event: %s", json.dumps(event, default=str))

    query = event.get("toolQuery")
    if not query:
        raise ValueError("No query found in the event payload")

    grok_response, grok_body = call_grok_api(query, event.get("toolPrompt", ""))
    event["grokResponse"] = grok_response
    event["grokBody"] = grok_body

    # This stage owns delivery: the workflow ends here.
    line_messaging.push_text(event, grok_response, retry_key=event.get("executionName"))

    # `grok_body` is empty when the search failed and grok_response is the
    # apology. Recording that would leave a fake assistant failure in the
    # context of every later turn.
    if grok_body:
        conversation_context = event.get("conversationContext")
        if conversation_context:
            line_messaging.append_and_save(event["userId"], conversation_context, grok_body)

    return event

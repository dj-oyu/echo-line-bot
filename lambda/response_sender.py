"""Failure notifier.

This used to be the pipeline's send stage. Sending now happens in the stage
that produces the message — ai_processor for a direct answer, grok_processor
for a search result — which removes a Lambda cold start from every request.

What remains is the Step Functions Catch target: the one path where the
producing stage died before it could say anything. Nothing here is on the
happy path, so its own cold start costs nothing that matters.
"""

import json
import logging

import line_messaging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

FAILURE_MESSAGE = "うわ〜😭 あいちゃんなんか失敗してもうた！ちょっと時間置いてもう一回話しかけてな〜"


def lambda_handler(event: dict, _context) -> dict:
    """Tell the user their message could not be answered.

    Reached only through a Catch, so the event is the original workflow input
    plus an `error` key added by Step Functions.

    Args:
        event: Workflow input carrying userId and source information

    Returns:
        The event, unchanged
    """
    logger.info("Failure notifier received event: %s", json.dumps(event, default=str))

    if not event.get("userId"):
        logger.error("No userId in event; cannot notify anyone")
        return event

    try:
        line_messaging.push_text(event, FAILURE_MESSAGE)
    except Exception as e:
        # Nothing left to fall back to; log loudly and let the execution end.
        logger.error("Failed to notify the user of the failure: %s", e)

    return event

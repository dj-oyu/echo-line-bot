import json
import requests
import logging
import os
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    # API Key authentication
    headers = event.get('headers', {})

    if 'body' not in event:
        logger.error("No body in event")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Bad Request'})
        }

    body = event['body']
    signature = headers.get('x-line-signature')

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid Signature'})
        }

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'OK'})
    }

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    logger.info("Dumping event: %s", json.dumps(event, default=str))
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            reply_message_request=ReplyMessageRequest(
                replyToken=event.reply_token,
                messages=[TextMessage(text=event.message.text)]
            )
        )

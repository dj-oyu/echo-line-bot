import json
import logging
import os
import re
import openai
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

BOT_USER_ID = None

def get_bot_user_id():
    """Retrieve and cache the bot's own user ID"""
    global BOT_USER_ID
    if BOT_USER_ID is None:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            BOT_USER_ID = line_bot_api.get_bot_info().user_id
    return BOT_USER_ID


def strip_mentions(text: str) -> str:
    """Remove '@username' style mentions from text"""
    if not text:
        return text
    cleaned = re.sub(r"@\S+", "", text)
    return re.sub(r"\s+", " ", cleaned).strip()

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
SAMBANOVA_API_KEY = os.getenv("SAMBA_NOVA_API_KEY")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Initialize SambaNova client
sambanova_client = openai.OpenAI(
    api_key=SAMBANOVA_API_KEY,
    base_url="https://api.sambanova.ai/v1",
)

def get_ai_response(user_message):
    """Get response from SambaNova DeepSeek-V3-0324 model"""
    try:
        logger.info(f"Calling SambaNova API with message: {user_message}")
        if not SAMBANOVA_API_KEY:
            logger.error("SambaNova API key is not set")
            return "申し訳ございません。AIサービスの設定に問題があります。"
        
        response = sambanova_client.chat.completions.create(
            model="DeepSeek-V3-0324",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant. Respond in Japanese if the user writes in Japanese, otherwise respond in the same language as the user."},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        logger.info(f"SambaNova API response received: {response.choices[0].message.content}")
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error calling SambaNova API: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        return "申し訳ございません。現在、AIサービスに接続できません。後でもう一度お試しください。"

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

    source_type = event.source.type
    user_message = event.message.text
    sanitized_message = strip_mentions(user_message)

    # Check mentions when in group or room
    if source_type in ("group", "room"):
        mention = event.message.mention
        if not mention:
            logger.info("No mention found in group message; ignoring")
            return
        bot_id = get_bot_user_id()
        if all(m.user_id != bot_id for m in mention.mentionees):
            logger.info("Bot not mentioned; ignoring message")
            return

    # Get AI response from SambaNova
    ai_response = get_ai_response(sanitized_message)
    
    logger.info(f"User message: {user_message}")
    logger.info(f"Sanitized message: {sanitized_message}")
    logger.info(f"AI response: {ai_response}")
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            reply_message_request=ReplyMessageRequest(
                replyToken=event.reply_token,
                messages=[TextMessage(text=ai_response)]
            )
        )

import json
import logging
import os
import re
import boto3
from datetime import datetime, timedelta
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CONVERSATION_TABLE_NAME = os.getenv("CONVERSATION_TABLE_NAME")
STEP_FUNCTION_ARN = os.getenv("STEP_FUNCTION_ARN")

# AWS clients
dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')
conversation_table = dynamodb.Table(CONVERSATION_TABLE_NAME)

# LINE Bot setup
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

BOT_USER_ID = None

def get_bot_user_id():
    """Retrieve and cache the bot's own user ID"""
    global BOT_USER_ID
    if BOT_USER_ID is None:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            BOT_USER_ID = line_bot_api.get_bot_info().user_id
    return BOT_USER_ID

def strip_mentions(text):
    """Remove '@username' style mentions from text"""
    if not text:
        return text
    cleaned = re.sub(r"@\S+", "", text)
    # collapse multiple spaces left after removal
    return re.sub(r"\s+", " ", cleaned).strip()

def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))
    
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
    logger.info("Handling message event: %s", json.dumps(event, default=str))
    
    user_id = event.source.user_id
    user_message = event.message.text
    sanitized_message = strip_mentions(user_message)
    source_type = event.source.type
    source_id = getattr(event.source, f"{source_type}_id", None)
    reply_token = event.reply_token

    # Check mentions when in group or room
    if source_type in ("group", "room"):
        mention = event.message.mention
        if not mention:
            logger.info("No mention found in group message; ignoring")
            return
        bot_id = get_bot_user_id()
        if all(
            (getattr(m, "user_id", None) != bot_id)
            and not getattr(m, "is_self", False)
            for m in mention.mentionees
        ):
            logger.info("Bot not mentioned; ignoring message")
            return
    
    # No immediate response - will respond via Push API after processing
    
    # Get or create conversation context
    conversation_context = get_conversation_context(user_id)

    # Add user message to conversation
    logger.info(f"Sanitized message: {sanitized_message}")
    conversation_context['messages'].append({
        'role': 'user',
        'content': sanitized_message,
        'timestamp': datetime.utcnow().isoformat()
    })
    
    # Save conversation context
    save_conversation_context(user_id, conversation_context)
    
    # Start Step Functions workflow
    start_ai_processing(user_id, conversation_context, source_type, source_id)

def get_conversation_context(user_id):
    """Get existing conversation context or create new one"""
    try:
        # Get most recent conversation
        response = conversation_table.query(
            KeyConditionExpression="userId = :user_id",
            ExpressionAttributeValues={":user_id": user_id},
            ScanIndexForward=False,
            Limit=1
        )
        
        if response['Items']:
            conversation = response['Items'][0]
            
            # Check if conversation is still active (within 30 minutes)
            last_activity = datetime.fromisoformat(conversation['lastActivity'])
            if datetime.utcnow() - last_activity < timedelta(minutes=30):
                return conversation
        
        # Create new conversation
        conversation_id = f"conv_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        return {
            'userId': user_id,
            'conversationId': conversation_id,
            'messages': [],
            'lastActivity': datetime.utcnow().isoformat(),
            'ttl': int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        }
    
    except Exception as e:
        logger.error(f"Error getting conversation context: {e}")
        # Return new conversation on error
        conversation_id = f"conv_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        return {
            'userId': user_id,
            'conversationId': conversation_id,
            'messages': [],
            'lastActivity': datetime.utcnow().isoformat(),
            'ttl': int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        }

def save_conversation_context(user_id, conversation_context):
    """Save conversation context to DynamoDB"""
    try:
        conversation_context['lastActivity'] = datetime.utcnow().isoformat()
        conversation_table.put_item(Item=conversation_context)
        logger.info(f"Saved conversation context for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving conversation context: {e}")

def start_ai_processing(user_id, conversation_context, source_type, source_id):
    """Start Step Functions workflow for AI processing"""
    try:
        input_data = {
            'userId': user_id,
            'conversationContext': conversation_context,
            'sourceType': source_type,
            'sourceId': source_id,
        }
        
        response = stepfunctions.start_execution(
            stateMachineArn=STEP_FUNCTION_ARN,
            input=json.dumps(input_data, default=str)
        )
        
        logger.info(f"Started Step Functions execution: {response['executionArn']}")
    except Exception as e:        logger.error(f"Error starting Step Functions: {e}")

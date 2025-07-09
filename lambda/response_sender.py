import json
import logging
import os
import boto3
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CONVERSATION_TABLE_NAME = os.getenv("CONVERSATION_TABLE_NAME")

# AWS clients
dynamodb = boto3.resource('dynamodb')
conversation_table = dynamodb.Table(CONVERSATION_TABLE_NAME)

# LINE Bot setup
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

def lambda_handler(event, context):
    logger.info("Response Sender received event: %s", json.dumps(event, default=str))
    
    try:
        user_id = event['userId']
        ai_response = event['aiResponse']
        source_type = event.get('sourceType')
        source_id = event.get('sourceId')
        
        # Send response to the appropriate destination
        target_id = source_id if source_type in ("group", "room") else user_id
        send_line_message(target_id, ai_response)
        
        return {
            'statusCode': 200,
            'message': 'Response sent successfully',
            'userId': user_id,
            'sourceType': source_type,
            'sourceId': source_id,
        }
    
    except Exception as e:
        logger.error(f"Error in response sender: {e}")
        
        # Try to send error message to user if possible
        try:
            user_id = event.get('userId')
            if user_id:
                send_line_message(user_id, "申し訳ございません。応答の送信中にエラーが発生しました。")
        except:
            pass
        
        return {
            'statusCode': 500,
            'error': str(e),
            'sourceType': event.get('sourceType'),
            'sourceId': event.get('sourceId')
        }

def send_line_message(to_id, message):
    """Send message to LINE destination using Push API"""
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            line_bot_api.push_message_with_http_info(
                push_message_request=PushMessageRequest(
                    to=to_id,
                    messages=[TextMessage(text=message)]
                )
            )

        logger.info(f"Sent message to {to_id}: {message}")
    
    except Exception as e:
        logger.error(f"Error sending LINE message: {e}")        raise e

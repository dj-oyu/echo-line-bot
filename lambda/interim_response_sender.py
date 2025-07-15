
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
CHANNEL_ACCESS_TOKEN_NAME = os.getenv("CHANNEL_ACCESS_TOKEN_NAME")

# AWS clients
secretsmanager = boto3.client('secretsmanager')

# Function to get secrets from Secrets Manager
def get_secret(secret_name):
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise

# LINE Bot setup
CHANNEL_ACCESS_TOKEN = get_secret(CHANNEL_ACCESS_TOKEN_NAME)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

def lambda_handler(event, context):
    logger.info("Interim Response Sender received event: %s", json.dumps(event, default=str))
    
    try:
        user_id = event['userId']
        source_type = event.get('sourceType')
        source_id = event.get('sourceId')
        
        # Determine the target ID for the push message
        target_id = source_id if source_type in ("group", "room") else user_id
        
        # Send a fixed interim message
        interim_message = "なんやややこしい質問やな～ 今こびとさんに調べてきてもろとるから待っとき！"
        send_line_message(target_id, interim_message)
        
        # Pass the original event payload through to the next step
        return event
    
    except Exception as e:
        logger.error(f"Error in interim response sender: {e}")
        # Propagate the error to stop the workflow
        raise

def send_line_message(to_id, message):
    """Send message to a LINE destination using the Push API"""
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message_with_http_info(
                push_message_request=PushMessageRequest(
                    to=to_id,
                    messages=[TextMessage(text=message)]
                )
            )
        logger.info(f"Sent interim message to {to_id}: {message}")
    except Exception as e:
        logger.error(f"Error sending LINE message: {e}")
        raise e

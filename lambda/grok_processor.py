import json
import logging
import os
import boto3
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.search import SearchParameters

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
XAI_API_KEY_SECRET_NAME = os.getenv("XAI_API_KEY_SECRET_NAME")

# AWS clients
secretsmanager = boto3.client('secretsmanager')

# Function to get secrets from Secrets Manager
def get_secret(secret_name):
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_name)
        secret_string = response['SecretString']
        return json.loads(secret_string)
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise

# xAI client (lazy initialization)
XAI_API_KEY = None

def get_xai_api_key():
    global XAI_API_KEY
    if XAI_API_KEY is None:
        try:
            xai_api_key_data = get_secret(XAI_API_KEY_SECRET_NAME)
            XAI_API_KEY = xai_api_key_data['XAI_API_KEY']
        except Exception as e:
            logger.error(f"Error retrieving xAI API key: {e}")
            raise
    return XAI_API_KEY

def call_grok_api(query):
    """Call xAI Grok API for search using official SDK"""
    try:
        logger.info(f"Calling Grok-4 with query: {query}")
        
        # Initialize xAI client
        client = Client(api_key=get_xai_api_key())
        
        # Create chat with search parameters
        chat = client.chat.create(
            model="grok-4",
            search_parameters=SearchParameters(mode="auto"),
        )
        
        # Create search prompt in Japanese
        search_prompt = f"以下について詳しく調べて、関西弁で分かりやすく教えて: {query}"
        chat.append(user(search_prompt))
        
        # Get response
        response = chat.sample()
        return response.content
        
    except Exception as e:
        logger.error(f"Error calling Grok-4 API: {e}")
        return f"ごめんやで～、こびとさんが情報見つけられへんかった...。もうちょっと簡単な言葉で聞いてみてくれる？"

def lambda_handler(event, context):
    logger.info("Grok Processor received event: %s", json.dumps(event, default=str))
    
    query = event.get('toolQuery')
    if not query:
        raise ValueError("No query found in the event payload")

    try:
        grok_response = call_grok_api(query)
        logger.info(f"Grok-4 response received: {grok_response}")
        
        # Return the response with all necessary context for the next lambda
        return {
            "grokResponse": grok_response,
            "userId": event.get('userId'),
            "conversationContext": event.get('conversationContext'),
            "sourceType": event.get('sourceType'),
            "sourceId": event.get('sourceId')
        }

    except Exception as e:
        logger.error(f"Error in Grok processor: {e}")
        # Return a user-friendly error message with context
        return {
            "grokResponse": "ごめんやで〜、こびとさんが情報見つけられへんかったわ...。もうちょっと簡単な言葉で聞いてみてくれる？",
            "userId": event.get('userId'),
            "conversationContext": event.get('conversationContext'),
            "sourceType": event.get('sourceType'),
            "sourceId": event.get('sourceId')
        }
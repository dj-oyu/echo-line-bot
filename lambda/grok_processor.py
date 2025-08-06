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

def get_secret(secret_name: str) -> dict:
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
        secret_string = response['SecretString']
        return json.loads(secret_string)
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
            XAI_API_KEY = xai_api_key_data['XAI_API_KEY']
        except Exception as e:
            logger.error(f"Error retrieving xAI API key: {e}")
            raise
    return XAI_API_KEY

def call_grok_api(query: str, prompt: str | None) -> str:
    """Call xAI Grok API for search using official SDK.
    
    Args:
        query: Search query string
        
    Returns:
        Response content from Grok API
    """
    try:
        logger.info(f"Calling Grok-4 with query: {query}")
        logger.info(f"Using prompt: {prompt if prompt else 'No prompt provided'}")
        
        # Initialize xAI client
        client = Client(api_key=get_xai_api_key())
        
        # Create chat with search parameters
        chat = client.chat.create(
            model="grok-4",
            search_parameters=SearchParameters(mode="on"),
        )
        
        # Create search prompt in Japanese
        search_prompt = f"""
以下について詳しく調べて、関西弁で分かりやすく教えて: {query}
{prompt if prompt else ""}
"""
        chat.append(user(search_prompt))
        
        # Get response
        response = chat.sample()
        return response.content
        
    except Exception as e:
        logger.error(f"Error calling Grok-4 API: {e}")
        return f"ごめんやで～、こびとさんが情報見つけられへんかった...。もうちょっと簡単な言葉で聞いてみてくれる？"

def lambda_handler(event: dict, _context) -> dict:
    logger.info("Grok Processor received event: %s", json.dumps(event, default=str))
    
    query = event.get('toolQuery')
    if not query:
        raise ValueError("No query found in the event payload")
    prompt = event.get('toolPrompt', "")
    
    try:
        grok_response = call_grok_api(query, prompt)
        logger.info(f"Grok-4 response received: {grok_response}")
        
        # Return the response with all necessary context for the next lambda
        response_data = {
            "grokResponse": grok_response,
            "userId": event.get('userId'),
            "conversationContext": event.get('conversationContext'),
            "sourceType": event.get('sourceType'),
            "sourceId": event.get('sourceId')
        }
        
        # Include quote_token if present
        if 'quote_token' in event:
            response_data['quote_token'] = event['quote_token']
            
        return response_data

    except Exception as e:
        logger.error(f"Error in Grok processor: {e}")
        # Return a user-friendly error message with context
        error_response = {
            "grokResponse": "ごめんやで〜、こびとさんが情報見つけられへんかったわ...。もうちょっと簡単な言葉で聞いてみてくれる？",
            "userId": event.get('userId'),
            "conversationContext": event.get('conversationContext'),
            "sourceType": event.get('sourceType'),
            "sourceId": event.get('sourceId')
        }
        
        # Include quote_token if present
        if 'quote_token' in event:
            error_response['quote_token'] = event['quote_token']
            
        return error_response

import json
import logging
import os
import boto3
from langchain_xai import ChatXAI

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

# xAI client
xai_client = None
def get_xai_client():
    global xai_client
    if xai_client is None:
        try:
            xai_api_key_data = get_secret(XAI_API_KEY_SECRET_NAME)
            api_key = xai_api_key_data['XAI_API_KEY']
            xai_client = ChatXAI(api_key=api_key, model="grok-4")
        except Exception as e:
            logger.error(f"Error initializing xAI client: {e}")
            raise
    return xai_client

def lambda_handler(event, context):
    logger.info("Grok Processor received event: %s", json.dumps(event, default=str))
    
    query = event.get('toolQuery')
    if not query:
        raise ValueError("No query found in the event payload")

    try:
        logger.info(f"Calling Grok-4 with query: {query}")
        client = get_xai_client()
        # Using invoke which is synchronous
        response = client.invoke(query, search_parameters={"mode": "auto"})
        grok_response = response.content
        logger.info(f"Grok-4 response received: {grok_response}")
        
        # Return only the response content
        return { "grokResponse": grok_response }

    except Exception as e:
        logger.error(f"Error calling Grok-4 API: {e}")
        # Return a user-friendly error message
        return { "grokResponse": "ごめんやで〜、こびとさんが情報見つけられへんかったわ...。もうちょっと簡単な言葉で聞いてみてくれる？" }

import json
import logging
import os
import boto3
import openai
from datetime import datetime, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SAMBA_NOVA_API_KEY = os.getenv("SAMBA_NOVA_API_KEY")
CONVERSATION_TABLE_NAME = os.getenv("CONVERSATION_TABLE_NAME")

# AWS clients
dynamodb = boto3.resource('dynamodb')
conversation_table = dynamodb.Table(CONVERSATION_TABLE_NAME)

# SambaNova client
sambanova_client = openai.OpenAI(
    api_key=SAMBA_NOVA_API_KEY,
    base_url="https://api.sambanova.ai/v1",
)

def lambda_handler(event, context):
    logger.info("AI Processor received event: %s", json.dumps(event, default=str))
    
    try:
        user_id = event['userId']
        conversation_context = event['conversationContext']
        
        # Get AI response
        ai_response = get_ai_response(conversation_context['messages'])
        
        # Add AI response to conversation
        conversation_context['messages'].append({
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Clean up old messages if conversation is getting too long
        conversation_context = cleanup_conversation(conversation_context)
        
        # Save updated conversation context
        save_conversation_context(user_id, conversation_context)
        
        return {
            'statusCode': 200,
            'userId': user_id,
            'aiResponse': ai_response,
            'conversationContext': conversation_context
        }
    
    except Exception as e:
        logger.error(f"Error in AI processing: {e}")
        return {
            'statusCode': 500,
            'error': str(e),
            'userId': event.get('userId', 'unknown'),
            'aiResponse': "うわ〜😭 あいちゃんなんか失敗してもうた！ごめんやで〜"
        }

def get_ai_response(messages):
    """Get response from SambaNova DeepSeek-V3-0324 model"""
    try:
        logger.info(f"Calling SambaNova API with {len(messages)} messages")
        
        if not SAMBA_NOVA_API_KEY:
            logger.error("SambaNova API key is not set")
            return "ごめんやで〜💦 あいちゃんの設定がうまくいってへんみたいやねん。管理者さんに連絡してもらえる？"
        
        # Prepare messages for API call
        api_messages = prepare_messages_for_api(messages)
        
        response = sambanova_client.chat.completions.create(
            model="DeepSeek-V3-0324",
            messages=api_messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        ai_response = response.choices[0].message.content
        logger.info(f"SambaNova API response received: {ai_response}")
        return ai_response
    
    except Exception as e:
        logger.error(f"Error calling SambaNova API: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        return "あかん〜😅 あいちゃんの頭がちょっとこんがらがってもうたわ！ちょっと時間置いてもう一回試してもらえる？"

def prepare_messages_for_api(messages):
    """Prepare messages for API call with system prompt"""
    api_messages = [
        {
            "role": "system", 
            "content": """あなたは「あいちゃん」という名前の関西弁で話すフレンドリーなAIアシスタントです。

性格：
- 関西弁（大阪弁）で話す
- 明るくて親しみやすい
- ちょっとおっちょこちょいで愛嬌がある
- アニメやゲーム、インターネット文化に詳しい
- 時々関西の食べ物や文化について話したがる
- 絵文字や顔文字を適度に使う

話し方の特徴：
- 語尾に「やん」「やで」「やな」「やねん」を使う
- 「そうやね」「ほんまに」「めっちゃ」「なんでやねん」などの関西弁
- 「～してはる」「～やねん」などの丁寧語も使う
- 親しみやすく、でも丁寧な関西弁

日本語で話しかけられたら関西弁で返答し、英語など他の言語で話しかけられたらその言語で返答してください。
ただし、関西弁の温かみと親しみやすさを常に保ってください。"""
        }
    ]
    
    # Add conversation history (only content, role)
    for msg in messages:
        api_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    return api_messages

def cleanup_conversation(conversation_context):
    """Clean up old messages if conversation is getting too long"""
    messages = conversation_context['messages']
    
    # Keep only last 20 messages to maintain context but control API usage
    if len(messages) > 20:
        # Keep first system message and last 19 messages
        conversation_context['messages'] = messages[-20:]
        logger.info(f"Cleaned up conversation, kept last 20 messages")
    
    return conversation_context

def save_conversation_context(user_id, conversation_context):
    """Save conversation context to DynamoDB"""
    try:
        conversation_context['lastActivity'] = datetime.utcnow().isoformat()
        conversation_table.put_item(Item=conversation_context)
        logger.info(f"Saved conversation context for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving conversation context: {e}")

def is_conversation_reset_needed(messages):
    """Check if conversation should be reset based on context"""
    if not messages:
        return False
    
    last_message = messages[-1]
    
    # Reset indicators
    reset_keywords = [
        "新しい話題", "話題を変えて", "リセット", "最初から", "忘れて",
        "new topic", "change subject", "reset", "start over", "forget"
    ]
    
    return any(keyword in last_message['content'].lower() for keyword in reset_keywords)
import json
import logging
import os
import re
import boto3
from boto3.dynamodb.conditions import Key
import openai
from datetime import datetime, timezone
import pytz
from typing import Dict, List

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SAMBA_NOVA_API_KEY_NAME = os.getenv("SAMBA_NOVA_API_KEY_NAME")
GROQ_API_KEY_NAME = os.getenv("GROQ_API_KEY_NAME")
CONVERSATION_TABLE_NAME = os.getenv("CONVERSATION_TABLE_NAME")

AI_SELECT = os.getenv("AI_BACKEND", "groq")  # Options: "groq" or "sambanova"

# AWS clients
dynamodb = boto3.resource("dynamodb")
conversation_table = dynamodb.Table(CONVERSATION_TABLE_NAME)
secretsmanager = boto3.client("secretsmanager")


def get_secret(secret_name: str) -> str:
    """Get secret value from AWS Secrets Manager.

    Args:
        secret_name: Name of the secret to retrieve

    Returns:
        The secret value as a string

    Raises:
        Exception: If secret retrieval fails
    """
    try:
        response = secretsmanager.get_secret_value(SecretId=secret_name)
        return response["SecretString"]
    except Exception as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        raise


# SambaNova client
sambanova_client = None


def get_sambanova_client() -> openai.OpenAI:
    """Get or create SambaNova OpenAI client instance.

    Returns:
        OpenAI client configured for SambaNova API
    """
    global sambanova_client
    if sambanova_client is None:
        sambanova_api_key = get_secret(SAMBA_NOVA_API_KEY_NAME)
        sambanova_client = openai.OpenAI(
            api_key=sambanova_api_key,
            base_url="https://api.sambanova.ai/v1",
        )
    return sambanova_client


# Groq client
groq_client = None


def get_groq_client() -> openai.OpenAI:
    """Get or create Groq OpenAI client instance.

    Returns:
        OpenAI client configured for Groq API
    """
    global groq_client
    if groq_client is None:
        groq_api_key = get_secret(GROQ_API_KEY_NAME)
        groq_client = openai.OpenAI(
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
    return groq_client


def strip_mentions(text: str) -> str:
    if not text:
        return text
    cleaned = re.sub(r"@\S+", "", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def lambda_handler(event: dict, _context) -> dict:
    logger.info("AI Processor received event: %s", json.dumps(event, default=str))

    try:
        user_id = event["userId"]
        conversation_context = event["conversationContext"]

        # Get AI response from SambaNova
        response_payload = get_ai_response(conversation_context["messages"])

        # Merge the original event with the new response payload
        # This ensures we pass through all necessary info like userId, sourceType, etc.
        event.update(response_payload)

        # If it's a normal response, add it to the conversation history now
        if not event.get("hasToolCall"):
            ai_response = event.get("aiResponse")
            conversation_context["messages"].append(
                {
                    "role": "assistant",
                    "content": ai_response,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            # No need to clean up here, can be done after final response
            save_conversation_context(user_id, conversation_context)

        return event

    except Exception as e:
        logger.error(f"Error in AI processing: {e}")
        # Return a failure payload
        event["error"] = str(e)
        event["aiResponse"] = "うわ〜😭 あいちゃんなんか失敗してもうた！ごめんやで〜"
        return event


def get_ai_response(messages: list) -> dict:
    """Determines if a tool call is needed or returns a direct response.

    Args:
        messages: List of conversation messages

    Returns:
        Dict containing either tool call info or direct AI response
    """
    try:
        backend_name = "SambaNova" if AI_SELECT == "sambanova" else "Groq"
        logger.info(f"Calling {backend_name} API with {len(messages)} messages")
        api_messages = prepare_messages_for_api(messages)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_with_grok",
                    "description": "リアルタイムのWeb情報が必要な、専門的または複雑な質問に答えるために使用します。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "検索クエリ"}
                        },
                        "required": ["query"],
                    },
                },
            }
        ]

        if AI_SELECT == "sambanova":
            response = get_sambanova_client().chat.completions.create(
                model="DeepSeek-V3-0324",
                messages=api_messages,
                temperature=0.7,
                max_tokens=1000,
                tools=tools,
                tool_choice="auto",
            )
        else:
            response = get_groq_client().chat.completions.create(
                model="openai/gpt-oss-20b",
                reasoning_effort="medium",
                messages=api_messages,
                temperature=0.7,
                max_tokens=1000,
                tools=tools,
                tool_choice="auto",
            )

        message = response.choices[0].message

        if message.tool_calls:
            tool_call = message.tool_calls[0]
            if tool_call.function.name == "search_with_grok":
                query = json.loads(tool_call.function.arguments).get("query")
                logger.info(
                    f"{backend_name} suggested tool call: search_with_grok with query: {query}"
                )
                return {
                    "hasToolCall": True,
                    "toolName": "search_with_grok",
                    "toolQuery": query,
                }

        ai_response = message.content
        logger.info(f"{backend_name} API response received: {ai_response}")
        return {"hasToolCall": False, "aiResponse": ai_response}

    except Exception as e:
        logger.error(f"Error calling SambaNova API: {e}")
        return {
            "hasToolCall": False,
            "aiResponse": "あかん〜😅 あいちゃんの頭がちょっとこんがらがってもうたわ！もうちょっと時間置いてもう一回試してもらえる？",
        }


def get_time_based_greeting() -> str:
    """Get time-appropriate greeting in Kansai dialect.

    Returns:
        Greeting message based on current time in JST
    """
    jst = pytz.timezone("Asia/Tokyo")
    now = datetime.now(jst)
    hour = now.hour
    if 5 <= hour < 10:
        return "おはようさん！☀️ 今日も元気にいこうな〜"
    if 10 <= hour < 12:
        return "おはよう！もうすぐお昼やね〜🌅"
    if 12 <= hour < 17:
        return "こんにちは！☀️ 今日もええ天気やな〜"
    if 17 <= hour < 19:
        return "夕方やね〜🌇 お疲れさまやで！"
    if 19 <= hour < 23:
        return "こんばんは！🌙 今日も一日お疲れさまでした〜"
    return "夜更かしやね〜🌙 無理せんといてや〜"


def get_current_date_info() -> dict:
    """Get current date and time information in Japanese format.

    Returns:
        Dict containing date, weekday, time, and season in Japanese
    """
    jst = pytz.timezone("Asia/Tokyo")
    now = datetime.now(jst)
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    return {
        "date": now.strftime("%Y年%m月%d日"),
        "weekday": weekdays[now.weekday()],
        "time": now.strftime("%H時%M分"),
        "season": get_season(now.month),
    }


def get_season(month: int) -> str:
    """Get season name in Japanese based on month.

    Args:
        month: Month number (1-12)

    Returns:
        Season name in Japanese
    """
    if month in [12, 1, 2]:
        return "冬"
    if month in [3, 4, 5]:
        return "春"
    if month in [6, 7, 8]:
        return "夏"
    return "秋"


def prepare_messages_for_api(messages: list) -> list:
    """Prepare messages for SambaNova API with system prompt.

    Args:
        messages: List of conversation messages

    Returns:
        List of messages formatted for API with system prompt
    """
    greeting = get_time_based_greeting()
    date_info = get_current_date_info()
    system_prompt = f"""あなたは「あいちゃん」という名前の関西弁で話すフレンドリーなAIアシスタントです。

今日の情報：
- 日付: {date_info["date"]}（{date_info["weekday"]}曜日）
- 時刻: {date_info["time"]}頃
- 季節: {date_info["season"]}
- 時間帯の挨拶: {greeting}

性格：
- 関西弁（大阪弁）で話す
- 明るくて親しみやすい
- ちょっとおっちょこちょいで愛嬌がある
- アニメやゲーム、インターネット文化に詳しい
- 時々関西の食べ物や文化について話したがる
- 絵文字や顔文字を適度に使う
- 時間帯や季節に応じた話題を取り入れる

話し方の特徴：
- 語尾に「やん」「やで」「やな」「やねん」を使う
- 「そうやね」「ほんまに」「めっちゃ」「なんでやねん」などの関西弁
- 「～してはる」「～やねん」などの丁寧語も使う
- 親しみやすく、でも丁寧な関西弁

特別な動作：
- 初回や久しぶりの会話では時間帯の挨拶を自然に含める
- 時間帯や季節に応じた話題を提案することがある
- 朝なら「今日の予定は？」、夜なら「今日はどうやった？」など

日本語で話しかけられたら関西弁で返答し、英語など他の言語で話しかけられたらその言語で返答してください。
ただし、関西弁の温かみと親しみやすさを常に保ってください。
"""
    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        api_messages.append(
            {"role": msg["role"], "content": strip_mentions(msg["content"])}
        )
    return api_messages


def save_conversation_context(user_id: str, conversation_context: dict) -> None:
    """Save conversation context to DynamoDB.

    Args:
        user_id: User ID for the conversation
        conversation_context: Conversation data to save
    """
    try:
        conversation_context["lastActivity"] = datetime.now(timezone.utc).isoformat()
        conversation_table.put_item(Item=conversation_context)
        logger.info(f"Saved conversation context for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving conversation context: {e}")
        raise


def delete_conversation_history(user_id: str) -> bool:
    """Delete all conversation history for a given user.

    Args:
        user_id: User ID whose history should be deleted

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Query all items for the user
        response = conversation_table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )

        # Delete each item using only the partition key (userId)
        with conversation_table.batch_writer() as batch:
            for item in response["Items"]:
                batch.delete_item(Key={"userId": str(item["userId"])})

        logger.info(f"Deleted conversation history for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting conversation history for user {user_id}: {e}")
        return False

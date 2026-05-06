## Lambda Functions

LINE Bot のバックエンド処理を担う Python Lambda 関数群。AI統合とメッセージ処理を行う。

## Technology Stack

- **Language**: Python 3.12
- **Package Manager**: uv
- **LINE SDK**: line-bot-sdk v3
- **AI Clients**: OpenAI SDK (SambaNova/Groq互換), xai-sdk

## Directory Structure

```
lambda/
├── webhook_handler.py       # LINE webhook処理、Step Functions起動
├── ai_processor.py          # SambaNova/Groq AI処理
├── grok_processor.py        # xAI Grok検索処理
├── interim_response_sender.py # 中間レスポンス送信
├── response_sender.py       # 最終レスポンス送信
├── requirements.txt         # Lambda Layer用依存関係
├── layer-dist/              # ビルド済みLayer（gitignore）
└── tests/                   # Pytestテスト
```

## Lambda Functions Overview

### webhook_handler.py
LINE Platformからのwebhookイベントを受信・検証し、Step Functionsワークフローを起動する。

**主な機能:**
- X-Line-Signature検証
- グループ/ルームでのメンション検出
- `/forget`コマンドによる履歴削除
- DynamoDBへの会話コンテキスト保存
- Step Functions起動

**ハンドラ:** `lambda_handler`

### ai_processor.py
高速AI推論を実行。SambaNovaまたはGroqを使用。

**主な機能:**
- 会話履歴の取得・管理
- OpenAI互換APIでのLLM呼び出し
- ツール呼び出し（function calling）判定
- 検索が必要な場合は`hasToolCall: true`を返却

**ハンドラ:** `lambda_handler`
**タイムアウト:** 60秒

### grok_processor.py
xAI Grok-4によるLive Search処理。Web検索が必要な場合に呼び出される。

**主な機能:**
- langchain_xaiを使用したGrok-4呼び出し
- Live Search APIによるリアルタイムWeb検索
- 検索結果を含む詳細な回答生成

**ハンドラ:** `lambda_handler`
**タイムアウト:** 180秒

### interim_response_sender.py
長時間処理の開始時に「調べています...」等の中間レスポンスを送信。

**ハンドラ:** `lambda_handler`
**タイムアウト:** 10秒

### response_sender.py
最終的なAI回答をLINEユーザーに送信し、会話履歴をDynamoDBに保存。

**主な機能:**
- LINE Push API使用（Reply Tokenは期限切れのため）
- グループ/ルームでの引用返信対応
- 会話履歴の更新

**ハンドラ:** `lambda_handler`
**タイムアウト:** 10秒

## Dependencies

`pyproject.toml` で管理:

```toml
dependencies = [
    "line-bot-sdk>=3.17.1",
    "openai>=1.0.0",
    "boto3>=1.28.0",
    "pytz>=2023.3",
    "xai-sdk>=1.0.0",
]
```

## AI Backend Configuration

環境変数 `AI_BACKEND` で切り替え:
- `groq` (デフォルト): Groq API使用
- `sambanova`: SambaNova API使用

両方ともOpenAI互換APIを提供。

## Message Processing Flow

```
[LINE User Message]
        │
        ▼
┌───────────────────┐
│ webhook_handler   │ ← 署名検証、メンション確認
└────────┬──────────┘
         │
         ▼ (Step Functions起動)
┌───────────────────┐
│  ai_processor     │ ← 高速AI処理
└────────┬──────────┘
         │
    hasToolCall?
    ┌────┴────┐
   true     false
    │         │
    ▼         │
┌────────────┐│
│interim_    ││
│response    ││
└─────┬──────┘│
      │       │
      ▼       │
┌────────────┐│
│grok_       ││
│processor   ││
└─────┬──────┘│
      │       │
      ▼       ▼
┌───────────────────┐
│ response_sender   │ ← LINE送信、履歴保存
└───────────────────┘
```

## Conversation Management

DynamoDB テーブル: `line-bot-conversations`

| Attribute | Type | Description |
|-----------|------|-------------|
| userId | String (PK) | LINE User ID |
| conversationId | String | 会話セッションID |
| messages | List | メッセージ履歴 |
| lastActivity | String | 最終活動時刻（ISO8601） |
| ttl | Number | TTL（24時間後） |

**会話セッション:**
- 30分以内の再会話は同一セッション継続
- 30分超過で新規セッション開始

## Special Commands

| Command | Description |
|---------|-------------|
| `/forget` | 会話履歴を削除 |
| `/忘れて` | 会話履歴を削除（日本語） |

## Group/Room Chat Support

- メンションされた場合のみ応答
- 引用返信（quoteToken）で元メッセージを参照
- メンション除去後のテキストを処理

## Testing

```bash
# プロジェクトルートから実行
uv run pytest

# 特定テストファイル
uv run pytest lambda/tests/test_webhook_handler.py

# 詳細出力
uv run pytest -v
```

## Local Development

```bash
# 依存関係インストール
uv sync

# Lambda Layer ビルド
./scripts/build-layer.sh
```

## Related Documentation

- [LINE Bot SDK](../docs/line-bot-sdk/index.md)
- [SambaNova Cloud](../docs/sambanova-cloud/index.md)
- [xAI Grok Integration](../docs/xai/grok_integration.md)
- [Webhooks](../docs/line-bot-sdk/webhooks.md)
- [Event Types](../docs/line-bot-sdk/event_types.md)

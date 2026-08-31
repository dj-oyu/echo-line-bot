## Lambda Functions

LINE Bot のバックエンド処理を担う Python Lambda 関数群。AI統合とメッセージ処理を行う。

## Technology Stack

- **Language**: Python 3.14
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
高速AI推論を実行。Groq（既定）またはSambaNovaを使用。

**主な機能:**
- 会話履歴の取得・管理
- OpenAI互換APIでのLLM呼び出し
- ツール呼び出し（function calling）判定
- 検索が必要な場合は`hasToolCall: true`を返却

**ハンドラ:** `lambda_handler`
**タイムアウト:** 60秒

### grok_processor.py
xAI Grok-4.6によるWeb検索処理。検索が必要な場合に呼び出される。

**主な機能:**
- xai_sdkを使用したGrok-4.6呼び出し
- Agent Tools APIの`web_search`によるリアルタイムWeb検索
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

### モデル設定

| 環境変数 | デフォルト | 備考 |
|----------|-----------|------|
| `GROQ_MODEL` | `openai/gpt-oss-20b` | qwen/qwen3.6-27b に替えたところ `search_with_grok` が発火しなくなったため差し戻し（[原因未特定](#groq-モデルとツール呼び出し)） |
| `GROQ_REASONING_EFFORT` | `GROQ_MODEL` から導出 | qwen3.6 は `none` / `default` の2値のみ、gpt-oss 系は `low` / `medium` / `high` と語彙が非互換（不正値は 400）。未設定なら `default_reasoning_effort()` がモデルに合う値を選ぶので、**通常は設定しない**。明示すると導出より優先されるため、モデル変更時に取り残されると全リクエストが落ちる |
| `XAI_MODEL` | `grok-4.6` | grok_processor の検索モデル。`GROQ_MODEL` と1文字違いになるのを避けて `GROK_MODEL` ではなく `XAI_MODEL`（同 Lambda の `XAI_API_KEY_SECRET_NAME` に揃えた）。取り違えると全リクエストが 400 |
| `SAMBANOVA_MODEL` | `DeepSeek-V3.2` | Preview 扱い / 32k コンテキスト。DeepSeek 系は tool calling が non-thinking モード限定なので `chat_template_kwargs.enable_thinking` は付けないこと（付けると `search_with_grok` が発火しなくなる）。Production 運用に寄せるなら `DeepSeek-V3.1`（128k）や `MiniMax-M2.7`（192k） |

CDK は `GROQ_REASONING_EFFORT` が明示された時だけ Lambda に渡す（`cdk/lib/lambda-stack.ts`）。
GitHub Actions の environment 変数にも置かないこと — 置くとモデルとの整合を人手で守る必要が戻る。

`GROQ_REASONING_EFFORT=default`（thinking 有効）にする場合、reasoning トークンが出力予算を消費するため
`max_tokens=1000` では応答が途中で切れうる。引き上げとセットで変更する。

### Groq モデルとツール呼び出し

`qwen/qwen3.6-27b` を既定にしたところ、リアルタイム情報を要する質問
（「最近の AWS のアップデート」）でも `search_with_grok` が発火せず、モデルが
自前の知識で回答した。本番ログでユーザーメッセージ2件・tool call 0件・
GrokProcessor 起動0件を確認し、`openai/gpt-oss-20b` に差し戻した。

原因は未特定。モデル自体の傾向と、`default_reasoning_effort()` が qwen に対して
`none`（非thinking）を選ぶことの、どちらが効いているか切り分けられていない
（差し戻すと effort も `medium` に戻るため）。qwen を再検討する場合は、
`GROQ_REASONING_EFFORT=default` と `max_tokens` の引き上げをセットで試すこと。

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

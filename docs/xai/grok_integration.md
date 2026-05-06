# xAI Grok and Tools API Integration

xAI の Grok モデルと Tools API（旧称 Live Search を含む組み込みツール群）を統合することで、リアルタイムの Web 情報を活用して応答を生成する検索エージェントを実装できます。本プロジェクトでは公式 Python SDK の `xai_sdk` を直接利用しており、`lambda/grok_processor.py` で `web_search` ツールを有効化した chat セッションを生成しています。

## Tools API の概要

xAI の組み込みツールはサーバーサイドで自動実行される。`tools` 引数にツール関数を渡すと、モデルが必要に応じて自律的に呼び出す。

| ツール | 用途 | gRPC SDK 対応 |
|--------|------|----------------|
| `web_search()` | Web 検索 | ✅ |
| `x_search()` | X (Twitter) 検索 | ✅ |
| `code_execution()` | サンドボックス Python 実行 | ❌ (Responses API のみ) |
| `collections_search()` | xAI にアップロードしたドキュメント (RAG) | ❌ |
| `attachment_search()` | メッセージ添付ファイル検索 | ✅ |

> Note: Python xAI SDK (gRPC) では `code_interpreter` と `file_search` は使えない。これらが必要な場合は OpenAI 互換の Responses API (`POST /v1/responses`) を利用する。

## 実装例 (xai_sdk)

`lambda/grok_processor.py` で実際に使っているパターン。

```python
import os
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4.3",
    tools=[web_search()],
)
chat.append(user("最近のxAIのアップデート教えて"))

response = chat.sample()

# 本文
print(response.content)

# 検索ソース URL（list[str]）
print(response.citations)
```

`response.citations` には `web_search` が参照したソース URL の一覧が入る。本プロジェクトでは観測用に CloudWatch Logs に記録している（ユーザーへの返信本文には含めない）。

### ストリーミング

逐次出力したい場合は `chat.stream()` を使う。LINE bot は完成したテキストを Push API で送るため非ストリーム (`chat.sample()`) を採用。

```python
for response, chunk in chat.stream():
    if chunk.content:
        print(chunk.content, end="", flush=True)
```

## Grok モデル

`grok-4.3` は xAI の最新の汎用モデルで、エージェント的なツール呼び出しと指示追従に優れる。`<modelname>` エイリアスは最新の安定版に自動追従するため、本プロジェクトでも `grok-4.3` を使用（旧モデル `grok-4-1-fast` 系は 2026-05-15 に廃止）。

## 料金 (2026-05 時点)

Tools API のコストは「トークン使用量」と「ツール呼び出し数」の合算。

| トークン (grok-4.3) | 単価 |
|---------------------|------|
| 入力 | $1.25 / 1M tokens |
| 出力 | $2.50 / 1M tokens |

| ツール呼び出し | 単価 |
|----------------|------|
| `web_search` / `x_search` | $5 / 1k calls |
| `code_execution` | $5 / 1k calls |
| `collections_search` | $2.50 / 1k calls |
| `attachment_search` | $10 / 1k calls |

旧 Live Search の「使用ソース数 × $25 / 1k」モデルからは値下げ。

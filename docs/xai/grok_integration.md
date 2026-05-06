
# xAI Grok and Live Search API Integration

xAIのGrokモデルとLive Search APIを統合することで、リアルタイムのWeb情報を活用して応答を生成する検索エージェントを実装できます。

## Live Search API

Live Search機能を利用するには、APIリクエストに`search_parameters`オブジェクトを含めます。このオブジェクトの`mode`フィールドで検索の動作を制御します。

*   **`off`**: 検索機能を無効にします。
*   **`auto`**: (デフォルト) モデルが検索を実行するかどうかを決定します。
*   **`on`**: モデルに常にライブ検索を強制します。

### Pythonでの使用例 (langchain_xai)

`langchain_xai`ライブラリを使用すると、GrokモデルとLive Search機能を簡単に利用できます。

```python
from langchain_xai import ChatXAI

llm = ChatXAI(
    model="grok-4.3",
    search_parameters={
        "mode": "auto",
        # オプションのパラメータ例
        "max_search_results": 3,
        "from_date": "2025-05-26",
        "to_date": "2025-05-27",
    }
)
```

## Grokモデル

`grok-4.3` は xAI の最新の汎用モデルで、エージェント的なツール呼び出しと指示追従に優れています。`<modelname>` エイリアスで最新の安定版を自動的に追従するため、本プロジェクトでも `grok-4.3` を使用します（旧モデル `grok-4-1-fast` 系は 2026-05-15 に廃止）。

## APIアクセスと料金

Grok APIを利用するには、xAIアカウントの作成、請求設定、APIキーの生成が必要です。

Live Search機能の料金は、使用されたソースの数に基づいており、1,000ソースあたり25ドルです。使用されたソースの数は、応答オブジェクトの`response.usage.num_sources_used`フィールドで確認できます。

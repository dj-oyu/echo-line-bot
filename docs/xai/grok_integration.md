
# xAI Grok-4 and Live Search API Integration

xAIのGrok-4モデルとLive Search APIを統合することで、リアルタイムのWeb情報を活用して応答を生成する検索エージェントを実装できます。

## Live Search API

Live Search機能を利用するには、APIリクエストに`search_parameters`オブジェクトを含めます。このオブジェクトの`mode`フィールドで検索の動作を制御します。

*   **`off`**: 検索機能を無効にします。
*   **`auto`**: (デフォルト) モデルが検索を実行するかどうかを決定します。
*   **`on`**: モデルに常にライブ検索を強制します。

### Pythonでの使用例 (langchain_xai)

`langchain_xai`ライブラリを使用すると、Grok-4モデルとLive Search機能を簡単に利用できます。

```python
from langchain_xai import ChatXAI

llm = ChatXAI(
    model="grok-4",
    search_parameters={
        "mode": "auto",
        # オプションのパラメータ例
        "max_search_results": 3,
        "from_date": "2025-05-26",
        "to_date": "2025-05-27",
    }
)
```

## Grok-4モデル

Grok-4は、xAIの最新の推論モデルであり、画像とテキストの両方の入力をサポートしています。

## APIアクセスと料金

Grok APIを利用するには、xAIアカウントの作成、請求設定、APIキーの生成が必要です。

Live Search機能の料金は、使用されたソースの数に基づいており、1,000ソースあたり25ドルです。使用されたソースの数は、応答オブジェクトの`response.usage.num_sources_used`フィールドで確認できます。

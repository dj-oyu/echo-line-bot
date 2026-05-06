
# SambaNova Function Calling

SambaNovaのFunction Callingは、言語モデルがユーザーの入力に基づいて事前に定義された関数をインテリジェントに呼び出すことを可能にする機能です。これにより、モデルが外部ツールやデータソースと対話するエージェント的なワークフローを構築できます。

## 仕組み

Function Callingのプロセスは以下のステップで構成されます。

1.  **関数スキーマの定義**: モデルに呼び出しを許可する関数のJSONスキーマを定義します。このスキーマには、関数名、目的、および受け入れるパラメータ（データ型を含む）が含まれます。

2.  **ツールを使用したクエリの送信**: モデルにクエリを送信する際、リクエストの`tools`パラメータに定義済みの関数スキーマを含めます。

3.  **モデルによる処理と提案**: モデルはユーザーのクエリを分析し、会話的に応答するか、提供された関数のいずれかを呼び出すかを決定します。関数を呼び出すことを選択した場合、ユーザーの入力と関数のスキーマに基づいて必要な引数を生成します。

4.  **関数呼び出しの受信と実行**: APIは、関数呼び出しの提案を含む可能性のある応答を返します。指定された関数を提供された引数で実行するのは、アプリケーションの責任です。API自体は関数を実行しません。

5.  **モデルへの結果の返却**: 関数を実行した後、その結果をモデルに送り返して、会話やワークフローを継続できます。これにより、モデルは関数の出力を使用して、より情報に基づいた応答を生成できます。

## API仕様

Function Calling機能はAPIリクエストで設定されます。主要なパラメータは以下の通りです。

*   **`tools`**: 各オブジェクトが関数のスキーマを表すJSONオブジェクトの配列。スキーマは、関数の`name`、`description`、および`parameters`を定義する必要があります。
*   **`tool_choice`**: このパラメータは、モデルが提供された関数をどのように使用するかを制御します。
    *   `auto`: (デフォルト) モデルはメッセージを生成するか、関数を呼び出すかを選択できます。
    *   `required`: モデルに強制的に関数を呼び出させます。
    *   `{"type": "function", "function": {"name": "FUNCTION_NAME"}}`: モデルに特定の関数を強制的に呼び出させます。

## Pythonでの使用例

以下は、OpenAI互換レイヤーを使用してFunction Calling APIを利用するPythonの例です。

```python
import openai
import json

# SambaNova CloudのベースURLとAPIキーでクライアントを初期化
client = openai.OpenAI(
    base_url="https://api.sambanova.ai/v1",
    api_key="YOUR_SAMBANOVA_API_KEY"
)

# 関数スキーマの定義
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "指定された都市の現在の天候情報を取得します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "天候情報を取得する都市の名前。"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

# 関数スキーマを含むチャット補完リクエストの作成
response = client.chat.completions.create(
    model="Meta-Llama-3.1-70B-Instruct", # または他のサポートされているモデル
    messages=[{"role": "user", "content": "ロンドンの天気は？"}],
    tools=tools,
    tool_choice="auto"
)

# 応答からのツール呼び出しの処理
tool_calls = response.choices[0].message.tool_calls
if tool_calls:
    # ... (関数を実行し、結果をモデルに送り返す)
    pass
```

## 対応モデル

Meta-Llama-3.1やMeta-Llama-4の様々なバージョンを含む、いくつかのモデルがFunction Callingをサポートしています。小規模なモデルでもゼロショットのツール呼び出しに使用できますが、より複雑な会話やツール呼び出しのアプリケーションには大規模なモデルが推奨されます。

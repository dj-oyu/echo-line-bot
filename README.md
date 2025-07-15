# LINE AI チャットボット

SambaNova Cloud の DeepSeek-V3 モデルと xAI の Grok を使用した、会話記憶機能付きの AI チャットボットです。関西弁で話す「あいちゃん」として設計されています。

## 機能

- **デュアル AI 機能**: SambaNova Cloud の DeepSeek-V3-0324 モデル + xAI Grok による高性能な会話
- **検索連携機能**: Grok の Live Search API によるリアルタイム情報検索
- **会話記憶**: DynamoDB を使用した文脈を考慮した会話継続（30分間）
- **関西弁キャラクター**: 「あいちゃん」として関西弁で親しみやすく応答
- **時間認識**: 時間帯に応じた挨拶と季節感のある応答
- **非同期処理**: AWS Step Functions による高速な webhook 応答と段階的応答
- **コスト管理**: 会話履歴を最新20件に制限してAPI コストを管理
- **Lambda Layer最適化**: 事前ビルド済み依存関係レイヤーによる高速デプロイ

## アーキテクチャ

```
LINE Platform → API Gateway → Webhook Lambda → Step Functions
                                     ↓                ↓
                                DynamoDB         AI Processor Lambda
                               (会話履歴)              ↓
                                              Tool Call判定
                                            ↙          ↘
                                 Interim Response    Direct Response
                                     Lambda           Lambda
                                       ↓               ↓
                                 Grok Processor   LINE Push API
                                    Lambda           ↓
                                       ↓         LINE User
                                Final Response
                                   Lambda
                                      ↓
                                LINE Push API
                                     ↓
                                 LINE User
```

### AWS リソース構成

- **DynamoDB テーブル**: `line-bot-conversations` - 会話履歴保存（TTL付き）
- **Lambda 関数** (5個):
  - `WebhookHandler`: 高速 webhook 応答処理とStep Functions起動
  - `AiProcessor`: SambaNova AI応答生成とツール呼び出し判定（15秒タイムアウト）
  - `InterimResponseSender`: Grok検索時の中間応答送信（10秒タイムアウト）
  - `GrokProcessor`: xAI Grok検索処理（60秒タイムアウト）
  - `ResponseSender`: LINE Push API経由での最終応答送信（10秒タイムアウト）
- **Lambda Layer**: 事前ビルド済み共通依存関係（line-bot-sdk, openai, boto3, langchain-xai, pytz）
- **Step Functions**: 条件分岐付きAI処理ワークフローの管理
- **API Gateway**: LINE webhook用REST APIエンドポイント
- **Secrets Manager**: 暗号化されたAPI キーとトークンの管理
- **IAM ロール**: Lambda、Step Functions、SecretsManagerの適切な権限設定

## プロジェクト構造

```
├── lambda/
│   ├── webhook_handler.py       # Webhook 処理ハンドラー
│   ├── ai_processor.py          # SambaNova AI 応答生成処理
│   ├── interim_response_sender.py # Grok検索時の中間応答送信
│   ├── grok_processor.py        # xAI Grok検索処理
│   ├── response_sender.py       # LINE 最終応答送信処理
│   └── layer-dist/              # Lambda Layer ビルド出力（.gitignore済み）
├── scripts/
│   └── build-layer.sh          # Lambda Layer 依存関係ビルドスクリプト
├── cdk/
│   ├── lib/
│   │   └── lambda-stack.ts     # CDK インフラストラクチャスタック
│   ├── bin/
│   │   └── cdk.ts             # CDK アプリエントリーポイント
│   ├── test/
│   │   └── cdk.test.ts        # CDK テスト（10テスト）
│   ├── package.json           # pnpm 依存関係
│   └── pnpm-lock.yaml         # pnpm ロックファイル
├── pyproject.toml             # uv Python 依存関係管理
├── .env.example              # 環境変数テンプレート
├── .github/workflows/
│   └── deploy.yml            # GitHub Actions CI/CD（pnpm + uv）
└── CLAUDE.md                # Claude Code用プロジェクト指示書
```

## 前提条件

- Node.js 20+ (CDK 用)
- Python 3.12+
- pnpm (パッケージマネージャー)
- uv (Python パッケージマネージャー)
- AWS CLI の設定済み
- LINE Developer アカウントとボットチャンネル
- SambaNova Cloud アカウントと API キー
- xAI アカウントと API キー

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd echo-line-bot
```

### 2. 依存関係のインストール

```bash
# CDK 依存関係のインストール（pnpm使用）
cd cdk
pnpm install

# Python 依存関係のインストール（uv使用）
cd ..
uv sync

# Lambda Layer のビルド
./scripts/build-layer.sh
```

### 3. AWS Secrets Manager での環境変数設定

GitHub Actions または AWS CLI を使用してSecrets Managerにシークレットを作成：

```bash
# AWS CLI での設定例
aws secretsmanager create-secret --name LINE_CHANNEL_SECRET --secret-string "your_line_channel_secret"
aws secretsmanager create-secret --name LINE_CHANNEL_ACCESS_TOKEN --secret-string "your_line_channel_access_token"
aws secretsmanager create-secret --name SAMBA_NOVA_API_KEY --secret-string "your_samba_nova_api_key"
aws secretsmanager create-secret --name XAI_API_KEY --secret-string '{"XAI_API_KEY":"your_xai_api_key"}'
```

### 4. AWS へのデプロイ

#### 初回デプロイ（新規構築時）
```bash
cd cdk
pnpm run cdk deploy --require-approval never
```

#### 既存環境へのデプロイ（DynamoDBテーブル既存時）
```bash
cd cdk
pnpm run cdk deploy --require-approval never -c useExistingTable=true
```

デプロイが完了すると API Gateway URL が出力されます。この URL を LINE webhook エンドポイントに設定してください。

### 5. LINE webhook の設定

1. LINE Developer Console にアクセス
2. ボットチャンネルの設定に移動
3. デプロイ出力の API Gateway URL を webhook URL に設定
4. webhook を有効化

## 開発

### CDK コマンド

```bash
cd cdk

# TypeScript のコンパイル
pnpm run build

# 開発用ウォッチモード
pnpm run watch

# テストの実行（10テスト実行）
pnpm test

# デプロイ差分の表示
pnpm run cdk diff

# 初回デプロイ
pnpm run cdk deploy --require-approval never

# 既存環境へのデプロイ
pnpm run cdk deploy --require-approval never -c useExistingTable=true

# スタックの削除
pnpm run cdk destroy
```

### Lambda Layer 管理

```bash
# Lambda Layer のビルド
./scripts/build-layer.sh

# 依存関係の確認
ls lambda/layer-dist/python/

# Layer サイズの確認
du -sh lambda/layer-dist/
```

### ローカルテスト

各 Lambda 関数は LINE webhook ペイロード形式のテストイベントを作成することでローカルテストが可能です。

## デプロイメント

このプロジェクトは GitHub Actions による自動CI/CDを使用しています：

### GitHub Actions ワークフロー

1. **テストジョブ**: PR時にCDK構文テスト、Lambda Layerビルド、10テスト実行
2. **デプロイジョブ**: `main`ブランチへのプッシュで自動デプロイ
3. **パッケージマネージャー**: pnpm（Node.js）+ uv（Python）
4. **リージョン**: ap-northeast-1（東京）

### ワークフロー特徴

- **Lambda Layer事前ビルド**: Docker不要の事前ビルド済みLayerでCI高速化
- **Secrets Manager統合**: 自動シークレット作成・更新
- **条件付きテーブル管理**: 既存DynamoDBテーブルとの競合回避
- **TypeScript型チェック**: isolatedModules設定でts-jest警告解消

### 必要な GitHub Secrets

- `AWS_ACCESS_KEY_ID`: AWS アクセスキー
- `AWS_SECRET_ACCESS_KEY`: AWS シークレットアクセスキー
- `CHANNEL_ACCESS_TOKEN`: LINE Botチャンネルアクセストークン
- `CHANNEL_SECRET`: LINE Botチャンネルシークレット
- `SAMBA_NOVA_API_KEY`: SambaNova Cloud APIキー
- `XAI_API_KEY`: xAI APIキー（Grok用）

### デプロイコマンド

GitHub Actionsでは以下のコマンドでデプロイされます：

```bash
# 既存環境向け（DynamoDBテーブル既存）
pnpm run cdk deploy --require-approval never --ci -c useExistingTable=true
```

## 動作仕組み

### 基本フロー
1. ユーザーがLINE ボットにメッセージを送信
2. LINE プラットフォームがAPI Gateway にwebhook イベントを送信
3. **Webhook Lambda**が高速応答でイベントを受信し、Step Functions を起動
4. **Step Functions**がAI 処理ワークフローを開始

### AI処理フロー
5. **AI Processor Lambda**が会話履歴を取得し、SambaNova API で応答を生成
6. Tool Call（検索要求）の有無を判定
   - **Tool Call あり**: 中間応答→Grok検索→最終応答
   - **Tool Call なし**: 直接応答

### Tool Call ありの場合
7a. **Interim Response Sender Lambda**が「検索中...」の中間応答を送信
8a. **Grok Processor Lambda**がxAI Grok Live Search APIで情報検索
9a. **Response Sender Lambda**が検索結果を含む最終応答を送信

### Tool Call なしの場合
7b. **Response Sender Lambda**が直接応答を送信

### 共通処理
10. 会話履歴がDynamoDB に保存（30分間のTTL）

## 環境変数とSecrets

### Lambda関数環境変数（CDK管理）
- `CONVERSATION_TABLE_NAME`: DynamoDB テーブル名
- `STEP_FUNCTION_ARN`: Step Functions ARN
- `CHANNEL_SECRET_NAME`: LINE Channel Secret（Secrets Manager参照）
- `CHANNEL_ACCESS_TOKEN_NAME`: LINE Channel Access Token（Secrets Manager参照）
- `SAMBA_NOVA_API_KEY_NAME`: SambaNova API キー（Secrets Manager参照）
- `XAI_API_KEY_SECRET_NAME`: xAI API キー（Secrets Manager参照）

### Secrets Manager 管理項目
- `LINE_CHANNEL_SECRET`: 署名検証用LINE Bot チャンネルシークレット
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Bot チャンネルアクセストークン
- `SAMBA_NOVA_API_KEY`: SambaNova Cloud API キー
- `XAI_API_KEY`: xAI API キー（JSON形式）

## AI の特徴

- **デュアルAIエンジン**: SambaNova DeepSeek-V3（基本会話）+ xAI Grok（検索連携）
- **キャラクター**: 関西弁で話す「あいちゃん」
- **会話記憶**: 30分間の会話セッションを維持
- **検索連携**: リアルタイム情報検索とTool Calling
- **段階的応答**: 検索時は中間応答で待機時間を軽減
- **時間認識**: 日本時間（JST）に基づく時間帯別挨拶
- **コスト管理**: 最新20件のメッセージのみ保持
- **エラーハンドリング**: 日本語でのエラーメッセージ

## 主要な依存関係

### Python（uv管理）
- **line-bot-sdk** (v3.17.1+): LINE Bot SDK v3
- **openai** (v1.95.1+): SambaNova API クライアント
- **langchain-xai** (v0.2.4+): xAI Grok統合
- **boto3** (v1.39.4+): AWS SDK
- **pytz** (v2025.2+): タイムゾーン処理

### Node.js（pnpm管理）
- **aws-cdk-lib** (v2.202.0): AWS CDK v2
- **constructs** (v10.4.2): CDK Constructs
- **typescript** (~5.6.3): TypeScript コンパイラ
- **jest** (v29.7.0): テストフレームワーク

### 外部API
- **SambaNova Cloud API**: DeepSeek-V3-0324モデル
- **xAI API**: Grok Live Search機能

## トラブルシューティング

### よくある問題と解決方法

#### 1. DynamoDBテーブル競合エラー
```
CloudFormation cannot update a stack when a custom-named resource requires replacing
```

**解決方法**:
```bash
# 既存テーブル使用モードでデプロイ
pnpm run cdk deploy --require-approval never -c useExistingTable=true
```

#### 2. Secrets Manager競合エラー
```
The operation failed because the secret already exists
```

**解決方法**: CDKは既存シークレットを参照するため、GitHub Actionsワークフローで作成済みの場合は問題なし。

#### 3. Lambda Layer importエラー
```
from langchain_xai import ChatXAI
ImportError: No module named 'langchain_xai'
```

**解決方法**:
```bash
# Lambda Layerを再ビルド
./scripts/build-layer.sh

# 依存関係の確認
ls lambda/layer-dist/python/langchain_xai/
```

#### 4. pnpm/uv 未インストールエラー

**解決方法**:
```bash
# pnpm インストール
npm install -g pnpm

# uv インストール（Linux/Mac）
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 5. CDKテスト失敗

**解決方法**:
```bash
cd cdk
pnpm run build  # TypeScript コンパイル
pnpm test       # 10テスト実行
```

#### 6. GitHub Actions デプロイ失敗

確認ポイント:
- GitHub Secrets の設定確認
- AWS IAM 権限の確認
- Lambda Layer ビルド成功の確認

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。

## 貢献

1. リポジトリをフォーク
2. フィーチャーブランチを作成
3. 変更を実装
4. プルリクエストを送信

## サポート

以下に関する問題については：
- **LINE Bot SDK**: [公式ドキュメント](https://developers.line.biz/ja/)をご確認ください
- **AWS CDK**: [AWS CDK ドキュメント](https://docs.aws.amazon.com/cdk/)をご参照ください
- **SambaNova Cloud**: [SambaNova Cloud ドキュメント](https://sambanova.ai/)をご参照ください
- **xAI**: [xAI ドキュメント](https://docs.x.ai/)をご参照ください
- **このプロジェクト**: このリポジトリで Issue を作成してください
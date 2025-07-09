# LINE AI チャットボット

SambaNova Cloud の DeepSeek-V3 モデルを使用した、会話記憶機能付きの AI チャットボットです。関西弁で話す「あいちゃん」として設計されています。

## 機能

- **AI 会話機能**: SambaNova Cloud の DeepSeek-V3-0324 モデルによる自然な会話
- **会話記憶**: DynamoDB を使用した文脈を考慮した会話継続（30分間）
- **関西弁キャラクター**: 「あいちゃん」として関西弁で親しみやすく応答
- **時間認識**: 時間帯に応じた挨拶と季節感のある応答
- **非同期処理**: AWS Step Functions による高速な webhook 応答
- **コスト管理**: 会話履歴を最新20件に制限してAPI コストを管理

## アーキテクチャ

```
LINE Platform → API Gateway → Webhook Lambda → Step Functions → AI Processor Lambda → Response Sender Lambda → LINE User
                                     ↓
                                DynamoDB (会話履歴)
```

### AWS リソース構成

- **DynamoDB テーブル**: `line-bot-conversations` - 会話履歴保存（TTL付き）
- **Lambda 関数** (3個):
  - `webhookHandler`: 高速 webhook 応答処理
  - `aiProcessor`: AI 応答生成処理
  - `responseSender`: LINE Push API 経由での応答送信
- **Lambda レイヤー**: 共通依存関係（line-bot-sdk, openai, boto3, pytz）
- **Step Functions**: AI 処理ワークフローの管理
- **API Gateway**: LINE webhook 用 REST API エンドポイント
- **IAM ロール**: Lambda と Step Functions の適切な権限設定

## プロジェクト構造

```
├── lambda/
│   ├── main.py              # 旧実装（未使用）
│   ├── webhook_handler.py   # Webhook 処理ハンドラー
│   ├── ai_processor.py      # AI 応答生成処理
│   └── response_sender.py   # LINE 応答送信処理
├── cdk/
│   ├── lib/
│   │   └── lambda-stack.ts  # CDK インフラストラクチャスタック
│   ├── bin/
│   │   └── cdk.ts          # CDK アプリエントリーポイント
│   └── test/               # CDK テスト
├── pyproject.toml          # Python 依存関係
├── .env.example           # 環境変数テンプレート
└── .github/workflows/     # GitHub Actions CI/CD
```

## 前提条件

- Node.js 18+ (CDK 用)
- Python 3.11+
- AWS CLI の設定済み
- LINE Developer アカウントとボットチャンネル
- SambaNova Cloud アカウントと API キー

## セットアップ

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd echo-line-bot
```

### 2. 依存関係のインストール

```bash
# CDK 依存関係のインストール
cd cdk
npm install

# Python 依存関係のインストール
uv sync
```

### 3. 環境変数の設定

`cdk` ディレクトリに `.env.local` ファイルを作成：

```bash
CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
CHANNEL_SECRET=your_line_channel_secret
SAMBA_NOVA_API_KEY=your_samba_nova_api_key
```

### 4. AWS へのデプロイ

```bash
cd cdk
npx cdk deploy
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
npm run build

# 開発用ウォッチモード
npm run watch

# テストの実行
npm test

# デプロイ差分の表示
npx cdk diff

# 変更のデプロイ
npx cdk deploy

# スタックの削除
npx cdk destroy
```

### ローカルテスト

各 Lambda 関数は LINE webhook ペイロード形式のテストイベントを作成することでローカルテストが可能です。

## デプロイメント

このプロジェクトは GitHub Actions による自動デプロイを使用しています：

1. **テストジョブ**: PR 時に CDK 構文テストを実行
2. **デプロイジョブ**: `main` ブランチへのプッシュで自動デプロイ
3. **リージョン**: ap-northeast-1 (東京)

### 必要な GitHub Secrets

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `CHANNEL_ACCESS_TOKEN`
- `CHANNEL_SECRET`
- `SAMBA_NOVA_API_KEY`

## 動作仕組み

1. ユーザーが LINE ボットにメッセージを送信
2. LINE プラットフォームが API Gateway に webhook イベントを送信
3. Webhook Lambda が高速応答でイベントを受信
4. Step Functions が AI 処理ワークフローを開始
5. AI Processor Lambda が会話履歴を取得し、SambaNova API で応答を生成
6. Response Sender Lambda が LINE Push API でユーザーに応答を送信
7. 会話履歴が DynamoDB に保存（30分間の TTL）

## 環境変数

Lambda 関数には以下の環境変数が必要です：

- `CHANNEL_ACCESS_TOKEN`: LINE Bot チャンネルアクセストークン
- `CHANNEL_SECRET`: 署名検証用 LINE Bot チャンネルシークレット
- `SAMBA_NOVA_API_KEY`: SambaNova Cloud API キー
- `CONVERSATION_TABLE_NAME`: DynamoDB テーブル名
- `STEP_FUNCTION_ARN`: Step Functions ARN

## AI の特徴

- **キャラクター**: 関西弁で話す「あいちゃん」
- **会話記憶**: 30分間の会話セッションを維持
- **時間認識**: 日本時間（JST）に基づく時間帯別挨拶
- **コスト管理**: 最新20件のメッセージのみ保持
- **エラーハンドリング**: 日本語でのエラーメッセージ

## 主要な依存関係

- **Python**: line-bot-sdk (v3.17.1+), openai (v1.0.0+), boto3, pytz
- **Node.js**: aws-cdk-lib (v2.202.0), dotenv
- **外部API**: SambaNova Cloud API

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。

## 貢献

1. リポジトリをフォーク
2. フィーチャーブランチを作成
3. 変更を実装
4. プルリクエストを送信

## サポート

以下に関する問題については：
- LINE Bot SDK: [公式ドキュメント](https://developers.line.biz/ja/)をご確認ください
- AWS CDK: [AWS CDK ドキュメント](https://docs.aws.amazon.com/cdk/)をご参照ください
- SambaNova Cloud: [SambaNova Cloud ドキュメント](https://sambanova.ai/)をご参照ください
- このプロジェクト: このリポジトリで Issue を作成してください
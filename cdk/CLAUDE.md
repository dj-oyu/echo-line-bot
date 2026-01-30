## CDK Infrastructure

AWS CDKを使用したインフラストラクチャ定義。TypeScriptで記述され、LINE BotのAWS環境をコードで管理する。

## Technology Stack

- **Language**: TypeScript
- **Package Manager**: pnpm
- **CDK Version**: aws-cdk-lib
- **Node.js**: 20

## Directory Structure

```
cdk/
├── bin/
│   └── cdk.ts           # CDKアプリエントリーポイント
├── lib/
│   └── lambda-stack.ts  # メインスタック定義
├── test/
│   └── __snapshots__/   # スナップショットテスト
├── package.json
├── tsconfig.json
└── cdk.json
```

## AWS Resources

### LineEchoStack

`lib/lambda-stack.ts` で定義される主要リソース:

| Resource | Type | Description |
|----------|------|-------------|
| ConversationHistory | DynamoDB Table | 会話履歴保存（TTL付き、PAY_PER_REQUEST） |
| WebhookHandler | Lambda | LINE webhook受信、Step Functions起動 |
| AiProcessor | Lambda | SambaNova/Groq AI処理（60秒タイムアウト） |
| InterimResponseSender | Lambda | 処理中の中間レスポンス送信 |
| GrokProcessor | Lambda | xAI Grok検索処理（180秒タイムアウト） |
| ResponseSender | Lambda | 最終レスポンス送信、履歴保存 |
| DependenciesLayer | Lambda Layer | Python依存関係 |
| AIProcessingWorkflow | Step Functions | AI処理オーケストレーション |
| Endpoint | API Gateway | LINE webhookエンドポイント |

### Secrets Manager References

既存のシークレットを参照（GitHub Actionsで作成）:
- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `SAMBA_NOVA_API_KEY`
- `GROQ_API_KEY`
- `XAI_API_KEY`

## Development Commands

```bash
# 依存関係インストール
pnpm install

# TypeScriptコンパイル
pnpm run build

# 開発時ウォッチモード
pnpm run watch

# テスト実行
pnpm test

# CloudFormationテンプレート生成
pnpm run cdk synth

# デプロイ差分確認
pnpm run cdk diff

# AWSへデプロイ
pnpm run cdk deploy

# スタック削除
pnpm run cdk destroy
```

## Step Functions Workflow

AI処理ワークフローの流れ:

```
┌─────────────────┐
│  ProcessWithAI  │  (ai_processor)
└────────┬────────┘
         │
    ┌────▼────┐
    │ Choice  │  hasToolCall?
    └────┬────┘
         │
    ┌────┴────┐
    │         │
   true     false
    │         │
    ▼         ▼
┌────────┐ ┌────────────────┐
│Interim │ │ SendDirect     │
│Response│ │ Response       │
└───┬────┘ └────────────────┘
    │
    ▼
┌────────────┐
│ProcessGrok │  (grok_processor)
└─────┬──────┘
      │
      ▼
┌─────────────┐
│SendFinal    │  (response_sender)
│Response     │
└─────────────┘
```

## Testing

```bash
# Jestテスト実行
pnpm test

# テストウォッチモード
pnpm test -- --watch

# スナップショット更新
pnpm test -- -u
```

テストファイルは `test/` ディレクトリに配置。

## Configuration Files

### cdk.json
CDK Toolkitの設定。`ts-node`でTypeScriptを直接実行。

### tsconfig.json
TypeScriptコンパイラ設定。strict mode有効。

## Environment Variables

Lambda関数に渡される環境変数:

| Lambda | Variables |
|--------|-----------|
| WebhookHandler | CONVERSATION_TABLE_NAME, CHANNEL_SECRET_NAME, CHANNEL_ACCESS_TOKEN_NAME, STEP_FUNCTION_ARN |
| AiProcessor | CONVERSATION_TABLE_NAME, SAMBA_NOVA_API_KEY_NAME, GROQ_API_KEY_NAME, AI_BACKEND |
| InterimResponseSender | CHANNEL_ACCESS_TOKEN_NAME |
| GrokProcessor | XAI_API_KEY_SECRET_NAME |
| ResponseSender | CONVERSATION_TABLE_NAME, CHANNEL_ACCESS_TOKEN_NAME |

## Related Documentation

- [AWS CDK詳細](../docs/aws-cdk/index.md)
- [Lambda定義](../docs/aws-cdk/defining_lambda.md)
- [API Gateway](../docs/aws-cdk/defining_api_gateway.md)
- [IAM Roles](../docs/aws-cdk/iam_roles.md)

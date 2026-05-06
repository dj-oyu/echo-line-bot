## GitHub Actions CI/CD

GitHub Actionsを使用した継続的インテグレーション・デプロイメント設定。

## Workflow Files

```
.github/
└── workflows/
    └── deploy.yml    # テスト・デプロイワークフロー
```

## Pipeline Overview

| Trigger | Job | Condition | Actions |
|---------|-----|-----------|---------|
| PR to main | `test` | `github.event_name == 'pull_request'` | Build, Test, Synth |
| Push to main | `deploy` | `github.ref == 'refs/heads/main'` | Build, Deploy |

## Test Job

PRがmainブランチに向けて作成された時に実行。

**Steps:**
1. Checkout code
2. Install pnpm (latest)
3. Setup Node.js 20 (cache: pnpm)
4. Setup Python 3.12
5. Install uv (latest)
6. `uv sync` - Python依存関係
7. `./scripts/build-layer.sh` - Lambda Layer
8. `pnpm install` - CDK依存関係
9. `pnpm run build` - TypeScript compile
10. `pnpm test` - Jest tests
11. `pnpm run cdk synth` - CloudFormation生成

## Deploy Job

mainブランチへのpush時に実行。

**Steps:**
1-9. Test Jobと同じビルドステップ
10. Configure AWS credentials
11. Update/Create Secrets Manager secrets
12. `pnpm run cdk deploy --require-approval never --ci`
13. Output API Gateway URL

## Required GitHub Secrets

### AWS Credentials
| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWSアクセスキーID |
| `AWS_SECRET_ACCESS_KEY` | AWSシークレットアクセスキー |

### LINE Bot Credentials
| Secret | Description |
|--------|-------------|
| `CHANNEL_SECRET` | LINEチャンネルシークレット |
| `CHANNEL_ACCESS_TOKEN` | LINEチャンネルアクセストークン |

### AI API Keys
| Secret | Description |
|--------|-------------|
| `SAMBA_NOVA_API_KEY` | SambaNova Cloud APIキー |
| `GROQ_API_KEY` | Groq APIキー |
| `XAI_API_KEY` | xAI APIキー |

## AWS Secrets Manager

GitHub Secretsの値はデプロイ時にAWS Secrets Managerに同期される:

```bash
# 作成または更新
aws secretsmanager update-secret --secret-id NAME --secret-string 'VALUE' ||
aws secretsmanager create-secret --name NAME --secret-string 'VALUE'
```

| Secret Manager Name | GitHub Secret |
|---------------------|---------------|
| LINE_CHANNEL_SECRET | CHANNEL_SECRET |
| LINE_CHANNEL_ACCESS_TOKEN | CHANNEL_ACCESS_TOKEN |
| SAMBA_NOVA_API_KEY | SAMBA_NOVA_API_KEY |
| GROQ_API_KEY | GROQ_API_KEY |
| XAI_API_KEY | XAI_API_KEY (JSON format) |

## Environment

ワークフローは `env` 環境を使用:
```yaml
environment: env
```

GitHub Settings > Environments で設定可能。

## AWS Region

デプロイリージョン: `ap-northeast-1` (Tokyo)

## Required AWS IAM Permissions

デプロイ用IAMユーザーに必要な権限:
- CloudFormation (full access)
- Lambda (full access)
- DynamoDB (full access)
- Step Functions (full access)
- API Gateway (full access)
- IAM (limited - role/policy management)
- S3 (CDK assets bucket)
- Secrets Manager (read/write)

## Deployment Outputs

成功時に出力される情報:
- API Gateway URL（LINE webhook設定用）

```bash
echo "API Gateway URL: $(aws cloudformation describe-stacks \
  --stack-name LineEchoStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
  --output text)"
```

## Troubleshooting

### AWS認証エラー
- `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`の設定確認
- IAMユーザーの権限確認

### CDKデプロイエラー
- AWSリソース制限の確認
- CloudFormation スタックのイベントログ確認

### テストエラー
```bash
cd cdk && pnpm test
```
ローカルで再現して原因特定。

### Secret作成エラー
既存シークレットと名前が競合していないか確認。

## Related Documentation

- [CI/CDセットアップガイド](../docs/cicd.md)
- [バックエンドCI/CD](../docs/backend-knowledge/ci_cd.md)
- [セキュリティ](../docs/backend-knowledge/security.md)

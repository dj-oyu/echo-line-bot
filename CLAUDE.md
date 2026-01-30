## Project Overview

LINE AIチャットボット。ユーザーのメッセージに応じて高速推論モデル（SambaNova/Groq）とxAI Grokによるディープリサーチを切り替えて応答する。

## Monorepo Structure

```
echo-line-bot/
├── lambda/          # Python Lambda関数群
├── cdk/             # AWS CDKインフラ（TypeScript）
├── scripts/         # ビルドスクリプト
├── .github/         # GitHub Actions CI/CD
└── docs/            # 詳細ドキュメント
```

各ディレクトリに `CLAUDE.md` を配置。詳細はそちらを参照。

## Technology Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.12, Node.js 20 |
| Package Managers | uv (Python), pnpm (CDK) |
| Infrastructure | AWS CDK (TypeScript) |
| Cloud Services | Lambda, API Gateway, DynamoDB, Step Functions, Secrets Manager |
| AI Providers | SambaNova, Groq, xAI (Grok-4) |
| CI/CD | GitHub Actions |
| Region | ap-northeast-1 |

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│ LINE        │────▶│ API Gateway │────▶│ Webhook      │
│ Platform    │     └─────────────┘     │ Handler      │
└─────────────┘                         └──────┬───────┘
                                               │
                                    ┌──────────▼───────────┐
                                    │   Step Functions     │
                                    └──────────┬───────────┘
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
            ┌───────▼───────┐          ┌───────▼───────┐          ┌───────▼───────┐
            │ AI Processor  │          │ Grok          │          │ Response      │
            │ (Groq/Samba)  │          │ Processor     │          │ Sender        │
            └───────────────┘          └───────────────┘          └───────────────┘
                    │                          │                          │
                    └──────────────────────────┴──────────────────────────┘
                                               │
                                    ┌──────────▼───────────┐
                                    │     DynamoDB         │
                                    │ (Conversation Store) │
                                    └──────────────────────┘
```

## Quick Start

```bash
# 依存関係インストール
uv sync                      # Python
cd cdk && pnpm install       # CDK

# Lambda Layerビルド
./scripts/build-layer.sh

# ローカルテスト
cd cdk && pnpm test

# デプロイ
cd cdk && pnpm run cdk deploy
```

## Directory-Specific Documentation

| Directory | CLAUDE.md | Description |
|-----------|-----------|-------------|
| [lambda/](lambda/CLAUDE.md) | Lambda関数、AI統合、メッセージ処理 |
| [cdk/](cdk/CLAUDE.md) | CDKスタック、AWSリソース定義 |
| [.github/](.github/CLAUDE.md) | CI/CDワークフロー、GitHub Secrets |
| [scripts/](scripts/CLAUDE.md) | ビルドスクリプト |

## Reference Documentation

`docs/` ディレクトリに詳細な技術ドキュメントを配置:

- [LINE Bot SDK](docs/line-bot-sdk/index.md)
- [AWS CDK](docs/aws-cdk/index.md)
- [SambaNova Cloud](docs/sambanova-cloud/index.md)
- [xAI Grok](docs/xai/grok_integration.md)
- [Backend Knowledge](docs/backend-knowledge/index.md)
- [CI/CD Setup](docs/cicd.md)

## Development Rules

`.claude/rules/` ディレクトリに開発ルールを定義:

| Rule File | Description |
|-----------|-------------|
| [git.md](.claude/rules/git.md) | Git workflow, commit guidelines |
| [python.md](.claude/rules/python.md) | Python/Lambda development |
| [typescript.md](.claude/rules/typescript.md) | TypeScript/CDK development |
| [security.md](.claude/rules/security.md) | Security best practices |
| [lsp.md](.claude/rules/lsp.md) | LSP integration guidelines |
| [notifications.md](.claude/rules/notifications.md) | VoiceVox notification rules |

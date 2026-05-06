# echo-line-bot

LINE bot powered by SambaNova AI (DeepSeek-V3-0324), deployed on AWS with CDK.

The bot ("あいちゃん") responds in Kansai dialect using a multi-Lambda asynchronous architecture:
- **webhook_handler** → validates LINE events, saves to DynamoDB, starts Step Functions
- **ai_processor** → calls SambaNova API with conversation history
- **response_sender** → pushes reply to LINE user

## Prerequisites

- Node.js 18+
- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- AWS CLI configured
- LINE Developer account
- SambaNova Cloud account

## Setup

1. Copy and fill credentials:
   ```bash
   cp .env.example .env.local
   # edit .env.local with CHANNEL_ACCESS_TOKEN, CHANNEL_SECRET, SAMBA_NOVA_API_KEY
   ```

2. Install dependencies:
   ```bash
   cd cdk && npm install
   uv sync
   ```

3. Deploy:
   ```bash
   cd cdk && npx cdk deploy
   ```

4. Set the API Gateway URL output as the LINE webhook endpoint.

## Development

```bash
cd cdk
npm run build    # compile TypeScript
npm run watch    # watch mode
npm test         # run Jest tests
npx cdk diff     # preview changes
```

See [docs/](docs/) for detailed documentation on LINE Bot SDK, AWS CDK, SambaNova integration, and CI/CD setup.

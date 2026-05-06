# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a LINE bot powered by SambaNova AI (DeepSeek-V3-0324) with AWS CDK infrastructure. The bot ("あいちゃん") receives messages from LINE users and replies with AI-generated responses in Kansai dialect.

## Architecture

The project uses a multi-Lambda asynchronous architecture with Step Functions:

1. **Webhook Handler** (`lambda/webhook_handler.py`): Validates LINE signatures, stores conversation context in DynamoDB, and kicks off Step Functions workflow
2. **AI Processor** (`lambda/ai_processor.py`): Calls SambaNova API with full conversation history, updates DynamoDB
3. **Response Sender** (`lambda/response_sender.py`): Sends the AI response back to the LINE user via Push API
4. **CDK Infrastructure** (`cdk/`): TypeScript CDK stack that deploys all resources

### Key Components

- **LineEchoStack** (`cdk/lib/lambda-stack.ts`): Main infrastructure stack that creates:
  - DynamoDB table (`line-bot-conversations`) for conversation history with 24h TTL
  - Lambda layer for `line-bot-sdk`, `openai`, `boto3`, `pytz` dependencies
  - `webhookHandler` Lambda (10s timeout) — receives LINE events
  - `aiProcessor` Lambda (60s timeout) — calls SambaNova API
  - `responseSender` Lambda (10s timeout) — sends Push messages to LINE
  - Step Functions state machine (`AIProcessingWorkflow`) chaining AI → Send
  - API Gateway REST API endpoint connected to `webhookHandler`

## Development Commands

### CDK Operations
```bash
cd cdk
npm install              # Install CDK dependencies
npm run build           # Compile TypeScript
npm run watch           # Watch mode for development
npm test               # Run Jest tests
npx cdk deploy         # Deploy to AWS
npx cdk diff           # Show deployment diff
npx cdk destroy        # Destroy the stack
```

### Python Dependencies
```bash
# Dependencies are managed via uv and pyproject.toml
uv sync                # Install Python dependencies
```

## Environment Configuration

The CDK stack reads environment variables from `.env.local`:
- `CHANNEL_ACCESS_TOKEN`: LINE Bot channel access token
- `CHANNEL_SECRET`: LINE Bot channel secret
- `SAMBA_NOVA_API_KEY`: SambaNova Cloud API key

These are passed to the Lambda functions as environment variables during deployment.

## Deployment

1. Ensure `.env.local` contains all three credentials above
2. Deploy the stack: `cd cdk && npx cdk deploy`
3. The output will show the API Gateway URL to configure as your LINE webhook endpoint

## Code Structure

- `lambda/webhook_handler.py`: Validates LINE webhook, stores context in DynamoDB, starts Step Functions
- `lambda/ai_processor.py`: Calls SambaNova API, manages conversation history, returns AI response
- `lambda/response_sender.py`: Sends AI response to LINE user via Push API
- `lambda/main.py`: Legacy single-file handler (not deployed, kept for reference)
- `cdk/lib/lambda-stack.ts`: Infrastructure definition using CDK constructs
- `cdk/bin/cdk.ts`: CDK app entry point
- `pyproject.toml`: Python dependencies and project metadata
- `.env.local`: Environment variables for LINE and SambaNova credentials (not in git)

## Testing

CDK tests are in `cdk/test/` but currently commented out. To run tests:
```bash
cd cdk
npm test
```

## Git Workflow Guidelines

### Branch Strategy
This project follows a simplified Git flow appropriate for a small-scale LINE bot:

- **main**: Production-ready code that is deployed to AWS
- **feature branches**: Create feature branches for new functionality (e.g., `feature/add-rich-message-support`)
- **hotfix branches**: For urgent production fixes (e.g., `hotfix/webhook-timeout`)

Always create pull requests to merge into main, even for solo development to maintain code history.

### Commit Guidelines

#### Commit Granularity
Commits should be atomic and focused on a single logical change:

**Good commit examples:**
- `fix: handle empty webhook body gracefully`
- `feat: add support for image message handling`
- `refactor: extract LINE API client configuration`
- `docs: update deployment instructions`

**Bad commit examples:**
- `fix stuff` (too vague)
- `add feature and fix bugs and update docs` (too many changes)
- `work in progress` (incomplete work)

#### Commit Timing - CRITICAL REMINDERS

**YOU MUST COMMIT AFTER EVERY SIGNIFICANT CHANGE. DO NOT FORGET TO COMMIT.**

Commit immediately after:
1. **Implementing a complete feature** - Don't wait, commit now
2. **Fixing a bug** - Commit the fix immediately
3. **Refactoring code** - Each refactor should be its own commit
4. **Adding/updating documentation** - Document changes deserve commits
5. **Infrastructure changes** - CDK stack changes must be committed
6. **Configuration updates** - Environment or build config changes

**NEVER leave uncommitted changes overnight or between work sessions.**

#### Commit Message Format
```
type(scope): description

- type: feat, fix, refactor, docs, test, chore
- scope: lambda, cdk, docs (optional)
- description: imperative mood, lowercase, no period
```

Examples:
```
feat(lambda): add support for sticker messages
fix(cdk): resolve Lambda timeout configuration
docs: update CLAUDE.md with git workflow
```

## VoiceVox Notification Guidelines

When VoiceVox MCP is available, use voice notifications to inform the user in the following situations:

1. **Task Completion**: When a long-running task is completed
2. **User Input Required**: When additional instructions or decisions are needed from the user
3. **Important Milestones**: When significant progress has been made on complex tasks

### Usage Rules
- Only use VoiceVox when tasks are expected to be long-running or complex
- Keep voice messages concise and informative
- Use appropriate Japanese for voice notifications
- Default speaker ID and speed settings are acceptable unless user specifies otherwise

## GitHub Actions Testing

This section documents testing of the CI/CD pipeline to verify GitHub Secrets configuration and deployment functionality.

### Test Execution
- Testing AWS credentials configuration
- Verifying automated deployment process
- Ensuring proper secret management
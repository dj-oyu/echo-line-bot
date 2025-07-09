# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a LINE bot echo application with AWS CDK infrastructure. The bot receives messages from LINE and replies with the same message text.

## Architecture

The project has a two-tier architecture:

1. **Lambda Function** (`lambda/main.py`): Python 3.11 Lambda that handles LINE webhook events using the LINE Bot SDK v3
2. **CDK Infrastructure** (`cdk/`): TypeScript CDK stack that deploys the Lambda with API Gateway and manages dependencies

### Key Components

- **LineEchoStack** (`cdk/lib/lambda-stack.ts`): Main infrastructure stack that creates:
  - Lambda function with Python 3.11 runtime
  - Lambda layer for line-bot-sdk dependencies
  - API Gateway REST API endpoint
  - Environment variables for LINE credentials
- **Lambda Handler** (`lambda/main.py`): Processes LINE webhook events and echoes text messages back

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

These are passed to the Lambda function as environment variables during deployment.

## Deployment

1. Ensure `.env.local` contains valid LINE credentials
2. Deploy the stack: `cd cdk && npx cdk deploy`
3. The output will show the API Gateway URL to configure as your LINE webhook endpoint

## Code Structure

- `lambda/main.py`: Single-file Lambda handler with webhook processing
- `cdk/lib/lambda-stack.ts`: Infrastructure definition using CDK constructs
- `cdk/bin/cdk.ts`: CDK app entry point
- `pyproject.toml`: Python dependencies and project metadata
- `.env.local`: Environment variables for LINE credentials (not in git)

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
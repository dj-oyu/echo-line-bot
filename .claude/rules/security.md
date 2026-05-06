---
description: Security rules for the project
globs: ["**/*"]
alwaysApply: true
---

# Security Rules

## Secrets Management

### Never Commit Secrets
- API keys
- Access tokens
- Passwords
- Private keys

### Use AWS Secrets Manager
All secrets are stored in AWS Secrets Manager and referenced by name:
- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `SAMBA_NOVA_API_KEY`
- `GROQ_API_KEY`
- `XAI_API_KEY`

### Environment Variables
Use environment variable names pointing to secret names, not values:
```python
CHANNEL_SECRET_NAME = os.getenv("CHANNEL_SECRET_NAME")  # Good
CHANNEL_SECRET = "abc123..."  # NEVER do this
```

## Files to Never Commit

- `.env` / `.env.local` (use `.env.example` for templates)
- `credentials.json`
- `*.pem` / `*.key`
- AWS credential files

## Code Security

### Input Validation
Validate all external input:
- LINE webhook signatures
- User message content
- API responses

### LINE Webhook Verification
Always verify X-Line-Signature:
```python
try:
    handler.handle(body, signature)
except InvalidSignatureError:
    return {'statusCode': 400, 'body': 'Invalid Signature'}
```

### Logging
Never log:
- Full API keys
- User credentials
- Sensitive personal data

Safe logging pattern:
```python
logger.info("Processing message for user: %s", user_id[:8] + "...")
```

## GitHub Secrets

Required secrets in GitHub repository settings:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `CHANNEL_SECRET`
- `CHANNEL_ACCESS_TOKEN`
- `SAMBA_NOVA_API_KEY`
- `GROQ_API_KEY`
- `XAI_API_KEY`

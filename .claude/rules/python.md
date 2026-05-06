---
description: Python Lambda development rules
globs: ["lambda/**/*.py", "**/*.py"]
alwaysApply: false
---

# Python Development Rules

## Runtime & Tools

- **Python**: 3.12
- **Package Manager**: uv
- **Dependencies**: Defined in `pyproject.toml`

## Code Style

### Imports
Order imports as:
1. Standard library
2. Third-party packages
3. Local modules

```python
import json
import logging
import os

import boto3
from linebot.v3 import WebhookHandler

import ai_processor
```

### Logging
Use the standard logging pattern:
```python
logger = logging.getLogger()
logger.setLevel(logging.INFO)
```

### Type Hints
Use type hints for function signatures:
```python
def get_secret(secret_name: str) -> str:
    ...
```

## AWS Integration

### Secrets Manager
Never hardcode secrets. Use Secrets Manager:
```python
secretsmanager = boto3.client('secretsmanager')

def get_secret(secret_name: str) -> str:
    response = secretsmanager.get_secret_value(SecretId=secret_name)
    return response['SecretString']
```

### DynamoDB
Use boto3.resource for table operations:
```python
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)
```

### Environment Variables
Access via os.getenv with descriptive names:
```python
CHANNEL_SECRET_NAME = os.getenv("CHANNEL_SECRET_NAME")
```

## Lambda Handler Pattern

```python
def lambda_handler(event, context):
    logger.info("Received event: %s", json.dumps(event))

    try:
        # Process event
        result = process(event)
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

## Testing

Run tests with:
```bash
uv run pytest
uv run pytest lambda/tests/ -v
```

## Dependencies

Update dependencies:
```bash
uv sync
./scripts/build-layer.sh
```

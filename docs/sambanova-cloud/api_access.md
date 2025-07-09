# API Access and Authentication

To integrate our chatbot with SambaNova Cloud, we need to understand how to securely access its API and make requests.

## 1. Authentication Method: API Keys

SambaNova Cloud primarily uses **API Keys** for authentication. An API key is a unique string that identifies your application and authorizes your requests. It should be kept confidential.

### Obtaining an API Key

You can generate your API key from the SambaNova Cloud platform, typically by navigating to a section like `cloud.sambanova.ai/apis` after logging into your account.

## 2. Making API Requests

Once you have an API key, you can include it in your API requests. SambaNova Cloud's API is designed to be straightforward, often following RESTful principles.

### Using the `Authorization` Header

For direct HTTP requests, the API key is typically passed in the `Authorization` header as a Bearer token:

```http
Authorization: Bearer <YOUR_SAMBANOVA_API_KEY>
Content-Type: application/json
```

### Example with `curl`

```bash
curl -H "Authorization: Bearer <YOUR_SAMBANOVA_API_KEY>" \
     -H "Content-Type: application/json" \
     -d '{
           "stream": false, # or true for streaming responses
           "model": "DeepSeek-V3-0324", # Example model
           "messages": [
             {"role": "system", "content": "You are a helpful assistant"},
             {"role": "user", "content": "Hello"}
           ]
         }' \
     -X POST https://api.sambanova.ai/v1/chat/completions
```

## 3. OpenAI-Compatible API Endpoint

A significant advantage for integration is that SambaNova Cloud offers an **OpenAI-compatible API endpoint** (`https://api.sambanova.ai/v1`). This means we can leverage the widely-used `openai` Python library to interact with SambaNova Cloud, simplifying development.

### Using the `openai` Python Library

If you are using Python (as our Lambda function does), you can use the `openai` library by configuring its `api_key` and `base_url`:

First, install the library:

```bash
pip install openai
```

Then, in your Python code:

```python
from openai import OpenAI
import os

# It's best practice to load API keys from environment variables
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY")

client = OpenAI(
    api_key=SAMBANOVA_API_KEY,
    base_url="https://api.sambanova.ai/v1"
)

# Example: Chat Completion
response = client.chat.completions.create(
    model="DeepSeek-V3-0324", # Replace with the actual model you want to use
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"}
    ]
)

print(response.choices[0].message.content)
```

This approach greatly streamlines the process of sending prompts and receiving responses from SambaNova Cloud's LLMs.

## 4. Secure Storage of API Keys

Similar to our LINE channel credentials, the SambaNova API Key should be treated as a secret. It should **not be hardcoded** in your source code. Instead, it should be loaded from environment variables (e.g., using `os.getenv()` in Python) which are securely managed (e.g., via AWS Secrets Manager or passed through CDK environment variables).


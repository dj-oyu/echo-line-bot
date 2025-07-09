# Authentication

To communicate with the LINE Messaging API, our application must prove its identity and authorization. This is handled by the Channel Secret and Channel Access Token.

These credentials are created in the [LINE Developer Console](https://developers.line.biz/console/) for your specific bot's channel.

## 1. Channel Secret

- **Purpose**: Used to verify that webhooks received by our application are genuinely from the LINE Platform. It acts like a shared secret for validating message signatures.
- **SDK Component**: `WebhookHandler`
- **Usage**: The `WebhookHandler` uses the Channel Secret to calculate a signature from the webhook's request body and compares it to the `X-Line-Signature` header sent by LINE. If they don't match, an `InvalidSignatureError` is raised. This prevents third parties from sending malicious requests to our endpoint.

```python
# The handler is initialized with the Channel Secret
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# The handle method performs the signature validation
try:
    handler.handle(body, signature)
except InvalidSignatureError:
    # Abort if the signature is invalid
```

## 2. Channel Access Token

- **Purpose**: Used as an authorization token when our application calls the LINE Messaging API (e.g., to send a reply message).
- **SDK Component**: `Configuration`
- **Usage**: The Channel Access Token is passed in the `Authorization` header of our API requests to LINE. The `Configuration` object holds this token, and the `ApiClient` uses it to authenticate our API calls.

```python
# The configuration is initialized with the Channel Access Token
configuration = Configuration(
    access_token=os.getenv("CHANNEL_ACCESS_TOKEN")
)

# The ApiClient uses this configuration to make authenticated calls
with ApiClient(configuration) as api_client:
    line_bot_api = MessagingApi(api_client)
    # ... call line_bot_api methods
```

## 3. Secure Storage

As shown in the code, these credentials should **never be hardcoded** in the source files. In this project:

1.  They are stored in a `.env.local` file at the root of the project.
2.  The AWS CDK stack (`lib/lambda-stack.ts`) reads this file using `dotenv`.
3.  The CDK then injects these values as **environment variables** into the deployed Lambda function.
4.  The Python code in `lambda/main.py` reads the credentials from the environment using `os.getenv()`.

This ensures the secrets are kept separate from the code and are managed securely.

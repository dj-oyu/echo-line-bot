# LINE Bot SDK for Python

This documentation provides a deep dive into the `line-bot-sdk` for Python, which is used as the core of our LINE bot.

## 1. Overview

The `line-bot-sdk` allows our application to interact with the LINE Messaging API. Its primary responsibilities in this project are:

- **Receiving and Parsing Webhooks**: When a user interacts with our bot, LINE sends a webhook (an HTTP POST request) to our server. The SDK validates these requests and parses them into easy-to-use Python objects.
- **Replying to Users**: It provides methods to send various types of messages back to the user who initiated the event.

This project uses the `v3` version of the SDK, which is the latest and recommended version.

## 2. Installation

The SDK is listed as a dependency in `pyproject.toml` and installed via `uv`.

```toml
# pyproject.toml
dependencies = [
    "line-bot-sdk>=3.17.1",
]
```

To install dependencies for local development, run `uv pip install -r requirements.txt` or `uv sync` after setting up the virtual environment.

## 3. Core Components & Initial Setup

As seen in `lambda/main.py`, there are a few essential components from the SDK that we need to initialize.

### `Configuration`

This object holds the authentication credential for our bot.

- **`access_token`**: The Channel Access Token obtained from the LINE Developer Console. This token authorizes our application to call the Messaging API.

```python
# lambda/main.py

from linebot.v3.messaging import Configuration

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
```

### `WebhookHandler`

This object is responsible for processing the incoming webhook requests from the LINE Platform.

- **`channel_secret`**: The Channel Secret from the LINE Developer Console. This is used to verify that the webhook request genuinely came from LINE and not a malicious third party.

```python
# lambda/main.py

from linebot.v3 import WebhookHandler

CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
handler = WebhookHandler(CHANNEL_SECRET)
```

The handler uses the signature sent in the `X-Line-Signature` request header to validate the request body. If the signature is invalid, it raises an `InvalidSignatureError`.

## Next Steps

- [**Handling Webhooks**](./webhooks.md)
- [**Sending Messages**](./sending_messages.md)
- [**Event Types**](./event_types.md)

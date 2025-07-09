# Sending Messages

This document covers how to send messages to users using the `line-bot-sdk`.

## 1. The `MessagingApi` Client

All message-sending operations are performed via the `MessagingApi` class. To use it, you first need to create an `ApiClient` instance, which is initialized with your bot's `Configuration` (containing the channel access token).

The recommended way to use the `ApiClient` is with a `with` statement, which ensures that the connection is properly closed.

```python
# lambda/main.py

from linebot.v3.messaging import ApiClient, MessagingApi

# ... (configuration is defined)

with ApiClient(configuration) as api_client:
    line_bot_api = MessagingApi(api_client)
    # ... use line_bot_api to send messages
```

## 2. Replying vs. Pushing

There are two main ways to send a message:

### Reply Messages

- **Method**: `reply_message_with_http_info(ReplyMessageRequest(...))`
- **When to use**: When responding to a user interaction within a webhook. This is the most common type of message.
- **Requirement**: You need a `reply_token` from the event object you received. This token is valid for a single reply and expires quickly.
- **Benefit**: The user knows the message is a direct response to their action. It's also free.

**Example from `lambda/main.py`:**
```python
# Replying to a text message
line_bot_api.reply_message_with_http_info(
    reply_message_request=ReplyMessageRequest(
        replyToken=event.reply_token,
        messages=[TextMessage(text=event.message.text)]
    )
)
```

### Push Messages

- **Method**: `push_message(PushMessageRequest(...))`
- **When to use**: When you want to send a message proactively, not in direct response to a user action. For example, sending a notification or a scheduled message.
- **Requirement**: You need the `user_id` of the recipient. You can get this from the `event.source` object in a webhook and store it for later use.
- **Cost**: Push messages may be subject to charges depending on your LINE Official Account plan.

**Example:**
```python
# Proactively sending a message to a user
line_bot_api.push_message(PushMessageRequest(
    to='U1234567890abcdef1234567890abcdef', # A valid user_id
    messages=[TextMessage(text='This is a notification!')]
))
```

## 3. Message Objects

You can send more than just plain text. The SDK provides various message objects that can be included in the `messages` list of a reply or push request.

- `TextMessage`: A simple text message.
- `StickerMessage`: A LINE sticker.
- `ImageMessage`: An image, specified by a URL.
- `VideoMessage`: A video, specified by a URL.
- `AudioMessage`: An audio file.
- `LocationMessage`: A map location.
- `TemplateMessage`: More complex, structured messages with buttons and actions, such as:
    - `ButtonsTemplate`
    - `ConfirmTemplate`
    - `CarouselTemplate`

Each message object has its own specific parameters.

### Example: Sending an Image

```python
from linebot.v3.messaging import ImageMessage

image_message = ImageMessage(
    originalContentUrl='https://example.com/image.jpg',
    previewImageUrl='https://example.com/preview.jpg'
)

line_bot_api.reply_message_with_http_info(
    ReplyMessageRequest(
        replyToken=event.reply_token,
        messages=[image_message]
    )
)
```

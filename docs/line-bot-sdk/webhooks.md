# Handling Webhooks

The `WebhookHandler` is the central component for processing events from the LINE Platform. This document explains how it works and how to use it.

## 1. The Webhook Flow

1.  A user interacts with the LINE Bot (e.g., sends a message).
2.  The LINE Platform sends an HTTP POST request with a JSON payload to the Webhook URL configured in the LINE Developer Console.
3.  Our application receives this request. In this project, the request is handled by Amazon API Gateway, which triggers our Lambda function.
4.  The `x-line-signature` header and the request body are passed to `handler.handle(body, signature)`.
5.  The handler first validates the signature to ensure the request is authentic.
6.  If the signature is valid, the handler parses the JSON body into specific `Event` objects.
7.  It then calls the appropriate function that has been registered to handle that specific event type.

## 2. Registering Event Handlers

We use the `@handler.add()` decorator to associate a function with one or more event types. This is the primary mechanism for defining the bot's behavior.

The decorator takes the `Event` class as its first argument. For `MessageEvent`, you can provide a second argument, `message`, to specify the content type of the message.

### Example from `lambda/main.py`

This code registers the `handle_message` function to be called whenever a `MessageEvent` containing `TextMessageContent` is received.

```python
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # ... logic to handle the text message ...
    # The `event` object contains all the information
```

## 3. The `event` Object

The `event` object passed to your handler function contains all the information about the interaction. Its attributes vary depending on the event type, but some common ones are:

- **`event.source`**: Information about where the event came from (a user, a group, or a room). Can be `event.source.user_id`.
- **`event.timestamp`**: The time the event occurred.
- **`event.mode`**: The channel state (`active` or `standby`).
- **`event.reply_token`**: A one-time token used to reply to this specific event. It becomes invalid after a short period.

For a `MessageEvent` with `TextMessageContent`, it also contains:

- **`event.message.id`**: The ID of the message.
- **`event.message.text`**: The text content of the message.

## 4. Handling Multiple Event Types

You can register handlers for many other event types to make your bot more interactive.

```python
from linebot.v3.webhooks import FollowEvent, PostbackEvent

# Handler for when a user follows the bot
@handler.add(FollowEvent)
def handle_follow(event):
    # Send a welcome message
    line_bot_api.reply_message(
        reply_token=event.reply_token,
        messages=[TextMessage(text='Thanks for following!')]
    )

# Handler for postback events from rich menus, etc.
@handler.add(PostbackEvent)
def handle_postback(event):
    # Parse data from event.postback.data
    data = event.postback.data
    # ... perform some action based on the data
```

## Next Steps

- [**Sending Messages**](./sending_messages.md)
- [**Event Types**](./event_types.md)

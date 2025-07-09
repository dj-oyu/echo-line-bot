# Event Types Reference

When the LINE Platform sends a webhook to our bot, it contains one or more `Event` objects. This document provides a reference for the most common event types.

Each event is a Python object with attributes that hold information about the interaction. You can define handlers for each of these events using the `@handler.add(EventType)` decorator.

---

## Message Events

Triggered when a user sends a message to the bot.

- **`MessageEvent`**: The base event for any message.

#### Message Content Types

You can specify the content type in the handler decorator (e.g., `@handler.add(MessageEvent, message=TextMessageContent)`).

- **`TextMessageContent`**: A plain text message. The content is in `event.message.text`.
- **`ImageMessageContent`**: An image. The user has sent a picture.
- **`VideoMessageContent`**: A video.
- **`AudioMessageContent`**: An audio file.
- **`FileMessageContent`**: A generic file.
- **`LocationMessageContent`**: A location pin.
- **`StickerMessageContent`**: A LINE sticker. Details are in `event.message.package_id` and `event.message.sticker_id`.

---

## User Interaction Events

Triggered by user actions other than sending messages.

- **`FollowEvent`**: A user adds the bot as a friend. This is a great opportunity to send a welcome message. Contains a `reply_token`.
- **`UnfollowEvent`**: A user blocks the bot or removes it as a friend. This event has no `reply_token`.
- **`PostbackEvent`**: A user taps a button in a template message or a rich menu that has a `postback` action. The data you defined for the action is in `event.postback.data`.
- **`AccountLinkEvent`**: Triggered when a user completes or fails the account linking process.

---

## Group/Room Events

Triggered by events in multi-person chats.

- **`JoinEvent`**: The bot is invited to and joins a group or room. Contains a `reply_token`.
- **`LeaveEvent`**: The bot is removed from a group or room. No `reply_token`.
- **`MemberJoinedEvent`**: A user joins a group/room that the bot is already in. You can use this to welcome new members. Contains a `reply_token`.
- **`MemberLeftEvent`**: A user leaves a group/room that the bot is in.

---

## Other Events

- **`BeaconEvent`**: Triggered when a user comes within range of a LINE Beacon. The beacon's hardware ID and type are in `event.beacon.hwid` and `event.beacon.type`.

For a complete and up-to-date list of all event types and their detailed JSON structure, always refer to the official LINE API documentation.

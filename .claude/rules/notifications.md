---
description: VoiceVox notification guidelines
globs: ["**/*"]
alwaysApply: false
---

# VoiceVox Notification Rules

## When to Use

Use VoiceVox MCP for voice notifications in these situations:

1. **Task Completion**: Long-running task finished
2. **User Input Required**: Need user decision or clarification
3. **Important Milestones**: Significant progress on complex tasks

## When NOT to Use

- Simple, quick operations
- Routine file reads/writes
- Standard command execution
- Every intermediate step

## Message Guidelines

### Language
- Use Japanese for all notifications
- Keep messages concise and informative

### Examples

**Good:**
- 「デプロイが完了しました」
- 「テストが失敗しました。確認が必要です」
- 「ビルドが完了しました。次のステップに進みます」

**Bad:**
- Long technical explanations
- English messages (unless user prefers)
- Every small step notification

## Settings

Use default settings unless user specifies otherwise:
- Default speaker ID
- Default speed
- Default volume

import json
import os
import sys
from types import SimpleNamespace as Block
from unittest.mock import patch

import anthropic
import httpx2
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import ai_processor


@pytest.mark.parametrize(
    "content,stop,expected_search",
    [
        ([{"type": "text", "text": "こんにちは"}], "end_turn", False),
        (
            [
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "search_with_grok",
                    "input": {"query": "最新のAWS"},
                }
            ],
            "tool_use",
            True,
        ),
    ],
)
def test_real_sdk_serializes_request_and_parses_response_offline(content, stop, expected_search):
    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "msg_offline",
                "type": "message",
                "role": "assistant",
                "model": "claude-haiku-5-5",
                "content": content,
                "stop_reason": stop,
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    with httpx2.Client(transport=httpx2.MockTransport(transport)) as http_client:
        sdk = anthropic.Anthropic(api_key="offline-dummy", http_client=http_client, max_retries=0)
        with (
            patch.object(ai_processor, "AI_SELECT", "anthropic"),
            patch.object(ai_processor, "anthropic_client", sdk),
        ):
            result = ai_processor.get_ai_response([{"role": "user", "content": "こんにちは"}])
    assert result["hasToolCall"] is expected_search
    assert len(requests) == 1
    assert requests[0]["model"] == "claude-haiku-5-5"
    assert requests[0]["output_config"] == {"effort": "low"}


@pytest.fixture
def client():
    with (
        patch.object(ai_processor, "AI_SELECT", "anthropic"),
        patch.object(ai_processor, "get_anthropic_client") as factory,
    ):
        yield factory.return_value


def respond(client, blocks, stop="end_turn"):
    client.messages.create.return_value = Block(content=blocks, stop_reason=stop)
    return ai_processor.get_ai_response([{"role": "user", "content": "@bot こんにちは"}])


def search(query="最新のAWS", prompt="要約して"):
    return Block(type="tool_use", name="search_with_grok", input={"query": query, "prompt": prompt})


def test_request_preserves_shared_prompt_history_and_schema(client):
    history = [{"role": "user", "content": "@bot こんにちは"}]
    with patch.object(
        ai_processor, "prepare_messages_for_api", wraps=ai_processor.prepare_messages_for_api
    ) as prepare:
        respond(client, [Block(type="text", text="こんにちは")])
    prepare.assert_called_once_with(history)
    request = client.messages.create.call_args.kwargs
    assert request["model"] == "claude-haiku-5-5"
    assert request["messages"] == [{"role": "user", "content": "こんにちは"}]
    assert "関西弁" in request["system"]
    assert "temperature" not in request
    assert "top_p" not in request
    assert request["tool_choice"] == {"type": "auto"}
    assert request["tools"][0]["input_schema"] == {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "検索クエリ"},
            "prompt": {"type": "string", "description": "検索結果をどのように使用するかの説明"},
        },
        "required": ["query"],
    }


def test_no_search_with_thinking_and_multiple_text_blocks(client):
    result = respond(
        client,
        [
            Block(type="thinking", thinking="private", signature="signature"),
            Block(type="text", text="**こんにちは**"),
            Block(type="redacted_thinking", data="private"),
            Block(type="text", text="元気やで"),
        ],
    )
    assert result == {"hasToolCall": False, "aiResponse": "こんにちは\n元気やで"}


def test_single_search_with_thinking_and_text(client):
    result = respond(
        client, [Block(type="thinking"), Block(type="text", text="調べるで"), search()], "tool_use"
    )
    assert result == {
        "hasToolCall": True,
        "toolName": "search_with_grok",
        "toolQuery": "最新のAWS",
        "toolPrompt": "要約して",
    }


def test_multiple_searches_keep_all_queries_and_prompts(client):
    result = respond(
        client, [search("東京", "東京の天気"), search("大阪", "大阪の天気")], "tool_use"
    )
    assert result["toolQuery"] == "東京\n大阪"
    assert result["toolPrompt"] == "東京の天気\n大阪の天気"


def test_optional_prompt(client):
    block = Block(type="tool_use", name="search_with_grok", input={"query": "天気"})
    assert respond(client, [block], "tool_use")["toolPrompt"] == ""


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"query": ""},
        {"query": "  "},
        {"query": None},
        {"query": 42},
        {"query": []},
        {"query": "天気", "prompt": None},
        {"query": "天気", "prompt": {}},
        None,
        "invalid json",
        [],
    ],
)
def test_invalid_arguments_do_not_trigger_search(client, args):
    result = respond(
        client, [Block(type="tool_use", name="search_with_grok", input=args)], "tool_use"
    )
    assert result["hasToolCall"] is False
    assert result["aiResponse"]


def test_invalid_second_call_does_not_dispatch_partial_search(client):
    assert respond(client, [search(), search("")], "tool_use")["hasToolCall"] is False


@pytest.mark.parametrize(
    "stop", ["max_tokens", "pause_turn", "refusal", "model_context_window_exceeded", None]
)
def test_incomplete_turn_does_not_publish_partial_answer_or_call(client, stop):
    assert (
        respond(client, [Block(type="text", text="途中"), search()], stop)["hasToolCall"] is False
    )


@pytest.mark.parametrize(
    "blocks,stop",
    [
        ([], "end_turn"),
        ([Block(type="thinking")], "end_turn"),
        ([Block(type="text", text=" ")], "end_turn"),
        ([search()], "end_turn"),
        ([Block(type="text", text="回答")], "tool_use"),
        ([Block(type="tool_use", name="unknown", input={})], "tool_use"),
    ],
)
def test_empty_or_inconsistent_response_uses_failure_answer(client, blocks, stop):
    result = respond(client, blocks, stop)
    assert result["hasToolCall"] is False
    assert "こんがらがって" in result["aiResponse"]


def test_api_failure_is_sanitized(client, caplog):
    client.messages.create.side_effect = RuntimeError("do-not-log-secret")
    result = ai_processor.get_ai_response([{"role": "user", "content": "こんにちは"}])
    assert result["hasToolCall"] is False
    assert "do-not-log-secret" not in caplog.text


def test_client_resolves_secret_only_once():
    with (
        patch.object(ai_processor, "anthropic_client", None),
        patch.object(ai_processor, "ANTHROPIC_API_KEY_NAME", "test-anthropic-key"),
        patch("line_messaging.get_secret", return_value="dummy") as secret,
        patch("anthropic.Anthropic") as factory,
    ):
        assert ai_processor.get_anthropic_client() is ai_processor.get_anthropic_client()
        secret.assert_called_once_with("test-anthropic-key")
        factory.assert_called_once_with(api_key="dummy", timeout=45.0, max_retries=0)


def test_handler_search_routes_without_saving_interim(client):
    client.messages.create.return_value = Block(content=[search()], stop_reason="tool_use")
    event = {
        "userId": "test",
        "conversationContext": {"messages": [{"role": "user", "content": "天気"}]},
    }
    with patch("line_messaging.push_text") as push, patch("line_messaging.append_and_save") as save:
        assert ai_processor.lambda_handler(event, None)["hasToolCall"] is True
        push.assert_called_once()
        save.assert_not_called()


def test_handler_direct_answer_delivers_and_saves(client):
    client.messages.create.return_value = Block(
        content=[Block(type="text", text="こんにちは")], stop_reason="end_turn"
    )
    event = {
        "userId": "test",
        "conversationContext": {"messages": [{"role": "user", "content": "挨拶して"}]},
    }
    with patch("line_messaging.push_text") as push, patch("line_messaging.append_and_save") as save:
        assert ai_processor.lambda_handler(event, None)["hasToolCall"] is False
        push.assert_called_once_with(event, "こんにちは", retry_key=None)
        save.assert_called_once()

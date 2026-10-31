"""WebSocket 流编解码单元测试。"""
import asyncio
import base64
import json

import pytest

from monkeycode.errors import APIError, AuthenticationError
from monkeycode.stream import (
    _ws_connect,
    decode_chunk,
    encode_user_input,
    format_round_text,
    round_kind,
    round_label,
)


def test_encode_user_input_structure() -> None:
    raw = encode_user_input("继续", [{"url": "a"}])
    obj = json.loads(raw)
    assert obj["type"] == "user-input"
    # 外层 data 是 base64(内层 JSON)
    inner = json.loads(base64.b64decode(obj["data"]).decode("utf-8"))
    assert inner["attachments"] == [{"url": "a"}]
    # 内层 content 是 base64(文本)
    assert base64.b64decode(inner["content"]).decode("utf-8") == "继续"


def test_decode_chunk_base64_json_data() -> None:
    inner = json.dumps({"request_id": "r1", "answers": ["ok"]})
    raw = json.dumps({"type": "reply-question", "data": base64.b64encode(inner.encode()).decode()})
    chunk = decode_chunk(raw)
    assert chunk.type == "reply-question"
    assert chunk.data == {"request_id": "r1", "answers": ["ok"]}


def test_decode_chunk_base64_plain_data() -> None:
    raw = json.dumps({"type": "message", "data": base64.b64encode(b"hello").decode()})
    chunk = decode_chunk(raw)
    assert chunk.type == "message"
    assert chunk.data == "hello"


def test_decode_chunk_dict_data() -> None:
    raw = json.dumps({"type": "event", "data": {"a": 1}})
    chunk = decode_chunk(raw)
    assert chunk.type == "event"
    assert chunk.data == {"a": 1}


def test_decode_chunk_non_json() -> None:
    chunk = decode_chunk("not-json")
    assert chunk.type == "raw"
    assert chunk.data == "not-json"


def test_decode_chunk_metadata() -> None:
    raw = json.dumps({"type": "task-started", "timestamp": 123, "turn_seq": 5, "data": ""})
    chunk = decode_chunk(raw)
    assert chunk.type == "task-started"
    assert chunk.timestamp == 123
    assert chunk.turn_seq == 5


def test_format_round_text_user_input_outer_envelope() -> None:
    text = format_round_text(json.loads(encode_user_input("继续")))
    assert text == "继续"


def test_format_round_text_user_input_double_b64() -> None:
    inner = json.dumps(
        {
            "content": base64.b64encode(
                "给我当前在运行的会话和账户详情".encode()
            ).decode(),
            "attachments": [],
        }
    )
    data = base64.b64encode(inner.encode()).decode()
    assert format_round_text(data) == "给我当前在运行的会话和账户详情"


def test_format_round_text_available_commands_update() -> None:
    payload = {
        "sessionId": "ses_e783",
        "update": {
            "sessionUpdate": "available_commands_update",
            "availableCommands": [
                {"name": "customize-opencode", "description": "x"},
                {"name": "deploy-website"},
            ],
        },
    }
    text = format_round_text(payload)
    # 前缀由标签提供，text 只返回纯内容
    assert not text.startswith("[可用命令更新]")
    assert "customize-opencode" in text
    assert "deploy-website" in text


def test_format_round_text_agent_message() -> None:
    payload = {
        "sessionId": "ses_1",
        "update": {
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": "正在查看会话"},
        },
    }
    assert format_round_text(payload) == "正在查看会话"


def test_format_round_text_agent_thought_chunk() -> None:
    payload = {
        "sessionId": "ses_1",
        "update": {
            "sessionUpdate": "agent_thought_chunk",
            "thought": {"type": "text", "text": "让我先读取文件"},
        },
    }
    assert format_round_text(payload) == "让我先读取文件"


def test_format_round_text_usage_update() -> None:
    payload = {
        "sessionId": "ses_1",
        "update": {
            "sessionUpdate": "usage_update",
            "usage": {"totalTokens": 1234},
        },
    }
    assert format_round_text(payload) == "用量：1234"


def test_format_round_text_tool_call() -> None:
    payload = {
        "sessionId": "ses_1",
        "update": {
            "sessionUpdate": "tool_call",
            "title": "Read App.vue",
            "kind": "read",
            "status": "completed",
        },
    }
    text = format_round_text(payload)
    assert not text.startswith("[工具调用]")
    assert "Read App.vue" in text


def test_format_round_text_redacts_envs() -> None:
    """call 事件中的 execution_config.envs 不得泄露密钥。"""
    payload = {
        "sessionId": "ses_1",
        "update": {
            "sessionUpdate": "call",
            "title": "RunCommand",
            "status": "pending",
            "execution_config": {
                "envs": {
                    "OPENAI_API_KEY": "sk-secret-abc",
                    "OPEN_CODE_API_KEY": "secret-def",
                }
            },
        },
    }
    text = format_round_text(payload)
    assert "sk-secret-abc" not in text
    assert "secret-def" not in text
    assert "OPENAI_API_KEY" not in text
    assert "RunCommand" in text


def test_round_kind_and_label_classify() -> None:
    commands = {
        "sessionId": "ses_1",
        "update": {
            "sessionUpdate": "available_commands_update",
            "availableCommands": [{"name": "customize-opencode"}],
        },
    }
    assert round_kind(commands) == "commands"
    assert round_label(commands) == "命令更新"

    agent = {
        "update": {
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": "正在查看"},
        },
    }
    assert round_kind(agent) == "agent"
    assert round_label(agent) == "Agent"

    tool = {
        "update": {
            "sessionUpdate": "tool_call",
            "title": "Read",
            "kind": "read",
            "status": "completed",
        },
    }
    assert round_kind(tool) == "tool"
    assert round_label(tool) == "工具"

    thought = {
        "update": {"sessionUpdate": "agent_thought_chunk", "thought": "x"},
    }
    assert round_kind(thought) == "agent"
    assert round_label(thought) == "思考"

    usage = {
        "update": {"sessionUpdate": "usage_update", "usage": {"totalTokens": 1}},
    }
    assert round_kind(usage) == "system"
    assert round_label(usage) == "用量"

    call = {
        "update": {"sessionUpdate": "call", "title": "RunCommand"},
    }
    assert round_kind(call) == "tool"
    assert round_label(call) == "调用"

    user = {"type": "user-input", "content": "继续"}
    assert round_kind(user) == "user"
    assert round_label(user) == "用户输入"

    ended = {"type": "task-ended", "data": ""}
    assert round_kind(ended) == "system"
    assert round_label(ended) == "任务结束"

    plain = "hello"
    assert round_kind(plain) == "other"
    assert round_label(plain, "some-event") == "some-event"


def test_redact_sensitive_nested_json_string() -> None:
    from monkeycode.stream import _redact_sensitive

    # config_files.content 是内嵌 JSON 字符串，应解析后脱敏
    payload = {
        "config_files": [
            {
                "path": "~/.local/share/opencode/auth.json",
                "content": json.dumps(
                    {"key": "125cb3d5-secret-token", "opencode_api_key": "sk-abc"}
                ),
            }
        ]
    }
    out = _redact_sensitive(payload)
    content = out["config_files"][0]["content"]
    assert "125cb3d5-secret-token" not in content
    assert "sk-abc" not in content
    assert "key" in content


def test_redact_sensitive_public_alias() -> None:
    from monkeycode.stream import redact_sensitive

    obj = {
        "execution_config": {"envs": {"OPENAI_API_KEY": "sk-123"}},
        "name": "ok",
        "nested": {"password": "p", "keep": 1},
    }
    out = redact_sensitive(obj)
    assert out["execution_config"]["envs"] == {"***": "***"}
    assert out["nested"]["password"] == "***"
    assert out["nested"]["keep"] == 1
    assert out["name"] == "ok"


# ---------- 连接异常包装 ----------

class _FakeResp:
    def __init__(self, status_code: int, body: bytes = b""):
        self.status_code = status_code
        self.body = body


def _raise_invalid_status(status: int):
    from websockets.exceptions import InvalidStatus

    async def fake_connect(*args, **kwargs):
        raise InvalidStatus(_FakeResp(status))

    return fake_connect


def test_ws_connect_401_wraps_authentication_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "monkeycode.stream.websockets.connect", _raise_invalid_status(401)
    )
    with pytest.raises(AuthenticationError) as ei:
        asyncio.run(_ws_connect("ws://x", {}))
    assert ei.value.code == 401


def test_ws_connect_400_wraps_api_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "monkeycode.stream.websockets.connect", _raise_invalid_status(400)
    )
    with pytest.raises(APIError) as ei:
        asyncio.run(_ws_connect("ws://x", {}))
    assert ei.value.code == 400
    assert "400" in str(ei.value)


def test_ws_connect_oserror_wraps_api_error(monkeypatch) -> None:
    async def fake_connect(*args, **kwargs):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr("monkeycode.stream.websockets.connect", fake_connect)
    with pytest.raises(APIError):
        asyncio.run(_ws_connect("ws://x", {}))


def test_ws_connect_success(monkeypatch) -> None:
    async def fake_connect(*args, **kwargs):
        return "ws-obj"

    monkeypatch.setattr("monkeycode.stream.websockets.connect", fake_connect)
    assert asyncio.run(_ws_connect("ws://x", {})) == "ws-obj"
"""WebSocket 流编解码单元测试。"""
import base64
import json

from monkeycode.stream import decode_chunk, encode_user_input


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
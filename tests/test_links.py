"""链接提取 / 存活检测单元测试。"""
import base64
import json

import pytest

from monkeycode.links import (
    _clean_url,
    _decode_data,
    _to_text,
    _unescape,
    check_url_status,
    collect_preview_links,
    extract_urls_from_chunk,
)


def b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


# ---------- 解码层 ----------

def test_decode_data_base64_str() -> None:
    assert _decode_data(b64("hello")) == "hello"


def test_decode_data_plain_str() -> None:
    assert _decode_data("not base64!!!") == "not base64!!!"


def test_decode_data_dict() -> None:
    assert _decode_data({"a": 1}) == '{"a": 1}'


def test_to_text_json_object() -> None:
    decoded = json.dumps({"url": "http://x"})
    assert _to_text(decoded) == decoded


def test_to_text_plain() -> None:
    assert _to_text("plain") == "plain"


def test_unescape() -> None:
    # 注意：_unescape 将 \t 替换为空格，\r 移除，\n 保留换行
    assert _unescape('a\\nb\\t\\"c\\r') == 'a\nb "c'


# ---------- 清洗 / 过滤 ----------

def test_clean_url_trailing_punctuation() -> None:
    assert _clean_url("http://localhost:8000).") == "http://localhost:8000"


def test_clean_url_splits_newline() -> None:
    assert _clean_url("http://localhost:8000\nrest") == "http://localhost:8000"


def test_clean_url_trailing_backslash() -> None:
    assert _clean_url("http://localhost:8000\\\\") == "http://localhost:8000"


def test_extract_filters_well_known() -> None:
    raw = b64(
        json.dumps(
            {"data": "https://monkeycode-ai.online/.well-known/mcai-preview-connect-status-detect"}
        )
    )
    chunk = {"data": raw}
    assert extract_urls_from_chunk(chunk) == []


def test_extract_filters_truncated_percent() -> None:
    # 截断的 percent-encoding：%E 只有 1 位十六进制
    raw = b64(json.dumps({"data": "https://monkeycode-ai.online/%E6%8E%A2%E"}))
    chunk = {"data": raw}
    assert extract_urls_from_chunk(chunk) == []


# ---------- extract_urls_from_chunk ----------

def test_extract_from_base64_json_data() -> None:
    inner = json.dumps({"content": "预览：http://localhost:8000/app"})
    chunk = {"type": "message", "data": b64(inner)}
    assert extract_urls_from_chunk(chunk) == ["http://localhost:8000/app"]


def test_extract_from_plain_text() -> None:
    chunk = {"type": "message", "data": "看这里 https://monkeycode-ai.online:8000/x"}
    assert extract_urls_from_chunk(chunk) == [
        "https://monkeycode-ai.online:8000/x"
    ]


def test_extract_filters_non_preview() -> None:
    chunk = {"type": "message", "data": "https://example.com 和 http://localhost:8000"}
    assert extract_urls_from_chunk(chunk) == ["http://localhost:8000"]


def test_extract_ignores_junk() -> None:
    chunk = {"type": "message", "data": "http://localhost: 和 http://localhost:8000"}
    assert extract_urls_from_chunk(chunk) == ["http://localhost:8000"]


def test_extract_ignores_ellipsis() -> None:
    chunk = {"type": "message", "data": "http://localhost:8000/very/long/..."}
    assert extract_urls_from_chunk(chunk) == []


def test_extract_handles_escaped_json() -> None:
    # JSON 字符串里的 \\n 转义，清洗后应还原为单个 URL
    raw = '{"text": "http://localhost:8000\\\\n后面还有"}' 
    chunk = {"type": "message", "data": b64(raw)}
    assert extract_urls_from_chunk(chunk) == ["http://localhost:8000"]


# ---------- collect_preview_links ----------

def test_collect_preview_links_stops_on_no_more() -> None:
    def fake_rounds(task_id, cursor=None, limit=10):
        if cursor is None:
            return {
                "chunks": [
                    {"type": "message", "data": "http://localhost:8000/a"},
                    {"type": "message", "data": "http://localhost:8000/b"},
                ],
                "has_more": True,
                "next_cursor": "c2",
            }
        return {
            "chunks": [
                {"type": "message", "data": "http://localhost:8000/a"}
            ],
            "has_more": False,
        }

    counts = collect_preview_links(fake_rounds, "task-1")
    assert counts == {
        "http://localhost:8000/a": 2,
        "http://localhost:8000/b": 1,
    }


# ---------- check_url_status ----------

def test_check_url_status_ok(monkeypatch) -> None:
    class FakeResp:
        status_code = 200

    monkeypatch.setattr(
        "monkeycode.links.httpx.get", lambda *a, **kw: FakeResp()
    )
    assert check_url_status("http://localhost:8000") == ("在线", 200)


def test_check_url_status_error(monkeypatch) -> None:
    class FakeResp:
        status_code = 500

    monkeypatch.setattr(
        "monkeycode.links.httpx.get", lambda *a, **kw: FakeResp()
    )
    assert check_url_status("http://localhost:8000") == ("异常", 500)


def test_check_url_status_closed(monkeypatch) -> None:
    def raise_conn(*a, **kw):
        raise ConnectionError("refused")

    monkeypatch.setattr("monkeycode.links.httpx.get", raise_conn)
    assert check_url_status("http://localhost:8000") == ("已关闭", None)
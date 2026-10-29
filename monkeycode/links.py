"""任务预览链接提取与存活检测。

从任务历史轮次（get_task_rounds）中提取 AI 拉起的预览链接，
过滤出 MonkeyCode 预览域名 / localhost / 8000 端口，并做 HTTP 存活检测。
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx

_URL_RE = re.compile(r'https?://[^\s"\'<>\)\]\}]+')

# MonkeyCode 预览域名 / 本地回环 / deploy-website 默认预览端口
_PREVIEW_HOST_RE = re.compile(
    r"monkeycode-ai\.online|localhost|127\.0\.0\.1|:8000\b"
)

_MAX_PAGES = 500


def _decode_data(data: Any) -> str:
    """把 chunk.data 解码为可提取 URL 的文本。"""
    if not isinstance(data, str):
        return json.dumps(data, ensure_ascii=False)
    try:
        decoded = base64.b64decode(data).decode("utf-8", errors="replace")
        return decoded
    except Exception:
        return data


def _to_text(decoded: str) -> str:
    """尝试把解码结果还原为 JSON 文本，否则原样返回。"""
    try:
        obj = json.loads(decoded)
        if isinstance(obj, (dict, list)):
            return json.dumps(obj, ensure_ascii=False)
        if isinstance(obj, str):
            return obj
    except Exception:
        pass
    return decoded


def _unescape(text: str) -> str:
    """还原 markdown/JSON 转义，避免 URL 粘连转义字符。"""
    text = text.replace("\\r", "")
    text = text.replace("\\t", " ")
    text = text.replace("\\n", "\n")
    text = text.replace('\\"', '"')
    text = text.replace("\\\\", "\\")
    return text


def _clean_url(url: str) -> str:
    """清洗单条 URL：按换行截断、去掉尾部标点与反斜杠。"""
    url = url.split("\n")[0]
    url = url.rstrip(".,;:!?`)]}>'\"")
    while url.endswith("\\") or url.endswith("`"):
        url = url[:-1]
    return url


def _is_junk(url: str) -> bool:
    """过滤占位符/无意义链接。"""
    if "..." in url:
        return True
    # http://localhost: 但没有端口
    if re.match(r"^http://localhost:(\D|$)", url):
        return True
    # 清洗后只剩 http://localhost（无端口）
    if re.match(r"^http://localhost$", url):
        return True
    if url.endswith(":\\") or url.endswith(":/"):
        return True
    return False


def extract_urls_from_chunk(chunk: dict[str, Any]) -> list[str]:
    """从单个轮次 chunk 中提取预览 URL 列表。"""
    data = chunk.get("data")
    if data is None:
        return []
    text = _to_text(_decode_data(data))
    text = _unescape(text)
    urls: list[str] = []
    for m in _URL_RE.finditer(text):
        raw_url = m.group(0)
        if _is_junk(raw_url):
            continue
        url = _clean_url(raw_url)
        if url and not _is_junk(url) and _PREVIEW_HOST_RE.search(url):
            urls.append(url)
    return urls


def check_url_status(url: str) -> tuple[str, int | None]:
    """探测链接存活状态，返回 (状态标记, HTTP 状态码)。

    - HTTP < 400  -> ("在线", code)
    - HTTP >= 400 -> ("异常", code)
    - 连接失败     -> ("已关闭", None)
    """
    try:
        resp = httpx.get(url, timeout=8, follow_redirects=True)
        code = resp.status_code
        if code < 400:
            return ("在线", code)
        return ("异常", code)
    except Exception:
        return ("已关闭", None)


def collect_preview_links(
    get_rounds, task_id: str, max_pages: int = _MAX_PAGES
) -> dict[str, int]:
    """分页拉取任务轮次，收集预览链接及出现次数。

    get_rounds: 可调用对象，签名 (task_id, cursor, limit) -> dict
    """
    counts: dict[str, int] = {}
    cursor: str | None = None
    for _ in range(max_pages):
        data = get_rounds(task_id, cursor=cursor, limit=10)
        if not isinstance(data, dict):
            break
        for chunk in data.get("chunks") or []:
            for url in extract_urls_from_chunk(chunk):
                counts[url] = counts.get(url, 0) + 1
        if data.get("has_more") and data.get("next_cursor"):
            cursor = data["next_cursor"]
        else:
            break
    return counts
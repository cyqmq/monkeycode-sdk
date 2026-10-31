"""MonkeyCode 任务 WebSocket 会话流。

基于 websockets 库，连接 /api/v1/users/tasks/stream?id=&mode=，
发送 user-input 让 agent 执行，并读取下行事件。

协议参考：前端 src/api/task-stream-client.ts 与桌面端实现。
"""
from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import websockets

from monkeycode.errors import (
    APIError,
    AuthenticationError,
    RateLimitError,
)
from monkeycode.models import TaskStreamChunk, UserInputPayload


def b64e(s: str | bytes) -> str:
    """编码为 base64 字符串。"""
    if isinstance(s, str):
        s = s.encode("utf-8")
    return base64.b64encode(s).decode("ascii")


def b64d(s: str) -> str:
    """解码 base64 为字符串。"""
    return base64.b64decode(s).decode("utf-8")


def _ws_url(base_url: str, path: str) -> str:
    """将 HTTP(S) base_url 转为 ws(s) 前缀并拼接 API 路径。

    自托管部署时 base_url 传私有地址，协议自动转换。
    """
    if base_url.startswith("https://"):
        ws_base = "wss://" + base_url[len("https://"):]
    elif base_url.startswith("http://"):
        ws_base = "ws://" + base_url[len("http://"):]
    else:
        ws_base = base_url
    return f"{ws_base}{path}"


def _session_headers(client: Any) -> dict[str, str]:
    """提取登录会话 Cookie 作为 WebSocket 请求头。

    同时兼容用户登录与团队登录两种会话 Cookie。
    """
    cookies = []
    for name in ("monkeycode_ai_session", "monkeycode_ai_team_session"):
        cookie = client._client.cookies.get(name)
        if cookie:
            cookies.append(f"{name}={cookie}")
    if cookies:
        return {"Cookie": "; ".join(cookies)}
    return {}


def _wrap_ws_error(exc: Exception) -> Exception:
    """把 WebSocket 连接异常包装为 SDK 统一异常。

    服务端拒绝升级（任务不存在、会话失效、限流等）时，
    websockets 会抛 InvalidStatus/InvalidStatusCode，这里提取
    HTTP 状态码与响应体，转为 APIError 家族异常。
    """
    if isinstance(
        exc,
        (
            getattr(websockets.exceptions, "InvalidStatus", ()),
            getattr(websockets.exceptions, "InvalidStatusCode", ()),
        ),
    ):
        resp = getattr(exc, "response", None)
        status: int | None = None
        body = ""
        if resp is not None:
            status = getattr(resp, "status_code", None)
            body = getattr(resp, "body", "")
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="replace")
        status = status or 0
        body = str(body)[:200]
        if status == 401:
            return AuthenticationError(
                "WebSocket 认证失败或会话已失效，请重新登录。", code=401
            )
        if status == 429:
            return RateLimitError(
                f"WebSocket 触发限流（HTTP 429）：{body}", code=429
            )
        return APIError(
            f"WebSocket 连接失败（HTTP {status}）：{body}", code=status
        )
    if isinstance(exc, (OSError, ConnectionError)):
        return APIError(f"WebSocket 连接失败：{exc}", code=0)
    return exc


async def _ws_connect(url: str, headers: dict[str, str]) -> Any:
    """建立 WebSocket 连接，连接异常统一包装为 SDK 异常。"""
    try:
        return await websockets.connect(url, additional_headers=headers)
    except Exception as exc:
        wrapped = _wrap_ws_error(exc)
        if wrapped is exc:
            raise
        raise wrapped from exc


def encode_user_input(
    content: str, attachments: list[dict] | None = None
) -> str:
    """构造上行 user-input 消息（外层 JSON 字符串）。

    格式：{"type": "user-input", "data": "<base64(内层JSON)>"}
    """
    payload = UserInputPayload(content=content, attachments=attachments or [])
    outer = {"type": "user-input", "data": b64e(payload.encode())}
    return json.dumps(outer, ensure_ascii=False)


def decode_chunk(raw: str) -> TaskStreamChunk:
    """解析服务器下行事件。data 可能是 base64 的 JSON 字符串。"""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return TaskStreamChunk(type="raw", data=raw, raw={"raw": raw})

    ctype = str(obj.get("type", ""))
    data = obj.get("data")
    if isinstance(data, str):
        try:
            decoded = b64d(data)
            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                data = decoded
        except Exception:
            pass

    return TaskStreamChunk(
        type=ctype,
        data=data,
        timestamp=int(obj.get("timestamp", 0) or 0),
        turn_seq=int(obj.get("turn_seq", 0) or 0),
        raw=obj,
    )


def _try_b64(s: str) -> str | None:
    """尝试把字符串当 base64 解码；失败返回 None。"""
    raw = s.replace("-", "+").replace("_", "/")
    pad = "=" * ((4 - len(raw) % 4) % 4)
    try:
        return base64.b64decode(raw + pad).decode("utf-8")
    except Exception:
        return None


_SENSITIVE_KEYWORDS = (
    "api_key",
    "apikey",
    "access_key",
    "secret",
    "password",
    "passwd",
    "token",
    "authorization",
    "cookie",
    "env",
    "credential",
)


def _redact_sensitive(value: Any) -> Any:
    """递归脱敏：密钥类字段（api_key/token/secret/password/env 等）值替换为 ***。"""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            kl = str(k).lower()
            if any(word in kl for word in _SENSITIVE_KEYWORDS) and v not in (None, ""):
                if kl == "envs" and isinstance(v, dict):
                    out[k] = {"***": "***"}
                else:
                    out[k] = "***"
            else:
                out[k] = _redact_sensitive(v)
        return out
    if isinstance(value, list):
        return [_redact_sensitive(v) for v in value]
    return value


redact_sensitive = _redact_sensitive


def _coerce_round_payload(data: Any) -> Any:
    """把 rounds chunk 的 data 规范成 dict/str。"""
    if data is None:
        return ""
    if isinstance(data, (dict, list)):
        return data
    if not isinstance(data, str):
        return str(data)
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        pass
    decoded = _try_b64(data)
    if decoded is None:
        return data
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return decoded


def _extract_text_field(value: Any) -> str:
    """从 ACP content/message 字段抽出纯文本。"""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        text = value.get("text") or value.get("message") or value.get("content")
        if isinstance(text, str):
            return text
    if isinstance(value, list):
        parts = [_extract_text_field(item) for item in value]
        return "".join(p for p in parts if p)
    return ""


def format_round_text(data: Any, max_len: int = 400) -> str:
    """把任务轮次 data 解码为可读短文本。

    - user-input：解开内层 content 的第二层 base64，得到用户原话
    - task-running ACP：按 sessionUpdate 分类精简
      available_commands_update / agent_message / tool_call
    """
    obj = _coerce_round_payload(data)
    if not isinstance(obj, dict):
        text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
        return text[:max_len]

    if str(obj.get("type") or "") == "user-input" and "content" not in obj:
        inner_data = obj.get("data")
        if inner_data is not None:
            return format_round_text(inner_data, max_len)

    content = obj.get("content")
    if isinstance(content, str):
        inner = _try_b64(content)
        if inner is not None and inner != content:
            return inner[:max_len]

    update = obj.get("update") if isinstance(obj.get("update"), dict) else {}
    session_update = str(
        obj.get("sessionUpdate") or update.get("sessionUpdate") or ""
    )
    src = update if update.get("sessionUpdate") else obj
    if session_update:
        if session_update == "available_commands_update":
            cmds = src.get("availableCommands") or update.get("availableCommands") or []
            names = [
                c.get("name")
                for c in cmds
                if isinstance(c, dict) and c.get("name")
            ][:10]
            if names:
                return "、".join(names)[:max_len]
            return f"共 {len(cmds)} 项"
        if session_update in ("agent_message", "agent_message_chunk"):
            msg = (
                _extract_text_field(src.get("message"))
                or _extract_text_field(src.get("content"))
                or _extract_text_field(update.get("message"))
                or _extract_text_field(update.get("content"))
            )
            return msg[:max_len]
        if session_update == "agent_thought_chunk":
            thought = _extract_text_field(src.get("thought"))
            if not thought:
                thought = _extract_text_field(src.get("content"))
            return thought[:max_len] if thought else "（思考中）"
        if session_update == "usage_update":
            usage = src.get("usage") or update.get("usage") or {}
            if isinstance(usage, dict):
                total = (
                    usage.get("totalTokens")
                    or usage.get("total_tokens")
                    or usage.get("total")
                    or ""
                )
                if total:
                    return f"用量：{total}"
            return "用量更新"
        if session_update in ("tool_call", "tool_call_update"):
            title = src.get("title") or src.get("kind") or src.get("toolName") or ""
            status = src.get("status") or ""
            return f"{title} {status}".strip()[:max_len]
        if session_update in ("call", "call-response"):
            title = src.get("title") or src.get("toolName") or src.get("kind") or ""
            status = src.get("status") or ""
            if title:
                return f"{title} {status}".strip()[:max_len]
            safe = _redact_sensitive(src)
            return json.dumps(safe, ensure_ascii=False)[:max_len]
        return (
            f"{session_update} "
            f"{json.dumps(_redact_sensitive(src), ensure_ascii=False)[:300]}"
        )

    for key in ("content", "message", "text"):
        extracted = _extract_text_field(obj.get(key))
        if extracted:
            return extracted[:max_len]
    return json.dumps(_redact_sensitive(obj), ensure_ascii=False)[:max_len]


def _round_session_update(data: Any) -> str:
    """提取轮次载荷中的 ACP sessionUpdate 类型。"""
    obj = _coerce_round_payload(data)
    if not isinstance(obj, dict):
        return ""
    update = obj.get("update") if isinstance(obj.get("update"), dict) else {}
    return str(obj.get("sessionUpdate") or update.get("sessionUpdate") or "")


def round_kind(data: Any, event: str | None = None) -> str:
    """返回轮次语义分类：user/agent/tool/system/commands/other。"""
    su = _round_session_update(data)
    if su == "available_commands_update":
        return "commands"
    if su in ("agent_message", "agent_message_chunk", "agent_thought_chunk"):
        return "agent"
    if su in ("tool_call", "tool_call_update", "call", "call-response"):
        return "tool"
    if su == "usage_update":
        return "system"
    obj = _coerce_round_payload(data)
    ctype = ""
    if isinstance(obj, dict):
        ctype = str(obj.get("type") or obj.get("event") or obj.get("kind") or "")
    ctype = ctype.lower() or (event or "").lower()
    if ctype == "user-input":
        return "user"
    if "task-started" in ctype or "task-ended" in ctype or "task-failed" in ctype:
        return "system"
    if ctype == "message":
        return "agent"
    return "other"


def round_label(data: Any, event: str | None = None) -> str:
    """返回轮次友好中文标签（与前端后台一致）。"""
    su = _round_session_update(data)
    if su == "available_commands_update":
        return "命令更新"
    if su in ("agent_message", "agent_message_chunk"):
        return "Agent"
    if su == "agent_thought_chunk":
        return "思考"
    if su == "usage_update":
        return "用量"
    if su in ("tool_call", "tool_call_update"):
        return "工具"
    if su == "call":
        return "调用"
    if su == "call-response":
        return "调用响应"
    obj = _coerce_round_payload(data)
    ctype = ""
    if isinstance(obj, dict):
        ctype = str(obj.get("type") or obj.get("event") or obj.get("kind") or "")
    ctype = ctype.lower() or (event or "").lower()
    if ctype == "user-input":
        return "用户输入"
    if ctype == "task-started":
        return "任务开始"
    if ctype == "task-ended":
        return "任务结束"
    if ctype == "message":
        return "消息"
    return event or su or ctype or "事件"


def round_tool_title(data: Any) -> str:
    """提取工具调用事件的工具名称（tool_call/call 等）。"""
    obj = _coerce_round_payload(data)
    if not isinstance(obj, dict):
        return ""
    update = obj.get("update") if isinstance(obj.get("update"), dict) else {}
    src = update if update.get("sessionUpdate") else obj
    return str(src.get("title") or src.get("toolName") or src.get("kind") or "")


class TaskStream:
    """任务实时流（WebSocket 会话）。

    用法：
        stream = TaskStream(client, task_id, mode="new")
        await stream.connect()
        await stream.send_user_input("继续")
        chunk = await stream.recv(timeout=60)
        await stream.close()
    """

    def __init__(self, client: Any, task_id: str, mode: str = "new") -> None:
        self.client = client
        self.task_id = task_id
        self.mode = mode
        self._ws: Any = None

    def _url(self) -> str:
        return _ws_url(
            self.client.base_url,
            f"/api/v1/users/tasks/stream?id={self.task_id}&mode={self.mode}",
        )

    async def connect(self) -> None:
        """建立 WebSocket 连接（携带登录 Cookie）。"""
        self._ws = await _ws_connect(
            self._url(), _session_headers(self.client)
        )

    async def send_user_input(
        self, content: str, attachments: list[dict] | None = None
    ) -> None:
        """发送用户文字/附件到任务会话。"""
        msg = encode_user_input(content, attachments)
        await self._ws.send(msg)

    async def send_cancel(self) -> None:
        """发送取消指令。"""
        await self._ws.send(json.dumps({"type": "user-cancel", "data": ""}))

    async def send_control(self, ctype: str, data: str = "") -> None:
        """发送任意控制类型消息（如 reply-question / auto-approve）。"""
        await self._ws.send(json.dumps({"type": ctype, "data": data}))

    async def send_reply_question(
        self, request_id: str, answers: list[str]
    ) -> None:
        """回复 AI 的提问（reply-question）。"""
        inner = json.dumps(
            {"request_id": request_id, "answers": answers}, ensure_ascii=False
        )
        await self.send_control("reply-question", b64e(inner))

    async def send_auto_approve(self, enable: bool = True) -> None:
        """开启/关闭自动批准（auto-approve / disable-auto-approve）。"""
        ctype = "auto-approve" if enable else "disable-auto-approve"
        await self.send_control(ctype, "")

    async def recv(self, timeout: float | None = None) -> TaskStreamChunk:
        """读取并解码一条事件。"""
        raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        return decode_chunk(raw)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> "TaskStream":
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()


class ControlStream:
    """任务控制通道（WebSocket）。

    用于同步调用类操作：switch_model / restart / 文件浏览 / 端口转发等。
    端点：/api/v1/users/tasks/control?id=<task_id>

    上行消息：
        {"type": "call", "kind": "<kind>", "data": "<base64(JSON)>"}
    下行消息：
        {"type": "call-response", "kind": "<kind>",
         "data": "<base64(响应JSON)>", "timestamp": 0}

    注意：data 必须是 base64(JSON字符串)，服务端 Go 的 []byte 字段
    会自动 base64 解码后再反序列化。
    """

    def __init__(self, client: Any, task_id: str) -> None:
        self.client = client
        self.task_id = task_id
        self._ws: Any = None

    def _url(self) -> str:
        return _ws_url(
            self.client.base_url,
            f"/api/v1/users/tasks/control?id={self.task_id}",
        )

    async def connect(self) -> None:
        """建立 WebSocket 连接（携带登录 Cookie）。"""
        self._ws = await _ws_connect(
            self._url(), _session_headers(self.client)
        )

    async def send_call(self, kind: str, data: dict[str, Any]) -> None:
        """发送控制调用。data 会被 base64(JSON) 编码后放入外层 data。"""
        inner = json.dumps(data, ensure_ascii=False)
        msg = {"type": "call", "kind": kind, "data": b64e(inner)}
        await self._ws.send(json.dumps(msg, ensure_ascii=False))

    async def send_raw(self, ctype: str, data: str = "") -> None:
        """发送任意类型控制消息（非 call 调用，如 sync-my-ip）。

        data 为原始字符串，会原样放入外层 data 字段。
        """
        msg = {"type": ctype, "data": data}
        await self._ws.send(json.dumps(msg, ensure_ascii=False))

    async def recv(self, timeout: float | None = None) -> TaskStreamChunk:
        """读取并解码一条控制通道事件。"""
        raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        return decode_chunk(raw)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> "ControlStream":
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()


class TerminalStream:
    """虚拟机终端流（WebSocket）。

    端点：/api/v1/users/hosts/vms/{vm_id}/terminals/connect

    上行消息：
        {"type": "data",   "data": "<base64(输入字节)>"}
        {"type": "resize", "data": "<base64({\"col\":..,\"row\":..})>"}
    下行消息：
        connected / data / resize / error / ping / pong
    """

    def __init__(
        self,
        client: Any,
        vm_id: str,
        terminal_id: str | None = None,
        col: int = 80,
        row: int = 24,
    ) -> None:
        self.client = client
        self.vm_id = vm_id
        self.terminal_id = terminal_id
        self.col = col
        self.row = row
        self._ws: Any = None

    def _url(self) -> str:
        path = f"/api/v1/users/hosts/vms/{self.vm_id}/terminals/connect"
        params = [f"col={self.col}", f"row={self.row}"]
        if self.terminal_id:
            params.append(f"terminal_id={self.terminal_id}")
        return _ws_url(self.client.base_url, f"{path}?{'&'.join(params)}")

    async def connect(self) -> None:
        """建立 WebSocket 连接（携带登录 Cookie）。"""
        self._ws = await _ws_connect(
            self._url(), _session_headers(self.client)
        )

    async def send_data(self, data: bytes | str) -> None:
        """发送终端输入（字符串或字节）。"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        msg = {"type": "data", "data": b64e(data)}
        await self._ws.send(json.dumps(msg, ensure_ascii=False))

    async def send_resize(self, col: int, row: int) -> None:
        """调整终端尺寸。"""
        inner = json.dumps({"col": col, "row": row})
        msg = {"type": "resize", "data": b64e(inner)}
        await self._ws.send(json.dumps(msg, ensure_ascii=False))

    async def recv(self, timeout: float | None = None) -> TaskStreamChunk:
        """读取并解码一条终端事件（data 自动 base64 解码）。"""
        raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        return decode_chunk(raw)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> "TerminalStream":
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()


class JoinTerminalStream:
    """加入共享终端流（WebSocket）。

    端点：/api/v1/users/hosts/vms/terminals/join
    需要分享密码（share_terminal 返回的 password）。

    上行/下行消息格式与 TerminalStream 一致（data / resize / 心跳）。
    """

    def __init__(
        self,
        client: Any,
        terminal_id: str,
        password: str,
        col: int = 80,
        row: int = 24,
    ) -> None:
        self.client = client
        self.terminal_id = terminal_id
        self.password = password
        self.col = col
        self.row = row
        self._ws: Any = None

    def _url(self) -> str:
        path = "/api/v1/users/hosts/vms/terminals/join"
        params = [
            f"terminal_id={self.terminal_id}",
            f"password={self.password}",
            f"col={self.col}",
            f"row={self.row}",
        ]
        return _ws_url(self.client.base_url, f"{path}?{'&'.join(params)}")

    async def connect(self) -> None:
        """建立 WebSocket 连接（携带登录 Cookie）。"""
        self._ws = await _ws_connect(
            self._url(), _session_headers(self.client)
        )

    async def send_data(self, data: bytes | str) -> None:
        """发送终端输入（字符串或字节）。"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        msg = {"type": "data", "data": b64e(data)}
        await self._ws.send(json.dumps(msg, ensure_ascii=False))

    async def send_resize(self, col: int, row: int) -> None:
        """调整终端尺寸。"""
        inner = json.dumps({"col": col, "row": row})
        msg = {"type": "resize", "data": b64e(inner)}
        await self._ws.send(json.dumps(msg, ensure_ascii=False))

    async def recv(self, timeout: float | None = None) -> TaskStreamChunk:
        """读取并解码一条终端事件（data 自动 base64 解码）。"""
        raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        return decode_chunk(raw)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> "JoinTerminalStream":
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
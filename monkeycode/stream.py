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
        self._ws = await websockets.connect(
            self._url(), additional_headers=_session_headers(self.client)
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
        self._ws = await websockets.connect(
            self._url(), additional_headers=_session_headers(self.client)
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
        self._ws = await websockets.connect(
            self._url(), additional_headers=_session_headers(self.client)
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
        self._ws = await websockets.connect(
            self._url(), additional_headers=_session_headers(self.client)
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
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
        base = self.client.base_url
        if base.startswith("https://"):
            ws_base = "wss://" + base[len("https://"):]
        elif base.startswith("http://"):
            ws_base = "ws://" + base[len("http://"):]
        else:
            ws_base = base
        return f"{ws_base}/api/v1/users/tasks/stream?id={self.task_id}&mode={self.mode}"

    async def connect(self) -> None:
        """建立 WebSocket 连接（携带登录 Cookie）。"""
        session_cookie = self.client._client.cookies.get("monkeycode_ai_session")
        headers: dict[str, str] = {}
        if session_cookie:
            headers["Cookie"] = f"monkeycode_ai_session={session_cookie}"
        self._ws = await websockets.connect(
            self._url(), additional_headers=headers
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
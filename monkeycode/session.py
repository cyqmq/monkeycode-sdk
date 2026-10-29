"""任务高层会话封装（轻量自动重连 + 事件缓冲）。

AgentSession 在 TaskStream 之上提供：
- 断线自动重连（可配置次数与间隔）
- 后台事件拉取与 asyncio.Queue 缓冲
- 发送消息前确保连接可用

注意：不做消息乱序去重。服务端事件通常按顺序到达，
turn_seq 仅作标识；如需严格有序，调用方可自行按 turn_seq 排序。
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

import websockets

from monkeycode.models import TaskStreamChunk
from monkeycode.stream import TaskStream

_TERMINAL_TYPES = {"task-ended", "task-error"}


class AgentSession:
    """任务高层会话。

    用法：
        session = AgentSession(client, task_id, mode="new")
        await session.start()
        await session.send_user_input("继续")
        async for chunk in session.events():
            print(chunk.type, chunk.data)
            if chunk.type == "task-ended":
                break
        await session.close()
    """

    def __init__(
        self,
        client: Any,
        task_id: str,
        mode: str = "new",
        max_reconnects: int = 3,
        reconnect_delay: float = 1.0,
    ) -> None:
        self.client = client
        self.task_id = task_id
        self.mode = mode
        self.max_reconnects = max_reconnects
        self.reconnect_delay = reconnect_delay
        self._stream = TaskStream(client, task_id, mode=mode)
        self._queue: asyncio.Queue[TaskStreamChunk] = asyncio.Queue()
        self._pump_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """建立连接并启动后台事件拉取循环。"""
        await self._ensure_connected()
        if self._running:
            return
        self._running = True
        self._pump_task = asyncio.create_task(self._pump())

    async def _ensure_connected(self) -> None:
        """确保 WebSocket 已连接；断线时自动重连。"""
        if self._stream._ws is not None:
            return
        attempts = 0
        while True:
            try:
                await self._stream.connect()
                return
            except Exception:
                attempts += 1
                if attempts > self.max_reconnects:
                    raise
                await asyncio.sleep(self.reconnect_delay)

    async def _pump(self) -> None:
        """后台拉取事件放入队列；断线时自动重连。"""
        while self._running:
            try:
                chunk = await self._stream.recv()
                await self._queue.put(chunk)
                if chunk.type in _TERMINAL_TYPES:
                    break
            except (websockets.ConnectionClosed, asyncio.TimeoutError, OSError):
                if not self._running:
                    break
                try:
                    await self._ensure_connected()
                except Exception:
                    # 重连失败：结束事件循环，由调用方决定后续
                    break

    async def send_user_input(
        self, content: str, attachments: list[dict] | None = None
    ) -> None:
        """发送用户消息；断线时自动重连后重发。"""
        await self._ensure_connected()
        await self._stream.send_user_input(content, attachments)

    async def send_reply_question(
        self, request_id: str, answers: list[str]
    ) -> None:
        """回复 AI 提问（自动确保连接可用）。"""
        await self._ensure_connected()
        await self._stream.send_reply_question(request_id, answers)

    async def send_auto_approve(self, enable: bool = True) -> None:
        """开启/关闭自动批准（自动确保连接可用）。"""
        await self._ensure_connected()
        await self._stream.send_auto_approve(enable)

    async def events(self) -> AsyncIterator[TaskStreamChunk]:
        """异步迭代事件队列，直到任务结束或出错。"""
        while True:
            chunk = await self._queue.get()
            yield chunk
            if chunk.type in _TERMINAL_TYPES:
                break

    async def close(self) -> None:
        """停止后台拉取并关闭连接。"""
        self._running = False
        if self._pump_task is not None:
            self._pump_task.cancel()
            try:
                await self._pump_task
            except (asyncio.CancelledError, Exception):
                pass
            self._pump_task = None
        await self._stream.close()

    async def __aenter__(self) -> "AgentSession":
        await self.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
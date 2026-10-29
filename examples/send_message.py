#!/usr/bin/env python3
"""发送消息到运行中的任务（WebSocket 实时会话）。

用法：
    export MONKEYCODE_EMAIL=you@example.com
    export MONKEYCODE_PASSWORD=your_password
    python examples/send_message.py <task_id> "继续"
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monkeycode import AgentSession, MonkeyCodeClient


async def main() -> None:
    task_id = sys.argv[1] if len(sys.argv) > 1 else ""
    content = sys.argv[2] if len(sys.argv) > 2 else "继续"
    if not task_id:
        print("用法：python examples/send_message.py <task_id> <内容>")
        return

    client = MonkeyCodeClient(
        email=os.environ.get("MONKEYCODE_EMAIL", ""),
        password=os.environ.get("MONKEYCODE_PASSWORD", ""),
    )
    client.login()

    # 使用高层会话 AgentSession：断线自动重连 + 事件缓冲
    async with AgentSession(client, task_id, mode="new") as session:
        await session.send_user_input(content)
        async for chunk in session.events():
            print(f"{chunk.type}: {str(chunk.data)[:200]}")
            if chunk.type in ("task-ended", "task-error"):
                break


if __name__ == "__main__":
    asyncio.run(main())
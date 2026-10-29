#!/usr/bin/env python3
"""打开虚拟机终端、发送命令、读取输出。

用法：
    export MONKEYCODE_EMAIL=you@example.com
    export MONKEYCODE_PASSWORD=your_password
    python examples/terminal.py <vm_id>
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monkeycode import MonkeyCodeClient


async def main() -> None:
    vm_id = sys.argv[1] if len(sys.argv) > 1 else ""
    if not vm_id:
        print("用法：python examples/terminal.py <vm_id>")
        return

    client = MonkeyCodeClient(
        email=os.environ.get("MONKEYCODE_EMAIL", ""),
        password=os.environ.get("MONKEYCODE_PASSWORD", ""),
    )
    client.login()

    async with client.open_terminal(vm_id, col=80, row=24) as term:
        await term.send_data("ls -la\r")
        for _ in range(5):
            chunk = await term.recv(timeout=10)
            print(str(chunk.data)[:500])
            if chunk.type == "error":
                break


if __name__ == "__main__":
    asyncio.run(main())
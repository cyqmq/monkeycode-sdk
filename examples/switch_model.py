#!/usr/bin/env python3
"""通过 control 通道切换运行中任务的模型。

用法：
    export MONKEYCODE_EMAIL=you@example.com
    export MONKEYCODE_PASSWORD=your_password
    python examples/switch_model.py <task_id> <model_id>
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monkeycode import MonkeyCodeClient


async def main() -> None:
    task_id = sys.argv[1] if len(sys.argv) > 1 else ""
    model_id = sys.argv[2] if len(sys.argv) > 2 else ""
    if not task_id or not model_id:
        print("用法：python examples/switch_model.py <task_id> <model_id>")
        return

    client = MonkeyCodeClient(
        email=os.environ.get("MONKEYCODE_EMAIL", ""),
        password=os.environ.get("MONKEYCODE_PASSWORD", ""),
    )
    client.login()

    result = await client.switch_task_model(task_id, model_id, load_session=True)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
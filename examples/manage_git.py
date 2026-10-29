#!/usr/bin/env python3
"""Git 身份 / Git Bot 的管理示例（只读 + 安全写操作）。

用法：
    export MONKEYCODE_EMAIL=you@example.com
    export MONKEYCODE_PASSWORD=your_password
    python examples/manage_git.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monkeycode import MonkeyCodeClient


def main() -> None:
    client = MonkeyCodeClient(
        email=os.environ.get("MONKEYCODE_EMAIL", ""),
        password=os.environ.get("MONKEYCODE_PASSWORD", ""),
    )
    with client:
        client.login()
        print("Git 身份列表：", client.list_git_identities())
        print("Git Bot 列表：", client.list_git_bots())

        # 演示添加 Git Bot（如需真实创建请取消注释并填参数）
        # bot = client.create_git_bot(host_id="...", platform="github", token="...")
        # print("已创建 Git Bot：", bot)
        # client.delete_git_bot(bot.id)


if __name__ == "__main__":
    main()
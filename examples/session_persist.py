#!/usr/bin/env python3
"""使用 session_path 持久化登录：第一次运行登录并保存会话，
第二次运行（同一 session 文件）直接复用，无需重新登录。

用法：
    export MONKEYCODE_EMAIL=you@example.com
    export MONKEYCODE_PASSWORD=your_password
    python examples/session_persist.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monkeycode import MonkeyCodeClient

SESSION_PATH = os.path.join(tempfile.gettempdir(), "monkeycode_example_session.json")


def main() -> None:
    client = MonkeyCodeClient(
        email=os.environ.get("MONKEYCODE_EMAIL", ""),
        password=os.environ.get("MONKEYCODE_PASSWORD", ""),
        session_path=SESSION_PATH,
    )
    with client:
        if client.is_logged_in():
            print(f"使用持久化会话（{SESSION_PATH}），免登录")
        else:
            print(f"首次运行，正在登录并保存会话到 {SESSION_PATH}")
            client.login()

        print("当前用户：", client.whoami())


if __name__ == "__main__":
    main()
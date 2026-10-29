#!/usr/bin/env python3
"""MonkeyCode SDK 冒烟测试（手动运行）。

覆盖：
1. 登录（如遇验证码会提示）
2. 枚举环境：hosts / images / models
3. 任务列表
4. 创建并删除 OhMyAgent API Key（只读之外唯一的写操作，安全）
5. 可选：创建任务（默认跳过，避免触发资源/计费；可用 --with-task 开启）

用法：
    export MONKEYCODE_EMAIL=你的邮箱
    export MONKEYCODE_PASSWORD=你的密码
    python tests/smoke_test.py [--with-task] [--base-url https://...]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monkeycode import (
    AuthenticationError,
    CaptchaRequiredError,
    MonkeyCodeClient,
    TaskError,
)
from monkeycode.models import RepoReq

PASS = "✅"
FAIL = "❌"
SKIP = "⏭"


def check(name: str, fn):
    try:
        result = fn()
        print(f"{PASS} {name}")
        return result
    except (AuthenticationError, CaptchaRequiredError) as e:
        print(f"{FAIL} {name} -> 认证类错误：{e}")
        raise
    except Exception as e:
        print(f"{FAIL} {name} -> {type(e).__name__}: {e}")
        return None


def do_login(client: MonkeyCodeClient) -> None:
    try:
        client.login()
        print(f"{PASS} 登录（无需验证码）")
        return
    except CaptchaRequiredError:
        print(f"{FAIL} 登录需要验证码（challenge 参数 c/s/d 需客户端渲染，当前未实现）")
        print("     请先在 MonkeyCode 网页端确认可登录，验证码渲染是下一步待解决项。")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="MonkeyCode SDK 冒烟测试")
    parser.add_argument("--with-task", action="store_true", help="额外执行创建任务（可能触发资源/计费）")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MONKEYCODE_BASE_URL", "https://monkeycode-ai.com"),
    )
    args = parser.parse_args()

    email = os.environ.get("MONKEYCODE_EMAIL", "").strip()
    password = os.environ.get("MONKEYCODE_PASSWORD", "")
    if not email or not password:
        print("请设置环境变量 MONKEYCODE_EMAIL 和 MONKEYCODE_PASSWORD")
        sys.exit(1)

    client = MonkeyCodeClient(email=email, password=password, base_url=args.base_url)
    with client:
        print("=== 1. 登录 ===")
        do_login(client)

        print("\n=== 2. 枚举环境 ===")
        hosts = check("list_hosts", client.list_hosts)
        images = check("list_images", client.list_images)
        models = check("list_models", client.list_models)
        print(f"      hosts={len(hosts or [])} images={len(images or [])} models={len(models or [])}")

        print("\n=== 3. 任务列表 ===")
        tasks_data = check("list_tasks", lambda: client.list_tasks(size=5))
        if isinstance(tasks_data, dict):
            print(f"      tasks={len(tasks_data.get('tasks') or [])}")
        elif tasks_data is not None:
            print(f"      tasks={len(tasks_data)}")

        print("\n=== 4. API Key 管理 ===")
        key = check("create_api_key", client.create_api_key)
        if key:
            print(f"      key_id={key.key_id} api_key 长度={len(key.api_key)}")
            check("delete_api_key", lambda: client.delete_api_key(key.key_id))

        if args.with_task:
            print("\n=== 5. 创建任务（--with-task）===")
            try:
                task = client.create_task(
                    content="写一个 hello world Python 脚本并运行",
                    repo=RepoReq(repo_url=""),
                )
                print(f"{PASS} 创建任务: id={task.id} status={task.status}")
                result = client.wait_task(task.id, timeout=600, interval=10)
                print(f"{PASS} 任务终态: {result.status}")
            except TaskError as e:
                print(f"{FAIL} 创建任务失败：{e}")
                print("     若提示 code=10205 主机不在线，为平台侧环境问题，请到控制台确认云端环境。")
        else:
            print(f"\n=== 5. 创建任务 ===")
            print(f"{SKIP} 已跳过（用 --with-task 开启；可能触发资源/计费，且平台有 10205 主机不可调度问题）")

        print("\n冒烟测试结束")


if __name__ == "__main__":
    main()
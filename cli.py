#!/usr/bin/env python3
"""MonkeyCode SDK 命令行验证入口。

用法：
    export MONKEYCODE_EMAIL=you@example.com
    export MONKEYCODE_PASSWORD=your_password

    python cli.py login                 # 登录（PoW 验证码自动求解）
    python cli.py list-hosts             # 列出云端环境
    python cli.py list-images            # 列出镜像
    python cli.py list-models            # 列出模型
    python cli.py run "写一个 hello world"  # 提交任务并轮询结果
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from monkeycode import (
    AuthenticationError,
    MonkeyCodeClient,
    TaskError,
)
from monkeycode.models import RepoReq


def get_credentials() -> tuple[str, str]:
    email = os.environ.get("MONKEYCODE_EMAIL", "").strip()
    password = os.environ.get("MONKEYCODE_PASSWORD", "")
    if not email or not password:
        print("缺少凭证：请设置环境变量 MONKEYCODE_EMAIL 和 MONKEYCODE_PASSWORD")
        sys.exit(1)
    return email, password


def print_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def interactive_login(client: MonkeyCodeClient) -> None:
    """登录（PoW 验证码由 SDK 自动求解）。"""
    try:
        client.login()
        print("登录成功")
    except AuthenticationError as e:
        print(f"登录失败：{e}")
        sys.exit(1)


def cmd_run(client: MonkeyCodeClient, content: str) -> None:
    hosts = client.list_hosts()
    images = client.list_images()
    models = client.list_models()
    if not hosts:
        raise TaskError("没有可用的云端宿主（hosts），请先在控制台创建环境。")
    if not images:
        raise TaskError("没有可用的镜像（images）。")
    if not models:
        raise TaskError("没有可用的模型（models）。")
    repo_url = input("请输入 GitHub 仓库 URL（回车跳过）：").strip()
    repo = RepoReq(repo_url=repo_url) if repo_url else RepoReq(repo_url="")
    task = client.create_task(
        content=content,
        repo=repo,
        host_id=hosts[0]["id"],
        image_id=images[0]["id"],
        model_id=models[0]["id"],
    )
    print(f"任务已创建：{task.id}，状态 {task.status}")
    print("等待任务完成...")
    result = client.wait_task(task.id, timeout=1800, interval=10)
    print("任务终态：", result.status)
    print_json(result.raw)


def cmd_links(client: MonkeyCodeClient, task_id: str) -> None:
    """列出任务中的预览链接并检测存活状态。"""
    links = client.list_task_links(task_id, check_alive=True)
    if not links:
        print("未在任务轮次中发现预览链接。")
        return
    for item in links:
        status = item["status"] or "未检测"
        code = item["http_code"]
        code_str = f" HTTP {code}" if code else ""
        print(f"{status}{code_str}  {item['url']}  (x{item['count']})")


def cmd_whoami(client: MonkeyCodeClient) -> None:
    """显示当前登录账户信息。"""
    print_json(client.whoami())


def cmd_logout(client: MonkeyCodeClient) -> None:
    """退出当前会话。"""
    client.logout()
    print("已退出登录")


def main() -> None:
    parser = argparse.ArgumentParser(description="MonkeyCode SDK CLI")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MONKEYCODE_BASE_URL", "https://monkeycode-ai.com"),
        help="MonkeyCode API 地址",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="登录并保存会话")
    sub.add_parser("whoami", help="显示当前登录账户信息")
    sub.add_parser("logout", help="退出当前会话")
    sub.add_parser("list-hosts", help="列出云端环境")
    sub.add_parser("list-images", help="列出镜像")
    sub.add_parser("list-models", help="列出模型")

    run_p = sub.add_parser("run", help="创建任务并轮询结果")
    run_p.add_argument("content", help="任务内容（自然语言）")

    links_p = sub.add_parser("links", help="列出任务中的预览链接并检测存活")
    links_p.add_argument("task_id", help="任务 ID")

    args = parser.parse_args()
    email, password = get_credentials()
    with MonkeyCodeClient(email=email, password=password, base_url=args.base_url) as client:
        if args.command == "login":
            interactive_login(client)
            return
        # 列表/任务命令需要登录态
        interactive_login(client)
        if args.command == "whoami":
            cmd_whoami(client)
        elif args.command == "logout":
            cmd_logout(client)
        elif args.command == "list-hosts":
            print_json(client.list_hosts())
        elif args.command == "list-images":
            print_json(client.list_images())
        elif args.command == "list-models":
            print_json(client.list_models())
        elif args.command == "run":
            cmd_run(client, args.content)
        elif args.command == "links":
            cmd_links(client, args.task_id)


if __name__ == "__main__":
    main()
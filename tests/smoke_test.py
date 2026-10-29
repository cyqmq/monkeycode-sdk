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
        client.login()  # PoW 验证码由 SDK 自动求解
        print(f"{PASS} 登录成功（PoW 验证码自动求解）")
    except AuthenticationError as e:
        print(f"{FAIL} 登录失败：{e}")
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

        print("\n=== 5. 只读接口覆盖 ===")
        check("whoami", client.whoami)
        check("get_task_options", client.get_task_options)
        check("get_wallet", client.get_wallet)
        check("get_wallet_transactions", client.get_wallet_transactions)
        check("get_subscription", client.get_subscription)
        check("list_plugins", client.list_plugins)
        check("list_skills", client.list_skills)
        check("list_git_identities", client.list_git_identities)
        check("list_git_bots", client.list_git_bots)
        check("list_mcp_upstreams", client.list_mcp_upstreams)
        check("list_notify_channels", client.list_notify_channels)
        check("list_notify_event_types", client.list_notify_event_types)
        check("list_available_models", client.list_available_models)
        check("list_model_providers", client.list_model_providers)
        check("list_playground_posts", client.list_playground_posts)
        check("get_public_stats", client.get_public_stats)

        projects = check("list_projects", client.list_projects)
        if projects:
            project_id = projects[0].get("id")
            if project_id:
                check(
                    "list_project_issues",
                    lambda: client.list_project_issues(project_id),
                )

        hosts = hosts or []
        vm_found = False
        for h in hosts:
            vms = h.get("virtualmachines") or h.get("vms") or []
            if vms:
                check(
                    "list_terminal_sessions",
                    lambda vm_id=vms[0].get("id"): client.list_terminal_sessions(
                        vm_id
                    ),
                )
                vm_found = True
                break
        if not vm_found:
            print(f"{SKIP} list_terminal_sessions（无可用虚拟机）")

        # 团队读取类（需要团队会话，可选）
        try:
            check("team_list_users", client.team_list_users)
            check("team_list_groups", client.team_list_groups)
            check("team_list_hosts", client.team_list_hosts)
            check("team_list_images", client.team_list_images)
            check("team_list_models", client.team_list_models)
            check("team_list_skills", client.team_list_skills)
            check("team_list_projects", client.team_list_projects)
            check("team_list_tasks", client.team_list_tasks)
            check("team_list_mcp_upstreams", client.team_list_mcp_upstreams)
            check("team_list_notify_channels", client.team_list_notify_channels)
            check("team_list_oauth_sites", client.team_list_oauth_sites)
            check("team_list_extension_packages", client.team_list_extension_packages)
            check("team_list_audits", client.team_list_audits)
            check("team_get_dashboard", client.team_get_dashboard)
        except AuthenticationError:
            print(f"{SKIP} team_* 读取类（非团队会话，跳过）")

        if args.with_task:
            print("\n=== 6. 创建任务（--with-task）===")
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
            print(f"\n=== 6. 创建任务 ===")
            print(f"{SKIP} 已跳过（用 --with-task 开启；可能触发资源/计费，且平台有 10205 主机不可调度问题）")

        print("\n冒烟测试结束")


if __name__ == "__main__":
    main()
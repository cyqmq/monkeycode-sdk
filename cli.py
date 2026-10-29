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
import asyncio
import json
import os
import sys
from pathlib import Path

from monkeycode import (
    AuthenticationError,
    MonkeyCodeClient,
    TaskError,
)
from monkeycode.models import RepoReq


def default_session_path() -> str:
    """默认会话持久化文件路径（可用环境变量覆盖）。"""
    return os.environ.get(
        "MONKEYCODE_SESSION",
        str(Path.home() / ".monkeycode_session.json"),
    )


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


def cmd_list_tasks(client: MonkeyCodeClient) -> None:
    """列出最近任务。"""
    data = client.list_tasks(size=10)
    tasks = data.get("tasks") if isinstance(data, dict) else data
    for t in tasks or []:
        status = t.get("status") or ""
        tid = t.get("id") or ""
        content = (t.get("content") or "")[:60]
        print(f"{tid}  {status:<12}  {content}")


def cmd_task_info(client: MonkeyCodeClient, task_id: str) -> None:
    """查看任务详情。"""
    print_json(client.get_task(task_id).raw)


def cmd_task_stop(client: MonkeyCodeClient, task_id: str) -> None:
    """停止任务。"""
    print_json(client.stop_task(task_id))


def cmd_task_delete(client: MonkeyCodeClient, task_id: str) -> None:
    """删除任务。"""
    print_json(client.delete_task(task_id))


def cmd_send_msg(client: MonkeyCodeClient, task_id: str, content: str) -> None:
    """向运行中的任务发送消息。"""
    events = asyncio.run(client.send_task_message(task_id, content))
    for e in events:
        text = str(e.data)
        print(f"{e.type}: {text[:200]}")


def cmd_wallet(client: MonkeyCodeClient) -> None:
    """查看钱包余额。"""
    print_json(client.get_wallet())


def cmd_checkin(client: MonkeyCodeClient) -> None:
    """每日签到（自动求解 PoW）。"""
    print_json(client.checkin())


def cmd_wallet_tx(client: MonkeyCodeClient) -> None:
    """查看钱包交易记录。"""
    print_json(client.get_wallet_transactions())


def cmd_list_projects(client: MonkeyCodeClient) -> None:
    """列出项目（仓库）。"""
    print_json(client.list_projects())


def cmd_options(client: MonkeyCodeClient) -> None:
    """显示创建任务的下拉选项统计。"""
    opts = client.get_task_options()
    print(
        f"models={len(opts['models'])} images={len(opts['images'])} "
        f"hosts={len(opts['hosts'])} projects={len(opts['projects'])} "
        f"plan={opts['plan']}"
    )


def cmd_vms(client: MonkeyCodeClient) -> None:
    """列出各宿主下的虚拟机。"""
    hosts = client.list_hosts()
    for h in hosts or []:
        vms = h.get("virtualmachines") or h.get("vms") or []
        print(f"host={h.get('id')} name={h.get('name')} vms={len(vms)}")
        for vm in vms:
            print(
                f"  vm={vm.get('id')}  {vm.get('name') or ''}  "
                f"{vm.get('status') or ''}"
            )


def cmd_terminal(client: MonkeyCodeClient, vm_id: str) -> None:
    """列出虚拟机终端会话。"""
    print_json(client.list_terminal_sessions(vm_id))


def cmd_api_key_create(client: MonkeyCodeClient) -> None:
    """创建 API Key（仅显示一次）。"""
    key = client.create_api_key()
    print(f"key_id={key.key_id}")
    print(f"api_key={key.api_key}")
    print("（api_key 仅此一次显示，请妥善保存）")


def cmd_api_key_delete(client: MonkeyCodeClient, key_id: str) -> None:
    """删除 API Key。"""
    print_json(client.delete_api_key(key_id))


def cmd_list_available_models(client: MonkeyCodeClient) -> None:
    """列出可用模型。"""
    print_json(client.list_available_models())


def cmd_list_model_providers(
    client: MonkeyCodeClient,
    provider: str,
    base_url: str,
    api_key: str,
    api_header: str | None = None,
) -> None:
    """列出模型供应商的模型列表。"""
    print_json(
        client.list_model_providers(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            api_header=api_header,
        )
    )


def cmd_switch_model(
    client: MonkeyCodeClient, task_id: str, model_id: str
) -> None:
    """切换运行中任务的模型。"""
    result = asyncio.run(client.switch_task_model(task_id, model_id))
    print_json(result)


def cmd_restart(client: MonkeyCodeClient, task_id: str) -> None:
    """重启任务。"""
    result = asyncio.run(client.restart_task(task_id))
    print_json(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="MonkeyCode SDK CLI")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("MONKEYCODE_BASE_URL", "https://monkeycode-ai.com"),
        help="MonkeyCode API 地址",
    )
    parser.add_argument(
        "--session",
        default=default_session_path(),
        help="会话 Cookie 持久化文件路径",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="登录并保存会话")
    sub.add_parser("whoami", help="显示当前登录账户信息")
    sub.add_parser("logout", help="退出当前会话")
    sub.add_parser("list-hosts", help="列出云端环境")
    sub.add_parser("list-images", help="列出镜像")
    sub.add_parser("list-models", help="列出模型")
    sub.add_parser("list-available-models", help="列出可用模型")
    lm_p = sub.add_parser("list-model-providers", help="列出模型供应商的模型列表")
    lm_p.add_argument("provider", help="供应商：SiliconFlow/OpenAI/Ollama/DeepSeek 等")
    lm_p.add_argument("base_url", help="Base URL")
    lm_p.add_argument("api_key", help="API Key")
    lm_p.add_argument("--api-header", default=None, help="API 请求头")
    sub.add_parser("list-tasks", help="列出最近任务")
    sub.add_parser("wallet", help="查看钱包余额")
    sub.add_parser("checkin", help="每日签到")
    sub.add_parser("wallet-tx", help="查看钱包交易记录")
    sub.add_parser("list-projects", help="列出项目（仓库）")
    sub.add_parser("options", help="显示创建任务的下拉选项统计")
    sub.add_parser("vms", help="列出各宿主下的虚拟机")

    api_key_p = sub.add_parser("api-key", help="API Key 管理")
    api_key_sub = api_key_p.add_subparsers(dest="api_key_command", required=True)
    api_key_sub.add_parser("create", help="创建 API Key")
    ak_delete_p = api_key_sub.add_parser("delete", help="删除 API Key")
    ak_delete_p.add_argument("key_id", help="API Key ID")

    run_p = sub.add_parser("run", help="创建任务并轮询结果")
    run_p.add_argument("content", help="任务内容（自然语言）")

    links_p = sub.add_parser("links", help="列出任务中的预览链接并检测存活")
    links_p.add_argument("task_id", help="任务 ID")

    info_p = sub.add_parser("task-info", help="查看任务详情")
    info_p.add_argument("task_id", help="任务 ID")

    stop_p = sub.add_parser("task-stop", help="停止任务")
    stop_p.add_argument("task_id", help="任务 ID")

    delete_p = sub.add_parser("task-delete", help="删除任务")
    delete_p.add_argument("task_id", help="任务 ID")

    send_p = sub.add_parser("send-msg", help="向运行中的任务发送消息")
    send_p.add_argument("task_id", help="任务 ID")
    send_p.add_argument("content", help="消息内容")

    term_p = sub.add_parser("terminal", help="列出虚拟机终端会话")
    term_p.add_argument("vm_id", help="虚拟机 ID")

    sm_p = sub.add_parser("switch-model", help="切换运行中任务的模型")
    sm_p.add_argument("task_id", help="任务 ID")
    sm_p.add_argument("model_id", help="模型 ID")

    restart_p = sub.add_parser("restart", help="重启任务")
    restart_p.add_argument("task_id", help="任务 ID")

    args = parser.parse_args()
    email, password = get_credentials()
    with MonkeyCodeClient(
        email=email,
        password=password,
        base_url=args.base_url,
        session_path=args.session,
    ) as client:
        if args.command == "login":
            interactive_login(client)
            return
        # 有持久化会话则直接使用；无效时 SDK 会自动重登
        try:
            client.whoami()
        except AuthenticationError:
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
        elif args.command == "list-available-models":
            cmd_list_available_models(client)
        elif args.command == "list-model-providers":
            cmd_list_model_providers(
                client,
                args.provider,
                args.base_url,
                args.api_key,
                args.api_header,
            )
        elif args.command == "list-tasks":
            cmd_list_tasks(client)
        elif args.command == "wallet":
            cmd_wallet(client)
        elif args.command == "checkin":
            cmd_checkin(client)
        elif args.command == "wallet-tx":
            cmd_wallet_tx(client)
        elif args.command == "list-projects":
            cmd_list_projects(client)
        elif args.command == "options":
            cmd_options(client)
        elif args.command == "vms":
            cmd_vms(client)
        elif args.command == "api-key":
            if args.api_key_command == "create":
                cmd_api_key_create(client)
            else:
                cmd_api_key_delete(client, args.key_id)
        elif args.command == "task-info":
            cmd_task_info(client, args.task_id)
        elif args.command == "task-stop":
            cmd_task_stop(client, args.task_id)
        elif args.command == "task-delete":
            cmd_task_delete(client, args.task_id)
        elif args.command == "send-msg":
            cmd_send_msg(client, args.task_id, args.content)
        elif args.command == "terminal":
            cmd_terminal(client, args.vm_id)
        elif args.command == "switch-model":
            cmd_switch_model(client, args.task_id, args.model_id)
        elif args.command == "restart":
            cmd_restart(client, args.task_id)
        elif args.command == "run":
            cmd_run(client, args.content)
        elif args.command == "links":
            cmd_links(client, args.task_id)


if __name__ == "__main__":
    main()
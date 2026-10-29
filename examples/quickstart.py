#!/usr/bin/env python3
"""快速开始：登录、枚举环境、创建任务、轮询结果。

用法：
    export MONKEYCODE_EMAIL=you@example.com
    export MONKEYCODE_PASSWORD=your_password
    python examples/quickstart.py "写一个 hello world"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monkeycode import MonkeyCodeClient
from monkeycode.models import RepoReq


def main() -> None:
    email = os.environ.get("MONKEYCODE_EMAIL", "")
    password = os.environ.get("MONKEYCODE_PASSWORD", "")
    if not email or not password:
        print("请设置 MONKEYCODE_EMAIL 和 MONKEYCODE_PASSWORD")
        sys.exit(1)

    content = sys.argv[1] if len(sys.argv) > 1 else "写一个 hello world Python 脚本并运行"

    client = MonkeyCodeClient(email=email, password=password)
    with client:
        client.login()
        hosts = client.list_hosts()
        images = client.list_images()
        models = client.list_models()
        print(f"hosts={len(hosts)} images={len(images)} models={len(models)}")

        task = client.create_task(
            content=content,
            repo=RepoReq(repo_url=""),
            host_id=hosts[0]["id"],
            image_id=images[0]["id"],
            model_id=models[0]["id"],
        )
        print(f"任务已创建：{task.id}（{task.status}）")

        result = client.wait_task(task.id, timeout=1800, interval=10)
        print("任务终态：", result.status)


if __name__ == "__main__":
    main()
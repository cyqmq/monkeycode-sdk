#!/usr/bin/env python3
"""查余额、每日签到、交易记录。

用法：
    export MONKEYCODE_EMAIL=you@example.com
    export MONKEYCODE_PASSWORD=your_password
    python examples/wallet_checkin.py
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
        print("钱包余额：", client.get_wallet())
        print("签到结果：", client.checkin())
        print("交易记录：", client.get_wallet_transactions())


if __name__ == "__main__":
    main()
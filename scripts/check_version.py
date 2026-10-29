#!/usr/bin/env python3
"""发布前版本一致性检查。

校验 pyproject.toml 的 version 与 monkeycode/__init__.py 的 __version__ 一致。
用法：python scripts/check_version.py
不一致时退出码为 1。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init = (ROOT / "monkeycode" / "__init__.py").read_text(encoding="utf-8")

    m_pyproject = re.search(r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', pyproject, re.M)
    m_init = re.search(r'__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', init)

    if not m_pyproject or not m_init:
        print("❌ 未找到版本号（检查 pyproject.toml 或 monkeycode/__init__.py）")
        return 1

    if m_pyproject.group(1) != m_init.group(1):
        print(
            f"❌ 版本号不一致：pyproject.toml = {m_pyproject.group(1)}，"
            f"__init__.py = {m_init.group(1)}"
        )
        return 1

    print(f"✅ 版本号一致：{m_pyproject.group(1)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
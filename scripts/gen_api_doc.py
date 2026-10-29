#!/usr/bin/env python3
"""生成 docs/API.md 方法索引表。

从 monkeycode/client.py 的 MonkeyCodeClient 类中提取全部公开方法
（同步 def + 异步 async def），按字母序生成带签名的索引表。

用法：python scripts/gen_api_doc.py
"""
from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLIENT = ROOT / "monkeycode" / "client.py"
OUTPUT = ROOT / "docs" / "API.md"


def main() -> None:
    tree = ast.parse(CLIENT.read_text(encoding="utf-8"))

    rows: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "MonkeyCodeClient":
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name.startswith("_"):
                    continue
                doc = ast.get_docstring(item) or ""
                first = doc.strip().split("\n")[0] if doc.strip() else ""
                first = re.sub(r"[。.]$", "", first)
                args_src = ast.unparse(item.args)
                sig = (
                    f"{item.name}({args_src})"
                    if args_src.strip()
                    else item.name
                )
                rows.append((item.name, sig, first))

    rows.sort(key=lambda r: r[0])
    lines = [
        "# API 方法索引",
        "",
        "按字母序排列的 MonkeyCodeClient 全部公开方法（共 %d 个，含 async WebSocket/控制通道方法）。"
        % len(rows),
        "详细示例见 [功能参考.md](功能参考.md)。",
        "",
        "| 方法签名 | 说明 |",
        "|------|------|",
    ]
    for _, sig, desc in rows:
        lines.append(f"| `{sig}` | {desc} |")
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"docs/API.md 已重新生成，共 {len(rows)} 个方法")


if __name__ == "__main__":
    main()
"""CLI 自动子命令覆盖测试。"""
import argparse

from monkeycode.client import MonkeyCodeClient

import cli


def _sub() -> argparse._SubParsersAction:
    parser = argparse.ArgumentParser()
    return parser.add_subparsers(dest="command", required=True)


def test_auto_subcommands_cover_uncovered_methods():
    """自动子命令应为每个未显式覆盖的公共方法生成一个命令。"""
    sub = _sub()
    cli._register_auto_subcommands(sub)
    assert "team-list-users" in sub.choices
    assert "create-model" in sub.choices
    assert "get-server-config" in sub.choices
    assert "upload-file" in sub.choices
    # 已用显式别名覆盖的方法不再重复生成
    assert "add-git-identity" not in sub.choices
    assert "list-mcp-upstreams" not in sub.choices


def test_auto_dispatch_no_arg_method():
    """无参方法经自动分发调用并打印结果（不抛错）。"""
    calls = {}

    class FakeClient:
        def get_server_config(self):
            calls["hit"] = True
            return {"server": "ok"}

    args = argparse.Namespace(
        command="get-server-config",
        _method_name="get_server_config",
        _positional=[],
        _optional=[],
        _has_vk=False,
    )
    cli._auto_dispatch(FakeClient(), args)  # type: ignore[arg-type]
    assert calls.get("hit") is True


def test_auto_dispatch_set_fields():
    """--set 字段合并进 kwargs。"""
    captured = {}

    class FakeClient:
        def create_model(self, **fields):
            captured.update(fields)
            return {"ok": True}

    args = argparse.Namespace(
        command="create-model",
        _method_name="create_model",
        _positional=[],
        _optional=[],
        _has_vk=True,
        _set_kv=["name=test", "enabled=true", "n=3"],
        _json=None,
    )
    cli._auto_dispatch(FakeClient(), args)  # type: ignore[arg-type]
    assert captured["name"] == "test"
    assert captured["enabled"] is True
    assert captured["n"] == 3


def test_coerce_scalar():
    assert cli._coerce_scalar("42") == 42
    assert cli._coerce_scalar("3.14") == 3.14
    assert cli._coerce_scalar("true") is True
    assert cli._coerce_scalar("false") is False
    assert cli._coerce_scalar("hello") == "hello"
    assert cli._coerce_scalar('{"a": 1}') == {"a": 1}

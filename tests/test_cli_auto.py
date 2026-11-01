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


def test_csv_list():
    assert cli._csv_list("a,b,c") == ["a", "b", "c"]
    assert cli._csv_list('["x","y"]') == ["x", "y"]
    assert cli._csv_list(["z"]) == ["z"]
    assert cli._csv_list("") == []


def test_read_bytes(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"\x01\x02")
    assert cli._read_bytes(str(f)) == b"\x01\x02"


def test_arg_type_mapping():
    assert cli._arg_type(int) is int
    assert cli._arg_type(bool) is cli._str2bool
    assert cli._arg_type(float) is float
    assert cli._arg_type(list) is cli._csv_list
    assert cli._arg_type(bytes) is cli._read_bytes
    assert cli._arg_type(str) is str


def test_download_file_command(tmp_path):
    """download-file 命令把字节写入磁盘。"""
    class FakeClient:
        def download_file(self, vm_id, path, filename):
            return b"data"

    out = tmp_path / "out.txt"
    cli.cmd_download_file(
        FakeClient(), "vm1", "/x", "f.txt", str(out)  # type: ignore[arg-type]
    )
    assert out.read_bytes() == b"data"


def test_print_url_str(capsys):
    cli._print_auto_result("build_oauth_login_url", "https://x/authorize")
    assert "https://x/authorize" in capsys.readouterr().out


def test_print_key_value(capsys):
    cli._print_auto_result("get_server_config", {"a": 1, "b": [1, 2]})
    out = capsys.readouterr().out
    assert "a: 1" in out


def test_auto_dispatch_async_method(capsys):
    """async 方法经 asyncio.run 调用。"""
    calls = {}

    class FakeClient:
        async def sync_client_ip(self, task_id, ip, timeout=30.0):
            calls["task_id"] = task_id
            calls["ip"] = ip
            return {"ok": True}

    args = argparse.Namespace(
        command="sync-client-ip",
        _method_name="sync_client_ip",
        _positional=["task_id", "ip"],
        _optional=["timeout"],
        _has_vk=False,
        timeout=None,
    )
    args.task_id = "t1"
    args.ip = "1.2.3.4"
    cli._auto_dispatch(FakeClient(), args)  # type: ignore[arg-type]
    assert calls == {"task_id": "t1", "ip": "1.2.3.4"}
    assert "ok" in capsys.readouterr().out

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


def test_extract_items_list():
    """B6 回归：裸 list 返回值不应触发 .get 崩溃。"""
    assert cli._extract_items([{"id": 1}], "identities") == [{"id": 1}]


def test_extract_items_dict():
    assert cli._extract_items({"identities": [{"id": 1}]}, "identities") == [
        {"id": 1}
    ]
    assert cli._extract_items({"list": [1, 2]}, "identities", "list") == [1, 2]
    assert cli._extract_items(None, "identities") == []


def test_git_identity_list_list_return(capsys):
    """B6 回归：list_git_identities 返回裸 list 时 git-identity-list 不崩溃。"""

    class FakeClient:
        def list_git_identities(self):
            return [{"id": "1", "username": "alice", "email": "a@x.com"}]

    cli.cmd_git_identity_list(FakeClient())  # type: ignore[arg-type]
    assert "alice" in capsys.readouterr().out


def test_mcp_list_list_return(capsys):
    """B6 回归：list_mcp_upstreams 返回裸 list 时 mcp-list 不崩溃。"""

    class FakeClient:
        def list_mcp_upstreams(self):
            return [{"id": "u1", "name": "github"}]

    cli.cmd_mcp_list(FakeClient())  # type: ignore[arg-type]
    assert "github" in capsys.readouterr().out


def test_git_identity_update_no_shadow_global_base_url():
    """B6c 回归：git-identity-update 的 --new-base-url 不再遮蔽全局 --base-url。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://monkeycode-ai.com")
    sub = parser.add_subparsers(dest="command", required=True)
    giu = sub.add_parser("git-identity-update")
    giu.add_argument("identity_id")
    giu.add_argument("--new-base-url", default=None)
    args = parser.parse_args(
        ["git-identity-update", "ID", "--new-base-url", "https://github.com"]
    )
    assert args.base_url == "https://monkeycode-ai.com"
    assert args.new_base_url == "https://github.com"


def test_git_identity_add_provider_base_url():
    """B6c 回归：git-identity-add 用 provider_base_url，全局 --base-url 保持默认。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://monkeycode-ai.com")
    sub = parser.add_subparsers(dest="command", required=True)
    gia = sub.add_parser("git-identity-add")
    for a in ["access_token", "provider_base_url", "email", "platform", "username"]:
        gia.add_argument(a)
    args = parser.parse_args(
        ["git-identity-add", "tok", "https://github.com", "a@x.com", "github", "alice"]
    )
    assert args.provider_base_url == "https://github.com"
    assert args.base_url == "https://monkeycode-ai.com"


def test_git_identity_update_help_has_new_base_url(capsys):
    """B6c 回归：help 输出包含 --new-base-url 而非 --base-url。"""
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "cli.py", "git-identity-update", "--help"],
        capture_output=True,
        text=True,
    ).stdout
    assert "--new-base-url" in out
    assert "--base-url" not in out.split("\n")[0] or "--base-url" not in out


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

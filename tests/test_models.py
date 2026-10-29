"""数据模型单元测试。"""
import base64
import json

from monkeycode.models import (
    APIKeyInfo,
    RepoReq,
    Task,
    TaskExtraConfig,
    UserInputPayload,
    VMResource,
)


def test_repo_req_to_dict() -> None:
    req = RepoReq(repo_url="https://github.com/a/b", branch="dev")
    d = req.to_dict()
    assert d == {
        "repo_url": "https://github.com/a/b",
        "branch": "dev",
        "repo_filename": "",
        "zip_url": "",
    }


def test_vm_resource_to_dict_defaults() -> None:
    d = VMResource().to_dict()
    assert d["core"] == 2
    assert d["memory"] == 8 << 30
    assert d["life"] == 3 * 60 * 60


def test_task_extra_config_empty() -> None:
    assert TaskExtraConfig().to_dict() == {}


def test_task_extra_config_full() -> None:
    d = TaskExtraConfig(
        skill_ids=["a", "b"],
        plugin_ids=["p"],
        project_id="proj-1",
        issue_id="issue-1",
    ).to_dict()
    assert d == {
        "skill_ids": ["a", "b"],
        "plugin_ids": ["p"],
        "project_id": "proj-1",
        "issue_id": "issue-1",
    }


def test_task_from_dict_with_id() -> None:
    raw = {"id": "t1", "status": "running", "title": "hi"}
    task = Task.from_dict(raw)
    assert task.id == "t1"
    assert task.status == "running"
    assert task.raw is raw
    assert task.title == "hi"


def test_task_from_dict_with_task_id() -> None:
    raw = {"task_id": "t2", "status": "pending"}
    task = Task.from_dict(raw)
    assert task.id == "t2"


def test_task_extra_property() -> None:
    raw = {
        "id": "t1",
        "status": "running",
        "extra": {"skill_ids": ["s"], "plugin_ids": []},
    }
    task = Task.from_dict(raw)
    assert task.extra is not None
    assert task.extra.skill_ids == ["s"]
    assert task.extra.plugin_ids == []


def test_api_key_info_from_dict() -> None:
    info = APIKeyInfo.from_dict({"api_key": "sk-xxx", "key_id": "k1"})
    assert info.api_key == "sk-xxx"
    assert info.key_id == "k1"


def test_api_key_info_from_dict_camel() -> None:
    info = APIKeyInfo.from_dict({"apiKey": "sk-yyy", "id": "k2"})
    assert info.api_key == "sk-yyy"
    assert info.key_id == "k2"


def test_user_input_payload_encode() -> None:
    payload = UserInputPayload(content="你好", attachments=[{"url": "u"}])
    encoded = payload.encode()
    obj = json.loads(encoded)
    assert obj["attachments"] == [{"url": "u"}]
    assert base64.b64decode(obj["content"]).decode("utf-8") == "你好"
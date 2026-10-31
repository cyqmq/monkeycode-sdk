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


def test_task_timestamps_tolerate_invalid() -> None:
    """非数字时间戳应容错返回 None，而不是抛 ValueError。"""
    raw = {
        "id": "t1",
        "status": "running",
        "created_at": "not-a-number",
        "completed_at": None,
    }
    task = Task.from_dict(raw)
    assert task.created_at is None
    assert task.completed_at is None


def test_task_timestamps_valid() -> None:
    raw = {
        "id": "t1",
        "status": "running",
        "created_at": "123",
        "completed_at": 456,
    }
    task = Task.from_dict(raw)
    assert task.created_at == 123
    assert task.completed_at == 456


def test_task_round_seq_tolerates_invalid() -> None:
    from monkeycode.models import TaskRound

    assert TaskRound(raw={"seq": "abc"}).seq is None
    assert TaskRound(raw={"seq": 7}).seq == 7


def test_group_models_partitions() -> None:
    from monkeycode.models import group_models

    models = [
        {"id": "m1", "access_level": "basic", "is_free": True,
         "owner": {"type": "organization"}},
        {"id": "m2", "access_level": "pro", "is_free": False,
         "owner": {"type": "organization"}},
        {"id": "m3", "access_level": "ultra", "is_free": False,
         "owner": {"type": "organization"}},
        {"id": "m4", "access_level": "basic", "is_free": False,
         "owner": {"type": "private"}},
        {"id": "m5", "access_level": "pro", "is_free": True,
         "owner": {"type": "user"}},
        {"id": "m6", "access_level": "", "is_free": True,
         "owner": {"type": "user"}},
    ]
    g = group_models(models)
    assert [m["id"] for m in g["private"]] == ["m4"]
    assert [m["id"] for m in g["basic"]] == ["m1"]
    assert [m["id"] for m in g["pro"]] == ["m2", "m5"]
    assert [m["id"] for m in g["ultra"]] == ["m3"]
    assert [m["id"] for m in g["other"]] == ["m6"]
    # paid 是交叉筛选：is_free == false 的模型
    assert [m["id"] for m in g["paid"]] == ["m2", "m3", "m4"]


def test_group_models_filters_hidden_and_dedupes() -> None:
    from monkeycode.models import group_models

    models = [
        {"id": "h1", "model": "hidden-model", "access_level": "basic",
         "is_free": True, "is_hidden": True, "owner": {"type": "user"}},
        {"id": "dup", "model": "glm-5", "access_level": "pro",
         "is_free": True, "owner": {"type": "user"}},
        {"id": "dup", "model": "glm-5", "access_level": "pro",
         "is_free": True, "owner": {"type": "user"}},
        {"id": "ok", "model": "glm-5", "access_level": "pro",
         "is_free": True, "owner": {"type": "user"}},
    ]
    g = group_models(models)
    # 隐藏模型不出现；同一 id 只保留一条
    ids = [m["id"] for m in g["pro"]]
    assert "h1" not in ids
    assert ids == ["dup", "ok"]

    # include_hidden=True 时隐藏模型出现
    g2 = group_models(models, include_hidden=True)
    hidden_ids = [m["id"] for m in g2["basic"]]
    assert "h1" in hidden_ids
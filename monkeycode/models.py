"""数据模型（轻量 dataclass，不引入 pydantic 依赖）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RepoReq:
    """任务仓库信息。"""

    repo_url: str
    branch: str = "main"
    repo_filename: str = ""
    zip_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_url": self.repo_url,
            "branch": self.branch,
            "repo_filename": self.repo_filename,
            "zip_url": self.zip_url,
        }


@dataclass
class VMResource:
    """云端虚拟机资源。

    默认值为 MonkeyCode 桌面端建任务的默认档位：
    2 核 / 8GB 内存 / 3 小时。
    """

    core: int = 2
    memory: int = 8 << 30  # 8GB（与桌面端常量一致，字节为单位）
    life: int = 3 * 60 * 60  # 3 小时（秒）

    def to_dict(self) -> dict[str, Any]:
        return {
            "core": self.core,
            "memory": self.memory,
            "life": self.life,
        }


@dataclass
class TaskExtraConfig:
    """任务扩展配置（对应 domain.TaskExtraConfig）。"""

    skill_ids: list[str] | None = None
    plugin_ids: list[str] | None = None
    project_id: str | None = None
    issue_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.skill_ids:
            out["skill_ids"] = self.skill_ids
        if self.plugin_ids:
            out["plugin_ids"] = self.plugin_ids
        if self.project_id:
            out["project_id"] = self.project_id
        if self.issue_id:
            out["issue_id"] = self.issue_id
        return out


@dataclass
class Task:
    """任务对象（响应的精简视图）。"""

    id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def title(self) -> str:
        return str(self.raw.get("title") or "")

    @property
    def summary(self) -> str:
        return str(self.raw.get("summary") or "")

    @property
    def content(self) -> str:
        return str(self.raw.get("content") or "")

    @property
    def branch(self) -> str:
        return str(self.raw.get("branch") or "")

    @property
    def repo_url(self) -> str:
        return str(self.raw.get("repo_url") or "")

    @property
    def pr_url(self) -> str | None:
        return (self.raw.get("pr_url") or self.raw.get("pull_request_url")) or None

    @property
    def model(self) -> dict[str, Any] | None:
        return self.raw.get("model") or None

    @property
    def image(self) -> dict[str, Any] | None:
        return self.raw.get("image") or None

    @property
    def extra(self) -> TaskExtraConfig | None:
        extra = self.raw.get("extra")
        if isinstance(extra, dict):
            return TaskExtraConfig(
                skill_ids=extra.get("skill_ids"),
                plugin_ids=extra.get("plugin_ids"),
                project_id=extra.get("project_id"),
                issue_id=extra.get("issue_id"),
            )
        return None

    @property
    def created_at(self) -> int | None:
        v = self.raw.get("created_at")
        return int(v) if v is not None else None

    @property
    def completed_at(self) -> int | None:
        v = self.raw.get("completed_at")
        return int(v) if v is not None else None

    @property
    def result(self) -> Any:
        return self.raw.get("result")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            id=str(data.get("id") or data.get("task_id") or ""),
            status=str(data.get("status") or ""),
            raw=data,
        )


@dataclass
class TaskRound:
    """任务历史轮次（domain.TaskRound 精简视图）。"""

    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def seq(self) -> int | None:
        v = self.raw.get("seq")
        return int(v) if v is not None else None

    @property
    def role(self) -> str:
        return str(self.raw.get("role") or "")

    @property
    def content(self) -> str:
        return str(self.raw.get("content") or "")


@dataclass
class CaptchaChallenge:
    """验证码质询。"""

    token: str
    expires: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CaptchaVerification:
    """验证码兑换结果。"""

    success: bool
    token: str = ""
    message: str = ""
    expires: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class APIKeyInfo:
    """OhMyAgent API Key（仅创建响应返回明文，需立即保存）。"""

    api_key: str
    key_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "APIKeyInfo":
        return cls(
            api_key=str(data.get("api_key") or data.get("apiKey") or ""),
            key_id=str(data.get("key_id") or data.get("id") or ""),
            raw=data,
        )
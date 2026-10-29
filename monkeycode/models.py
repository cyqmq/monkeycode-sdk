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
    """云端虚拟机资源。"""

    core: int = 1
    memory: int = 1024
    life: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "core": self.core,
            "memory": self.memory,
            "life": self.life,
        }


@dataclass
class Task:
    """任务对象（响应的精简视图）。"""

    id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def pr_url(self) -> str | None:
        return (self.raw.get("pr_url") or self.raw.get("pull_request_url")) or None

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
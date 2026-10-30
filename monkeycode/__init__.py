"""MonkeyCode SDK。

封装 MonkeyCode 云平台 REST API，提供认证、任务提交、结果轮询、
WebSocket 会话交互等能力。
"""
from monkeycode.client import MonkeyCodeClient
from monkeycode.errors import (
    APIError,
    AuthenticationError,
    CaptchaRequiredError,
    RateLimitError,
    TaskError,
)
from monkeycode.models import (
    APIKeyInfo,
    CaptchaChallenge,
    CaptchaVerification,
    RepoReq,
    Task,
    TaskExtraConfig,
    TaskRound,
    TaskStreamChunk,
    UserInputPayload,
    VMResource,
)
from monkeycode.session import AgentSession
from monkeycode.stream import (
    ControlStream,
    JoinTerminalStream,
    TaskStream,
    TerminalStream,
)

__version__ = "1.7.3"

__all__ = [
    "MonkeyCodeClient",
    "APIError",
    "AuthenticationError",
    "CaptchaRequiredError",
    "RateLimitError",
    "TaskError",
    "APIKeyInfo",
    "CaptchaChallenge",
    "CaptchaVerification",
    "RepoReq",
    "Task",
    "TaskExtraConfig",
    "TaskRound",
    "TaskStream",
    "TaskStreamChunk",
    "UserInputPayload",
    "VMResource",
    "ControlStream",
    "TerminalStream",
    "JoinTerminalStream",
    "AgentSession",
]
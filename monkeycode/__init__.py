"""MonkeyCode SDK。

封装 MonkeyCode 云平台 REST API，提供认证、任务提交、结果轮询等能力。
"""
from monkeycode.client import MonkeyCodeClient
from monkeycode.errors import (
    APIError,
    AuthenticationError,
    CaptchaRequiredError,
    RateLimitError,
    TaskError,
)

__version__ = "0.1.0"

__all__ = [
    "MonkeyCodeClient",
    "APIError",
    "AuthenticationError",
    "CaptchaRequiredError",
    "RateLimitError",
    "TaskError",
]
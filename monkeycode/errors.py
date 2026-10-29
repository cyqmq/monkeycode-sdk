"""异常定义。"""


class MonkeyCodeError(Exception):
    """所有 MonkeyCode SDK 异常的基类。"""


class APIError(MonkeyCodeError):
    """接口返回业务错误（HTTP 成功但 code != 0）。"""

    def __init__(self, message: str, code: int | None = None, raw: dict | None = None):
        super().__init__(message)
        self.code = code
        self.raw = raw or {}


class AuthenticationError(APIError):
    """认证失败（邮箱/密码错误、未登录、会话失效）。"""


class CaptchaRequiredError(AuthenticationError):
    """登录需要验证码（captcha_token 缺失或无效）。"""


class RateLimitError(APIError):
    """触发限流（HTTP 429）。"""


class TaskError(MonkeyCodeError):
    """任务相关错误（创建失败、状态异常、超时）。"""
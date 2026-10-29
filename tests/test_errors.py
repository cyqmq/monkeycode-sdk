"""异常层次单元测试。"""
from monkeycode.errors import (
    APIError,
    AuthenticationError,
    CaptchaRequiredError,
    MonkeyCodeError,
    RateLimitError,
    TaskError,
)


def test_exception_hierarchy() -> None:
    assert issubclass(CaptchaRequiredError, AuthenticationError)
    assert issubclass(AuthenticationError, APIError)
    assert issubclass(APIError, MonkeyCodeError)
    assert issubclass(RateLimitError, APIError)
    assert issubclass(TaskError, MonkeyCodeError)


def test_api_error_fields() -> None:
    err = APIError("业务错误", code=10205, raw={"code": 10205})
    assert err.code == 10205
    assert err.raw == {"code": 10205}


def test_authentication_error_code() -> None:
    err = AuthenticationError("未认证", code=401)
    assert err.code == 401
    assert isinstance(err, APIError)
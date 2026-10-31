"""客户端核心逻辑单元测试（httpx.MockTransport，不依赖真实平台）。"""
import json

import httpx
import pytest

from monkeycode import (
    APIError,
    AuthenticationError,
    MonkeyCodeClient,
)


def make_client(handler) -> MonkeyCodeClient:
    client = MonkeyCodeClient(email="user@example.com", password="secret")
    client._client = httpx.Client(
        base_url=client.base_url, transport=httpx.MockTransport(handler)
    )
    return client


def json_response(body, status=200, headers=None):
    return httpx.Response(
        status,
        json=body,
        headers=headers or {},
        request=httpx.Request("GET", "http://test"),
    )


def read_json(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


def test_list_git_identities_redacts_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            {
                "code": 0,
                "data": {
                    "identities": [
                        {
                            "id": "g1",
                            "name": "my-bot",
                            "access_token": "ghp_123456",
                            "token": "raw-secret",
                        }
                    ]
                },
            }
        )

    client = make_client(handler)
    data = client.list_git_identities()
    identity = data["identities"][0]
    assert identity["id"] == "g1"
    assert identity["name"] == "my-bot"
    assert identity["access_token"] == "***"
    assert identity["token"] == "***"


def test_list_playground_posts_not_found_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"message": "Not Found"})

    client = make_client(handler)
    with pytest.raises(APIError):
        client.list_playground_posts()


def test_get_license_status_not_found_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return json_response({"message": "Not Found"})

    client = make_client(handler)
    with pytest.raises(APIError):
        client.get_license_status()


# ---------- 登录 ----------

def test_login_success() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = read_json(request)
        return json_response({"code": 0, "data": {"user": {"id": "u1"}}})

    client = make_client(handler)
    client.login()
    assert client.is_logged_in()
    assert seen["path"] == "/api/v1/users/password-login"
    assert seen["body"]["email"] == "user@example.com"
    assert seen["body"]["password"] == "secret"


def test_login_wrong_password() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request)

    client = make_client(handler)
    with pytest.raises(AuthenticationError):
        client.login()


# ---------- PoW 自动求解 ----------

def test_login_auto_pow() -> None:
    login_attempts = {"n": 0}
    challenge_called = {"n": 0}
    redeem_called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/password-login":
            login_attempts["n"] += 1
            if login_attempts["n"] == 1:
                # 第一次要求验证码
                return httpx.Response(403, json={"code": 1}, request=request)
            return json_response({"code": 0, "data": {"user": {"id": "u1"}}})
        if path == "/api/v1/public/captcha/challenge":
            challenge_called["n"] += 1
            return json_response(
                {
                    "token": "tok1",
                    "expires": 100,
                    "challenge": {"c": 1, "s": 4, "d": 2},
                }
            )
        if path == "/api/v1/public/captcha/redeem":
            redeem_called["n"] += 1
            body = read_json(request)
            assert body["token"] == "tok1"
            assert isinstance(body["solutions"], list)
            assert len(body["solutions"]) == 1
            return json_response(
                {"success": True, "token": "captcha-token", "expires": 100}
            )
        return httpx.Response(404, request=request)

    client = make_client(handler)
    client.login()
    assert client.is_logged_in()
    assert login_attempts["n"] == 2
    assert challenge_called["n"] == 1
    assert redeem_called["n"] == 1


# ---------- 401 自动重登 ----------

def test_401_auto_relogin() -> None:
    status_calls = {"n": 0}
    login_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/users/status":
            status_calls["n"] += 1
            if status_calls["n"] == 1:
                return httpx.Response(401, request=request)
            return json_response({"code": 0, "data": {"email": "user@example.com"}})
        if path == "/api/v1/users/password-login":
            login_calls["n"] += 1
            return json_response({"code": 0, "data": {}})
        return httpx.Response(404, request=request)

    client = make_client(handler)
    client.login()
    data = client.whoami()
    assert data == {"email": "user@example.com"}
    assert status_calls["n"] == 2  # 首次 401 + 重试成功
    assert login_calls["n"] == 2  # 显式登录 + 自动重登各一次


# ---------- 只读请求网络重试 ----------

def test_get_retries_on_connection_error() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectError("connection reset")
        return json_response({"code": 0, "data": {"hosts": []}})

    client = make_client(handler)
    assert client.list_hosts() == []
    assert attempts["n"] == 2


# ---------- 429 限流重试 ----------

def test_429_retry_with_retry_after() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, request=request)
        return json_response({"code": 0, "data": {"models": []}})

    client = make_client(handler)
    assert client.list_models() == []
    assert attempts["n"] == 2


# ---------- 写操作不自动重试 ----------

def test_post_not_retried_on_network_error() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.ConnectError("boom")

    client = make_client(handler)
    from monkeycode.errors import APIError

    with pytest.raises(APIError):
        client.logout()
    assert attempts["n"] == 1  # 只读才重试，POST 不重试


# ---------- download_file 业务错误码解析 ----------

def test_download_file_raises_on_business_error() -> None:
    """后端 HTTP 200 + 业务错误 JSON 时应抛 APIError，而不是返回错误内容。"""
    from monkeycode.errors import APIError

    def handler(request: httpx.Request) -> httpx.Response:
        return json_response(
            {"code": 10231, "message": "开发环境已被回收"},
            headers={"Content-Type": "application/json"},
        )

    client = make_client(handler)
    with pytest.raises(APIError) as ei:
        client.download_file("vm-1", "/root", "a.txt")
    assert ei.value.code == 10231
    assert "开发环境已被回收" in str(ei.value)


def test_download_file_returns_bytes_on_success() -> None:
    """正常下载应返回文件字节内容。"""
    import io

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"file-content",
            headers={"Content-Type": "application/octet-stream"},
            request=request,
        )

    client = make_client(handler)
    assert client.download_file("vm-1", "/root", "a.txt") == b"file-content"
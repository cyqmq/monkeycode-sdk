"""MonkeyCode 云平台 REST API 客户端。

基于 httpx，登录后自动携带会话 Cookie（monkeycode_ai_session）。
支持密码登录（MD5 + 可选验证码）、枚举环境、创建任务、轮询结果。
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

from monkeycode.consts import CliName, TaskSubType, TaskType
from monkeycode.errors import (
    APIError,
    AuthenticationError,
    CaptchaRequiredError,
    RateLimitError,
    TaskError,
)
from monkeycode.models import (
    CaptchaChallenge,
    CaptchaVerification,
    RepoReq,
    Task,
    VMResource,
)

DEFAULT_BASE_URL = "https://monkeycode-ai.com"
SESSION_COOKIE = "monkeycode_ai_session"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class MonkeyCodeClient:
    """MonkeyCode 云平台客户端。

    示例：
        client = MonkeyCodeClient(email="...", password="...")
        client.login()
        task = client.create_task("修复登录接口异常", repo=RepoReq(repo_url="..."), ...)
        result = client.wait_task(task.id)
    """

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        password_md5: bool = False,
    ) -> None:
        self.email = email
        self._password = password or ""
        self._password_md5_mode = password_md5
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=True,
        )
        self._logged_in = False

    # ---------- 认证 ----------

    def login(self, captcha_token: str | None = None) -> dict[str, Any]:
        """使用邮箱 + 密码登录。

        生产平台 monkeycode-ai.com 使用 bcrypt 校验，需传**明文密码**；
        早期/部分私有化部署可能要求 MD5，可用 password_md5=True 兼容。

        云平台可能启用验证码：先调用 create_captcha / redeem_captcha 获取
        captcha_token 后传入。登录成功后自动保存会话 Cookie。
        """
        if not self.email or not self._password:
            raise AuthenticationError("缺少邮箱或密码，请在构造客户端时传入。")
        password = _md5(self._password) if self._password_md5_mode else self._password
        body: dict[str, Any] = {
            "email": self.email,
            "password": password,
        }
        if captcha_token:
            body["captcha_token"] = captcha_token
        try:
            data = self._request("POST", "/api/v1/users/password-login", json=body)
        except AuthenticationError as exc:
            # 403 且无 captcha_token 时提示需要验证码
            if exc.code == 403 and not captcha_token:
                raise CaptchaRequiredError(
                    "登录需要验证码，请先调用 create_captcha/redeem_captcha 获取 captcha_token。",
                    code=403,
                ) from exc
            raise
        self._logged_in = True
        return data

    def create_captcha(self) -> CaptchaChallenge:
        """创建验证码质询。"""
        data = self._request(
            "POST", "/api/v1/public/captcha/challenge", json={}, auth_required=False
        )
        return CaptchaChallenge(
            token=str(data.get("token") or ""),
            expires=int(data.get("expires") or 0),
            raw=data,
        )

    def redeem_captcha(self, token: str, solutions: list[int]) -> CaptchaVerification:
        """提交验证码答案，兑换登录用的 captcha_token。"""
        data = self._request(
            "POST",
            "/api/v1/public/captcha/redeem",
            json={"token": token, "solutions": solutions},
            auth_required=False,
        )
        return CaptchaVerification(
            success=bool(data.get("success")),
            token=str(data.get("token") or ""),
            message=str(data.get("message") or ""),
            expires=int(data.get("expires") or 0),
            raw=data,
        )

    # ---------- 枚举环境 ----------

    def list_hosts(self) -> list[dict[str, Any]]:
        """获取可用的云端宿主/环境列表（返回 data.hosts）。"""
        data = self._request("GET", "/api/v1/users/hosts")
        if isinstance(data, dict):
            return data.get("hosts") or []
        return data or []

    def list_images(self) -> list[dict[str, Any]]:
        """获取可用的镜像列表（返回 data.images）。"""
        data = self._request("GET", "/api/v1/users/images")
        if isinstance(data, dict):
            return data.get("images") or []
        return data or []

    def list_models(self) -> list[dict[str, Any]]:
        """获取可用的模型列表（返回 data.models）。"""
        data = self._request("GET", "/api/v1/users/models")
        if isinstance(data, dict):
            return data.get("models") or []
        return data or []

    def list_projects(self) -> list[dict[str, Any]]:
        """获取项目（仓库）列表。"""
        data = self._request("GET", "/api/v1/users/projects")
        if isinstance(data, dict):
            return data.get("projects") or []
        return data or []

    # ---------- 任务 ----------

    def create_task(
        self,
        content: str,
        repo: RepoReq,
        host_id: str,
        image_id: str,
        model_id: str,
        resource: VMResource | None = None,
        task_type: TaskType = TaskType.DEVELOP,
        sub_type: TaskSubType | None = None,
        cli_name: CliName | None = None,
        git_identity_id: str | None = None,
        system_prompt: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Task:
        """创建任务。

        必填：content / repo / host_id / image_id / model_id / resource。
        """
        body: dict[str, Any] = {
            "content": content,
            "repo": repo.to_dict(),
            "host_id": str(host_id),
            "image_id": str(image_id),
            "model_id": str(model_id),
            "resource": (resource or VMResource()).to_dict(),
            "task_type": task_type.value,
        }
        if sub_type:
            body["sub_type"] = sub_type.value
        if cli_name:
            body["cli_name"] = cli_name.value
        if git_identity_id:
            body["git_identity_id"] = git_identity_id
        if system_prompt:
            body["system_prompt"] = system_prompt
        if extra:
            body["extra"] = extra
        data = self._request("POST", "/api/v1/users/tasks", json=body)
        return Task.from_dict(data)

    def get_task(self, task_id: str) -> Task:
        """获取任务详情。"""
        data = self._request("GET", f"/api/v1/users/tasks/{task_id}")
        return Task.from_dict(data)

    def stop_task(self, task_id: str) -> dict[str, Any]:
        """停止任务。"""
        return self._request("PUT", "/api/v1/users/tasks/stop", json={"id": task_id})

    def wait_task(
        self,
        task_id: str,
        timeout: float = 1800.0,
        interval: float = 5.0,
        terminal_statuses: set[str] | None = None,
    ) -> Task:
        """轮询任务直到进入终态。

        终态默认：success / failed / stopped / canceled。
        """
        terminals = terminal_statuses or {
            "success",
            "failed",
            "stopped",
            "canceled",
            "cancelled",
        }
        deadline = time.monotonic() + timeout
        last = Task.from_dict({"id": task_id, "status": "running"})
        while time.monotonic() < deadline:
            last = self.get_task(task_id)
            if last.status.lower() in terminals:
                return last
            time.sleep(interval)
        raise TaskError(f"等待任务 {task_id} 超时（{timeout}s），最后状态：{last.status}")

    # ---------- 内部请求 ----------

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        auth_required: bool = True,
    ) -> Any:
        try:
            resp = self._client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise APIError(f"请求失败：{exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("未认证或会话已失效，请重新登录。", code=401)
        if resp.status_code == 429:
            raise RateLimitError("触发限流（HTTP 429），请稍后重试。", code=429)
        if resp.status_code == 403 and auth_required:
            raise AuthenticationError("无权限访问该资源。", code=403)

        try:
            body = resp.json()
        except ValueError:
            if resp.status_code != 200:
                raise APIError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return resp.text

        if isinstance(body, dict) and "code" in body:
            code = body.get("code")
            if code != 0:
                message = body.get("message") or body.get("msg") or "未知错误"
                raise APIError(f"{message}（code={code}）", code=code, raw=body)
            return body.get("data")
        return body

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MonkeyCodeClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
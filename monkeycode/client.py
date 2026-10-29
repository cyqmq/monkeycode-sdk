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
    APIKeyInfo,
    CaptchaChallenge,
    CaptchaVerification,
    RepoReq,
    Task,
    TaskExtraConfig,
    VMResource,
)
from monkeycode.pow import solve

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
        """使用邮箱 + 密码登录，自动处理 PoW 验证码。

        生产平台 monkeycode-ai.com 使用 bcrypt 校验，需传**明文密码**；
        早期/部分私有化部署可能要求 MD5，可用 password_md5=True 兼容。

        云平台强制启用验证码（SHA-256 前缀碰撞），本方法会自动：
        challenge -> 本地求解 -> redeem -> 携带 captcha_token 登录。
        也可以显式传入 captcha_token 跳过自动求解。
        登录成功后自动保存会话 Cookie。
        """
        if not self.email or not self._password:
            raise AuthenticationError("缺少邮箱或密码，请在构造客户端时传入。")
        try:
            return self._login_request(captcha_token)
        except CaptchaRequiredError:
            if captcha_token:
                raise
            token = self._solve_captcha()
            return self._login_request(token)

    def _login_request(self, captcha_token: str | None) -> dict[str, Any]:
        """发送登录请求。"""
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
            if exc.code == 403 and not captcha_token:
                raise CaptchaRequiredError(
                    "登录需要验证码。",
                    code=403,
                ) from exc
            raise
        self._logged_in = True
        return data

    def _solve_captcha(self) -> str:
        """自动完成 PoW 验证码：challenge -> 本地求解 -> redeem。"""
        challenge = self.create_captcha()
        c = int(challenge.raw["challenge"]["c"])
        s = int(challenge.raw["challenge"]["s"])
        d = int(challenge.raw["challenge"]["d"])
        solutions = solve(challenge.token, c, s, d)
        result = self.redeem_captcha(challenge.token, solutions)
        if not result.success:
            raise AuthenticationError(f"验证码兑换失败：{result.message}")
        return result.token

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
        host_id: str = "public_host",
        image_id: str | None = None,
        model_id: str | None = None,
        resource: VMResource | None = None,
        task_type: TaskType = TaskType.DEVELOP,
        sub_type: TaskSubType | None = None,
        cli_name: CliName = CliName.OPENCODE,
        git_identity_id: str | None = None,
        system_prompt: str | None = None,
        skill_ids: list[str] | None = None,
        plugin_ids: list[str] | None = None,
        project_id: str | None = None,
        issue_id: str | None = None,
    ) -> Task:
        """创建任务。

        必填：content / repo。host_id 默认 public_host；
        image_id / model_id 留空时自动取列表第一个可用项；
        资源默认 2 核 / 8GB / 3 小时（桌面端默认档位）。
        """
        if not image_id:
            images = self.list_images()
            if not images:
                raise TaskError("没有可用的镜像（images），请先在控制台创建镜像。")
            image_id = images[0]["id"]
        if not model_id:
            models = self.list_models()
            if not models:
                raise TaskError("没有可用的模型（models），请先在控制台配置模型。")
            model_id = models[0]["id"]

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
        extra = TaskExtraConfig(
            skill_ids=skill_ids,
            plugin_ids=plugin_ids,
            project_id=project_id,
            issue_id=issue_id,
        ).to_dict()
        if extra:
            body["extra"] = extra
        data = self._request("POST", "/api/v1/users/tasks", json=body)
        return Task.from_dict(data)

    def list_tasks(
        self,
        page: int | None = None,
        size: int | None = None,
        status: str | None = None,
        project_id: str | None = None,
        quick_start: str | None = None,
        next_token: str | None = None,
    ) -> Any:
        """任务列表。

        返回接口原始 data（通常为 {"tasks": [...], "page": {...}} 或列表），
        支持状态筛选：status 多值用逗号分隔，如 "pending,processing"。
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if size is not None:
            params["size"] = size
        if status is not None:
            params["status"] = status
        if project_id is not None:
            params["project_id"] = project_id
        if quick_start is not None:
            params["quick_start"] = quick_start
        if next_token is not None:
            params["next_token"] = next_token
        return self._request("GET", "/api/v1/users/tasks", params=params)

    def get_task(self, task_id: str) -> Task:
        """获取任务详情。"""
        data = self._request("GET", f"/api/v1/users/tasks/{task_id}")
        return Task.from_dict(data)

    def get_task_rounds(
        self,
        task_id: str,
        cursor: str | None = None,
        limit: int = 2,
        direction: str = "backward",
        inclusive: bool | None = None,
    ) -> Any:
        """查询任务历史轮次。"""
        params: dict[str, Any] = {
            "id": task_id,
            "limit": limit,
            "direction": direction,
        }
        if cursor is not None:
            params["cursor"] = cursor
        if inclusive is not None:
            params["inclusive"] = inclusive
        return self._request("GET", "/api/v1/users/tasks/rounds", params=params)

    def get_task_user_inputs(
        self,
        task_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> Any:
        """查询任务用户输入列表。"""
        params: dict[str, Any] = {"id": task_id, "limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        return self._request("GET", "/api/v1/users/tasks/user-inputs", params=params)

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

    # ---------- OhMyAgent API Key ----------

    def create_api_key(self) -> APIKeyInfo:
        """创建 OhMyAgent API Key。

        注意：明文 api_key 仅在本次响应中返回，调用方应立即安全保存。
        该 Key 用于 OhMyAgent 代理（LLM 请求的 model 字段传模型配置 ID），
        不是 REST API 的会话凭证。
        """
        data = self._request("POST", "/api/v1/users/ohmyagent/api-keys", json={})
        return APIKeyInfo.from_dict(data)

    def delete_api_key(self, key_id: str) -> Any:
        """按 Key ID 删除当前用户的 OhMyAgent API Key。"""
        return self._request("DELETE", f"/api/v1/users/ohmyagent/api-keys/{key_id}")

    # ---------- 内部请求 ----------

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth_required: bool = True,
    ) -> Any:
        try:
            resp = self._client.request(method, path, json=json, params=params)
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
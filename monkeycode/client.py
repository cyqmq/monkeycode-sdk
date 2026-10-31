"""MonkeyCode 云平台 REST API 客户端。

基于 httpx，登录后自动携带会话 Cookie（monkeycode_ai_session）。
支持密码登录（MD5 + 可选验证码）、枚举环境、创建任务、轮询结果。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

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
    TaskStreamChunk,
    VMResource,
)
from monkeycode.links import check_url_status, collect_preview_links
from monkeycode.pow import solve
from monkeycode.stream import (
    ControlStream,
    JoinTerminalStream,
    TaskStream,
    TerminalStream,
    redact_sensitive,
)

DEFAULT_BASE_URL = "https://monkeycode-ai.com"
SESSION_COOKIE = "monkeycode_ai_session"


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


_RETRYABLE_METHODS = {"GET", "HEAD", "OPTIONS"}
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0

_FRIENDLY_ERRORS: dict[int, str] = {
    10606: "邮箱或密码错误",
    10205: "云端宿主不可调度，请到控制台检查云端环境",
}


def _friendly_error(code: int | str | None, message: str) -> str:
    """将已知业务错误码替换为更友好的提示。"""
    try:
        hint = _FRIENDLY_ERRORS.get(int(code))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return message
    if hint:
        return f"{message}（提示：{hint}）"
    return message


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
        session_path: str | None = None,
        auto_relogin: bool = True,
    ) -> None:
        self.email = email
        self._password = password or ""
        self._password_md5_mode = password_md5
        self.base_url = base_url.rstrip("/")
        self._session_path = session_path
        self._auto_relogin = auto_relogin
        self._relogging = False
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=True,
        )
        self._logged_in = False
        self._load_session()

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
        self._save_session()
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

    # ---------- 用户状态 / 退出登录 ----------

    def get_user_status(self) -> Any:
        """获取当前登录用户身份/状态（whoami 底层接口）。"""
        return self._request("GET", "/api/v1/users/status")

    def whoami(self) -> Any:
        """获取当前登录用户信息（get_user_status 别名）。"""
        return self.get_user_status()

    def is_logged_in(self) -> bool:
        """是否已有登录态（含从 session_path 加载的持久化会话）。"""
        return self._logged_in

    def logout(self) -> Any:
        """退出当前用户会话（清除云端登录态并删除本地会话文件）。"""
        result = self._request("POST", "/api/v1/users/logout")
        self._logged_in = False
        self._clear_session()
        return result

    def team_logout(self) -> Any:
        """退出团队管理员会话（清除云端登录态并删除本地会话文件）。"""
        result = self._request("POST", "/api/v1/teams/users/logout")
        self._logged_in = False
        self._clear_session()
        return result

    # ---------- 会话持久化 ----------

    def _save_session(self) -> None:
        """将当前会话 Cookie 持久化到 session_path（可选）。"""
        if not self._session_path:
            return
        try:
            cookies = {
                name: value for name, value in self._client.cookies.items()
            }
            path = Path(self._session_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cookies), encoding="utf-8")
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except OSError:
            pass

    def _load_session(self) -> None:
        """从 session_path 加载持久化 Cookie（可选）。"""
        if not self._session_path:
            return
        try:
            path = Path(self._session_path)
            if not path.exists():
                return
            cookies = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for name, value in cookies.items():
            self._client.cookies.set(name, value)
        if cookies:
            self._logged_in = True

    def _clear_session(self) -> None:
        """删除本地会话文件（退出登录时调用）。"""
        if not self._session_path:
            return
        try:
            Path(self._session_path).unlink(missing_ok=True)
        except OSError:
            pass

    def team_list_conversations(self) -> Any:
        """获取团队 agent 会话列表（管理端）。"""
        return self._request("GET", "/api/v1/teams/conversations")

    # ---------- 服务器配置 / 团队登录 ----------

    def get_server_config(self) -> dict[str, Any]:
        """获取服务器公开配置（无需登录）。

        返回 data 通常包含 edition / region / captcha_enabled 等字段，
        自托管部署可通过该接口确认是否启用验证码。
        """
        return self._request("GET", "/api/v1/server/config", auth_required=False)

    def team_login(
        self,
        email: str | None = None,
        password: str | None = None,
        captcha_token: str | None = None,
    ) -> dict[str, Any]:
        """团队管理员登录。

        使用 POST /api/v1/teams/users/login，成功后保存团队会话 Cookie
        monkeycode_ai_team_session。邮箱/密码缺省时使用构造客户端时的凭证。
        与个人登录一样，云平台强制 PoW 验证码时自动求解。
        """
        mail = email or self.email
        pwd = password or self._password
        if not mail or not pwd:
            raise AuthenticationError("缺少邮箱或密码，请在构造客户端时传入。")
        try:
            return self._team_login_request(mail, pwd, captcha_token)
        except CaptchaRequiredError:
            if captcha_token:
                raise
            token = self._solve_captcha()
            return self._team_login_request(mail, pwd, token)

    def _team_login_request(
        self, email: str, password: str, captcha_token: str | None
    ) -> dict[str, Any]:
        """发送团队登录请求。"""
        pwd = _md5(password) if self._password_md5_mode else password
        body: dict[str, Any] = {
            "email": email,
            "password": pwd,
        }
        if captcha_token:
            body["captcha_token"] = captcha_token
        try:
            return self._request("POST", "/api/v1/teams/users/login", json=body)
        except AuthenticationError as exc:
            if exc.code == 403 and not captcha_token:
                raise CaptchaRequiredError(
                    "团队登录需要验证码。",
                    code=403,
                ) from exc
            raise

    # ---------- 枚举环境 ----------

    def list_hosts(self) -> list[dict[str, Any]]:
        """获取可用的云端宿主/环境列表（返回 data.hosts）。"""
        data = self._request("GET", "/api/v1/users/hosts")
        if isinstance(data, dict):
            return data.get("hosts") or []
        return data or []

    # ---------- 宿主机管理 ----------

    def create_host(self, **fields: Any) -> Any:
        """注册宿主机。

        字段以关键字参数传入（如 name、host_id、api_key、备注等），
        与平台前端注册表单保持一致。
        """
        return self._request("POST", "/api/v1/users/hosts", json=fields)

    def update_host(self, host_id: str, **fields: Any) -> Any:
        """更新宿主机配置。"""
        return self._request(
            "PUT", f"/api/v1/users/hosts/{host_id}", json=fields
        )

    def delete_host(self, host_id: str) -> Any:
        """删除宿主机。"""
        return self._request("DELETE", f"/api/v1/users/hosts/{host_id}")

    def get_host_install_command(self) -> Any:
        """获取宿主机安装命令（用于接入新宿主机）。"""
        return self._request("GET", "/api/v1/users/hosts/install-command")

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

    def list_available_models(self) -> Any:
        """获取可用模型列表（仅查询，不做 CRUD）。"""
        return self._request("GET", "/api/v1/users/models/available")

    # ---------- AI 大模型管理 ----------

    def create_model(self, **fields: Any) -> Any:
        """创建模型配置。

        字段以关键字参数传入（如 name、provider、api_key、base_url 等），
        与平台前端表单字段保持一致。
        """
        return self._request("POST", "/api/v1/users/models", json=fields)

    def update_model(self, model_id: str, **fields: Any) -> Any:
        """更新模型配置（如 API Key、备注、供应商等）。"""
        return self._request(
            "PUT", f"/api/v1/users/models/{model_id}", json=fields
        )

    def delete_model(self, model_id: str) -> Any:
        """删除模型配置。"""
        return self._request("DELETE", f"/api/v1/users/models/{model_id}")

    def list_model_providers(
        self,
        provider: str,
        base_url: str,
        api_key: str,
        api_header: str | None = None,
    ) -> Any:
        """列出模型供应商的模型列表。

        provider 取值：SiliconFlow / OpenAI / Ollama / DeepSeek /
        Moonshot / AzureOpenAI / BaiZhiCloud / Hunyuan / BaiLian /
        Volcengine / Gemini / Other。
        """
        params: dict[str, Any] = {
            "provider": provider,
            "base_url": base_url,
            "api_key": api_key,
        }
        if api_header:
            params["api_header"] = api_header
        return self._request(
            "GET", "/api/v1/users/models/providers", params=params
        )

    def model_health_check(self, model_ids: list[str]) -> Any:
        """批量执行模型健康检查。

        model_ids 为模型 ID 列表，返回各模型连通性/鉴权结果。
        """
        return self._request(
            "POST",
            "/api/v1/users/models/health-check",
            json={"model_ids": model_ids},
        )

    def get_model_health_check(self, model_id: str) -> Any:
        """获取单个模型健康检查结果。"""
        return self._request(
            "GET", f"/api/v1/users/models/{model_id}/health-check"
        )

    def list_projects(
        self, cursor: str | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """获取项目（仓库）列表，支持分页。"""
        params: dict[str, Any] = {}
        if cursor:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit
        data = self._request("GET", "/api/v1/users/projects", params=params)
        if isinstance(data, dict):
            return data.get("projects") or []
        return data or []

    # ---------- 分页 helper ----------

    def paginate(
        self,
        fetcher,
        extract=None,
        page_size: int = 20,
        max_pages: int = 100,
    ):
        """通用分页迭代器。

        fetcher(page, size) 返回一页原始数据；
        extract(raw) 提取当前页条目列表（默认 raw 本身是列表）。
        当某页条目数小于 page_size 时结束。
        """
        extract = extract or (lambda raw: raw if isinstance(raw, list) else [])
        for page in range(1, max_pages + 1):
            raw = fetcher(page, page_size)
            items = extract(raw) or []
            for item in items:
                yield item
            if len(items) < page_size:
                break

    def iter_tasks(
        self,
        page_size: int = 20,
        max_pages: int = 100,
        **filters: Any,
    ):
        """分页迭代任务列表。

        额外筛选参数透传给 list_tasks（status/project_id 等）。
        """
        return self.paginate(
            lambda page, size: self.list_tasks(
                page=page, size=size, **filters
            ),
            extract=lambda raw: raw.get("tasks")
            if isinstance(raw, dict)
            else (raw or []),
            page_size=page_size,
            max_pages=max_pages,
        )

    def iter_projects(
        self,
        page_size: int = 20,
        max_pages: int = 100,
        **filters: Any,
    ):
        """分页迭代项目列表。

        额外筛选参数透传给 list_projects。
        """
        return self.paginate(
            lambda page, size: self.list_projects(
                limit=size, **filters
            ),
            extract=lambda raw: raw if isinstance(raw, list) else (raw or []),
            page_size=page_size,
            max_pages=max_pages,
        )

    def create_project(
        self,
        name: str,
        repo_url: str,
        platform: str = "github",
        git_identity_id: str | None = None,
        image_id: str | None = None,
        description: str | None = None,
        env_variables: dict[str, Any] | None = None,
    ) -> Any:
        """创建项目（仓库关联）。"""
        body: dict[str, Any] = {
            "name": name,
            "repo_url": repo_url,
            "platform": platform,
        }
        if git_identity_id:
            body["git_identity_id"] = git_identity_id
        if image_id:
            body["image_id"] = image_id
        if description:
            body["description"] = description
        if env_variables:
            body["env_variables"] = env_variables
        return self._request("POST", "/api/v1/users/projects", json=body)

    def get_project_tree(
        self,
        project_id: str,
        path: str = "",
        ref: str | None = None,
        recursive: bool | None = None,
    ) -> Any:
        """获取项目仓库树。"""
        params: dict[str, Any] = {"path": path}
        if ref:
            params["ref"] = ref
        if recursive is not None:
            params["recursive"] = recursive
        return self._request(
            "GET", f"/api/v1/users/projects/{project_id}/tree", params=params
        )

    def get_project_file(
        self, project_id: str, path: str, ref: str | None = None
    ) -> Any:
        """获取项目文件内容。"""
        params: dict[str, Any] = {"path": path}
        if ref:
            params["ref"] = ref
        return self._request(
            "GET", f"/api/v1/users/projects/{project_id}/tree/blob", params=params
        )

    def list_project_issues(
        self, project_id: str, cursor: str | None = None, limit: int | None = None
    ) -> Any:
        """获取项目 Issue 列表。"""
        params: dict[str, Any] = {}
        if cursor:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit
        return self._request(
            "GET", f"/api/v1/users/projects/{project_id}/issues", params=params
        )

    def create_project_issue(
        self,
        project_id: str,
        title: str,
        assignee_id: str | None = None,
        priority: int | None = None,
        requirement_document: str | None = None,
    ) -> Any:
        """创建项目 Issue。"""
        body: dict[str, Any] = {"title": title}
        if assignee_id:
            body["assignee_id"] = assignee_id
        if priority is not None:
            body["priority"] = priority
        if requirement_document:
            body["requirement_document"] = requirement_document
        return self._request(
            "POST", f"/api/v1/users/projects/{project_id}/issues", json=body
        )

    def update_project_issue(
        self,
        project_id: str,
        issue_id: str,
        title: str | None = None,
        assignee_id: str | None = None,
        priority: int | None = None,
        status: str | None = None,
        requirement_document: str | None = None,
        design_document: str | None = None,
    ) -> Any:
        """更新项目 Issue。"""
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if assignee_id:
            body["assignee_id"] = assignee_id
        if priority is not None:
            body["priority"] = priority
        if status:
            body["status"] = status
        if requirement_document:
            body["requirement_document"] = requirement_document
        if design_document:
            body["design_document"] = design_document
        return self._request(
            "PUT",
            f"/api/v1/users/projects/{project_id}/issues/{issue_id}",
            json=body,
        )

    def delete_project_issue(self, project_id: str, issue_id: str) -> Any:
        """删除项目 Issue。"""
        return self._request(
            "DELETE", f"/api/v1/users/projects/{project_id}/issues/{issue_id}"
        )

    def list_issue_comments(
        self,
        project_id: str,
        issue_id: str,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> Any:
        """获取 Issue 评论列表。"""
        params: dict[str, Any] = {}
        if cursor:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit
        return self._request(
            "GET",
            f"/api/v1/users/projects/{project_id}/issues/{issue_id}/comments",
            params=params,
        )

    def add_issue_comment(
        self,
        project_id: str,
        issue_id: str,
        comment: str,
        parent_id: str | None = None,
    ) -> Any:
        """创建 Issue 评论。"""
        body: dict[str, Any] = {"comment": comment}
        if parent_id:
            body["parent_id"] = parent_id
        return self._request(
            "POST",
            f"/api/v1/users/projects/{project_id}/issues/{issue_id}/comments",
            json=body,
        )

    # ---------- 插件 / 技能 ----------

    def list_plugins(self) -> Any:
        """获取可用插件列表。"""
        return self._request("GET", "/api/v1/plugins")

    def list_skills(self) -> Any:
        """获取可用技能列表（配合 create_task 的 skill_ids）。"""
        return self._request("GET", "/api/v1/skills")

    # ---------- 钱包 / 签到 ----------

    def get_wallet(self) -> Any:
        """查询钱包（积分余额）。"""
        return self._request("GET", "/api/v1/users/wallet")

    def get_wallet_transactions(self) -> Any:
        """查询钱包交易记录。"""
        return self._request("GET", "/api/v1/users/wallet/transaction")

    def checkin(self) -> Any:
        """每日签到（自动求解 PoW 验证码）。"""
        token = self._solve_captcha()
        return self._request(
            "POST", "/api/v1/users/wallet/checkin", json={"captcha_token": token}
        )

    def get_subscription(self) -> Any:
        """查询会员订阅信息。"""
        return self._request("GET", "/api/v1/users/subscription")

    # ---------- Git 身份 / Git Bots ----------

    def list_git_identities(self) -> Any:
        """获取 Git 身份列表（access_token 已打码为 ***）。"""
        data = self._request("GET", "/api/v1/users/git-identities")
        return redact_sensitive(data)

    def list_git_branches(
        self,
        identity_id: str,
        repo_full_name: str,
        page: int = 1,
        per_page: int = 50,
    ) -> Any:
        """获取指定仓库的分支列表。

        repo_full_name 形如 "owner/repo"，会自动做 URL 编码。
        """
        escaped = quote(repo_full_name, safe="")
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        return self._request(
            "GET",
            f"/api/v1/users/git-identities/{identity_id}/{escaped}/branches",
            params=params,
        )

    def add_git_identity(
        self,
        access_token: str,
        base_url: str,
        email: str,
        platform: str,
        username: str,
        remark: str | None = None,
        organization_id: str | None = None,
    ) -> Any:
        """添加 Git 身份。"""
        body: dict[str, Any] = {
            "access_token": access_token,
            "base_url": base_url,
            "email": email,
            "platform": platform,
            "username": username,
        }
        if remark:
            body["remark"] = remark
        if organization_id:
            body["organization_id"] = organization_id
        return self._request("POST", "/api/v1/users/git-identities", json=body)

    def update_git_identity(
        self, identity_id: str, **fields: Any
    ) -> Any:
        """更新 Git 身份（token/备注/组织等）。

        字段以关键字参数传入，如 access_token、remark、organization_id。
        """
        return self._request(
            "PUT", f"/api/v1/users/git-identities/{identity_id}", json=fields
        )

    def delete_git_identity(self, identity_id: str) -> Any:
        """删除 Git 身份。"""
        return self._request(
            "DELETE", f"/api/v1/users/git-identities/{identity_id}"
        )

    def list_git_bots(self) -> Any:
        """获取 Git Bot 列表。"""
        return self._request("GET", "/api/v1/users/git-bots")

    def create_git_bot(
        self,
        host_id: str,
        platform: str,
        token: str,
        name: str | None = None,
    ) -> Any:
        """创建 Git Bot。"""
        body: dict[str, Any] = {
            "host_id": host_id,
            "platform": platform,
            "token": token,
        }
        if name:
            body["name"] = name
        return self._request("POST", "/api/v1/users/git-bots", json=body)

    def list_git_bot_tasks(
        self, git_bot_id: str, page: int | None = None, size: int | None = None
    ) -> Any:
        """获取 Git Bot 任务列表。"""
        params: dict[str, Any] = {"id": git_bot_id}
        if page is not None:
            params["page"] = page
        if size is not None:
            params["size"] = size
        return self._request("GET", "/api/v1/users/git-bots/tasks", params=params)

    # ---------- 文件管理 ----------

    def list_folders(self, vm_id: str, path: str = "") -> Any:
        """列出虚拟机目录。"""
        params: dict[str, Any] = {"id": vm_id, "path": path}
        return self._request("GET", "/api/v1/users/folders", params=params)

    def upload_file(
        self,
        vm_id: str,
        path: str,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        filename: str | None = None,
    ) -> Any:
        """上传文件到 VM 的绝对路径。

        file_path 和 (file_bytes, filename) 二选一。
        """
        if file_path is None and file_bytes is None:
            raise ValueError("请提供 file_path 或 file_bytes。")
        params: dict[str, Any] = {"id": vm_id, "path": path}
        if file_path is not None:
            import os

            fname = filename or os.path.basename(file_path)
            with open(file_path, "rb") as f:
                files: dict[str, Any] = {"file": (fname, f)}
                return self._request(
                    "POST",
                    "/api/v1/users/files/upload",
                    params=params,
                    files=files,
                )
        files = {"file": (filename or "file", file_bytes)}
        return self._request(
            "POST", "/api/v1/users/files/upload", params=params, files=files
        )

    def download_file(self, vm_id: str, path: str, filename: str) -> bytes:
        """下载 VM 中的文件，返回字节内容。"""
        params: dict[str, Any] = {"id": vm_id, "path": path, "filename": filename}
        resp = self._client.get("/api/v1/users/files/download", params=params)
        if resp.status_code != 200:
            raise APIError(f"下载失败（HTTP {resp.status_code}）：{resp.text[:200]}")
        # 后端可能以 HTTP 200 返回业务错误 JSON（如开发环境已被回收），
        # 此时不能把错误 JSON 当文件内容返回。
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = resp.json()
            except ValueError:
                body = None
            if isinstance(body, dict) and body.get("code") not in (None, 0):
                code = body.get("code")
                message = body.get("message") or body.get("msg") or "未知错误"
                message = _friendly_error(code, message)
                raise APIError(
                    f"{message}（code={code}）", code=code, raw=body
                )
        return resp.content

    def move_file(self, vm_id: str, source: str, target: str) -> Any:
        """移动/重命名 VM 中的文件或目录。"""
        body: dict[str, Any] = {"id": vm_id, "source": source, "target": target}
        return self._request("PUT", "/api/v1/users/files/move", json=body)

    def copy_file(self, vm_id: str, source: str, target: str) -> Any:
        """复制 VM 中的文件或目录。"""
        body: dict[str, Any] = {"id": vm_id, "source": source, "target": target}
        return self._request("POST", "/api/v1/users/files/copy", json=body)

    def delete_file(self, vm_id: str, path: str) -> Any:
        """删除 VM 中的文件或目录。"""
        params: dict[str, Any] = {"id": vm_id, "path": path}
        return self._request("DELETE", "/api/v1/users/files", params=params)

    # ---------- VM 管理 ----------

    def get_vm(self, vm_id: str) -> Any:
        """获取虚拟机详情。"""
        return self._request("GET", f"/api/v1/users/hosts/vms/{vm_id}")

    def delete_vm(self, host_id: str, vm_id: str) -> Any:
        """删除虚拟机。"""
        return self._request(
            "DELETE", f"/api/v1/users/hosts/{host_id}/vms/{vm_id}"
        )

    def create_vm(self, host_id: str, **fields: Any) -> Any:
        """创建虚拟机/开发环境。

        字段以关键字参数传入（如 image_id、resource、名称等），
        与平台前端创建表单保持一致。
        """
        return self._request(
            "POST", f"/api/v1/users/hosts/{host_id}/vms", json=fields
        )

    def update_vm(self, host_id: str, vm_id: str, **fields: Any) -> Any:
        """更新虚拟机（如续期、调整配置）。"""
        return self._request(
            "PUT",
            f"/api/v1/users/hosts/{host_id}/vms/{vm_id}",
            json=fields,
        )

    # ---------- 端口转发 ----------

    def list_port_forwards(self, host_id: str, vm_id: str) -> Any:
        """列出虚拟机的端口转发规则。"""
        return self._request(
            "GET", f"/api/v1/users/hosts/{host_id}/vms/{vm_id}/ports"
        )

    def add_port_forward(
        self, host_id: str, vm_id: str, **fields: Any
    ) -> Any:
        """添加端口转发规则。

        字段以关键字参数传入（如 port、target 等），与平台前端一致。
        """
        return self._request(
            "POST",
            f"/api/v1/users/hosts/{host_id}/vms/{vm_id}/ports",
            json=fields,
        )

    def delete_port_forward(
        self, host_id: str, vm_id: str, port: int | str
    ) -> Any:
        """删除端口转发规则。"""
        return self._request(
            "DELETE",
            f"/api/v1/users/hosts/{host_id}/vms/{vm_id}/ports/{port}",
        )

    # ---------- 附件上传（任务/消息附件） ----------

    def presign_upload(self, filename: str) -> dict[str, Any]:
        """获取附件预签名上传信息。

        返回 data 通常包含 upload_url / access_url 等字段。
        """
        return self._request(
            "POST",
            "/api/v1/uploader/presign",
            json={"filename": filename},
        )

    def upload_attachment(
        self,
        filename: str,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        """上传附件并返回 access_url。

        流程：presign 获取 upload_url/access_url -> 用 PUT 上传文件内容。
        上传成功后可用返回的 access_url 作为任务/消息的附件 url。
        """
        if file_path is None and file_bytes is None:
            raise ValueError("请提供 file_path 或 file_bytes。")
        presigned = self.presign_upload(filename)
        upload_url = presigned.get("upload_url")
        if not upload_url:
            raise APIError(f"presign 响应缺少 upload_url：{presigned}")
        if file_path is not None:
            with open(file_path, "rb") as f:
                content = f.read()
        else:
            content = file_bytes
        resp = self._client.put(upload_url, content=content)
        if resp.status_code not in (200, 201, 204):
            raise APIError(
                f"附件上传失败（HTTP {resp.status_code}）：{resp.text[:200]}"
            )
        return presigned

    def upload_object(
        self,
        filename: str,
        file_bytes: bytes,
        usage: str = "attachment",
    ) -> Any:
        """直接 multipart 上传文件对象（POST /api/v1/uploader）。

        与 presign 路径（upload_attachment）互补；usage 按平台约定
        传入（如 attachment / avatar 等）。
        """
        return self._request(
            "POST",
            "/api/v1/uploader",
            files={"file": (filename, file_bytes)},
            params={"usage": usage},
        )

    # ---------- 扩展 / 管理功能（覆盖完整 API，按需使用） ----------

    def create_image(self, image_name: str, is_default: bool | None = None, remark: str | None = None) -> Any:
        """创建镜像。"""
        body: dict[str, Any] = {"image_name": image_name}
        if is_default is not None:
            body["is_default"] = is_default
        if remark:
            body["remark"] = remark
        return self._request("POST", "/api/v1/users/images", json=body)

    def update_image(self, image_id: str, image_name: str | None = None, is_default: bool | None = None, remark: str | None = None) -> Any:
        """更新镜像。"""
        body: dict[str, Any] = {}
        if image_name is not None:
            body["image_name"] = image_name
        if is_default is not None:
            body["is_default"] = is_default
        if remark:
            body["remark"] = remark
        return self._request("PUT", f"/api/v1/users/images/{image_id}", json=body)

    def delete_image(self, image_id: str) -> Any:
        """删除镜像。"""
        return self._request("DELETE", f"/api/v1/users/images/{image_id}")

    def create_subscription(self) -> Any:
        """开通会员订阅。"""
        return self._request("POST", "/api/v1/users/subscription", json={})

    def set_auto_renew(self, enabled: bool) -> Any:
        """设置订阅自动续费。"""
        return self._request("PUT", "/api/v1/users/subscription/auto-renew", json={"enabled": enabled})

    def set_credit_consumption(self, enabled: bool) -> Any:
        """设置订阅积分消费。"""
        return self._request("PUT", "/api/v1/users/subscription/credit-consumption", json={"enabled": enabled})

    def list_invitations(self) -> Any:
        """获取邀请列表。"""
        return self._request("GET", "/api/v1/users/invitations")

    def list_mcp_upstreams(self) -> Any:
        """获取 MCP 上游列表。"""
        return self._request("GET", "/api/v1/users/mcp/upstreams")

    def create_mcp_upstream(self, name: str, url: str, headers: dict[str, Any] | None = None) -> Any:
        """创建 MCP 上游。"""
        body: dict[str, Any] = {"name": name, "url": url}
        if headers:
            body["headers"] = headers
        return self._request("POST", "/api/v1/users/mcp/upstreams", json=body)

    def update_mcp_upstream(self, upstream_id: str, **fields: Any) -> Any:
        """更新 MCP 上游。"""
        return self._request("PUT", f"/api/v1/users/mcp/upstreams/{upstream_id}", json=fields)

    def delete_mcp_upstream(self, upstream_id: str) -> Any:
        """删除 MCP 上游。"""
        return self._request("DELETE", f"/api/v1/users/mcp/upstreams/{upstream_id}")

    def sync_mcp_upstream(self, upstream_id: str) -> Any:
        """同步 MCP 上游。"""
        return self._request("POST", f"/api/v1/users/mcp/upstreams/{upstream_id}/sync", json={})

    def set_mcp_tool(self, tool_id: str, enabled: bool) -> Any:
        """启用/关闭 MCP 工具。"""
        return self._request("PUT", f"/api/v1/users/mcp/tools/{tool_id}", json={"enabled": enabled})

    def list_notify_channels(self) -> Any:
        """获取通知渠道列表。"""
        return self._request("GET", "/api/v1/users/notify/channels")

    def create_notify_channel(self, name: str, kind: str, webhook_url: str, event_types: list[str], headers: dict[str, Any] | None = None) -> Any:
        """创建通知渠道。"""
        body: dict[str, Any] = {
            "name": name, "kind": kind, "webhook_url": webhook_url, "event_types": event_types,
        }
        if headers:
            body["headers"] = headers
        return self._request("POST", "/api/v1/users/notify/channels", json=body)

    def update_notify_channel(self, channel_id: str, **fields: Any) -> Any:
        """更新通知渠道。"""
        return self._request("PUT", f"/api/v1/users/notify/channels/{channel_id}", json=fields)

    def delete_notify_channel(self, channel_id: str) -> Any:
        """删除通知渠道。"""
        return self._request("DELETE", f"/api/v1/users/notify/channels/{channel_id}")

    def test_notify_channel(self, channel_id: str) -> Any:
        """测试通知渠道。"""
        return self._request("POST", f"/api/v1/users/notify/channels/{channel_id}/test", json={})

    def list_notify_event_types(self) -> Any:
        """获取通知事件类型。"""
        return self._request("GET", "/api/v1/users/notify/event-types")

    def update_user_profile(self, name: str | None = None, avatar_url: str | None = None) -> Any:
        """更新用户昵称/头像。"""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if avatar_url is not None:
            body["avatar_url"] = avatar_url
        return self._request("PUT", "/api/v1/users", json=body)

    def delete_account(self) -> Any:
        """注销账号。"""
        return self._request("DELETE", "/api/v1/users/account")

    def change_password(self, new_password: str, current_password: str | None = None) -> Any:
        """修改密码。"""
        body: dict[str, Any] = {"new_password": new_password}
        if current_password:
            body["current_password"] = current_password
        return self._request("PUT", "/api/v1/users/passwords/change", json=body)

    def request_password_reset(self, email: str) -> Any:
        """发送密码重置邮件。"""
        return self._request("PUT", "/api/v1/users/passwords/reset-request", json={"email": email})

    def reset_password(self, token: str, new_password: str) -> Any:
        """重置密码。"""
        return self._request("PUT", "/api/v1/users/passwords/reset", json={"token": token, "new_password": new_password})

    def get_reset_password_account(self, token: str) -> Any:
        """用重置链接中的 token 查询账户信息（网页重置用）。"""
        return self._request(
            "GET", f"/api/v1/users/passwords/accounts/{token}"
        )

    def update_git_bot(self, **fields: Any) -> Any:
        """更新 Git Bot。"""
        return self._request("PUT", "/api/v1/users/git-bots", json=fields)

    def delete_git_bot(self, git_bot_id: str) -> Any:
        """删除 Git Bot。"""
        return self._request("DELETE", f"/api/v1/users/git-bots/{git_bot_id}")

    def share_git_bot(self, git_bot_id: str, user_ids: list[str]) -> Any:
        """分享 Git Bot。"""
        return self._request("POST", "/api/v1/users/git-bots/share", json={"id": git_bot_id, "user_ids": user_ids})

    def list_members(self) -> Any:
        """获取团队成员列表。"""
        return self._request("GET", "/api/v1/users/members")

    def get_public_stats(self) -> Any:
        """获取公开统计。"""
        return self._request("GET", "/api/v1/public/stats")

    def bind_email_request(self, email: str) -> Any:
        """请求绑定邮箱。"""
        return self._request("PUT", "/api/v1/users/email/bind-request", json={"email": email})

    def bind_wechat_qrcode(self) -> Any:
        """创建微信公众号绑定二维码。"""
        return self._request("POST", "/api/v1/users/wechat-mp/bind-qrcode", json={})

    def unbind_wechat(self) -> Any:
        """解绑微信公众号。"""
        return self._request("DELETE", "/api/v1/users/wechat-mp/bind")

    def list_playground_posts(self) -> Any:
        """获取社区帖子列表。"""
        return self._raise_on_not_found(
            self._request("GET", "/api/v1/playground-posts")
        )

    def create_playground_post(self, content: str) -> Any:
        """发布普通社区帖子。"""
        return self._request("POST", "/api/v1/users/playground-normal-posts", json={"content": content})

    def create_playground_task_post(self, task_id: str, content: str) -> Any:
        """发布任务帖。"""
        return self._request("POST", f"/api/v1/users/playground-task-posts/{task_id}", json={"content": content})

    def get_license_status(self) -> Any:
        """获取 License 状态。"""
        return self._raise_on_not_found(
            self._request("GET", "/api/v1/license/status")
        )

    def get_license_machine_code(self) -> Any:
        """获取机器码。"""
        return self._request("GET", "/api/v1/license/machine-code")

    def import_license(self, license_key: str) -> Any:
        """导入 License。"""
        return self._request("POST", "/api/v1/license/import", json={"license": license_key})

    def get_cnb_authorize_url(self) -> Any:
        """获取 CNB 授权 URL。"""
        return self._request("GET", "/api/v1/cnb/authorize_url")

    def get_gitea_authorize_url(self) -> Any:
        """获取 Gitea 授权 URL。"""
        return self._request("GET", "/api/v1/gitea/authorize_url")

    def get_gitea_sites(self) -> Any:
        """获取 Gitea 站点列表。"""
        return self._request("GET", "/api/v1/gitea/sites")

    def get_gitee_authorize_url(self) -> Any:
        """获取 Gitee 授权 URL。"""
        return self._request("GET", "/api/v1/gitee/authorize_url")

    def get_gitlab_authorize_url(self) -> Any:
        """获取 GitLab 授权 URL。"""
        return self._request("GET", "/api/v1/gitlab/authorize_url")

    def get_gitlab_sites(self) -> Any:
        """获取 GitLab 站点列表。"""
        return self._request("GET", "/api/v1/gitlab/sites")

    def build_oauth_login_url(self, provider: str, redirect_url: str | None = None) -> str:
        """构造 OAuth 登录跳转 URL（供浏览器使用）。"""
        base = f"{self.base_url}/api/v1/users/oauth/{provider}/login"
        if redirect_url:
            from urllib.parse import urlencode
            return f"{base}?{urlencode({'redirect_url': redirect_url})}"
        return base

    def build_oidc_login_url(self, team_id: str | None = None) -> str:
        """构造企业 OIDC 登录跳转 URL（供浏览器使用）。"""
        base = f"{self.base_url}/api/v1/users/oidc/login"
        if team_id:
            from urllib.parse import urlencode
            return f"{base}?{urlencode({'team_id': team_id})}"
        return base

    def speech_to_text(self, **fields: Any) -> Any:
        """语音转文字（提交音频）。"""
        return self._request("POST", "/api/v1/users/tasks/speech-to-text", json=fields)

    # ---------- 团队管理（管理员控制面） ----------

    def team_admin_initialize(self) -> Any:
        """初始化团队。"""
        return self._request("POST", "/api/v1/teams/admin", json={})

    def team_list_groups(self) -> Any:
        """团队分组列表。"""
        return self._request("GET", "/api/v1/teams/groups")

    def team_create_group(self, name: str) -> Any:
        """创建团队分组。"""
        return self._request("POST", "/api/v1/teams/groups", json={"name": name})

    def team_delete_group(self, group_id: str) -> Any:
        """删除团队分组。"""
        return self._request("DELETE", f"/api/v1/teams/groups/{group_id}")

    def team_list_group_users(self, group_id: str) -> Any:
        """获取分组内用户。"""
        return self._request("GET", f"/api/v1/teams/groups/{group_id}/users")

    def team_set_group_users(self, group_id: str, user_ids: list[str]) -> Any:
        """调整分组内用户。"""
        return self._request("PUT", f"/api/v1/teams/groups/{group_id}/users", json={"user_ids": user_ids})

    def team_list_users(self) -> Any:
        """团队成员列表。"""
        return self._request("GET", "/api/v1/teams/users")

    def team_add_user(self, **fields: Any) -> Any:
        """添加团队成员。"""
        return self._request("POST", "/api/v1/teams/users", json=fields)

    def team_delete_user(self, user_id: str) -> Any:
        """删除团队成员。"""
        return self._request("DELETE", f"/api/v1/teams/users/{user_id}")

    def team_list_hosts(self) -> Any:
        """团队宿主列表。"""
        return self._request("GET", "/api/v1/teams/hosts")

    def team_list_images(self) -> Any:
        """团队镜像列表。"""
        return self._request("GET", "/api/v1/teams/images")

    def team_list_models(self) -> Any:
        """团队模型列表。"""
        return self._request("GET", "/api/v1/teams/models")

    def team_list_skills(self) -> Any:
        """团队技能列表。"""
        return self._request("GET", "/api/v1/teams/skills")

    def team_list_projects(self) -> Any:
        """团队项目列表。"""
        return self._request("GET", "/api/v1/teams/projects")

    def team_list_tasks(self) -> Any:
        """团队任务列表。"""
        return self._request("GET", "/api/v1/teams/tasks")

    def team_get_oidc(self) -> Any:
        """获取团队 OIDC 配置。"""
        return self._request("GET", "/api/v1/teams/oidc")

    def team_save_oidc(self, **fields: Any) -> Any:
        """保存团队 OIDC 配置。"""
        return self._request("PUT", "/api/v1/teams/oidc", json=fields)

    def team_test_oidc(self, **fields: Any) -> Any:
        """测试团队 OIDC 配置。"""
        return self._request("POST", "/api/v1/teams/oidc/test", json=fields)

    def team_list_mcp_upstreams(self) -> Any:
        """团队 MCP 上游列表。"""
        return self._request("GET", "/api/v1/teams/mcp/upstreams")

    def team_list_notify_channels(self) -> Any:
        """团队通知渠道列表。"""
        return self._request("GET", "/api/v1/teams/notify/channels")

    def team_list_oauth_sites(self) -> Any:
        """团队 OAuth 站点列表。"""
        return self._request("GET", "/api/v1/teams/oauth-sites")

    def team_list_extension_packages(self) -> Any:
        """团队扩展包列表。"""
        return self._request("GET", "/api/v1/teams/extension-packages")

    def team_get_vm_idle_policy(self) -> Any:
        """获取 VM 空闲策略。"""
        return self._request("GET", "/api/v1/teams/task-vm-idle-policy")

    def team_set_vm_idle_policy(self, **fields: Any) -> Any:
        """设置 VM 空闲策略。"""
        return self._request("PUT", "/api/v1/teams/task-vm-idle-policy", json=fields)

    def team_list_audits(self) -> Any:
        """获取团队审计日志。"""
        return self._request("GET", "/api/v1/teams/audits")

    def team_get_dashboard(self) -> Any:
        """获取团队 Dashboard。"""
        return self._request("GET", "/api/v1/teams/dashboard")

    # ---------- 团队用户（管理写操作） ----------

    def team_get_user_status(self) -> Any:
        """查询当前团队用户状态（团队会话）。"""
        return self._request("GET", "/api/v1/teams/users/status")

    def team_change_password(self, **fields: Any) -> Any:
        """团队用户修改密码。"""
        return self._request(
            "PUT", "/api/v1/teams/users/passwords/change", json=fields
        )

    def team_add_user_with_password(self, **fields: Any) -> Any:
        """创建团队成员并返回初始密码（仅响应返回一次）。"""
        return self._request(
            "POST", "/api/v1/teams/users/with-password", json=fields
        )

    def team_update_user(self, user_id: str, **fields: Any) -> Any:
        """更新团队成员信息。"""
        return self._request(
            "PUT", f"/api/v1/teams/users/{user_id}", json=fields
        )

    def team_reset_user_password(self, user_id: str) -> Any:
        """管理员重置成员密码（仅响应返回一次）。"""
        return self._request(
            "PUT", f"/api/v1/teams/users/{user_id}/passwords/reset"
        )

    # ---------- 团队分组（管理写操作） ----------

    def team_update_group(self, group_id: str, name: str) -> Any:
        """更新分组名称。"""
        return self._request(
            "PUT", f"/api/v1/teams/groups/{group_id}", json={"name": name}
        )

    # ---------- 团队宿主（管理写操作） ----------

    def team_get_host_install_command(self) -> Any:
        """获取团队宿主机安装命令。"""
        return self._request("GET", "/api/v1/teams/hosts/install-command")

    def team_update_host(self, host_id: str, **fields: Any) -> Any:
        """更新团队宿主机。"""
        return self._request(
            "PUT", f"/api/v1/teams/hosts/{host_id}", json=fields
        )

    def team_delete_host(self, host_id: str) -> Any:
        """删除团队宿主机。"""
        return self._request("DELETE", f"/api/v1/teams/hosts/{host_id}")

    # ---------- 团队镜像（管理写操作） ----------

    def team_create_image(self, **fields: Any) -> Any:
        """创建团队镜像。"""
        return self._request("POST", "/api/v1/teams/images", json=fields)

    def team_update_image(self, image_id: str, **fields: Any) -> Any:
        """更新团队镜像。"""
        return self._request(
            "PUT", f"/api/v1/teams/images/{image_id}", json=fields
        )

    def team_delete_image(self, image_id: str) -> Any:
        """删除团队镜像。"""
        return self._request("DELETE", f"/api/v1/teams/images/{image_id}")

    # ---------- 团队模型（管理写操作） ----------

    def team_create_model(self, **fields: Any) -> Any:
        """创建团队模型配置。"""
        return self._request("POST", "/api/v1/teams/models", json=fields)

    def team_update_model(self, model_id: str, **fields: Any) -> Any:
        """更新团队模型。"""
        return self._request(
            "PUT", f"/api/v1/teams/models/{model_id}", json=fields
        )

    def team_delete_model(self, model_id: str) -> Any:
        """删除团队模型。"""
        return self._request("DELETE", f"/api/v1/teams/models/{model_id}")

    def team_model_health_check(self, model_ids: list[str]) -> Any:
        """团队模型批量健康检查。"""
        return self._request(
            "POST",
            "/api/v1/teams/models/health-check",
            json={"model_ids": model_ids},
        )

    def team_get_model_health_check(self, model_id: str) -> Any:
        """单个团队模型健康检查。"""
        return self._request(
            "GET", f"/api/v1/teams/models/{model_id}/health-check"
        )

    # ---------- 团队技能（管理写操作） ----------

    def team_create_skill(self, **fields: Any) -> Any:
        """创建团队技能。"""
        return self._request("POST", "/api/v1/teams/skills", json=fields)

    def team_create_skill_package(self, **fields: Any) -> Any:
        """上传/创建团队技能包。"""
        return self._request(
            "POST", "/api/v1/teams/skills/package", json=fields
        )

    def team_update_skill(self, skill_id: str, **fields: Any) -> Any:
        """更新团队技能。"""
        return self._request(
            "PUT", f"/api/v1/teams/skills/{skill_id}", json=fields
        )

    def team_delete_skill(self, skill_id: str) -> Any:
        """删除团队技能。"""
        return self._request("DELETE", f"/api/v1/teams/skills/{skill_id}")

    # ---------- 团队 MCP（管理写操作） ----------

    def team_create_mcp_upstream(self, **fields: Any) -> Any:
        """创建团队 MCP 上游。"""
        return self._request(
            "POST", "/api/v1/teams/mcp/upstreams", json=fields
        )

    def team_update_mcp_upstream(
        self, upstream_id: str, **fields: Any
    ) -> Any:
        """更新团队 MCP 上游。"""
        return self._request(
            "PUT", f"/api/v1/teams/mcp/upstreams/{upstream_id}", json=fields
        )

    def team_delete_mcp_upstream(self, upstream_id: str) -> Any:
        """删除团队 MCP 上游。"""
        return self._request(
            "DELETE", f"/api/v1/teams/mcp/upstreams/{upstream_id}"
        )

    def team_sync_mcp_upstream(self, upstream_id: str) -> Any:
        """同步团队 MCP 上游。"""
        return self._request(
            "POST", f"/api/v1/teams/mcp/upstreams/{upstream_id}/sync"
        )

    # ---------- 团队通知（管理写操作） ----------

    def team_create_notify_channel(self, **fields: Any) -> Any:
        """创建团队通知渠道。"""
        return self._request(
            "POST", "/api/v1/teams/notify/channels", json=fields
        )

    def team_update_notify_channel(
        self, channel_id: str, **fields: Any
    ) -> Any:
        """更新团队通知渠道。"""
        return self._request(
            "PUT", f"/api/v1/teams/notify/channels/{channel_id}", json=fields
        )

    def team_delete_notify_channel(self, channel_id: str) -> Any:
        """删除团队通知渠道。"""
        return self._request(
            "DELETE", f"/api/v1/teams/notify/channels/{channel_id}"
        )

    def team_test_notify_channel(self, channel_id: str) -> Any:
        """测试团队通知渠道。"""
        return self._request(
            "POST", f"/api/v1/teams/notify/channels/{channel_id}/test"
        )

    def team_list_notify_event_types(self) -> Any:
        """团队通知事件类型列表。"""
        return self._request("GET", "/api/v1/teams/notify/event-types")

    # ---------- 团队 OAuth 站点（管理写操作） ----------

    def team_create_oauth_site(self, **fields: Any) -> Any:
        """创建团队 OAuth 站点配置。"""
        return self._request("POST", "/api/v1/teams/oauth-sites", json=fields)

    def team_update_oauth_site(self, site_id: str, **fields: Any) -> Any:
        """更新团队 OAuth 站点。"""
        return self._request(
            "PUT", f"/api/v1/teams/oauth-sites/{site_id}", json=fields
        )

    def team_delete_oauth_site(self, site_id: str) -> Any:
        """删除团队 OAuth 站点。"""
        return self._request("DELETE", f"/api/v1/teams/oauth-sites/{site_id}")

    # ---------- 团队扩展包（管理写操作） ----------

    def team_create_extension_package(self, **fields: Any) -> Any:
        """创建团队扩展包。"""
        return self._request(
            "POST", "/api/v1/teams/extension-packages", json=fields
        )

    # ---------- 任务 ----------

    def create_task(
        self,
        content: str,
        repo: RepoReq | None = None,
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
        attachments: list[dict] | None = None,
    ) -> Task:
        """创建任务。

        必填：content。repo 可空（不绑定 Git 仓库也能创建任务）；
        host_id 默认 public_host；image_id / model_id 留空时自动取列表第一个可用项；
        资源默认 2 核 / 8GB / 3 小时（桌面端默认档位）。
        attachments：附件列表（最多 10 个），每项 {url, filename}。
        """
        repo = repo or RepoReq(repo_url="")
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
        if attachments:
            body["attachments"] = attachments[:10]
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

    def delete_task(self, task_id: str) -> Any:
        """删除任务。"""
        return self._request("DELETE", f"/api/v1/users/tasks/{task_id}")

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

    # ---------- 预览链接 ----------

    def list_task_links(
        self, task_id: str, check_alive: bool = True, max_pages: int = 500
    ) -> list[dict[str, Any]]:
        """列出任务中 AI 拉起的预览链接，并检测存活状态。

        返回 [{url, count, status, http_code}]，按出现次数降序。
        status 取值：在线 / 异常 / 已关闭（check_alive=False 时为 None）。
        """
        counts = collect_preview_links(self.get_task_rounds, task_id, max_pages)
        result: list[dict[str, Any]] = []
        for url, count in sorted(counts.items(), key=lambda x: -x[1]):
            status: str | None = None
            http_code: int | None = None
            if check_alive:
                status, http_code = check_url_status(url)
            result.append(
                {
                    "url": url,
                    "count": count,
                    "status": status,
                    "http_code": http_code,
                }
            )
        return result

    # ---------- WebSocket 会话交互 ----------

    def open_task_stream(self, task_id: str, mode: str = "new") -> TaskStream:
        """打开任务实时流（WebSocket 上下文管理器）。

        mode="new"：等待用户输入（发送消息用）；
        mode="attach"：只拉取当前轮次历史 + 订阅实时流（旁观用）。
        """
        return TaskStream(self, task_id, mode=mode)

    async def send_task_message(
        self,
        task_id: str,
        content: str,
        attachments: list[dict] | None = None,
        read_timeout: float = 30.0,
    ) -> list[TaskStreamChunk]:
        """进入任务会话，发送用户消息，返回直到 task-started 的首批事件。

        需要在 asyncio 事件循环中调用（AstrBot 插件环境天然支持）。
        """
        stream = TaskStream(self, task_id, mode="new")
        await stream.connect()
        try:
            await stream.send_user_input(content, attachments)
            events: list[TaskStreamChunk] = []
            while True:
                chunk = await stream.recv(timeout=read_timeout)
                events.append(chunk)
                if chunk.type in ("task-started", "task-ended", "task-error"):
                    break
            return events
        finally:
            await stream.close()

    # ---------- 任务控制 / 选项 / 终端 ----------

    def get_task_options(self) -> dict[str, Any]:
        """聚合创建任务所需的下拉选项，一次返回。

        对应桌面端 mc_task_options：聚合多个 REST 列表接口。
        返回 {models, images, hosts, projects, plan}。
        """
        subscription = self.get_subscription()
        plan = ""
        if isinstance(subscription, dict):
            plan = subscription.get("plan") or ""
        return {
            "models": self.list_models(),
            "images": self.list_images(),
            "hosts": self.list_hosts(),
            "projects": self.list_projects(),
            "plan": plan,
        }

    def open_task_control(self, task_id: str) -> ControlStream:
        """打开任务控制通道（WebSocket 上下文管理器）。

        用于 switch_model / restart / 文件浏览 / 端口转发等同步调用。
        """
        return ControlStream(self, task_id)

    async def switch_task_model(
        self,
        task_id: str,
        model_id: str,
        load_session: bool = True,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """切换运行中任务的模型（走 control 通道）。

        成功时返回服务端响应 dict（含 session_id / model）；
        失败时返回 {"success": False, "error": "..."}。
        """
        stream = ControlStream(self, task_id)
        await stream.connect()
        try:
            await stream.send_call(
                "switch_model",
                {"model_id": str(model_id), "load_session": load_session},
            )
            while True:
                chunk = await stream.recv(timeout=timeout)
                if chunk.type == "call-response":
                    data = chunk.data
                    if isinstance(data, dict):
                        return data
                    return {"success": False, "error": str(data)}
                if chunk.type == "error":
                    return {"success": False, "error": str(chunk.data)}
        finally:
            await stream.close()

    def list_terminal_sessions(self, vm_id: str) -> list[dict[str, Any]]:
        """获取虚拟机终端会话列表。"""
        data = self._request(
            "GET", f"/api/v1/users/hosts/vms/{vm_id}/terminals"
        )
        if isinstance(data, dict):
            return (
                data.get("terminals")
                or data.get("sessions")
                or data.get("list")
                or []
            )
        return data or []

    def share_terminal(
        self,
        vm_id: str,
        mode: str = "read_write",
        terminal_id: str | None = None,
    ) -> Any:
        """分享终端，返回 {password}。

        mode 支持 read_write / read_only；terminal_id 可选。
        """
        body: dict[str, Any] = {"mode": mode}
        if terminal_id:
            body["terminal_id"] = terminal_id
        return self._request(
            "POST",
            f"/api/v1/users/hosts/vms/{vm_id}/terminals/share",
            json=body,
        )

    def close_terminal(self, vm_id: str, terminal_id: str) -> Any:
        """关闭指定终端会话。"""
        return self._request(
            "DELETE",
            f"/api/v1/users/hosts/vms/{vm_id}/terminals/{terminal_id}",
        )

    def open_terminal(
        self,
        vm_id: str,
        terminal_id: str | None = None,
        col: int = 80,
        row: int = 24,
    ) -> TerminalStream:
        """打开虚拟机终端流（WebSocket 上下文管理器）。

        终端输出/输入均为原始字节，data 消息自动 base64 解码。
        """
        return TerminalStream(
            self, vm_id, terminal_id=terminal_id, col=col, row=row
        )

    def join_terminal(
        self,
        terminal_id: str,
        password: str,
        col: int = 80,
        row: int = 24,
    ) -> JoinTerminalStream:
        """加入共享终端（WebSocket 上下文管理器）。

        使用 share_terminal() 返回的分享密码加入他人终端。
        """
        return JoinTerminalStream(
            self, terminal_id, password=password, col=col, row=row
        )

    # ---------- 任务控制调用（WebSocket control 专用封装） ----------

    async def _task_control_call(
        self,
        task_id: str,
        kind: str,
        data: dict[str, Any],
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """通用控制通道调用：发送 call 并等待 call-response。"""
        stream = ControlStream(self, task_id)
        await stream.connect()
        try:
            await stream.send_call(kind, data)
            while True:
                chunk = await stream.recv(timeout=timeout)
                if chunk.type == "call-response":
                    result = chunk.data
                    if isinstance(result, dict):
                        return result
                    return {"success": False, "error": str(result)}
                if chunk.type == "error":
                    return {"success": False, "error": str(chunk.data)}
        finally:
            await stream.close()

    async def switch_task_agent_resources(
        self,
        task_id: str,
        skill_ids: list[str] | None = None,
        plugin_ids: list[str] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """运行中全量更新任务的技能/插件列表（kind=switch_agent_resources）。"""
        return await self._task_control_call(
            task_id,
            "switch_agent_resources",
            {
                "skill_ids": skill_ids or [],
                "plugin_ids": plugin_ids or [],
            },
            timeout=timeout,
        )

    async def restart_task(
        self,
        task_id: str,
        load_session: bool = True,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """重启任务，可选加载历史会话（kind=restart）。"""
        return await self._task_control_call(
            task_id,
            "restart",
            {"load_session": load_session},
            timeout=timeout,
        )

    async def list_task_repo_files(
        self,
        task_id: str,
        path: str = "",
        glob_pattern: str = "*",
        include_hidden: bool = True,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """列出任务仓库文件（kind=repo_file_list）。"""
        return await self._task_control_call(
            task_id,
            "repo_file_list",
            {
                "path": path,
                "glob_pattern": glob_pattern,
                "include_hidden": include_hidden,
            },
            timeout=timeout,
        )

    async def read_task_repo_file(
        self,
        task_id: str,
        path: str,
        offset: int = 0,
        length: int = 1024 * 1024,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """读取任务仓库文件（kind=repo_read_file，默认前 1MB）。"""
        return await self._task_control_call(
            task_id,
            "repo_read_file",
            {"path": path, "offset": offset, "length": length},
            timeout=timeout,
        )

    async def get_task_repo_diff(
        self, task_id: str, path: str, timeout: float = 30.0
    ) -> dict[str, Any]:
        """获取任务仓库文件 diff（kind=repo_file_diff）。"""
        return await self._task_control_call(
            task_id, "repo_file_diff", {"path": path}, timeout=timeout
        )

    async def get_task_repo_changes(
        self, task_id: str, timeout: float = 30.0
    ) -> dict[str, Any]:
        """获取任务仓库变更列表（kind=repo_file_changes）。"""
        return await self._task_control_call(
            task_id, "repo_file_changes", {}, timeout=timeout
        )

    async def sync_client_ip(
        self, task_id: str, ip: str, timeout: float = 30.0
    ) -> dict[str, Any]:
        """上报客户端 IP（控制通道上行消息 sync-my-ip，Web 前端用）。

        通过 ControlStream.send_raw 发送非 call 消息；返回收到的
        下一条事件（可能是 call-response / error / 心跳）。
        """
        stream = ControlStream(self, task_id)
        await stream.connect()
        try:
            inner = json.dumps({"ip": ip}, ensure_ascii=False)
            await stream.send_raw("sync-my-ip", b64e(inner))
            chunk = await stream.recv(timeout=timeout)
            return {"success": chunk.type != "error", "event": chunk.raw}
        finally:
            await stream.close()

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

    def _raise_on_not_found(self, data: Any) -> Any:
        """把仅含错误 message 的响应（如 {'message': 'Not Found'}）转为 APIError。"""
        if isinstance(data, dict) and set(data.keys()) == {"message"}:
            msg = str(data.get("message") or "").strip()
            low = msg.lower()
            if msg and (
                "not found" in low
                or "404" in low
                or "不存在" in low
                or "forbidden" in low
                or "unauthorized" in low
                or "error" in low
                or "失败" in low
            ):
                raise APIError(msg, code=0, raw=data)
        return data

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth_required: bool = True,
        files: dict[str, Any] | None = None,
        _retry: bool = True,
        _attempt: int = 0,
    ) -> Any:
        try:
            resp = self._client.request(
                method, path, json=json, params=params, files=files
            )
        except httpx.HTTPError as exc:
            # 网络抖动：只读请求自动重试（指数退避）
            if method.upper() in _RETRYABLE_METHODS and _attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BASE_DELAY * (2 ** _attempt))
                return self._request(
                    method,
                    path,
                    json=json,
                    params=params,
                    auth_required=auth_required,
                    files=files,
                    _retry=_retry,
                    _attempt=_attempt + 1,
                )
            raise APIError(f"请求失败：{exc}") from exc

        if resp.status_code == 401:
            if (
                _retry
                and auth_required
                and self._auto_relogin
                and not self._relogging
                and self.email
                and self._password
            ):
                # 会话过期：自动重新登录后重试原请求一次
                self._relogging = True
                try:
                    self.login()
                except AuthenticationError:
                    pass
                finally:
                    self._relogging = False
                if self._logged_in:
                    return self._request(
                        method,
                        path,
                        json=json,
                        params=params,
                        auth_required=auth_required,
                        files=files,
                        _retry=False,
                    )
            raise AuthenticationError("未认证或会话已失效，请重新登录。", code=401)
        if resp.status_code == 429:
            # 限流：只读请求按 Retry-After / 指数退避等待后重试
            if method.upper() in _RETRYABLE_METHODS and _attempt < _MAX_RETRIES:
                retry_after = resp.headers.get("Retry-After")
                delay = _RETRY_BASE_DELAY * (2 ** _attempt)
                if retry_after and retry_after.isdigit():
                    delay = max(int(retry_after), 1)
                time.sleep(delay)
                return self._request(
                    method,
                    path,
                    json=json,
                    params=params,
                    auth_required=auth_required,
                    files=files,
                    _retry=_retry,
                    _attempt=_attempt + 1,
                )
            raise RateLimitError("触发限流（HTTP 429），请稍后重试。", code=429)
        if resp.status_code == 403 and auth_required:
            raise AuthenticationError("无权限访问该资源。", code=403)

        try:
            body = resp.json()
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            if resp.status_code != 200:
                raise APIError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return resp.text

        if isinstance(body, dict) and "code" in body:
            code = body.get("code")
            if code != 0:
                message = body.get("message") or body.get("msg") or "未知错误"
                message = _friendly_error(code, message)
                raise APIError(f"{message}（code={code}）", code=code, raw=body)
            return body.get("data")
        return body

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MonkeyCodeClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
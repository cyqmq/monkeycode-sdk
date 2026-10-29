"""MonkeyCode 云平台 REST API 客户端。

基于 httpx，登录后自动携带会话 Cookie（monkeycode_ai_session）。
支持密码登录（MD5 + 可选验证码）、枚举环境、创建任务、轮询结果。
"""
from __future__ import annotations

import hashlib
import time
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
from monkeycode.stream import TaskStream

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
        """获取 Git 身份列表。"""
        return self._request("GET", "/api/v1/users/git-identities")

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
        return resp.content

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
        files: dict[str, Any] | None = None,
    ) -> Any:
        try:
            resp = self._client.request(
                method, path, json=json, params=params, files=files
            )
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
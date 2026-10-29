# API 方法索引

按字母序排列的 MonkeyCodeClient 全部公开方法（共 205 个，含 async WebSocket/控制通道方法）。
详细示例见 [功能参考.md](功能参考.md)。

| 方法签名 | 说明 |
|------|------|
| `add_git_identity(self, access_token: str, base_url: str, email: str, platform: str, username: str, remark: str | None=None, organization_id: str | None=None)` | 添加 Git 身份 |
| `add_issue_comment(self, project_id: str, issue_id: str, comment: str, parent_id: str | None=None)` | 创建 Issue 评论 |
| `add_port_forward(self, host_id: str, vm_id: str, **fields: Any)` | 添加端口转发规则 |
| `bind_email_request(self, email: str)` | 请求绑定邮箱 |
| `bind_wechat_qrcode(self)` | 创建微信公众号绑定二维码 |
| `build_oauth_login_url(self, provider: str, redirect_url: str | None=None)` | 构造 OAuth 登录跳转 URL（供浏览器使用） |
| `build_oidc_login_url(self, team_id: str | None=None)` | 构造企业 OIDC 登录跳转 URL（供浏览器使用） |
| `change_password(self, new_password: str, current_password: str | None=None)` | 修改密码 |
| `checkin(self)` | 每日签到（自动求解 PoW 验证码） |
| `close(self)` |  |
| `close_terminal(self, vm_id: str, terminal_id: str)` | 关闭指定终端会话 |
| `copy_file(self, vm_id: str, source: str, target: str)` | 复制 VM 中的文件或目录 |
| `create_api_key(self)` | 创建 OhMyAgent API Key |
| `create_captcha(self)` | 创建验证码质询 |
| `create_git_bot(self, host_id: str, platform: str, token: str, name: str | None=None)` | 创建 Git Bot |
| `create_host(self, **fields: Any)` | 注册宿主机 |
| `create_image(self, image_name: str, is_default: bool | None=None, remark: str | None=None)` | 创建镜像 |
| `create_mcp_upstream(self, name: str, url: str, headers: dict[str, Any] | None=None)` | 创建 MCP 上游 |
| `create_model(self, **fields: Any)` | 创建模型配置 |
| `create_notify_channel(self, name: str, kind: str, webhook_url: str, event_types: list[str], headers: dict[str, Any] | None=None)` | 创建通知渠道 |
| `create_playground_post(self, content: str)` | 发布普通社区帖子 |
| `create_playground_task_post(self, task_id: str, content: str)` | 发布任务帖 |
| `create_project(self, name: str, repo_url: str, platform: str='github', git_identity_id: str | None=None, image_id: str | None=None, description: str | None=None, env_variables: dict[str, Any] | None=None)` | 创建项目（仓库关联） |
| `create_project_issue(self, project_id: str, title: str, assignee_id: str | None=None, priority: int | None=None, requirement_document: str | None=None)` | 创建项目 Issue |
| `create_subscription(self)` | 开通会员订阅 |
| `create_task(self, content: str, repo: RepoReq | None=None, host_id: str='public_host', image_id: str | None=None, model_id: str | None=None, resource: VMResource | None=None, task_type: TaskType=TaskType.DEVELOP, sub_type: TaskSubType | None=None, cli_name: CliName=CliName.OPENCODE, git_identity_id: str | None=None, system_prompt: str | None=None, skill_ids: list[str] | None=None, plugin_ids: list[str] | None=None, project_id: str | None=None, issue_id: str | None=None, attachments: list[dict] | None=None)` | 创建任务 |
| `create_vm(self, host_id: str, **fields: Any)` | 创建虚拟机/开发环境 |
| `delete_account(self)` | 注销账号 |
| `delete_api_key(self, key_id: str)` | 按 Key ID 删除当前用户的 OhMyAgent API Key |
| `delete_file(self, vm_id: str, path: str)` | 删除 VM 中的文件或目录 |
| `delete_git_bot(self, git_bot_id: str)` | 删除 Git Bot |
| `delete_git_identity(self, identity_id: str)` | 删除 Git 身份 |
| `delete_host(self, host_id: str)` | 删除宿主机 |
| `delete_image(self, image_id: str)` | 删除镜像 |
| `delete_mcp_upstream(self, upstream_id: str)` | 删除 MCP 上游 |
| `delete_model(self, model_id: str)` | 删除模型配置 |
| `delete_notify_channel(self, channel_id: str)` | 删除通知渠道 |
| `delete_port_forward(self, host_id: str, vm_id: str, port: int | str)` | 删除端口转发规则 |
| `delete_project_issue(self, project_id: str, issue_id: str)` | 删除项目 Issue |
| `delete_task(self, task_id: str)` | 删除任务 |
| `delete_vm(self, host_id: str, vm_id: str)` | 删除虚拟机 |
| `download_file(self, vm_id: str, path: str, filename: str)` | 下载 VM 中的文件，返回字节内容 |
| `get_cnb_authorize_url(self)` | 获取 CNB 授权 URL |
| `get_gitea_authorize_url(self)` | 获取 Gitea 授权 URL |
| `get_gitea_sites(self)` | 获取 Gitea 站点列表 |
| `get_gitee_authorize_url(self)` | 获取 Gitee 授权 URL |
| `get_gitlab_authorize_url(self)` | 获取 GitLab 授权 URL |
| `get_gitlab_sites(self)` | 获取 GitLab 站点列表 |
| `get_host_install_command(self)` | 获取宿主机安装命令（用于接入新宿主机） |
| `get_license_machine_code(self)` | 获取机器码 |
| `get_license_status(self)` | 获取 License 状态 |
| `get_model_health_check(self, model_id: str)` | 获取单个模型健康检查结果 |
| `get_project_file(self, project_id: str, path: str, ref: str | None=None)` | 获取项目文件内容 |
| `get_project_tree(self, project_id: str, path: str='', ref: str | None=None, recursive: bool | None=None)` | 获取项目仓库树 |
| `get_public_stats(self)` | 获取公开统计 |
| `get_reset_password_account(self, token: str)` | 用重置链接中的 token 查询账户信息（网页重置用） |
| `get_server_config(self)` | 获取服务器公开配置（无需登录） |
| `get_subscription(self)` | 查询会员订阅信息 |
| `get_task(self, task_id: str)` | 获取任务详情 |
| `get_task_options(self)` | 聚合创建任务所需的下拉选项，一次返回 |
| `get_task_repo_changes(self, task_id: str, timeout: float=30.0)` | 获取任务仓库变更列表（kind=repo_file_changes） |
| `get_task_repo_diff(self, task_id: str, path: str, timeout: float=30.0)` | 获取任务仓库文件 diff（kind=repo_file_diff） |
| `get_task_rounds(self, task_id: str, cursor: str | None=None, limit: int=2, direction: str='backward', inclusive: bool | None=None)` | 查询任务历史轮次 |
| `get_task_user_inputs(self, task_id: str, cursor: str | None=None, limit: int=20)` | 查询任务用户输入列表 |
| `get_user_status(self)` | 获取当前登录用户身份/状态（whoami 底层接口） |
| `get_vm(self, vm_id: str)` | 获取虚拟机详情 |
| `get_wallet(self)` | 查询钱包（积分余额） |
| `get_wallet_transactions(self)` | 查询钱包交易记录 |
| `import_license(self, license_key: str)` | 导入 License |
| `is_logged_in(self)` | 是否已有登录态（含从 session_path 加载的持久化会话） |
| `iter_projects(self, page_size: int=20, max_pages: int=100, **filters: Any)` | 分页迭代项目列表 |
| `iter_tasks(self, page_size: int=20, max_pages: int=100, **filters: Any)` | 分页迭代任务列表 |
| `join_terminal(self, terminal_id: str, password: str, col: int=80, row: int=24)` | 加入共享终端（WebSocket 上下文管理器） |
| `list_available_models(self)` | 获取可用模型列表（仅查询，不做 CRUD） |
| `list_folders(self, vm_id: str, path: str='')` | 列出虚拟机目录 |
| `list_git_bot_tasks(self, git_bot_id: str, page: int | None=None, size: int | None=None)` | 获取 Git Bot 任务列表 |
| `list_git_bots(self)` | 获取 Git Bot 列表 |
| `list_git_branches(self, identity_id: str, repo_full_name: str, page: int=1, per_page: int=50)` | 获取指定仓库的分支列表 |
| `list_git_identities(self)` | 获取 Git 身份列表 |
| `list_hosts(self)` | 获取可用的云端宿主/环境列表（返回 data.hosts） |
| `list_images(self)` | 获取可用的镜像列表（返回 data.images） |
| `list_invitations(self)` | 获取邀请列表 |
| `list_issue_comments(self, project_id: str, issue_id: str, cursor: str | None=None, limit: int | None=None)` | 获取 Issue 评论列表 |
| `list_mcp_upstreams(self)` | 获取 MCP 上游列表 |
| `list_members(self)` | 获取团队成员列表 |
| `list_model_providers(self, provider: str, base_url: str, api_key: str, api_header: str | None=None)` | 列出模型供应商的模型列表 |
| `list_models(self)` | 获取可用的模型列表（返回 data.models） |
| `list_notify_channels(self)` | 获取通知渠道列表 |
| `list_notify_event_types(self)` | 获取通知事件类型 |
| `list_playground_posts(self)` | 获取社区帖子列表 |
| `list_plugins(self)` | 获取可用插件列表 |
| `list_port_forwards(self, host_id: str, vm_id: str)` | 列出虚拟机的端口转发规则 |
| `list_project_issues(self, project_id: str, cursor: str | None=None, limit: int | None=None)` | 获取项目 Issue 列表 |
| `list_projects(self, cursor: str | None=None, limit: int | None=None)` | 获取项目（仓库）列表，支持分页 |
| `list_skills(self)` | 获取可用技能列表（配合 create_task 的 skill_ids） |
| `list_task_links(self, task_id: str, check_alive: bool=True, max_pages: int=500)` | 列出任务中 AI 拉起的预览链接，并检测存活状态 |
| `list_task_repo_files(self, task_id: str, path: str='', glob_pattern: str='*', include_hidden: bool=True, timeout: float=30.0)` | 列出任务仓库文件（kind=repo_file_list） |
| `list_tasks(self, page: int | None=None, size: int | None=None, status: str | None=None, project_id: str | None=None, quick_start: str | None=None, next_token: str | None=None)` | 任务列表 |
| `list_terminal_sessions(self, vm_id: str)` | 获取虚拟机终端会话列表 |
| `login(self, captcha_token: str | None=None)` | 使用邮箱 + 密码登录，自动处理 PoW 验证码 |
| `logout(self)` | 退出当前用户会话（清除云端登录态并删除本地会话文件） |
| `model_health_check(self, model_ids: list[str])` | 批量执行模型健康检查 |
| `move_file(self, vm_id: str, source: str, target: str)` | 移动/重命名 VM 中的文件或目录 |
| `open_task_control(self, task_id: str)` | 打开任务控制通道（WebSocket 上下文管理器） |
| `open_task_stream(self, task_id: str, mode: str='new')` | 打开任务实时流（WebSocket 上下文管理器） |
| `open_terminal(self, vm_id: str, terminal_id: str | None=None, col: int=80, row: int=24)` | 打开虚拟机终端流（WebSocket 上下文管理器） |
| `paginate(self, fetcher, extract=None, page_size: int=20, max_pages: int=100)` | 通用分页迭代器 |
| `presign_upload(self, filename: str)` | 获取附件预签名上传信息 |
| `read_task_repo_file(self, task_id: str, path: str, offset: int=0, length: int=1024 * 1024, timeout: float=30.0)` | 读取任务仓库文件（kind=repo_read_file，默认前 1MB） |
| `redeem_captcha(self, token: str, solutions: list[int])` | 提交验证码答案，兑换登录用的 captcha_token |
| `request_password_reset(self, email: str)` | 发送密码重置邮件 |
| `reset_password(self, token: str, new_password: str)` | 重置密码 |
| `restart_task(self, task_id: str, load_session: bool=True, timeout: float=30.0)` | 重启任务，可选加载历史会话（kind=restart） |
| `send_task_message(self, task_id: str, content: str, attachments: list[dict] | None=None, read_timeout: float=30.0)` | 进入任务会话，发送用户消息，返回直到 task-started 的首批事件 |
| `set_auto_renew(self, enabled: bool)` | 设置订阅自动续费 |
| `set_credit_consumption(self, enabled: bool)` | 设置订阅积分消费 |
| `set_mcp_tool(self, tool_id: str, enabled: bool)` | 启用/关闭 MCP 工具 |
| `share_git_bot(self, git_bot_id: str, user_ids: list[str])` | 分享 Git Bot |
| `share_terminal(self, vm_id: str, mode: str='read_write', terminal_id: str | None=None)` | 分享终端，返回 {password} |
| `speech_to_text(self, **fields: Any)` | 语音转文字（提交音频） |
| `stop_task(self, task_id: str)` | 停止任务 |
| `switch_task_agent_resources(self, task_id: str, skill_ids: list[str] | None=None, plugin_ids: list[str] | None=None, timeout: float=30.0)` | 运行中全量更新任务的技能/插件列表（kind=switch_agent_resources） |
| `switch_task_model(self, task_id: str, model_id: str, load_session: bool=True, timeout: float=30.0)` | 切换运行中任务的模型（走 control 通道） |
| `sync_client_ip(self, task_id: str, ip: str, timeout: float=30.0)` | 上报客户端 IP（控制通道上行消息 sync-my-ip，Web 前端用） |
| `sync_mcp_upstream(self, upstream_id: str)` | 同步 MCP 上游 |
| `team_add_user(self, **fields: Any)` | 添加团队成员 |
| `team_add_user_with_password(self, **fields: Any)` | 创建团队成员并返回初始密码（仅响应返回一次） |
| `team_admin_initialize(self)` | 初始化团队 |
| `team_change_password(self, **fields: Any)` | 团队用户修改密码 |
| `team_create_extension_package(self, **fields: Any)` | 创建团队扩展包 |
| `team_create_group(self, name: str)` | 创建团队分组 |
| `team_create_image(self, **fields: Any)` | 创建团队镜像 |
| `team_create_mcp_upstream(self, **fields: Any)` | 创建团队 MCP 上游 |
| `team_create_model(self, **fields: Any)` | 创建团队模型配置 |
| `team_create_notify_channel(self, **fields: Any)` | 创建团队通知渠道 |
| `team_create_oauth_site(self, **fields: Any)` | 创建团队 OAuth 站点配置 |
| `team_create_skill(self, **fields: Any)` | 创建团队技能 |
| `team_create_skill_package(self, **fields: Any)` | 上传/创建团队技能包 |
| `team_delete_group(self, group_id: str)` | 删除团队分组 |
| `team_delete_host(self, host_id: str)` | 删除团队宿主机 |
| `team_delete_image(self, image_id: str)` | 删除团队镜像 |
| `team_delete_mcp_upstream(self, upstream_id: str)` | 删除团队 MCP 上游 |
| `team_delete_model(self, model_id: str)` | 删除团队模型 |
| `team_delete_notify_channel(self, channel_id: str)` | 删除团队通知渠道 |
| `team_delete_oauth_site(self, site_id: str)` | 删除团队 OAuth 站点 |
| `team_delete_skill(self, skill_id: str)` | 删除团队技能 |
| `team_delete_user(self, user_id: str)` | 删除团队成员 |
| `team_get_dashboard(self)` | 获取团队 Dashboard |
| `team_get_host_install_command(self)` | 获取团队宿主机安装命令 |
| `team_get_model_health_check(self, model_id: str)` | 单个团队模型健康检查 |
| `team_get_oidc(self)` | 获取团队 OIDC 配置 |
| `team_get_user_status(self)` | 查询当前团队用户状态（团队会话） |
| `team_get_vm_idle_policy(self)` | 获取 VM 空闲策略 |
| `team_list_audits(self)` | 获取团队审计日志 |
| `team_list_conversations(self)` | 获取团队 agent 会话列表（管理端） |
| `team_list_extension_packages(self)` | 团队扩展包列表 |
| `team_list_group_users(self, group_id: str)` | 获取分组内用户 |
| `team_list_groups(self)` | 团队分组列表 |
| `team_list_hosts(self)` | 团队宿主列表 |
| `team_list_images(self)` | 团队镜像列表 |
| `team_list_mcp_upstreams(self)` | 团队 MCP 上游列表 |
| `team_list_models(self)` | 团队模型列表 |
| `team_list_notify_channels(self)` | 团队通知渠道列表 |
| `team_list_notify_event_types(self)` | 团队通知事件类型列表 |
| `team_list_oauth_sites(self)` | 团队 OAuth 站点列表 |
| `team_list_projects(self)` | 团队项目列表 |
| `team_list_skills(self)` | 团队技能列表 |
| `team_list_tasks(self)` | 团队任务列表 |
| `team_list_users(self)` | 团队成员列表 |
| `team_login(self, email: str | None=None, password: str | None=None, captcha_token: str | None=None)` | 团队管理员登录 |
| `team_logout(self)` | 退出团队管理员会话（清除云端登录态并删除本地会话文件） |
| `team_model_health_check(self, model_ids: list[str])` | 团队模型批量健康检查 |
| `team_reset_user_password(self, user_id: str)` | 管理员重置成员密码（仅响应返回一次） |
| `team_save_oidc(self, **fields: Any)` | 保存团队 OIDC 配置 |
| `team_set_group_users(self, group_id: str, user_ids: list[str])` | 调整分组内用户 |
| `team_set_vm_idle_policy(self, **fields: Any)` | 设置 VM 空闲策略 |
| `team_sync_mcp_upstream(self, upstream_id: str)` | 同步团队 MCP 上游 |
| `team_test_notify_channel(self, channel_id: str)` | 测试团队通知渠道 |
| `team_test_oidc(self, **fields: Any)` | 测试团队 OIDC 配置 |
| `team_update_group(self, group_id: str, name: str)` | 更新分组名称 |
| `team_update_host(self, host_id: str, **fields: Any)` | 更新团队宿主机 |
| `team_update_image(self, image_id: str, **fields: Any)` | 更新团队镜像 |
| `team_update_mcp_upstream(self, upstream_id: str, **fields: Any)` | 更新团队 MCP 上游 |
| `team_update_model(self, model_id: str, **fields: Any)` | 更新团队模型 |
| `team_update_notify_channel(self, channel_id: str, **fields: Any)` | 更新团队通知渠道 |
| `team_update_oauth_site(self, site_id: str, **fields: Any)` | 更新团队 OAuth 站点 |
| `team_update_skill(self, skill_id: str, **fields: Any)` | 更新团队技能 |
| `team_update_user(self, user_id: str, **fields: Any)` | 更新团队成员信息 |
| `test_notify_channel(self, channel_id: str)` | 测试通知渠道 |
| `unbind_wechat(self)` | 解绑微信公众号 |
| `update_git_bot(self, **fields: Any)` | 更新 Git Bot |
| `update_git_identity(self, identity_id: str, **fields: Any)` | 更新 Git 身份（token/备注/组织等） |
| `update_host(self, host_id: str, **fields: Any)` | 更新宿主机配置 |
| `update_image(self, image_id: str, image_name: str | None=None, is_default: bool | None=None, remark: str | None=None)` | 更新镜像 |
| `update_mcp_upstream(self, upstream_id: str, **fields: Any)` | 更新 MCP 上游 |
| `update_model(self, model_id: str, **fields: Any)` | 更新模型配置（如 API Key、备注、供应商等） |
| `update_notify_channel(self, channel_id: str, **fields: Any)` | 更新通知渠道 |
| `update_project_issue(self, project_id: str, issue_id: str, title: str | None=None, assignee_id: str | None=None, priority: int | None=None, status: str | None=None, requirement_document: str | None=None, design_document: str | None=None)` | 更新项目 Issue |
| `update_user_profile(self, name: str | None=None, avatar_url: str | None=None)` | 更新用户昵称/头像 |
| `update_vm(self, host_id: str, vm_id: str, **fields: Any)` | 更新虚拟机（如续期、调整配置） |
| `upload_attachment(self, filename: str, file_path: str | None=None, file_bytes: bytes | None=None)` | 上传附件并返回 access_url |
| `upload_file(self, vm_id: str, path: str, file_path: str | None=None, file_bytes: bytes | None=None, filename: str | None=None)` | 上传文件到 VM 的绝对路径 |
| `upload_object(self, filename: str, file_bytes: bytes, usage: str='attachment')` | 直接 multipart 上传文件对象（POST /api/v1/uploader） |
| `wait_task(self, task_id: str, timeout: float=1800.0, interval: float=5.0, terminal_statuses: set[str] | None=None)` | 轮询任务直到进入终态 |
| `whoami(self)` | 获取当前登录用户信息（get_user_status 别名） |
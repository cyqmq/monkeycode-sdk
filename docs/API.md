# API 方法索引

按字母序排列的 MonkeyCodeClient 全部公开方法（共 196 个）。
详细示例见 [功能参考.md](功能参考.md)。

| 方法 | 说明 |
|------|------|
| `add_git_identity` | 添加 Git 身份 |
| `add_issue_comment` | 创建 Issue 评论 |
| `add_port_forward` | 添加端口转发规则 |
| `bind_email_request` | 请求绑定邮箱 |
| `bind_wechat_qrcode` | 创建微信公众号绑定二维码 |
| `build_oauth_login_url` | 构造 OAuth 登录跳转 URL（供浏览器使用） |
| `build_oidc_login_url` | 构造企业 OIDC 登录跳转 URL（供浏览器使用） |
| `change_password` | 修改密码 |
| `checkin` | 每日签到（自动求解 PoW 验证码） |
| `close` |  |
| `close_terminal` | 关闭指定终端会话 |
| `copy_file` | 复制 VM 中的文件或目录 |
| `create_api_key` | 创建 OhMyAgent API Key |
| `create_captcha` | 创建验证码质询 |
| `create_git_bot` | 创建 Git Bot |
| `create_host` | 注册宿主机 |
| `create_image` | 创建镜像 |
| `create_mcp_upstream` | 创建 MCP 上游 |
| `create_model` | 创建模型配置 |
| `create_notify_channel` | 创建通知渠道 |
| `create_playground_post` | 发布普通社区帖子 |
| `create_playground_task_post` | 发布任务帖 |
| `create_project` | 创建项目（仓库关联） |
| `create_project_issue` | 创建项目 Issue |
| `create_subscription` | 开通会员订阅 |
| `create_task` | 创建任务 |
| `create_vm` | 创建虚拟机/开发环境 |
| `delete_account` | 注销账号 |
| `delete_api_key` | 按 Key ID 删除当前用户的 OhMyAgent API Key |
| `delete_file` | 删除 VM 中的文件或目录 |
| `delete_git_bot` | 删除 Git Bot |
| `delete_git_identity` | 删除 Git 身份 |
| `delete_host` | 删除宿主机 |
| `delete_image` | 删除镜像 |
| `delete_mcp_upstream` | 删除 MCP 上游 |
| `delete_model` | 删除模型配置 |
| `delete_notify_channel` | 删除通知渠道 |
| `delete_port_forward` | 删除端口转发规则 |
| `delete_project_issue` | 删除项目 Issue |
| `delete_task` | 删除任务 |
| `delete_vm` | 删除虚拟机 |
| `download_file` | 下载 VM 中的文件，返回字节内容 |
| `get_cnb_authorize_url` | 获取 CNB 授权 URL |
| `get_gitea_authorize_url` | 获取 Gitea 授权 URL |
| `get_gitea_sites` | 获取 Gitea 站点列表 |
| `get_gitee_authorize_url` | 获取 Gitee 授权 URL |
| `get_gitlab_authorize_url` | 获取 GitLab 授权 URL |
| `get_gitlab_sites` | 获取 GitLab 站点列表 |
| `get_host_install_command` | 获取宿主机安装命令（用于接入新宿主机） |
| `get_license_machine_code` | 获取机器码 |
| `get_license_status` | 获取 License 状态 |
| `get_model_health_check` | 获取单个模型健康检查结果 |
| `get_project_file` | 获取项目文件内容 |
| `get_project_tree` | 获取项目仓库树 |
| `get_public_stats` | 获取公开统计 |
| `get_reset_password_account` | 用重置链接中的 token 查询账户信息（网页重置用） |
| `get_server_config` | 获取服务器公开配置（无需登录） |
| `get_subscription` | 查询会员订阅信息 |
| `get_task` | 获取任务详情 |
| `get_task_options` | 聚合创建任务所需的下拉选项，一次返回 |
| `get_task_rounds` | 查询任务历史轮次 |
| `get_task_user_inputs` | 查询任务用户输入列表 |
| `get_user_status` | 获取当前登录用户身份/状态（whoami 底层接口） |
| `get_vm` | 获取虚拟机详情 |
| `get_wallet` | 查询钱包（积分余额） |
| `get_wallet_transactions` | 查询钱包交易记录 |
| `import_license` | 导入 License |
| `is_logged_in` | 是否已有登录态（含从 session_path 加载的持久化会话） |
| `iter_projects` | 分页迭代项目列表 |
| `iter_tasks` | 分页迭代任务列表 |
| `join_terminal` | 加入共享终端（WebSocket 上下文管理器） |
| `list_available_models` | 获取可用模型列表（仅查询，不做 CRUD） |
| `list_folders` | 列出虚拟机目录 |
| `list_git_bot_tasks` | 获取 Git Bot 任务列表 |
| `list_git_bots` | 获取 Git Bot 列表 |
| `list_git_branches` | 获取指定仓库的分支列表 |
| `list_git_identities` | 获取 Git 身份列表 |
| `list_hosts` | 获取可用的云端宿主/环境列表（返回 data.hosts） |
| `list_images` | 获取可用的镜像列表（返回 data.images） |
| `list_invitations` | 获取邀请列表 |
| `list_issue_comments` | 获取 Issue 评论列表 |
| `list_mcp_upstreams` | 获取 MCP 上游列表 |
| `list_members` | 获取团队成员列表 |
| `list_model_providers` | 列出模型供应商 |
| `list_models` | 获取可用的模型列表（返回 data.models） |
| `list_notify_channels` | 获取通知渠道列表 |
| `list_notify_event_types` | 获取通知事件类型 |
| `list_playground_posts` | 获取社区帖子列表 |
| `list_plugins` | 获取可用插件列表 |
| `list_port_forwards` | 列出虚拟机的端口转发规则 |
| `list_project_issues` | 获取项目 Issue 列表 |
| `list_projects` | 获取项目（仓库）列表，支持分页 |
| `list_skills` | 获取可用技能列表（配合 create_task 的 skill_ids） |
| `list_task_links` | 列出任务中 AI 拉起的预览链接，并检测存活状态 |
| `list_tasks` | 任务列表 |
| `list_terminal_sessions` | 获取虚拟机终端会话列表 |
| `login` | 使用邮箱 + 密码登录，自动处理 PoW 验证码 |
| `logout` | 退出当前用户会话（清除云端登录态并删除本地会话文件） |
| `model_health_check` | 批量执行模型健康检查 |
| `move_file` | 移动/重命名 VM 中的文件或目录 |
| `open_task_control` | 打开任务控制通道（WebSocket 上下文管理器） |
| `open_task_stream` | 打开任务实时流（WebSocket 上下文管理器） |
| `open_terminal` | 打开虚拟机终端流（WebSocket 上下文管理器） |
| `paginate` | 通用分页迭代器 |
| `presign_upload` | 获取附件预签名上传信息 |
| `redeem_captcha` | 提交验证码答案，兑换登录用的 captcha_token |
| `request_password_reset` | 发送密码重置邮件 |
| `reset_password` | 重置密码 |
| `set_auto_renew` | 设置订阅自动续费 |
| `set_credit_consumption` | 设置订阅积分消费 |
| `set_mcp_tool` | 启用/关闭 MCP 工具 |
| `share_git_bot` | 分享 Git Bot |
| `share_terminal` | 分享终端，返回 {password} |
| `speech_to_text` | 语音转文字（提交音频） |
| `stop_task` | 停止任务 |
| `sync_mcp_upstream` | 同步 MCP 上游 |
| `team_add_user` | 添加团队成员 |
| `team_add_user_with_password` | 创建团队成员并返回初始密码（仅响应返回一次） |
| `team_admin_initialize` | 初始化团队 |
| `team_change_password` | 团队用户修改密码 |
| `team_create_extension_package` | 创建团队扩展包 |
| `team_create_group` | 创建团队分组 |
| `team_create_image` | 创建团队镜像 |
| `team_create_mcp_upstream` | 创建团队 MCP 上游 |
| `team_create_model` | 创建团队模型配置 |
| `team_create_notify_channel` | 创建团队通知渠道 |
| `team_create_oauth_site` | 创建团队 OAuth 站点配置 |
| `team_create_skill` | 创建团队技能 |
| `team_create_skill_package` | 上传/创建团队技能包 |
| `team_delete_group` | 删除团队分组 |
| `team_delete_host` | 删除团队宿主机 |
| `team_delete_image` | 删除团队镜像 |
| `team_delete_mcp_upstream` | 删除团队 MCP 上游 |
| `team_delete_model` | 删除团队模型 |
| `team_delete_notify_channel` | 删除团队通知渠道 |
| `team_delete_oauth_site` | 删除团队 OAuth 站点 |
| `team_delete_skill` | 删除团队技能 |
| `team_delete_user` | 删除团队成员 |
| `team_get_dashboard` | 获取团队 Dashboard |
| `team_get_host_install_command` | 获取团队宿主机安装命令 |
| `team_get_model_health_check` | 单个团队模型健康检查 |
| `team_get_oidc` | 获取团队 OIDC 配置 |
| `team_get_user_status` | 查询当前团队用户状态（团队会话） |
| `team_get_vm_idle_policy` | 获取 VM 空闲策略 |
| `team_list_audits` | 获取团队审计日志 |
| `team_list_conversations` | 获取团队 agent 会话列表（管理端） |
| `team_list_extension_packages` | 团队扩展包列表 |
| `team_list_group_users` | 获取分组内用户 |
| `team_list_groups` | 团队分组列表 |
| `team_list_hosts` | 团队宿主列表 |
| `team_list_images` | 团队镜像列表 |
| `team_list_mcp_upstreams` | 团队 MCP 上游列表 |
| `team_list_models` | 团队模型列表 |
| `team_list_notify_channels` | 团队通知渠道列表 |
| `team_list_notify_event_types` | 团队通知事件类型列表 |
| `team_list_oauth_sites` | 团队 OAuth 站点列表 |
| `team_list_projects` | 团队项目列表 |
| `team_list_skills` | 团队技能列表 |
| `team_list_tasks` | 团队任务列表 |
| `team_list_users` | 团队成员列表 |
| `team_login` | 团队管理员登录 |
| `team_logout` | 退出团队管理员会话（清除云端登录态并删除本地会话文件） |
| `team_model_health_check` | 团队模型批量健康检查 |
| `team_reset_user_password` | 管理员重置成员密码（仅响应返回一次） |
| `team_save_oidc` | 保存团队 OIDC 配置 |
| `team_set_group_users` | 调整分组内用户 |
| `team_set_vm_idle_policy` | 设置 VM 空闲策略 |
| `team_sync_mcp_upstream` | 同步团队 MCP 上游 |
| `team_test_notify_channel` | 测试团队通知渠道 |
| `team_test_oidc` | 测试团队 OIDC 配置 |
| `team_update_group` | 更新分组名称 |
| `team_update_host` | 更新团队宿主机 |
| `team_update_image` | 更新团队镜像 |
| `team_update_mcp_upstream` | 更新团队 MCP 上游 |
| `team_update_model` | 更新团队模型 |
| `team_update_notify_channel` | 更新团队通知渠道 |
| `team_update_oauth_site` | 更新团队 OAuth 站点 |
| `team_update_skill` | 更新团队技能 |
| `team_update_user` | 更新团队成员信息 |
| `test_notify_channel` | 测试通知渠道 |
| `unbind_wechat` | 解绑微信公众号 |
| `update_git_bot` | 更新 Git Bot |
| `update_git_identity` | 更新 Git 身份（token/备注/组织等） |
| `update_host` | 更新宿主机配置 |
| `update_image` | 更新镜像 |
| `update_mcp_upstream` | 更新 MCP 上游 |
| `update_model` | 更新模型配置（如 API Key、备注、供应商等） |
| `update_notify_channel` | 更新通知渠道 |
| `update_project_issue` | 更新项目 Issue |
| `update_user_profile` | 更新用户昵称/头像 |
| `update_vm` | 更新虚拟机（如续期、调整配置） |
| `upload_attachment` | 上传附件并返回 access_url |
| `upload_file` | 上传文件到 VM 的绝对路径 |
| `upload_object` | 直接 multipart 上传文件对象（POST /api/v1/uploader） |
| `wait_task` | 轮询任务直到进入终态 |
| `whoami` | 获取当前登录用户信息（get_user_status 别名） |
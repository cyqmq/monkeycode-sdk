# 更新日志

## [1.12.0] - 2026-10-31

### 新增
- `redact_sensitive()`：递归脱敏公共函数（api_key/token/secret/password/env 等字段打码为 `***`）
- `list_git_identities()` 返回前自动对 `access_token` 等敏感字段打码

### 修复
- `list_playground_posts()` / `get_license_status()` 遇到 `{'message': 'Not Found'}` 时抛出 `APIError`，不再静默返回
- CLI 所有命令统一捕获异常打印友好错误，不再直接 Traceback（假任务 ID、接口异常等）

### 改进（CLI 输出风格统一）
- `list-hosts`：状态 / 核心 / 内存 / 自建·公共（复用后台宿主摘要逻辑）
- `list-images`：名称 + ID + 默认标记 + 说明
- `list-available-models`：按分类分组输出（同 list-models 风格），并显示总数
- `list-tasks`：支持 `--limit N` 与 `--full`，显示中文状态与创建时间
- `list-projects`：空列表提示「暂无项目」，显示仓库名 + ID + URL
- `wallet-tx`：收支方向中文化（收入/支出）、金额换算为「点」、时间戳格式化
- `links`：只保留 MonkeyCode 预览域名，可访问/异常分组展示，过滤 localhost 与无关链接
- `terminal`：会话列表格式化输出（终端 ID / 状态 / 共享模式 / 创建时间）
- `list-model-providers`：非 JSON 响应容错展示，模型列表精简输出

## [1.11.0] - 2026-10-31

### 新增
- CLI `rounds` 支持 `--all`（分页拉取全部）、`--turn N`（只看指定轮次）、按 turn 折叠输出
- `round_tool_title(data)`：提取工具调用事件的工具名称
- 轮次解码脱敏：`call`/`call-response` 等事件中的 `execution_config.envs`、api_key/token/secret/password 等字段自动打码为 `***`，不再泄露到终端
- `agent_thought_chunk`（思考）、`usage_update`（用量）、`call`/`call-response`（调用/调用响应）分类与精简展示

### 改进
- `format_round_text` 对 `available_commands_update`/`tool_call` 返回纯内容（不再带「[可用命令更新]」「[工具调用]」前缀，避免与标签重复）
- CLI `rounds` 去重：连续相同的「命令更新」只显示一次；同一 turn 同一工具的状态流转（pending/in_progress/completed）只保留最后一条
- `group_models` 默认过滤 `is_hidden=true` 并按 id 去重（与平台页面一致）；CLI `list-models` 不再末尾重复刷「付费模型」整表
- CLI `run` 只从可见模型（我的/基础/专业/旗舰）中选第一个，不再误选隐藏模型
- CLI `send-msg` 使用 `format_round_text` + `round_label` 输出
- 会话过期自动重登缺少环境变量时，给出明确提示（先提示复用会话，失效时提示设置环境变量或 `python3 cli.py login`）
- 文档命令统一为 `python3 cli.py`

## [1.10.0] - 2026-10-31

### 新增
- `group_models(models)`：按页面分类本地分组模型列表（我的模型 `owner.type=private` / 基础 `access_level=basic` / 专业 `pro` / 旗舰 `ultra` / 付费 `is_free=false`），无需单独分类接口
- CLI `list-models` 增强：按分类分组输出模型（含付费标记）

## [1.9.0] - 2026-10-31

### 新增
- `round_kind(data, event=None)`：返回轮次语义分类（user / agent / tool / system / commands / other）
- `round_label(data, event=None)`：返回轮次友好中文标签（用户输入 / 任务开始 / 任务结束 / Agent / 工具 / 命令更新）
- CLI `rounds --color`：用 ANSI 颜色区分事件类型；默认输出中文标签

## [1.8.0] - 2026-10-31

### 新增
- CLI `rounds <task_id>`：解码任务轮次后按 `turn_seq` 打印（user-input 双层 base64、ACP `sessionUpdate` 分类精简）
- `format_round_text()`：把 rounds chunk 的 data 解码为可读短文本

### 改进
- CLI `get_credentials()`：已有 `~/.monkeycode_session.json`（或 `--session`）时不必再设 `MONKEYCODE_EMAIL` / `MONKEYCODE_PASSWORD`

## [1.7.5] - 2026-10-31

### 其他
- 仓库定位更新：README 改为描述 SDK 能力（认证/任务/WebSocket/文件/终端/团队管理/CLI），不再限定具体用途

## [1.7.4] - 2026-10-30

### 修复
- `Task.created_at` / `Task.completed_at` / `TaskRound.seq` 对非数字时间戳容错：无效输入返回 `None`，不再抛 `ValueError`
- 新增 3 个单元测试（共 61 个）

## [1.7.3] - 2026-10-30

### 修复
- `download_file` 解析 HTTP 200 + 业务错误 JSON：当 VM 不存在/被回收时（如 code=10231）抛出 `APIError`，不再把错误 JSON 当作文件内容静默返回
- 新增 2 个单元测试（共 58 个）

## [1.7.2] - 2026-10-30

### 改进
- **WebSocket 连接异常统一包装**：`TaskStream` / `ControlStream` / `TerminalStream` / `JoinTerminalStream` 的 `connect()` 不再抛出原始 `websockets.exceptions.InvalidStatus`，而是包装为 SDK 统一异常（401 → `AuthenticationError`，429 → `RateLimitError`，其他 → `APIError` 带状态码与响应文本）
- 新增 4 个连接异常包装单元测试（共 56 个）

## [1.7.1] - 2026-10-29

### 其他
- `pyproject.toml` 改用 SPDX `license = "MIT"`（消除打包警告）
- PyPI 发布改用 Trusted Publishing（OIDC）验证

## [1.7.0] - 2026-10-29

### 新增（工程化：测试 / CI / 架构文档）
- **单元测试**：52 个 pytest 用例（pow / links / models / stream / errors / client），全部 mock，不依赖真实平台
- **CI**：新增 GitHub Actions（Python 3.10/3.11/3.12 × 版本检查 + 编译检查 + pytest）
- **架构文档**：新增 `docs/架构说明.md`（模块划分、WebSocket 协议摘要、认证流程、健壮性机制）

### 修复
- `links.py`：`...` 占位符链接过滤失效（先清洗后检查导致）已修复；`http://localhost`（无端口）新增过滤规则

## [1.6.2] - 2026-10-29

### 修复
- `docs/API.md` 方法索引遗漏 9 个 async WebSocket/控制通道方法（send_task_message / switch_task_model / restart_task / switch_task_agent_resources / list_task_repo_files / read_task_repo_file / get_task_repo_diff / get_task_repo_changes / sync_client_ip），文档从 196 修正为 **205**
- 新增 `scripts/gen_api_doc.py` 文档生成脚本（同步 + 异步方法全覆盖），后续可一键重新生成

## [1.6.1] - 2026-10-29

### 修复
- `list_model_providers()` 补充必填参数 `provider` / `base_url` / `api_key`（可选 `api_header`），修复无参调用返回 400
- CLI `list-model-providers` 命令同步增加位置参数与 `--api-header`
- 冒烟测试中该项改为跳过（需要真实供应商 API Key）

## [1.6.0] - 2026-10-29

### 新增（体验层改进）
- **CLI 命令扩展**（+18 个）：任务（list-tasks/task-info/task-stop/task-delete/send-msg）、钱包（wallet/checkin/wallet-tx）、项目/环境（list-projects/options/vms/terminal）、API Key（api-key create/delete）、模型（list-available-models/list-model-providers）、会话控制（switch-model/restart）
- **分页 helper**：`paginate` 通用迭代器 + `iter_tasks` / `iter_projects`
- **错误友好化**：10606 登录失败、10205 主机不可调度等错误码附加中文提示
- **重试机制**：只读请求网络抖动自动重试（指数退避）；429 按 Retry-After 等待重试
- **冒烟测试扩展**：只读接口全覆盖（whoami/钱包/订阅/插件/技能/Git/MCP/通知/模型供应商/社区/团队读取）
- **示例代码**：新增 `examples/` 8 个可运行示例（快速开始/发消息/换模型/终端/钱包签到/Git/团队管理/会话持久化）
- **文档**：新增 `docs/API.md` 方法索引表

## [1.5.0] - 2026-10-29

### 新增（团队管理控制面补全，+34 方法，总计 202）
- **团队用户**：`team_get_user_status` / `team_change_password` / `team_add_user_with_password` / `team_update_user` / `team_reset_user_password`
- **团队分组**：`team_update_group`
- **团队宿主**：`team_get_host_install_command` / `team_update_host` / `team_delete_host`
- **团队镜像**：`team_create_image` / `team_update_image` / `team_delete_image`
- **团队模型**：`team_create_model` / `team_update_model` / `team_delete_model` / `team_model_health_check` / `team_get_model_health_check`
- **团队技能**：`team_create_skill` / `team_create_skill_package` / `team_update_skill` / `team_delete_skill`
- **团队 MCP**：`team_create_mcp_upstream` / `team_update_mcp_upstream` / `team_delete_mcp_upstream` / `team_sync_mcp_upstream`
- **团队通知**：`team_create_notify_channel` / `team_update_notify_channel` / `team_delete_notify_channel` / `team_test_notify_channel` / `team_list_notify_event_types`
- **团队 OAuth 站点**：`team_create_oauth_site` / `team_update_oauth_site` / `team_delete_oauth_site`
- **团队扩展包**：`team_create_extension_package`
- 覆盖自托管 MonkeyCode 管理员的完整控制面（团队 CRUD 写操作全量补齐）

## [1.4.1] - 2026-10-29

### 新增
- `is_logged_in()`：判断是否已有登录态（含从 session_path 加载的持久化会话），便于插件避免重复登录

## [1.4.0] - 2026-10-29

### 新增
- **认证恢复**：`session_path` 会话 Cookie 持久化（登录一次免重复登录）+ `_request` 401 自动重登一次并重试原请求（`auto_relogin` 可关闭）
- **AgentSession**：任务高层会话封装（断线自动重连 + asyncio 事件缓冲 + 发送前确保连接可用），导出 `AgentSession`
- **CLI**：支持 `--session` 持久化，`login` 后其他命令免重复登录

## [1.3.0] - 2026-10-29

### 新增（剩余缺失功能补全，总计 ~166 方法）
- **用户/会话**：`get_user_status` / `whoami` / `logout` / `team_logout` / `team_list_conversations`
- **密码重置辅助**：`get_reset_password_account`
- **直接上传**：`upload_object`（POST /api/v1/uploader，multipart 直传）
- **任务控制调用封装**：`switch_task_agent_resources`（技能/插件）、`restart_task`、`list_task_repo_files`、`read_task_repo_file`、`get_task_repo_diff`、`get_task_repo_changes`、`sync_client_ip`
- **共享终端**：`join_terminal`（WebSocket，密码加入）
- **CLI**：新增 `whoami` / `logout` 命令

## [1.2.0] - 2026-10-29

### 新增（配置管理补全，+17 方法，总计 152）
- **Git 身份**：`update_git_identity` / `delete_git_identity`
- **AI 大模型管理**：`create_model` / `update_model` / `delete_model` / `list_model_providers` / `model_health_check`（批量）/ `get_model_health_check`（单个）
- **宿主机管理**：`create_host` / `update_host` / `delete_host` / `get_host_install_command`
- **开发环境 / VM**：`create_vm` / `update_vm` / `list_port_forwards` / `add_port_forward` / `delete_port_forward`

## [1.1.0] - 2026-10-25

### 新增
- **会话换模型**：`switch_task_model` / `open_task_control`（WebSocket 控制通道 `/tasks/control`，data 需 base64(JSON)）
- **命令下拉选项**：`get_task_options` 聚合 models/images/hosts/projects/plan 一次返回
- **终端**：`list_terminal_sessions` / `share_terminal` / `close_terminal` / `open_terminal`（REST + WebSocket 交互，支持 data/resize）
- 导出 `ControlStream` / `TerminalStream`

### 其他
- 新增 `scripts/check_version.py` 发布前版本一致性检查

## [1.0.1] - 2026-10-25

### 文档
- README 拆分为精简主文档 + `docs/` 专题文档（认证说明 / 功能参考 / CLI / 已知问题）

## [1.0.0] - 2026-10-25

### 新增（完整覆盖 MonkeyCode REST API）
- **镜像 CRUD**：`create_image` / `update_image` / `delete_image`
- **订阅管理**：`create_subscription` / `set_auto_renew` / `set_credit_consumption`
- **邀请列表**：`list_invitations`
- **MCP 管理**：`list/create/update/delete_mcp_upstream`、`sync_mcp_upstream`、`set_mcp_tool`
- **通知渠道**：`list/create/update/delete/test_notify_channel`、`list_notify_event_types`
- **账号/密码**：`update_user_profile` / `delete_account` / `change_password` / `request_password_reset` / `reset_password`
- **Git Bots 补全**：`update_git_bot` / `delete_git_bot` / `share_git_bot`
- **成员/统计**：`list_members` / `get_public_stats`
- **邮箱/微信绑定**：`bind_email_request` / `bind_wechat_qrcode` / `unbind_wechat`
- **社区**：`list_playground_posts` / `create_playground_post` / `create_playground_task_post`
- **License**：`get_license_status` / `get_license_machine_code` / `import_license`
- **Git 平台授权 URL**：`get_cnb/gitea/gitee/gitlab_authorize_url`、`get_gitea_sites`、`get_gitlab_sites`
- **OAuth/OIDC URL**：`build_oauth_login_url` / `build_oidc_login_url`
- **语音转文字**：`speech_to_text`
- **团队管理控制面**：`team_*` 系列（分组/用户/宿主/镜像/模型/技能/项目/任务/OIDC/MCP/通知/OAuth 站点/扩展包/VM 策略/审计/Dashboard/初始化）

### 里程碑
- SDK 升级到 **1.0.0**：核心功能 + 管理/扩展功能完整覆盖 MonkeyCode REST API，进入稳定阶段

## [0.1.11] - 2026-10-25

### 新增
- **可用模型**：`list_available_models()`
- **Issue 补全**：`create_project_issue` / `update_project_issue` / `delete_project_issue` / `list_issue_comments` / `add_issue_comment`
- **文件管理补全**：`move_file` / `copy_file` / `delete_file`
- **VM 管理**：`get_vm` / `delete_vm`
- **任务流控制**：`TaskStream.send_reply_question`（回复 AI 提问）、`send_auto_approve`（自动批准开关）、`send_control`（任意控制类型）

## [0.1.10] - 2026-10-25

### 新增
- `create_task` 支持 **attachments 附件**（最多 10 个 `{url, filename}`）
- **附件上传**：`presign_upload(filename)` 获取预签名信息，`upload_attachment()` 上传并返回 access_url
- **任务删除**：`delete_task(task_id)`
- **插件/技能列表**：`list_plugins()` / `list_skills()`
- **钱包交易记录**：`get_wallet_transactions()`
- **Git 分支列表**：`list_git_branches(identity_id, repo_full_name)`（自动 URL 编码）

## [0.1.9] - 2026-10-25

### 新增
- **预览链接提取**：`list_task_links(task_id)` 从任务轮次历史中提取 AI 拉起的预览链接（MonkeyCode 预览域名 / localhost / 8000 端口），去重计数并做 HTTP 存活检测
- 新增 `monkeycode/links.py`：base64 解码、转义还原、URL 正则提取、清洗过滤、存活探测
- CLI 新增 `links <task_id>` 子命令，输出 [在线]/[异常]/[已关闭] + URL + 出现次数

## [0.1.8] - 2026-10-25

### 新增
- **文件管理**：
  - `list_folders(vm_id, path)`：虚拟机目录列表
  - `upload_file(vm_id, path, file_path | file_bytes+filename)`：上传文件到 VM
  - `download_file(vm_id, path, filename)`：下载 VM 文件内容（bytes）

## [0.1.7] - 2026-10-25

### 新增
- **钱包/签到**：`get_wallet()`、`checkin()`（每日签到自动 PoW）、`get_subscription()`
- **项目管理**：`create_project()`、`get_project_tree()`、`get_project_file()`、`list_project_issues()`；`list_projects()` 支持分页
- **Git 身份**：`list_git_identities()`、`add_git_identity()`
- **Git Bots**：`list_git_bots()`、`create_git_bot()`、`list_git_bot_tasks()`

## [0.1.6] - 2026-10-25

### 新增
- **WebSocket 任务会话交互**：
  - `send_task_message(task_id, content, attachments=None)`：进入任务会话发送用户消息，返回首批事件
  - `open_task_stream(task_id, mode="new")`：实时流上下文管理器（可订阅任务运行过程）
  - `monkeycode/stream.py`：上行 user-input 编码、下行事件解码、基于 websockets 的连接管理
- 新增模型 `TaskStreamChunk`、`UserInputPayload`

### 依赖
- 新增 `websockets>=12`

### 变更
- `create_task` 的 `repo` 参数改为可选：**不绑定 Git 仓库也能创建任务**（传空 `RepoReq` 即可）
- 文档说明：MonkeyCode 任务不强制绑定仓库

## [0.1.4] - 2026-10-25

### 新增
- **团队管理员登录**：`team_login(email, password)` 走 `POST /api/v1/teams/users/login`，自动 PoW 求解，保存团队会话 Cookie `monkeycode_ai_team_session`
- **自托管支持**：新增 `get_server_config()` 读取公开配置（含 `captcha_enabled`）；自托管部署只需改 `base_url`，验证码关闭时自动直接登录

### 文档
- README 说明 OhMyAgent API Key 的真实用途：不是 REST 会话凭证，而是 OhMyAgent 代理 Key（`X-OhMyAgent-Signature` 签名）

## [0.1.3] - 2026-10-25

### 新增
- **PoW 验证码自动求解**：`login()` 自动完成 challenge -> 本地 SHA-256 前缀碰撞求解 -> redeem -> 登录，无需人工输入验证码
- 新增 `monkeycode/pow.py`：FNV-1a 播种 + xorshift32 PRNG + nonce 爆破（实测 50 个子质询约 0.1s）

### 变更
- `cli.py` / `smoke_test.py` 登录不再需要交互输入验证码，全部自动处理

## [0.1.2] - 2026-10-25

### 新增
- `create_task` 内置**默认建任务档位**：`host_id="public_host"`、`cli_name=opencode`、资源默认 2核/8GB/3小时；`image_id/model_id` 留空时自动取列表第一个
- 支持任务扩展配置：`skill_ids` / `plugin_ids` / `project_id` / `issue_id`（写入 `extra`）
- 新增 `list_tasks`（支持 page/size/status/project_id/quick_start/next_token 筛选）
- 新增 `get_task_rounds`、`get_task_user_inputs`（任务过程查询）
- 新增 `create_api_key` / `delete_api_key`（OhMyAgent API Key 管理）

### 变更
- 新增数据模型：`TaskExtraConfig`、`TaskRound`、`APIKeyInfo`；`Task` 增加 title/summary/branch/model/image/extra 等属性

## [0.1.1] - 2026-10-25

### 修复
- **密码传输**：改为默认发送**明文密码**（生产平台使用 bcrypt 直接校验明文，swagger 的 MD5 注释已过时）；保留 `password_md5=True` 兼容私有化部署
- **列表接口**：`list_hosts/list_images/list_models` 自动提取嵌套的 `hosts/images/models` 字段，解决 `KeyError: 0`
- **CLI**：`list-hosts/list-images/list-models/run` 命令先自动登录再调用接口
- README 更新认证说明（明文密码、列表结构、CLI 自动登录）

### 已知问题（平台侧）
- 创建任务可能返回 `code=10205 主机不在线`：列表里 `status=online` 的宿主实际 taskflow 代理可能不可调度，需在 MonkeyCode 控制台确认/重建云端环境

## [0.1.0] - 2026-10-25

### 新增
- `MonkeyCodeClient`：密码登录（MD5）、验证码 challenge/redeem、会话 Cookie 自动管理
- 枚举环境：`list_hosts` / `list_images` / `list_models` / `list_projects`
- 任务：`create_task` / `get_task` / `wait_task` / `stop_task`
- 命令行验证入口 `cli.py`（login / list-* / run）
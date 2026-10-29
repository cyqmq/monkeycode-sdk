# 更新日志

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
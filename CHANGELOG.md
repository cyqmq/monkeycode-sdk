# 更新日志

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
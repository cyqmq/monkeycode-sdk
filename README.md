# monkeycode-sdk

MonkeyCode 云平台 REST API 的 Python SDK。用于在任意 Python 项目/聊天框架（AstrBot、NoneBot 等）中：
认证登录 → 创建 AI 编程任务 → 轮询结果，让机器人像人一样使用 MonkeyCode。

## 安装

```bash
pip install monkeycode-sdk
```

或从源码安装：

```bash
git clone https://github.com/cyqmq/monkeycode-sdk.git
cd monkeycode-sdk
pip install -e .
```

## 快速开始

```python
from monkeycode import MonkeyCodeClient
from monkeycode.models import RepoReq

client = MonkeyCodeClient(email="you@example.com", password="your_password")
client.login()  # PoW 验证码自动求解

# 枚举环境
hosts = client.list_hosts()
images = client.list_images()
models = client.list_models()

# 创建任务（默认档位：public_host / opencode / 2核8GB3小时）
task = client.create_task(
    content="修复登录接口的异常处理",
    repo=RepoReq(repo_url="https://github.com/org/repo", branch="main"),
    skill_ids=["feature-design", "project-wiki"],
)

# 任务列表与过程
tasks = client.list_tasks(status="pending,processing")
rounds = client.get_task_rounds(task.id)
user_inputs = client.get_task_user_inputs(task.id)

# 轮询结果
result = client.wait_task(task.id, timeout=1800, interval=10)
print(result.status, result.pr_url)

# OhMyAgent API Key（明文仅返回一次，立即保存）
key = client.create_api_key()
print(key.api_key)
client.delete_api_key(key.key_id)
```

## 命令行验证

```bash
export MONKEYCODE_EMAIL=you@example.com
export MONKEYCODE_PASSWORD=your_password

python cli.py login          # 登录（PoW 验证码自动求解）
python cli.py list-hosts     # 列出云端环境（自动先登录）
python cli.py list-images    # 列出镜像（自动先登录）
python cli.py list-models    # 列出模型（自动先登录）
python cli.py run "写一个 hello world"
```

除 `login` 外的命令会自动先执行登录。

## 认证说明

- 登录接口 `POST /api/v1/users/password-login`，**传明文密码**。
  生产平台 `monkeycode-ai.com` 使用 bcrypt 存储并直接校验明文（swagger 中"MD5"注释已过时）。
  如你的私有化部署仍要求 MD5，构造客户端时传 `password_md5=True` 兼容。
- 云平台强制启用 **PoW 验证码**（SHA-256 前缀碰撞，非图片），SDK **自动求解**：
  1. `POST /api/v1/public/captcha/challenge` 获取质询参数（c/s/d + token）
  2. 本地对每个子质询爆破 nonce，使 `sha256(salt + nonce)` 以 target 开头（约 0.1s）
  3. `POST /api/v1/public/captcha/redeem` 提交 solutions，得到 `captcha_token`
  4. 携带 `captcha_token` 登录
  实现见 `monkeycode/pow.py`。
- **团队管理员登录**：`client.team_login(email, password)` 走
  `POST /api/v1/teams/users/login`，成功后保存团队会话 Cookie
  `monkeycode_ai_team_session`；PoW 验证码同样自动求解。
- **自托管支持**：构造客户端时传 `base_url` 指向自托管地址即可。
  可用 `client.get_server_config()` 读取 `captcha_enabled` 等公开配置；
  若自托管关闭了验证码，`login()` 会直接成功（无需 PoW）。
- 列表接口返回嵌套结构，SDK 已自动提取：
  - `list_hosts()` → `data["hosts"]`
  - `list_images()` → `data["images"]`
  - `list_models()` → `data["models"]`
- 登录成功后自动保存会话 Cookie `monkeycode_ai_session`，后续请求自动携带。

## 安全提示

- 不要在公共仓库/聊天中泄露你的密码。
- **OhMyAgent API Key 不是 REST 会话凭证**：`create_api_key() / delete_api_key()`
  已支持管理该 Key，但它用于 OhMyAgent 代理（走 `X-OhMyAgent-Signature` 签名，
  LLM 请求的 `model` 字段传模型配置 ID），不能替代 Cookie 调用 `/api/v1` 主 API。
- SDK 不落盘任何凭证。

## 已知问题（平台侧）

- 创建任务时可能返回 `code=10205 主机不在线`：列表接口中 `status=online` 的宿主，
  其底层 taskflow 代理可能实际不可调度。这是 MonkeyCode 云平台/环境问题，非 SDK 问题。
  请在 MonkeyCode 控制台确认云端环境已真正启动，或重建一个环境后再试。

## 开发

```bash
pip install -e .
pytest
```

## 文档与参考

- API 定义基于 MonkeyCode 开源仓库 `chaitin/MonkeyCode` 的 `backend/docs/swagger.json`。
- 认证机制参考 `backend/middleware/auth.go` 与 `backend/pkg/session/session.go`。
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
client.login()  # 如遇验证码，先 create_captcha/redeem_captcha

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

python cli.py login          # 登录（验证码会提示输入答案）
python cli.py list-hosts     # 列出云端环境（自动先登录）
python cli.py list-images    # 列出镜像（自动先登录）
python cli.py list-models    # 列出模型（自动先登录）
python cli.py run "写一个 hello world"
```

除 `login` 外的命令会自动先执行登录，登录失败或需要验证码时会在终端提示。

## 认证说明

- 登录接口 `POST /api/v1/users/password-login`，**传明文密码**。
  生产平台 `monkeycode-ai.com` 使用 bcrypt 存储并直接校验明文（swagger 中"MD5"注释已过时）。
  如你的私有化部署仍要求 MD5，构造客户端时传 `password_md5=True` 兼容。
- 列表接口返回嵌套结构，SDK 已自动提取：
  - `list_hosts()` → `data["hosts"]`
  - `list_images()` → `data["images"]`
  - `list_models()` → `data["models"]`
- 云平台启用了验证码（`captcha_enabled: true`），登录可能返回需要 `captcha_token`。
  流程：
  1. `POST /api/v1/public/captcha/challenge` 获取验证码质询
  2. 人工/OCR 解出答案（整数数组）
  3. `POST /api/v1/public/captcha/redeem` 兑换得到 `captcha_token`
  4. 将 `captcha_token` 传入 `login()`
- 登录成功后自动保存会话 Cookie `monkeycode_ai_session`，后续请求自动携带。

## 安全提示

- 不要在公共仓库/聊天中泄露你的密码。
- 建议登录一次后创建 **API Key**（`POST /api/v1/users/ohmyagent/api-keys`），后续用 Key 认证（SDK 的 API Key 支持将在后续版本加入）。
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
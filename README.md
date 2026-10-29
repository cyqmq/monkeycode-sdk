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

# 创建任务
task = client.create_task(
    content="修复登录接口的异常处理",
    repo=RepoReq(repo_url="https://github.com/org/repo", branch="main"),
    host_id=hosts[0]["id"],
    image_id=images[0]["id"],
    model_id=models[0]["id"],
)

# 轮询结果
result = client.wait_task(task.id, timeout=1800, interval=10)
print(result.status, result.pr_url)
```

## 命令行验证

```bash
export MONKEYCODE_EMAIL=you@example.com
export MONKEYCODE_PASSWORD=your_password

python cli.py login          # 登录（验证码会提示输入答案）
python cli.py list-hosts     # 列出云端环境
python cli.py list-images    # 列出镜像
python cli.py list-models    # 列出模型
python cli.py run "写一个 hello world"
```

## 认证说明

- 登录接口 `POST /api/v1/users/password-login`，密码以 **MD5** 传输。
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

## 开发

```bash
pip install -e .
pytest
```

## 文档与参考

- API 定义基于 MonkeyCode 开源仓库 `chaitin/MonkeyCode` 的 `backend/docs/swagger.json`。
- 认证机制参考 `backend/middleware/auth.go` 与 `backend/pkg/session/session.go`。
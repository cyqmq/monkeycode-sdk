# monkeycode-sdk

MonkeyCode 云平台 REST API 的 Python SDK。用于在任意 Python 项目/聊天框架（AstrBot、NoneBot 等）中：
认证登录 → 创建 AI 编程任务 → 轮询结果，让机器人像人一样使用 MonkeyCode。

**特性**
- 密码登录 / 团队登录 / PoW 验证码全自动求解
- 任务创建（附件、技能、默认档位）、列表、轮询、WebSocket 实时会话
- 任务控制通道：切换模型、端口转发等同步调用
- 项目管理、Git 身份、Git Bots、钱包签到、文件/VM 管理、预览链接
- 虚拟机终端：会话管理（REST）+ 实时交互（WebSocket）
- 覆盖完整 REST API（镜像/MCP/通知/团队管理/License/社区等）
- 支持自托管部署

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

# 创建任务（默认档位；repo 可空）
task = client.create_task(
    content="修复登录接口的异常处理",
    repo=RepoReq(repo_url="https://github.com/org/repo", branch="main"),
    skill_ids=["feature-design", "project-wiki"],
)

# 轮询结果
result = client.wait_task(task.id, timeout=1800, interval=10)
print(result.status, result.pr_url)
```

## 文档导航

| 文档 | 内容 |
|---|---|
| [docs/认证说明.md](docs/认证说明.md) | 密码/PoW/团队登录、自托管、安全提示 |
| [docs/功能参考.md](docs/功能参考.md) | 全部功能方法示例（任务/项目/Git/钱包/文件/预览/管理） |
| [docs/CLI.md](docs/CLI.md) | 命令行使用 |
| [docs/已知问题.md](docs/已知问题.md) | 平台侧已知问题、开发与参考 |

完整变更见 [CHANGELOG.md](CHANGELOG.md)。
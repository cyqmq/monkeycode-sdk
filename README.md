# monkeycode-sdk

MonkeyCode 云平台 REST API 的 Python SDK。用于在任意 Python 项目/聊天框架（AstrBot、NoneBot 等）中：
认证登录 → 创建 AI 编程任务 → 轮询结果，让机器人像人一样使用 MonkeyCode。

**特性**
- 密码登录 / 团队登录 / PoW 验证码全自动求解
- 会话持久化：Cookie 保存到文件，长期运行自动重登（401 自动恢复）
- 任务创建（附件、技能、默认档位）、列表、轮询、WebSocket 实时会话
- AgentSession 高层封装：断线自动重连 + 事件缓冲
- 任务控制通道：切换模型、重启、技能/插件、仓库文件 diff/changes 等同步调用
- 项目管理、Git 身份、Git Bots、钱包签到、文件/VM 管理、预览链接
- 虚拟机终端：会话管理（REST）+ 实时交互/共享加入（WebSocket）
- 用户与会话：whoami / logout / 团队会话列表
- 配置管理：模型/宿主机/VM/端口转发/Git 身份 CRUD 与健康检查
- 团队管理：用户/分组/宿主/镜像/模型/技能/MCP/通知/OAuth/扩展包完整控制面
- 分页迭代：`iter_tasks` / `iter_projects` / `paginate` 自动翻页
- 健壮性：只读请求自动重试（指数退避）、429 限流等待、错误提示友好化
- CLI：25+ 命令（任务/钱包/项目/终端/API Key/会话控制）
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
| [docs/API.md](docs/API.md) | 全部公开方法索引表（205 个） |
| [docs/架构说明.md](docs/架构说明.md) | 模块划分、WebSocket 协议摘要、认证流程 |
| [docs/CLI.md](docs/CLI.md) | 命令行使用 |
| [docs/已知问题.md](docs/已知问题.md) | 平台侧已知问题、开发与参考 |

完整变更见 [CHANGELOG.md](CHANGELOG.md)。
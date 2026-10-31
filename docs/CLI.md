# 命令行（CLI）

## 环境变量

```bash
export MONKEYCODE_EMAIL=you@example.com
export MONKEYCODE_PASSWORD=your_password
# 可选：自托管
# export MONKEYCODE_BASE_URL=https://你的域名
# 可选：会话持久化文件路径（默认 ~/.monkeycode_session.json）
# export MONKEYCODE_SESSION=/path/to/session.json
```

## 登录与账户

```bash
python cli.py login                       # 登录（PoW 验证码自动求解，会话保存到 --session）
python cli.py whoami                      # 显示当前登录账户信息
python cli.py logout                      # 退出当前会话
```

除 `login` 外的命令会自动复用持久化会话（`~/.monkeycode_session.json` 或 `--session`）；已有会话文件时不必再设邮箱密码环境变量。会话失效时 SDK 自动重登（此时仍需环境变量）。

## 任务

```bash
python cli.py run "写一个 hello world"        # 创建任务并轮询结果
python cli.py list-tasks                      # 列出最近任务
python cli.py task-info <task_id>             # 查看任务详情
python cli.py task-stop <task_id>             # 停止任务
python cli.py task-delete <task_id>           # 删除任务
python cli.py send-msg <task_id> "继续"       # 向运行中的任务发送消息
python cli.py links <task_id>                 # 列出任务预览链接及存活状态
python cli.py switch-model <task_id> <model_id>  # 切换运行中任务的模型
python cli.py restart <task_id>               # 重启任务
python cli.py rounds <task_id> [--limit 20]   # 查看执行轮次（解码后按 turn_seq 打印）
```

## 环境 / 项目

```bash
python cli.py list-hosts          # 列出云端环境
python cli.py list-images         # 列出镜像
python cli.py list-models         # 列出模型
python cli.py list-available-models   # 列出可用模型
python cli.py list-model-providers <provider> <base_url> <api_key> [--api-header xxx]
                                      # 列出模型供应商的模型列表（provider/base_url/api_key 必填）
python cli.py vms                 # 列出各宿主下的虚拟机
python cli.py terminal <vm_id>    # 列出虚拟机终端会话
python cli.py list-projects       # 列出项目（仓库）
python cli.py options             # 显示创建任务的下拉选项统计
```

## 钱包

```bash
python cli.py wallet       # 查看钱包余额
python cli.py checkin      # 每日签到（自动求解 PoW）
python cli.py wallet-tx    # 查看钱包交易记录
```

## API Key

```bash
python cli.py api-key create            # 创建 API Key（仅显示一次）
python cli.py api-key delete <key_id>   # 删除 API Key
```
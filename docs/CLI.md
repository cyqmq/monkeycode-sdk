# 命令行（CLI）

## 环境变量

```bash
export MONKEYCODE_EMAIL=you@example.com
export MONKEYCODE_PASSWORD=your_password
# 可选：自托管
# export MONKEYCODE_BASE_URL=https://你的域名
```

## 命令

```bash
python cli.py login          # 登录（PoW 验证码自动求解）
python cli.py list-hosts     # 列出云端环境（自动先登录）
python cli.py list-images   # 列出镜像（自动先登录）
python cli.py list-models    # 列出模型（自动先登录）
python cli.py run "写一个 hello world"   # 创建任务并轮询
python cli.py links <task_id>           # 列出任务预览链接及存活状态
```

除 `login` 外的命令会自动先执行登录。
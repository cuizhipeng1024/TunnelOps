# TunnelOps

内网设备反向隧道运维平台 —— 通过公网 Server 访问无固定公网 IP 的内网 Agent 设备。

## 架构

```
┌─────────────┐     HTTPS/WSS      ┌──────────────────┐
│  Web 浏览器  │ ◄────────────────► │  TunnelOps Server │ (公网)
└─────────────┘                    │  - Web 管理界面    │
                                   │  - 反向隧道网关    │
                                   │  - SSH 桥接       │
                                   └────────┬─────────┘
                                            │ WSS 出站连接
                                   ┌────────▼─────────┐
                                   │  Agent (内网设备)  │
                                   │  - 主动连接 Server │
                                   │  - 转发本地 SSH    │
                                   └────────┬─────────┘
                                            │
                                   ┌────────▼─────────┐
                                   │  本地 SSH 服务     │
                                   └──────────────────┘
```

## 功能

| 功能 | 说明 |
|------|------|
| 反向隧道 | Agent 主动连接公网 Server，无需内网设备有公网 IP |
| Shell 访问 | Web 终端通过反向隧道 SSH 到内网设备 |
| 密码/密钥登录 | 支持 SSH 密码或用户配置的通用私钥 |
| 设备管理 | Agent 增删改查、在线状态、Token 管理 |
| 一键部署 | 生成 bash 脚本，内网设备一条命令安装 Agent |
| 审计日志 | 登录、连接、设备/用户变更等操作记录 |
| 用户管理 | 管理员可管理平台账号 |

## 快速开始

### 1. 启动 Server

```bash
cd server
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
# source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # 生产环境请修改 SECRET_KEY
python -m app.main
```

默认管理员：`admin` / `admin123`（首次启动自动创建，请立即修改密码）

### 2. 启动 Web 前端（开发模式）

```bash
cd web
npm install
npm run dev
```

访问 http://localhost:3000

### 3. 生产部署（构建前端）

```bash
cd web
npm install
npm run build   # 输出到 server/static/web
cd ../server
python -m app.main
```

访问 http://your-server:8080

### 4. 部署 Agent（内网设备）

1. 在 Web 界面「设备管理」中添加设备
2. 点击「部署」，复制一键部署脚本
3. 在内网 Linux 设备上执行（需要 root、python3、curl）：

```bash
curl -fsSL https://your-server/static/agent/agent.py -o /tmp/agent.py
# 或使用界面生成的完整安装脚本
```

手动运行 Agent：

```bash
cd agent
pip install -r requirements.txt
export TUNNELOPS_SERVER=http://your-server:8080
export TUNNELOPS_TOKEN=<设备Token>
export TUNNELOPS_NAME=my-device
python agent.py
```

### 5. 连接设备

1. 确认 Agent 状态为「在线」
2. 点击「连接」进入 Web 终端
3. 选择密码或密钥认证，建立 SSH 会话

## 配置

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `SECRET_KEY` | JWT 签名密钥 | 需修改 |
| `DATABASE_URL` | 数据库连接 | SQLite 本地文件 |
| `SERVER_HOST` | 监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 监听端口 | `8080` |

Agent 环境变量：

| 变量 | 说明 |
|------|------|
| `TUNNELOPS_SERVER` | Server 公网地址 |
| `TUNNELOPS_TOKEN` | 设备 Token（Web 界面获取） |
| `TUNNELOPS_NAME` | 设备名称 |

## 安全建议

- 生产环境必须使用 HTTPS（反向代理如 Nginx + Let's Encrypt）
- 立即修改默认管理员密码
- 设置强 `SECRET_KEY`
- 定期轮换 Agent Token
- 限制 Server 端口的访问来源

## 项目结构

```
TunnelOps/
├── server/          # FastAPI 后端 + 隧道服务
│   ├── app/
│   └── static/      # Agent 脚本 & 构建后的 Web
├── agent/           # Agent 客户端
├── web/             # React 前端
└── README.md
```

## 技术栈

- **Server**: Python, FastAPI, SQLAlchemy, Paramiko
- **Agent**: Python, websockets
- **Web**: React, TypeScript, Ant Design, xterm.js
# TunnelOps

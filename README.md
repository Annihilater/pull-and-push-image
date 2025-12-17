# Docker Image Sync

从 DockerHub 拉取多平台镜像并推送到内网 Harbor 的一键同步工具。

## 功能特性

- **跨平台镜像同步**：支持同时拉取 AMD64 和 ARM64 架构的镜像
- **多平台 Manifest**：自动创建并推送多平台 manifest
- **实时进度**：前端实时显示同步进度和日志
- **Harbor 认证**：支持配置 Harbor 用户名密码
- **多种同步方式**：
  - Docker + Buildx：使用 Docker 原生命令
  - Skopeo（可选）：更高效的镜像复制，无需本地存储

## 技术栈

### 后端

- Python 3.10+
- FastAPI
- Uvicorn

### 前端

- React 18
- Vite
- TailwindCSS

## 前置要求

1. **Docker**：必须安装并运行

   ```bash
   docker --version
   ```

2. **Docker Buildx**（推荐）：用于多平台支持

   ```bash
   docker buildx version
   ```

3. **Skopeo**（可选）：更高效的镜像同步

   ```bash
   # macOS
   brew install skopeo
   
   # Ubuntu
   apt-get install skopeo
   ```

4. **Node.js 18+**：用于前端开发

   ```bash
   node --version
   ```

5. **Python 3.10+**：用于后端服务

   ```bash
   python3 --version
   ```

## 快速开始

### 1. 启动后端

```bash
# 方式一：使用启动脚本
chmod +x start-backend.sh
./start-backend.sh

# 方式二：手动启动
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端启动后访问 <http://localhost:8000/docs> 查看 API 文档。

### 2. 启动前端

```bash
# 方式一：使用启动脚本
chmod +x start-frontend.sh
./start-frontend.sh

# 方式二：手动启动
cd frontend
npm install
npm run dev
```

前端启动后访问 <http://localhost:5173>

## 使用方法

1. 打开前端页面 <http://localhost:5173>
2. 输入源镜像地址（如 `nginx:latest` 或 `bitnami/redis:7.0`）
3. 输入目标 Harbor 地址（如 `harbor.company.com`）
4. 配置 Harbor 认证（点击"Harbor 认证"按钮）
5. 选择需要同步的平台架构（AMD64/ARM64）
6. 点击"开始同步"按钮

## 配置说明

### 环境变量

可以通过 `.env` 文件配置默认的 Harbor 凭据：

```bash
cd backend
cp .env.example .env
# 编辑 .env 文件
```

```env
HARBOR_REGISTRY=harbor.company.com
HARBOR_USERNAME=admin
HARBOR_PASSWORD=your_password
```

### API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/health | 健康检查 |
| GET | /api/config | 获取系统配置状态 |
| POST | /api/config/harbor | 设置 Harbor 配置 |
| POST | /api/sync | 创建同步任务 |
| GET | /api/sync/{task_id} | 获取任务进度 |
| GET | /api/tasks | 列出所有任务 |

## 工作原理

### 使用 Docker 方式

1. 登录到目标 Harbor
2. 分别拉取各平台架构的镜像 (`docker pull --platform linux/amd64`)
3. 为每个平台的镜像打标签
4. 推送各平台镜像到 Harbor
5. 创建并推送多平台 manifest

### 使用 Skopeo 方式（如果可用）

1. 使用 `skopeo copy --all` 直接复制镜像
2. 自动处理所有平台架构
3. 无需本地存储，更高效

## 常见问题

### 1. Docker 未运行

确保 Docker Desktop 或 Docker daemon 正在运行。

### 2. Harbor 登录失败

- 检查 Harbor 地址是否正确
- 确认用户名密码正确
- 检查 Harbor 是否配置了 HTTPS（如果是自签名证书，可能需要配置 Docker 信任）

### 3. 某些平台拉取失败

并非所有镜像都提供多平台版本，这种情况下会跳过不存在的平台。

## 项目结构

```bash
pull-and-push-image/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py      # API 路由
│   │   ├── models/
│   │   │   └── schemas.py     # 数据模型
│   │   ├── services/
│   │   │   └── image_sync.py  # 同步服务
│   │   ├── config.py          # 配置
│   │   └── main.py            # 入口
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # 主组件
│   │   ├── main.jsx           # 入口
│   │   └── index.css          # 样式
│   ├── package.json
│   └── vite.config.js
├── start-backend.sh           # 后端启动脚本
├── start-frontend.sh          # 前端启动脚本
└── README.md
```

## License

MIT

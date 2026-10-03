# 安装指南

## 快速开始

### 1. 安装 uv

如果还没有安装 uv，使用以下命令安装：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

### 2. 安装项目依赖

```bash
# uv 会自动创建虚拟环境并安装依赖
uv sync
```

### 3. 构建前端资源

```bash
# 安装前端依赖
pnpm install

# 构建前端资源
pnpm run build
```

### 4. 启动 PostgreSQL

#### 方式一：使用 Docker Compose（推荐）

```bash
docker-compose up -d
```

#### 方式二：使用已有的 PostgreSQL

先建好数据库（如 `createdb fg`），并在 `.env` 文件中配置 `DATABASE_URL`。表会在应用启动时自动创建。

### 5. 配置环境变量

复制示例配置文件并修改：

```bash
# 创建 .env 文件
cat > .env << 'EOF'
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fg
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
JWT_SECRET_KEY=$(openssl rand -hex 32 | head -c 64)
CACHE_TTL_SECONDS=60
EOF
```

### 6. 启动应用

```bash
# 使用 uv 运行
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或者先激活虚拟环境
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. 访问系统

打开浏览器访问：

- 主页: http://localhost:8000
- 登录页: http://localhost:8000/login
- 管理页: http://localhost:8000/admin
- API 文档: http://localhost:8000/docs

### 8. 初始登录

使用在 `.env` 中配置的管理员账户登录：

- 用户名: admin
- 密码: admin123（或您设置的密码）

## 验证安装

运行测试脚本验证系统功能：

```bash
python3 test_api.py
```

预期输出：

```
==================================================
Feature Gating 系统功能测试
==================================================

✓ 测试 1: 检查模块导入...
  ✓ 所有模块导入成功

✓ 测试 2: 检查配置...
  ✓ 配置加载成功

✓ 测试 3: 测试密码哈希...
  ✓ 密码哈希验证成功

✓ 测试 4: 测试字段哈希...
  ✓ 字段哈希成功且稳定

✓ 测试 5: 测试条件计算...
  ✓ 条件计算成功

✓ 测试 6: 测试缓存...
  ✓ 缓存功能正常

==================================================
✅ 所有测试通过！
==================================================
```

## 常见问题

### Q: PostgreSQL 连接失败

**A:** 检查以下几点：
1. PostgreSQL 服务是否已启动、数据库是否已创建
2. `.env` 文件中的 `DATABASE_URL` 是否正确
3. 防火墙是否允许连接

### Q: 依赖安装失败

**A:** 尝试清除缓存并重新安装：

```bash
# 清除 uv 缓存
uv cache clean

# 重新同步依赖
uv sync
```

### Q: 端口 8000 已被占用

**A:** 使用不同端口启动：

```bash
uvicorn app.main:app --reload --port 8001
```

### Q: 无法创建管理员用户

**A:** 检查 PostgreSQL 是否正常运行，并查看应用启动日志。

## 开发环境配置

### 安装开发依赖

```bash
uv pip install black isort ruff pytest pytest-asyncio httpx
```

### 代码格式化

```bash
# 使用 ruff (推荐)
uv run ruff format app/

# 或使用 black
uv run black app/
uv run isort app/
```

### 运行 Linter

```bash
# 使用 ruff (推荐)
uv run ruff check app/

# 或使用 flake8
uv run flake8 app/
```

## 生产环境部署

### 使用 Gunicorn + Uvicorn

```bash
# 安装 gunicorn
uv pip install gunicorn

# 启动服务
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### 使用 Systemd 服务

创建 `/etc/systemd/system/wawa-fg.service`:

```ini
[Unit]
Description=Feature Gating Service
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/wawa-fg
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl enable wawa-fg
sudo systemctl start wawa-fg
```

## Docker 部署

创建 `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 复制依赖文件
COPY pyproject.toml .

# 安装依赖
RUN uv sync --frozen

# 复制应用代码
COPY . .

# 构建前端资源（如果需要）
RUN apt-get update && apt-get install -y nodejs npm && \
    npm install -g pnpm && \
    pnpm install && \
    pnpm run build && \
    apt-get remove -y nodejs npm && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

构建和运行：

```bash
docker build -t wawa-fg .
docker run -d -p 8000:8000 --env-file .env wawa-fg
```


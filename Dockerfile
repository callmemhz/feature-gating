# 多阶段构建 - 前端构建阶段
FROM node:20-alpine AS frontend-builder

# 安装 pnpm（锁定大版本：新版 pnpm 遇到被忽略的依赖构建脚本会直接报错退出）
RUN npm install -g pnpm@9

WORKDIR /app

# 复制前端相关文件
COPY app/package.json app/pnpm-lock.yaml app/
COPY app/tailwind.config.js app/
COPY app/src app/src
COPY app/templates app/templates

# 安装前端依赖并构建
WORKDIR /app/app
RUN pnpm install --frozen-lockfile
RUN pnpm build


# Python 运行阶段
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装 uv - Python 包管理器
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY app ./app

# 从前端构建阶段复制构建产物
COPY --from=frontend-builder /app/app/static ./app/static

# 安装 Python 依赖
RUN uv pip install --no-cache -r pyproject.toml

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

# 启动应用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


"""FastAPI 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.database import connect_to_db, close_db_connection, get_database
from app.routers import auth, projects, snapshots, admin, fg, pages
from app.services.auth import get_password_hash
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    await connect_to_db()
    await init_admin_user()
    yield
    # 关闭时
    await close_db_connection()


app = FastAPI(
    title=f"{settings.app_title}",
    description="基于业务字段表达式的功能控制平台",
    version="0.1.0",
    lifespan=lifespan
)

# 添加 Session 中间件（用于 flash messages）
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 注册路由
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(snapshots.router)
app.include_router(admin.router)
app.include_router(fg.router)


async def init_admin_user():
    """初始化管理员用户"""
    db = get_database()
    
    # 检查是否已有用户
    user_count = await db.fetchval("SELECT count(*) FROM users")
    if user_count == 0:
        # 创建初始管理员（多副本同时启动时靠 username 唯一约束去重）
        result = await db.execute(
            """INSERT INTO users (username, hashed_password, role, created_by)
               VALUES ($1, $2, 'admin', 'system') ON CONFLICT (username) DO NOTHING""",
            settings.admin_username,
            get_password_hash(settings.admin_password),
        )
        if result.endswith(" 1"):
            print(f"创建初始管理员用户: {settings.admin_username}")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


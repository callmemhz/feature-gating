"""FastAPI 依赖注入"""
import secrets
from typing import Optional
from fastapi import Depends, HTTPException, status, Cookie, Header, Request
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.database import get_database
from app.services.auth import decode_access_token
from app.config import get_settings

# Jinja2 模板
templates = Jinja2Templates(directory="app/templates")

# 添加全局上下文处理器
def get_template_context():
    """获取模板全局上下文"""
    settings = get_settings()
    return {
        "app_title": settings.app_title
    }

# 将全局上下文添加到模板环境
templates.env.globals.update(get_template_context())


async def get_db() -> AsyncIOMotorDatabase:
    """获取数据库连接"""
    return get_database()


def _match_api_key(provided: Optional[str]) -> Optional[dict]:
    """校验 X-API-Key。命中返回合成的 service 用户（admin），否则 None。

    配置 API_KEYS 为逗号分隔，每项 "secret" 或 "label:secret"；label 仅用于审计
    （快照 updated_by），不填默认为 "api"。比较用 compare_digest 防时序侧信道。
    """
    if not provided:
        return None
    raw = (get_settings().api_keys or "").strip()
    if not raw:
        return None
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            label, _, secret = entry.partition(":")
            label = label.strip() or "api"
        else:
            label, secret = "api", entry
        if secret and secrets.compare_digest(provided, secret):
            return {"username": label, "role": "admin", "auth": "api_key"}
    return None


async def get_current_user(
    access_token: Optional[str] = Cookie(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    """获取当前登录用户（先认 API Key，再回落 cookie JWT）"""
    api_user = _match_api_key(x_api_key)
    if api_user:
        return api_user

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录"
        )
    
    payload = decode_access_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )
    
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )
    
    # 从数据库获取用户信息
    user = await db.users.find_one({"username": username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )
    
    return user


async def get_current_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """验证当前用户是管理员"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def get_optional_user(
    access_token: Optional[str] = Cookie(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> Optional[dict]:
    """获取当前用户（可选，不强制登录）"""
    api_user = _match_api_key(x_api_key)
    if api_user:
        return api_user

    if not access_token:
        return None
    
    payload = decode_access_token(access_token)
    if not payload:
        return None
    
    username = payload.get("sub")
    if not username:
        return None
    
    user = await db.users.find_one({"username": username})
    return user


def flash(request: Request, message: str, category: str = "info"):
    """添加 flash 消息到 session"""
    if "_messages" not in request.session:
        request.session["_messages"] = []
    request.session["_messages"].append({
        "message": message,
        "category": category
    })


def get_flashed_messages(request: Request):
    """获取并清除 flash 消息"""
    return request.session.pop("_messages", [])


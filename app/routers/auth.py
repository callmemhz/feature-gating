"""认证路由"""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Form, Request
from fastapi.responses import RedirectResponse
import asyncpg
from app.deps import get_db, get_current_user, flash, find_user_by_username
from app.schemas.user import UserLogin, Token, UserResponse
from app.services.auth import verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: asyncpg.Pool = Depends(get_db)
):
    """用户登录"""
    # 查找用户
    user = await find_user_by_username(db, username)
    if not user:
        flash(request, "用户名或密码错误", "error")
        return RedirectResponse(url="/login", status_code=303)
    
    # 验证密码
    if not verify_password(password, user["hashed_password"]):
        flash(request, "用户名或密码错误", "error")
        return RedirectResponse(url="/login", status_code=303)
    
    # 创建 JWT token
    access_token = create_access_token(data={"sub": user["username"]})
    
    # 设置 HttpOnly cookie 并重定向到首页
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=60 * 60 * 24 * 7,  # 7 days
        samesite="lax"
    )
    flash(request, f"欢迎回来，{user['username']}！", "success")
    
    return response


@router.post("/logout")
async def logout(response: Response):
    """用户登出"""
    response.delete_cookie(key="access_token")
    return {"message": "登出成功"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": str(current_user.get("id", "")),
        "username": current_user["username"],
        "role": current_user["role"],
        "created_by": current_user.get("created_by", "system")
    }


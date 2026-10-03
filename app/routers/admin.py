"""管理员路由"""
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.database import parse_id
from app.deps import get_db, get_current_admin
from app.schemas.user import UserCreate, UserResponse, PasswordChange
from app.services.auth import get_password_hash, verify_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _user_response(user) -> dict:
    return {
        "id": str(user["id"]),
        "username": user["username"],
        "role": user["role"],
        "created_by": user["created_by"]
    }


@router.get("/users", response_model=List[UserResponse])
async def get_users(
    db: asyncpg.Pool = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """获取所有用户"""
    rows = await db.fetch("SELECT * FROM users ORDER BY id")
    return [_user_response(user) for user in rows]


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: asyncpg.Pool = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """创建用户"""
    # 用户名唯一约束兜底并发重复
    user = await db.fetchrow(
        """INSERT INTO users (username, hashed_password, role, created_by)
           VALUES ($1, $2, $3, $4)
           ON CONFLICT (username) DO NOTHING
           RETURNING *""",
        user_data.username,
        get_password_hash(user_data.password),
        user_data.role,
        current_admin["username"],
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    return _user_response(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: asyncpg.Pool = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """删除用户"""
    uid = parse_id(user_id, "用户不存在")
    # 检查用户是否存在
    user = await db.fetchrow("SELECT * FROM users WHERE id = $1", uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 不能删除自己（API Key 合成用户没有 id）
    if user["id"] == current_admin.get("id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己"
        )

    await db.execute("DELETE FROM users WHERE id = $1", uid)

    return {"message": "用户已删除"}


@router.put("/users/{user_id}/password")
async def change_password(
    user_id: str,
    password_data: PasswordChange,
    db: asyncpg.Pool = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    """修改用户密码"""
    uid = parse_id(user_id, "用户不存在")
    # 检查用户是否存在
    user = await db.fetchrow("SELECT * FROM users WHERE id = $1", uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 如果是修改自己的密码，需要验证旧密码
    if user["id"] == current_admin.get("id") and password_data.old_password:
        if not verify_password(password_data.old_password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="旧密码不正确"
            )

    # 更新密码
    await db.execute(
        "UPDATE users SET hashed_password = $1 WHERE id = $2",
        get_password_hash(password_data.new_password),
        uid,
    )

    return {"message": "密码已更新"}

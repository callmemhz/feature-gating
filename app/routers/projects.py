"""项目路由"""
import re
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
import asyncpg
from typing import List
from app.database import parse_id
from app.deps import get_db, get_current_user, get_current_admin
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate, ProjectItemsPatch
from app.services.cache import invalidate_cache

router = APIRouter(prefix="/api/projects", tags=["projects"])

# 允许的 Key 字符：小写字母、数字、-_.$#@
_KEY_PATTERN = re.compile(r'^[a-z0-9_.\-#$@]+$')


def _validate_item_keys(items):
    """校验一批 item 的 key：非空、格式合法、批内无重复（大小写不敏感）。不合法抛 400。"""
    empty_items = [i for i, item in enumerate(items) if not item.name or not item.name.strip()]
    if empty_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"第 {', '.join(str(i+1) for i in empty_items)} 个 Item 的 Key 不能为空"
        )

    invalid_items = [
        (i, item.name.strip())
        for i, item in enumerate(items)
        if not _KEY_PATTERN.match(item.name.strip())
    ]
    if invalid_items:
        invalid_names = [f"'{name}' (第{i+1}个)" for i, name in invalid_items]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Key 格式不正确: {', '.join(invalid_names)}。只能包含小写字母、数字、-_.$#@"
        )

    names = [item.name.strip().lower() for item in items]
    if len(names) != len(set(names)):
        duplicates = [name for name, count in Counter(names).items() if count > 1]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"存在重复的 Key（大小写不敏感）: {', '.join(duplicates)}"
        )


def _project_response(project) -> dict:
    return {
        "id": str(project["id"]),
        "name": project["name"],
        "created_by": project["created_by"],
        "created_at": project["created_at"],
        "items": project["items"] or []
    }


async def _get_project_or_404(db, project_id: str, for_update: bool = False):
    pid = parse_id(project_id, "项目不存在")
    sql = "SELECT * FROM projects WHERE id = $1" + (" FOR UPDATE" if for_update else "")
    project = await db.fetchrow(sql, pid)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    return project


@router.get("", response_model=List[ProjectResponse])
async def get_projects(
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取所有项目"""
    rows = await db.fetch("SELECT * FROM projects ORDER BY id")
    return [_project_response(project) for project in rows]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取单个项目"""
    project = await _get_project_or_404(db, project_id)
    return _project_response(project)


@router.post("")
async def create_project(
    request: Request,
    project_data: ProjectCreate,
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """创建项目"""
    # 项目名唯一约束兜底并发重复
    project = await db.fetchrow(
        """INSERT INTO projects (name, created_by) VALUES ($1, $2)
           ON CONFLICT (name) DO NOTHING RETURNING *""",
        project_data.name,
        current_user["username"],
    )
    if not project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="项目名称已存在"
        )
    
    result = _project_response(project)
    result["created_at"] = project["created_at"].isoformat()
    return result


@router.put("/{project_id}")
async def update_project(
    request: Request,
    project_id: str,
    project_data: ProjectUpdate,
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """更新项目（包括 items）"""
    pid = parse_id(project_id, "项目不存在")

    # 校验 key（非空 / 格式 / 批内重复）
    _validate_item_keys(project_data.items)

    # 将 Pydantic 对象转换为字典
    items_dict = [item.model_dump() for item in project_data.items]
    
    # 更新整个项目（包括 items）
    updated_project = await db.fetchrow(
        "UPDATE projects SET items = $1 WHERE id = $2 RETURNING *",
        items_dict,
        pid,
    )
    if not updated_project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )
    
    # 清除缓存
    invalidate_cache(updated_project["name"])
    
    result = _project_response(updated_project)
    result["created_at"] = updated_project["created_at"].isoformat()
    return result


@router.patch("/{project_id}/items")
async def patch_project_items(
    project_id: str,
    patch: ProjectItemsPatch,
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """局部更新项目 items：仅 upsert 指定 key、删除 delete 列出的 key，其余 item 原样保留。

    相比 PUT 的全量替换，PATCH 只动点名的 key，避免漏带 key 把其它配置抹掉，更适合脚本化操作。
    """
    if not patch.upsert and not patch.delete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="upsert 和 delete 不能同时为空"
        )

    # 校验待写入的 key
    _validate_item_keys(patch.upsert)

    # 读改写放在一个事务里并锁行，避免并发 PATCH 互相覆盖
    async with db.acquire() as conn:
        async with conn.transaction():
            project = await _get_project_or_404(conn, project_id, for_update=True)

            result_items = list(project["items"] or [])

            delete_set = {d.strip().lower() for d in patch.delete if d and d.strip()}
            if delete_set:
                result_items = [
                    it for it in result_items
                    if str(it.get("name", "")).strip().lower() not in delete_set
                ]

            index_by_name = {
                str(it.get("name", "")).strip().lower(): idx
                for idx, it in enumerate(result_items)
            }
            for item in patch.upsert:
                item_dict = item.model_dump()
                key = item.name.strip().lower()
                if key in index_by_name:
                    result_items[index_by_name[key]] = item_dict  # 原位替换，保留顺序
                else:
                    index_by_name[key] = len(result_items)
                    result_items.append(item_dict)

            # 最终去重保险（大小写不敏感）
            final_names = [str(it.get("name", "")).strip().lower() for it in result_items]
            if len(final_names) != len(set(final_names)):
                duplicates = [name for name, count in Counter(final_names).items() if count > 1]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"合并后存在重复的 Key（大小写不敏感）: {', '.join(duplicates)}"
                )

            await conn.execute(
                "UPDATE projects SET items = $1 WHERE id = $2",
                result_items,
                project["id"],
            )

    # 清除缓存
    invalidate_cache(project["name"])

    return {
        "id": str(project["id"]),
        "name": project["name"],
        "upserted": [item.name for item in patch.upsert],
        "deleted": sorted(delete_set),
        "item_count": len(result_items)
    }


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_admin)  # 只有管理员可以删除项目
):
    """删除项目（仅管理员）"""
    project = await _get_project_or_404(db, project_id)
    
    # 删除项目（items 会一起删除）
    await db.execute("DELETE FROM projects WHERE id = $1", project["id"])
    
    # 清除缓存
    invalidate_cache(project["name"])
    
    return {"message": "项目已删除"}

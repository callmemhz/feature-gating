"""快照路由"""
from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg
from typing import List
import yaml
from app.database import parse_id
from app.deps import get_db, get_current_user
from app.schemas.snapshot import SnapshotCreate, SnapshotResponse
from app.services.cache import invalidate_cache

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


def _snapshot_response(snapshot, with_project_name: bool = False) -> dict:
    result = {
        "id": str(snapshot["id"]),
        "project_id": str(snapshot["project_id"]),
        "yaml": snapshot["yaml"],
        "updated_by": snapshot["updated_by"],
        "updated_at": snapshot["updated_at"],
        "remark": snapshot["remark"] or ""
    }
    if with_project_name:
        result["project_name"] = snapshot["project_name"]
    return result


def generate_snapshot_yaml(project, remark: str = "", updated_by: str = "") -> str:
    """生成项目快照的 YAML"""
    # 构建 YAML 数据（items 已经在 project 中）
    snapshot_data = {
        "snapshot": {
            "updated_by": updated_by,
            "remark": remark
        },
        "project": {
            "id": str(project["id"]),
            "name": project["name"],
            "created_at": project["created_at"].isoformat()
        },
        "items": project["items"] or []
    }
    
    return yaml.dump(snapshot_data, allow_unicode=True, sort_keys=False)


@router.get("/all")
async def get_all_snapshots(
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取所有快照（用于管理员页面）"""
    rows = await db.fetch("SELECT * FROM snapshots ORDER BY updated_at DESC")
    return [_snapshot_response(snapshot, with_project_name=True) for snapshot in rows]


@router.get("", response_model=List[SnapshotResponse])
async def get_snapshots(
    project_id: str,
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取项目的历史快照"""
    try:
        pid = int(project_id)
    except ValueError:
        return []
    rows = await db.fetch(
        "SELECT * FROM snapshots WHERE project_id = $1 ORDER BY updated_at DESC", pid
    )
    return [_snapshot_response(snapshot) for snapshot in rows]


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(
    snapshot_id: str,
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """获取特定快照详情"""
    sid = parse_id(snapshot_id, "快照不存在")
    snapshot = await db.fetchrow("SELECT * FROM snapshots WHERE id = $1", sid)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="快照不存在"
        )
    
    return _snapshot_response(snapshot)


@router.post("", response_model=SnapshotResponse)
async def create_snapshot(
    snapshot_data: SnapshotCreate,
    db: asyncpg.Pool = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """创建快照"""
    # 获取项目信息
    pid = parse_id(snapshot_data.project_id, "项目不存在")
    project = await db.fetchrow("SELECT * FROM projects WHERE id = $1", pid)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    # 生成 YAML（包含备注和操作者）
    yaml_content = generate_snapshot_yaml(
        project,
        remark=snapshot_data.remark,
        updated_by=current_user["username"]
    )
    
    snapshot = await db.fetchrow(
        """INSERT INTO snapshots (project_id, project_name, yaml, updated_by, remark)
           VALUES ($1, $2, $3, $4, $5) RETURNING *""",
        project["id"],
        project["name"],  # 冗余保存项目名称
        yaml_content,
        current_user["username"],
        snapshot_data.remark,
    )
    
    # 清除缓存
    invalidate_cache(project["name"])
    
    return _snapshot_response(snapshot, with_project_name=True)

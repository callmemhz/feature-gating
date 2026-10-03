"""Feature Gate 查询接口"""
from fastapi import APIRouter, Depends, HTTPException, status
import asyncpg
from pydantic import BaseModel
from typing import Optional, List, Dict
from app.deps import get_db
from app.services.cache import get_cached_item, set_cached_item
from app.services.evaluator import evaluate_conditions, evaluate_condition_groups
from app.schemas.project import Item

router = APIRouter(prefix="/api/fg", tags=["feature-gate"])


class FGCheckRequest(BaseModel):
    """FG 检查请求"""
    project: str
    key: str
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    email: Optional[str] = None
    org_id: Optional[str] = None


class FGCheckResponse(BaseModel):
    """FG 检查响应"""
    enabled: bool
    key: str


class FGDebugResponse(BaseModel):
    """调试响应"""
    results: Dict[str, bool]  # key -> enabled


class FGDebugRequest(BaseModel):
    """调试请求 - 使用 draft 配置检测"""
    items: List[Item]
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    email: Optional[str] = None
    org_id: Optional[str] = None


class FGGetRequest(BaseModel):
    """FG 获取配置值请求"""
    project: str
    key: str


class FGGetResponse(BaseModel):
    """FG 获取配置值响应"""
    value: str
    key: str


@router.post("/debug", response_model=FGDebugResponse)
async def debug_feature_gate(request: FGDebugRequest):
    """使用 draft 配置检测命中情况（不需要保存）"""
    results = {}
    
    # 构建上下文
    context = {}
    if request.user_id:
        context["user_id"] = request.user_id
    if request.chat_id:
        context["chat_id"] = request.chat_id
    if request.email:
        context["email"] = request.email
    if request.org_id:
        context["org_id"] = request.org_id
    
    for item in request.items:
        if not item.name or not item.name.strip():
            continue
            
        # 检查 enabled
        if not item.enabled:
            results[item.name] = False
            continue
        
        # 转换为 dict 格式供 evaluator 使用
        condition_groups = [g.model_dump() for g in item.condition_groups]
        conditions = [c.model_dump() for c in item.conditions]
        
        # 优先使用 condition_groups
        if condition_groups:
            result = evaluate_condition_groups(condition_groups, context)
        elif conditions:
            result = evaluate_conditions(conditions, context)
        else:
            # 没有条件，直接返回 enabled
            result = True
        
        results[item.name] = result
    
    return FGDebugResponse(results=results)


@router.get("/check", response_model=FGCheckResponse)
async def check_feature_gate(
    project: str,
    key: str,
    user_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    email: Optional[str] = None,
    org_id: Optional[str] = None,
    db: asyncpg.Pool = Depends(get_db)
):
    """检查功能是否对特定用户生效（GET 请求）"""
    return await _check_feature_gate(project, key, user_id, chat_id, email, org_id, db)


@router.post("/check", response_model=FGCheckResponse)
async def check_feature_gate_post(
    request: FGCheckRequest,
    db: asyncpg.Pool = Depends(get_db)
):
    """检查功能是否对特定用户生效（POST 请求）"""
    return await _check_feature_gate(
        request.project,
        request.key,
        request.user_id,
        request.chat_id,
        request.email,
        request.org_id,
        db
    )


async def _check_feature_gate(
    project: str,
    key: str,
    user_id: Optional[str],
    chat_id: Optional[str],
    email: Optional[str],
    org_id: Optional[str],
    db: asyncpg.Pool
) -> FGCheckResponse:
    """Feature Gate 检查核心逻辑"""
    
    # 1. 尝试从缓存获取
    cached_item = get_cached_item(project, key)
    
    if cached_item is None:
        # 2. 缓存未命中，从数据库查询
        # 首先找到项目
        project_doc = await db.fetchrow("SELECT items FROM projects WHERE name = $1", project)
        if not project_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目 '{project}' 不存在"
            )
        
        # 在项目的 items 数组中查找（大小写不敏感）
        items = project_doc["items"] or []
        key_lower = key.lower()
        item = next((i for i in items if i.get("name", "").lower() == key_lower), None)
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"功能项 '{key}' 不存在"
            )
        
        # 缓存 item（使用小写的 key 作为缓存键）
        cached_item = {
            "enabled": item.get("enabled", True),
            "value": item.get("value", ""),
            "conditions": item.get("conditions", []),
            "condition_groups": item.get("condition_groups", [])
        }
        set_cached_item(project, key_lower, cached_item)
    
    # 3. 检查 enabled 开关
    if not cached_item["enabled"]:
        return FGCheckResponse(enabled=False, key=key)
    
    # 4. 构建上下文
    context = {}
    if user_id:
        context["user_id"] = user_id
    if chat_id:
        context["chat_id"] = chat_id
    if email:
        context["email"] = email
    if org_id:
        context["org_id"] = org_id
    
    # 5. 计算条件
    condition_groups = cached_item.get("condition_groups", [])
    conditions = cached_item.get("conditions", [])
    
    # 优先使用 condition_groups（分组逻辑），否则回退到 conditions（向后兼容）
    if condition_groups:
        # 分组逻辑：组间 OR，组内按各组的 logic 配置
        result = evaluate_condition_groups(condition_groups, context)
    elif conditions:
        # 向后兼容：使用原有的 conditions，AND 逻辑
        result = evaluate_conditions(conditions, context)
    else:
        # 没有任何条件，直接返回 enabled
        return FGCheckResponse(enabled=True, key=key)
    
    return FGCheckResponse(enabled=result, key=key)


@router.get("/get", response_model=FGGetResponse)
async def get_feature_value(
    project: str,
    key: str,
    db: asyncpg.Pool = Depends(get_db)
):
    """获取功能配置值（GET 请求）"""
    return await _get_feature_value(project, key, db)


@router.post("/get", response_model=FGGetResponse)
async def get_feature_value_post(
    request: FGGetRequest,
    db: asyncpg.Pool = Depends(get_db)
):
    """获取功能配置值（POST 请求）"""
    return await _get_feature_value(request.project, request.key, db)


async def _get_feature_value(
    project: str,
    key: str,
    db: asyncpg.Pool
) -> FGGetResponse:
    """获取功能配置值核心逻辑"""
    
    # 1. 尝试从缓存获取
    cached_item = get_cached_item(project, key)
    
    if cached_item is None:
        # 2. 缓存未命中，从数据库查询
        project_doc = await db.fetchrow("SELECT items FROM projects WHERE name = $1", project)
        if not project_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"项目 '{project}' 不存在"
            )
        
        # 在项目的 items 数组中查找（大小写不敏感）
        items = project_doc["items"] or []
        key_lower = key.lower()
        item = next((i for i in items if i.get("name", "").lower() == key_lower), None)
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"功能项 '{key}' 不存在"
            )
        
        # 缓存 item（使用小写的 key 作为缓存键）
        cached_item = {
            "enabled": item.get("enabled", True),
            "value": item.get("value", ""),
            "conditions": item.get("conditions", []),
            "condition_groups": item.get("condition_groups", [])
        }
        set_cached_item(project, key_lower, cached_item)
    
    # 3. 检查 enabled 开关，如果关闭则返回空字符串
    if not cached_item["enabled"]:
        return FGGetResponse(value="", key=key)
    
    # 4. 返回配置值
    return FGGetResponse(value=cached_item.get("value", ""), key=key)


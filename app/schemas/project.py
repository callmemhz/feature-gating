"""项目 Schemas"""
from pydantic import BaseModel
from typing import Optional, List, Union
from datetime import datetime


class Condition(BaseModel):
    """条件"""
    field: str
    operator: str
    value: Union[int, str, List[str]]  # 支持数字、字符串、字符串数组
    comparator: Optional[str] = None  # 对于白名单操作符，comparator 可选
    target: Optional[Union[int, str]] = None  # 对于白名单操作符，target 可选


class ConditionGroup(BaseModel):
    """条件组（组内按 logic 逻辑，组间 OR）"""
    logic: str = "and"  # 组内逻辑: "and" | "or"
    conditions: List[Condition] = []


class Item(BaseModel):
    """Item"""
    name: str
    description: str = ""
    enabled: bool = True
    value: str = ""  # 配置值，通过 /api/fg/get 获取
    conditions: List[Condition] = []  # 保留，向后兼容
    condition_groups: List[ConditionGroup] = []  # 新增：条件分组


class ProjectCreate(BaseModel):
    """创建项目"""
    name: str


class ProjectUpdate(BaseModel):
    """更新项目（全量替换 items）"""
    items: List[Item]


class ProjectItemsPatch(BaseModel):
    """局部更新项目 items：upsert 指定 key（替换或新增），删除 delete 列出的 key，其余 item 不动。"""
    upsert: List[Item] = []
    delete: List[str] = []


class ProjectResponse(BaseModel):
    """项目响应"""
    id: str
    name: str
    created_by: str
    created_at: datetime
    items: List[Item] = []
    
    class Config:
        from_attributes = True

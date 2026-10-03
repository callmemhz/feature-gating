"""PostgreSQL 数据库连接管理"""
import json
from typing import Optional

import asyncpg
from fastapi import HTTPException, status

from app.config import get_settings

settings = get_settings()

# 连接池
pool: Optional[asyncpg.Pool] = None

# 启动时幂等建表。items 整体存 json（与原 Mongo 嵌入数组语义一致；
# 用 json 而非 jsonb 以保留字段顺序，快照 YAML 输出与原来一致）
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'user',
    created_by      TEXT NOT NULL DEFAULT 'system',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    items      JSON NOT NULL DEFAULT '[]'::json
);

CREATE TABLE IF NOT EXISTS snapshots (
    id           BIGSERIAL PRIMARY KEY,
    project_id   BIGINT NOT NULL,
    project_name TEXT,
    yaml         TEXT NOT NULL,
    updated_by   TEXT NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    remark       TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS snapshots_project_updated_idx
    ON snapshots (project_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS snapshots_updated_idx
    ON snapshots (updated_at DESC);
"""


async def _init_connection(conn: asyncpg.Connection):
    """json 列自动与 Python 对象互转"""
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def connect_to_db():
    """创建连接池并建表"""
    global pool
    pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=1,
        max_size=settings.database_pool_size,
        init=_init_connection,
    )
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
    print("Connected to PostgreSQL")


async def close_db_connection():
    """关闭连接池"""
    if pool:
        await pool.close()
        print("Closed PostgreSQL connection")


def get_database() -> asyncpg.Pool:
    """获取连接池"""
    return pool


def parse_id(value: str, not_found_detail: str) -> int:
    """把路径/参数里的字符串 ID 转成整数；非法 ID 一律按不存在处理"""
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)

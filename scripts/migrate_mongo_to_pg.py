"""把旧版 MongoDB 数据一次性迁移到 PostgreSQL。

用法（pymongo 只在迁移时需要，不进运行依赖）：

    MONGO_URL=mongodb://host:27017/wawa-fg \\
    DATABASE_URL=postgresql://user:pass@host:5432/fg \\
    uv run --with pymongo python scripts/migrate_mongo_to_pg.py

- 目标库需为空（users / projects / snapshots 都没有数据），否则直接退出，避免重复导入。
- 表结构与应用启动时创建的一致；脚本会先执行同一份建表 SQL。
- 项目 ID 会重新分配（ObjectId -> 自增整数），快照的 project_id 按映射改写；
  历史快照 YAML 正文里记录的旧 ID 保持原样，不改写。
- 全部写入在一个事务里，失败整体回滚。
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import asyncpg
from pymongo import MongoClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import SCHEMA_SQL  # noqa: E402


def _utc(dt):
    """Mongo 读出的是 naive UTC 时间，补上时区"""
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def main():
    mongo_url = os.environ["MONGO_URL"]
    database_url = os.environ["DATABASE_URL"]

    mongo = MongoClient(mongo_url)
    mdb = mongo.get_database()

    conn = await asyncpg.connect(database_url)
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.execute(SCHEMA_SQL)

    for table in ("users", "projects", "snapshots"):
        if await conn.fetchval(f"SELECT count(*) FROM {table}"):
            sys.exit(f"目标库 {table} 表已有数据，终止迁移")

    project_ids = {}  # 旧 ObjectId 字符串 -> 新整数 ID
    counts = {"users": 0, "projects": 0, "snapshots": 0, "orphan_snapshots": 0}

    async with conn.transaction():
        for u in mdb.users.find().sort("_id", 1):
            await conn.execute(
                """INSERT INTO users (username, hashed_password, role, created_by, created_at)
                   VALUES ($1, $2, $3, $4, $5)""",
                u["username"], u["hashed_password"], u.get("role", "user"),
                u.get("created_by", "system"), _utc(u.get("created_at")),
            )
            counts["users"] += 1

        for p in mdb.projects.find().sort("_id", 1):
            new_id = await conn.fetchval(
                """INSERT INTO projects (name, created_by, created_at, items)
                   VALUES ($1, $2, $3, $4) RETURNING id""",
                p["name"], p.get("created_by", "system"), _utc(p.get("created_at")),
                p.get("items", []),
            )
            project_ids[str(p["_id"])] = new_id
            counts["projects"] += 1

        for s in mdb.snapshots.find().sort("updated_at", 1):
            new_pid = project_ids.get(str(s.get("project_id")))
            if new_pid is None:
                # 项目已被删除的快照，原系统里也无法再通过项目查到，跳过
                counts["orphan_snapshots"] += 1
                continue
            await conn.execute(
                """INSERT INTO snapshots (project_id, project_name, yaml, updated_by, updated_at, remark)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                new_pid, s.get("project_name"), s["yaml"], s.get("updated_by", ""),
                _utc(s.get("updated_at")), s.get("remark", ""),
            )
            counts["snapshots"] += 1

    await conn.close()
    mongo.close()

    print("迁移完成:", counts)
    print("项目 ID 映射:")
    for old, new in project_ids.items():
        print(f"  {old} -> {new}")


if __name__ == "__main__":
    asyncio.run(main())

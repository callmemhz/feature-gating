"""API 测试脚本"""
import asyncio
import sys
from datetime import datetime

async def test_basic_functionality():
    """测试基本功能"""
    print("=" * 50)
    print("Feature Gating 系统功能测试")
    print("=" * 50)
    
    # 测试导入
    print("\n✓ 测试 1: 检查模块导入...")
    try:
        from app.config import get_settings
        from app.services.auth import get_password_hash, verify_password
        from app.services.hash import hash_user_id, hash_chat_id
        from app.services.evaluator import evaluate_condition, evaluate_conditions
        from app.services.cache import get_cached_item, set_cached_item
        print("  ✓ 所有模块导入成功")
    except Exception as e:
        print(f"  ✗ 模块导入失败: {e}")
        return False
    
    # 测试配置
    print("\n✓ 测试 2: 检查配置...")
    try:
        settings = get_settings()
        print(f"  - Database URL: {settings.database_url}")
        print(f"  - Admin Username: {settings.admin_username}")
        print(f"  - Cache TTL: {settings.cache_ttl_seconds}s")
        print("  ✓ 配置加载成功")
    except Exception as e:
        print(f"  ✗ 配置加载失败: {e}")
        return False
    
    # 测试密码哈希
    print("\n✓ 测试 3: 测试密码哈希...")
    try:
        password = "test123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed)
        assert not verify_password("wrong", hashed)
        print("  ✓ 密码哈希验证成功")
    except Exception as e:
        print(f"  ✗ 密码哈希失败: {e}")
        return False
    
    # 测试字段哈希
    print("\n✓ 测试 4: 测试字段哈希...")
    try:
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        chat_id = "chat_12345"
        
        hash1 = hash_user_id(user_id)
        hash2 = hash_chat_id(chat_id)
        
        print(f"  - hash(user_id): {hash1}")
        print(f"  - hash(chat_id): {hash2}")
        
        # 测试稳定性
        assert hash_user_id(user_id) == hash1
        assert hash_chat_id(chat_id) == hash2
        print("  ✓ 字段哈希成功且稳定")
    except Exception as e:
        print(f"  ✗ 字段哈希失败: {e}")
        return False
    
    # 测试条件计算
    print("\n✓ 测试 5: 测试条件计算...")
    try:
        condition = {
            "field": "user_id",
            "operator": "%",
            "value": 10,
            "comparator": ">",
            "target": 5
        }
        
        context = {"user_id": user_id}
        result = evaluate_condition(condition, context)
        print(f"  - 条件: hash(user_id) % 10 > 5")
        print(f"  - 结果: {result}")
        
        # 测试多条件
        conditions = [
            {"field": "user_id", "operator": "%", "value": 10, "comparator": ">=", "target": 0},
            {"field": "user_id", "operator": "%", "value": 10, "comparator": "<", "target": 10}
        ]
        result = evaluate_conditions(conditions, context)
        print(f"  - 多条件结果: {result}")
        print("  ✓ 条件计算成功")
    except Exception as e:
        print(f"  ✗ 条件计算失败: {e}")
        return False
    
    # 测试缓存
    print("\n✓ 测试 6: 测试缓存...")
    try:
        project = "test_project"
        key = "test_key"
        data = {"enabled": True, "conditions": []}
        
        set_cached_item(project, key, data)
        cached = get_cached_item(project, key)
        
        assert cached == data
        print(f"  - 缓存写入: ✓")
        print(f"  - 缓存读取: ✓")
        print("  ✓ 缓存功能正常")
    except Exception as e:
        print(f"  ✗ 缓存测试失败: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✅ 所有测试通过！")
    print("=" * 50)
    return True


async def test_feature_gate_logic():
    """测试 Feature Gate 逻辑"""
    print("\n" + "=" * 50)
    print("Feature Gate 灰度逻辑测试")
    print("=" * 50)
    
    from app.services.hash import hash_user_id
    from app.services.evaluator import evaluate_condition
    
    # 测试 20% 灰度
    print("\n测试场景: 20% 用户灰度")
    condition = {
        "field": "user_id",
        "operator": "%",
        "value": 10,
        "comparator": "<",
        "target": 2
    }
    
    test_users = [
        "550e8400-e29b-41d4-a716-446655440000",
        "550e8400-e29b-41d4-a716-446655440001",
        "550e8400-e29b-41d4-a716-446655440002",
        "550e8400-e29b-41d4-a716-446655440003",
        "550e8400-e29b-41d4-a716-446655440004",
    ]
    
    enabled_count = 0
    for user_id in test_users:
        context = {"user_id": user_id}
        result = evaluate_condition(condition, context)
        hash_val = hash_user_id(user_id)
        mod_result = hash_val % 10
        
        if result:
            enabled_count += 1
        
        print(f"  User {user_id[-4:]}: hash % 10 = {mod_result}, enabled = {result}")
    
    print(f"\n  灰度比例: {enabled_count}/{len(test_users)} = {enabled_count/len(test_users)*100:.0f}%")
    print("=" * 50)


if __name__ == "__main__":
    print(f"开始时间: {datetime.now()}\n")
    
    # 运行测试
    success = asyncio.run(test_basic_functionality())
    
    if success:
        asyncio.run(test_feature_gate_logic())
        print(f"\n结束时间: {datetime.now()}")
        sys.exit(0)
    else:
        print("\n❌ 测试失败")
        sys.exit(1)


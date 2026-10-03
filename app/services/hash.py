"""字段哈希处理"""
import hashlib


def hash_field(value: str) -> int:
    """对字符串进行哈希，返回整数"""
    # 使用 md5 获取稳定的哈希值
    hash_bytes = hashlib.md5(value.encode()).digest()
    # 转换为整数（取前8字节）
    return int.from_bytes(hash_bytes[:8], byteorder='big')


def hash_user_id(user_id: str) -> int:
    """对 user_id (uuidv4) 进行哈希"""
    return hash_field(user_id)


def hash_chat_id(chat_id: str) -> int:
    """对 chat_id 进行哈希"""
    return hash_field(chat_id)


def hash_email(email: str) -> int:
    """对 email 进行哈希"""
    return hash_field(email)


def hash_org_id(org_id: str) -> int:
    """对 org_id 进行哈希"""
    return hash_field(org_id)


# 字段哈希映射
FIELD_HASHERS = {
    "user_id": hash_user_id,
    "chat_id": hash_chat_id,
    "email": hash_email,
    "org_id": hash_org_id,
}


def get_hashed_value(field: str, value: str) -> int:
    """根据字段名获取哈希值"""
    hasher = FIELD_HASHERS.get(field)
    if hasher:
        return hasher(value)
    # 默认使用通用哈希
    return hash_field(value)


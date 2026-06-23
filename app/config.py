"""配置管理"""
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # App
    app_title: str = "Feature Gating"
    
    # MongoDB
    mongo_url: str = "mongodb://localhost:27017/wawa-fg"
    
    # Admin User
    admin_username: str = "admin"
    admin_password: str = "admin"
    
    # API Keys（机器调用：逗号分隔，每项为 "secret" 或 "label:secret"）
    # 持有有效 key 的请求带 X-API-Key 头即可调所有需登录的接口（等同 admin）。
    api_keys: str = ""

    # JWT
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    
    # Session
    session_secret_key: str = "session-secret-key-change-in-production"
    
    # Cache
    cache_ttl_seconds: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


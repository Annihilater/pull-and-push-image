"""
应用配置管理
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    应用配置类
    """
    # Harbor 配置
    harbor_registry: Optional[str] = None
    harbor_username: Optional[str] = None
    harbor_password: Optional[str] = None
    
    # 应用配置
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    
    # 前端 URL（用于 CORS）
    frontend_url: str = "http://localhost:5173"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


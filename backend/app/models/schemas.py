"""
API 请求和响应的 Pydantic 模型定义
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class Platform(str, Enum):
    """
    支持的平台架构
    """
    AMD64 = "linux/amd64"
    ARM64 = "linux/arm64"


class SyncStatus(str, Enum):
    """
    同步状态枚举
    """
    PENDING = "pending"
    PULLING = "pulling"
    PUSHING = "pushing"
    SUCCESS = "success"
    FAILED = "failed"


class ImageSyncRequest(BaseModel):
    """
    镜像同步请求模型
    """
    source_image: str = Field(..., description="源镜像地址，如 nginx:latest")
    target_registry: str = Field(..., description="目标 Harbor 地址，如 harbor.company.com")
    target_project: str = Field(default="library", description="目标项目名")
    target_image_name: Optional[str] = Field(None, description="目标镜像名，为空则使用源镜像名")
    target_tag: Optional[str] = Field(None, description="目标 tag，为空则使用源 tag")
    platforms: List[Platform] = Field(
        default=[Platform.AMD64, Platform.ARM64],
        description="要同步的平台架构列表"
    )


class ImageSyncResponse(BaseModel):
    """
    镜像同步响应模型
    """
    task_id: str = Field(..., description="任务 ID")
    status: SyncStatus = Field(..., description="同步状态")
    message: str = Field(..., description="状态消息")


class SyncProgress(BaseModel):
    """
    同步进度模型
    """
    task_id: str
    status: SyncStatus
    current_step: str
    progress: int = Field(default=0, ge=0, le=100)
    logs: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class HarborConfig(BaseModel):
    """
    Harbor 配置模型
    """
    registry: str = Field(..., description="Harbor 地址")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class ConfigResponse(BaseModel):
    """
    配置响应模型
    """
    harbor_configured: bool
    docker_available: bool
    skopeo_available: bool
    buildx_available: bool
    default_registry: Optional[str] = None
    default_username: Optional[str] = None


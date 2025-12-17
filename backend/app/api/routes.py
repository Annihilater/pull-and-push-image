"""
API 路由定义
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.models.schemas import (
    ImageSyncRequest,
    ImageSyncResponse,
    SyncProgress,
    SyncStatus,
    HarborConfig,
    ConfigResponse
)
from app.services.image_sync import image_sync_service
from app.config import settings

router = APIRouter()

# 存储 Harbor 配置（运行时）
_harbor_config: Optional[HarborConfig] = None


@router.get("/health")
async def health_check():
    """
    健康检查接口
    :return:
    """
    return {"status": "ok"}


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """
    获取系统配置状态
    :return:
    """
    global _harbor_config
    
    harbor_configured = bool(
        _harbor_config is not None
        or (settings.harbor_registry and settings.harbor_username)
    )
    
    return ConfigResponse(
        harbor_configured=harbor_configured,
        docker_available=image_sync_service.check_docker_available(),
        skopeo_available=image_sync_service.check_skopeo_available(),
        buildx_available=image_sync_service.check_buildx_available(),
        default_registry=settings.harbor_registry,
        default_username=settings.harbor_username
    )


@router.post("/config/harbor")
async def set_harbor_config(config: HarborConfig):
    """
    设置 Harbor 配置
    :param config:
    :return:
    """
    global _harbor_config
    _harbor_config = config
    print(f"[DEBUG] Harbor 配置已保存: registry={config.registry}, username={config.username}")
    return {"status": "ok", "message": f"Harbor 配置已保存，用户: {config.username}"}


@router.post("/sync", response_model=ImageSyncResponse)
async def sync_image(
        request: ImageSyncRequest,
        background_tasks: BackgroundTasks
):
    """
    创建镜像同步任务
    :param request:
    :param background_tasks:
    :return:
    """
    global _harbor_config
    
    # 检查 Docker 是否可用
    if not image_sync_service.check_docker_available():
        raise HTTPException(
            status_code=500,
            detail="Docker 未安装或未运行"
        )
    
    # 解析源镜像
    source_registry, source_name, source_tag = image_sync_service.parse_image_reference(
        request.source_image
    )
    
    # 确定目标镜像名
    if request.target_image_name:
        target_name = request.target_image_name
    else:
        # 使用源镜像名（去掉 library/ 前缀）
        target_name = source_name
        if target_name.startswith("library/"):
            target_name = target_name[8:]
    
    # 确定目标 tag
    target_tag = request.target_tag if request.target_tag else source_tag
    
    # 构建完整的目标镜像地址
    target_image = f"{request.target_registry}/{request.target_project}/{target_name}:{target_tag}"
    
    # 获取 Harbor 凭据
    harbor_username = None
    harbor_password = None
    
    print(f"[DEBUG] 检查 Harbor 配置: _harbor_config={_harbor_config is not None}")
    if _harbor_config:
        harbor_username = _harbor_config.username
        harbor_password = _harbor_config.password
        print(f"[DEBUG] 使用前端配置: username={harbor_username}")
    elif settings.harbor_username and settings.harbor_password:
        harbor_username = settings.harbor_username
        harbor_password = settings.harbor_password
        print(f"[DEBUG] 使用 .env 配置: username={harbor_username}")
    
    # 检查是否使用 skopeo
    use_skopeo = image_sync_service.check_skopeo_available()
    
    # 在后台执行同步任务
    async def run_sync():
        await image_sync_service.sync_image(
            source_image=request.source_image,
            target_image=target_image,
            platforms=request.platforms,
            harbor_username=harbor_username,
            harbor_password=harbor_password,
            use_skopeo=use_skopeo
        )
    
    # 创建任务并立即返回
    import uuid
    task_id = str(uuid.uuid4())[:8]
    
    # 先创建任务记录
    from app.services.image_sync import SyncTask
    task = SyncTask(
        task_id=task_id,
        source_image=request.source_image,
        target_image=target_image,
        platforms=request.platforms,
        status=SyncStatus.PENDING
    )
    image_sync_service.tasks[task_id] = task
    
    # 在后台执行实际同步
    async def execute_sync():
        task.status = SyncStatus.PULLING
        task.logs.append(f"开始同步任务: {task_id}")
        task.logs.append(f"源镜像: {request.source_image}")
        task.logs.append(f"目标镜像: {target_image}")
        task.logs.append(f"平台: {[p.value for p in request.platforms]}")
        
        try:
            if use_skopeo:
                success = await image_sync_service.sync_image_with_skopeo(
                    task,
                    harbor_username,
                    harbor_password
                )
            else:
                success = await image_sync_service.sync_image_with_docker(
                    task,
                    harbor_username,
                    harbor_password
                )
            
            if success:
                task.status = SyncStatus.SUCCESS
                task.current_step = "同步完成"
                task.logs.append("✅ 镜像同步成功!")
            else:
                task.status = SyncStatus.FAILED
                task.current_step = "同步失败"
                if not task.error:
                    task.error = "同步过程中发生错误"
                task.logs.append(f"❌ 同步失败: {task.error}")
                
        except Exception as e:
            task.status = SyncStatus.FAILED
            task.error = str(e)
            task.current_step = "发生异常"
            task.logs.append(f"❌ 发生异常: {str(e)}")
    
    background_tasks.add_task(execute_sync)
    
    return ImageSyncResponse(
        task_id=task_id,
        status=SyncStatus.PENDING,
        message=f"同步任务已创建，目标: {target_image}"
    )


@router.get("/sync/{task_id}", response_model=SyncProgress)
async def get_sync_progress(task_id: str):
    """
    获取同步任务进度
    :param task_id:
    :return:
    """
    progress = image_sync_service.get_task_progress(task_id)
    
    if not progress:
        raise HTTPException(
            status_code=404,
            detail=f"任务 {task_id} 不存在"
        )
    
    return progress


@router.get("/tasks")
async def list_tasks():
    """
    列出所有任务
    :return:
    """
    tasks = []
    for task_id, task in image_sync_service.tasks.items():
        tasks.append({
            "task_id": task_id,
            "source_image": task.source_image,
            "target_image": task.target_image,
            "status": task.status,
            "progress": task.progress
        })
    
    return {"tasks": tasks}


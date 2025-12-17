"""
镜像同步核心服务
支持从 DockerHub 拉取多平台镜像并推送到内网 Harbor
"""
import asyncio
import subprocess
import uuid
import re
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field

from app.models.schemas import Platform, SyncStatus, SyncProgress


@dataclass
class SyncTask:
    """
    同步任务数据类
    """
    task_id: str
    source_image: str
    target_image: str
    platforms: List[Platform]
    status: SyncStatus = SyncStatus.PENDING
    current_step: str = ""
    progress: int = 0
    logs: List[str] = field(default_factory=list)
    error: Optional[str] = None


class ImageSyncService:
    """
    镜像同步服务类
    提供从 DockerHub 到 Harbor 的多平台镜像同步功能
    """
    
    def __init__(self):
        self.tasks: Dict[str, SyncTask] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
    
    def parse_image_reference(
            self,
            image_ref: str
    ) -> tuple[str, str, str]:
        """
        解析镜像引用，提取 registry、name 和 tag
        :param image_ref:
        :return: (registry, name, tag)
        """
        # 默认 registry 是 docker.io
        registry = "docker.io"
        tag = "latest"
        
        # 检查是否包含 registry
        if "/" in image_ref:
            parts = image_ref.split("/")
            if "." in parts[0] or ":" in parts[0]:
                registry = parts[0]
                image_ref = "/".join(parts[1:])
        
        # 检查是否包含 tag
        if ":" in image_ref:
            name, tag = image_ref.rsplit(":", 1)
        else:
            name = image_ref
        
        # 处理官方镜像（添加 library 前缀）
        if registry == "docker.io" and "/" not in name:
            name = f"library/{name}"
        
        return registry, name, tag
    
    def check_tool_available(self, tool: str) -> bool:
        """
        检查命令行工具是否可用
        :param tool:
        :return:
        """
        try:
            result = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def check_docker_available(self) -> bool:
        """
        检查 Docker 是否可用
        :return:
        """
        return self.check_tool_available("docker")
    
    def check_buildx_available(self) -> bool:
        """
        检查 Docker Buildx 是否可用
        :return:
        """
        try:
            result = subprocess.run(
                ["docker", "buildx", "version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def check_skopeo_available(self) -> bool:
        """
        检查 Skopeo 是否可用
        :return:
        """
        return self.check_tool_available("skopeo")
    
    async def run_command(
            self,
            cmd: List[str],
            task: SyncTask,
            stdin_input: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        异步执行命令并记录日志
        :param cmd:
        :param task:
        :param stdin_input: 可选的 stdin 输入
        :return: (success, output)
        """
        cmd_str = " ".join(cmd)
        # 隐藏密码（docker login 和 skopeo 的凭据）
        safe_cmd_str = re.sub(r'--password\s+\S+', '--password ***', cmd_str)
        safe_cmd_str = re.sub(r'--dest-creds\s+\S+', '--dest-creds ***:***', safe_cmd_str)
        task.logs.append(f"$ {safe_cmd_str}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_input else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            if stdin_input:
                stdout, _ = await process.communicate(input=stdin_input.encode())
            else:
                stdout, _ = await process.communicate()
            
            output = stdout.decode("utf-8", errors="replace")
            
            for line in output.strip().split("\n"):
                if line.strip():
                    task.logs.append(line)
            
            success = process.returncode == 0
            if not success:
                task.logs.append(f"命令执行失败，返回码: {process.returncode}")
            
            return success, output
            
        except Exception as e:
            error_msg = f"执行命令时出错: {str(e)}"
            task.logs.append(error_msg)
            return False, error_msg
    
    async def run_command_silent(
            self,
            cmd: List[str]
    ) -> tuple[bool, str]:
        """
        静默执行命令，不记录日志（用于预期可能失败的命令）
        :param cmd:
        :return: (success, output)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            stdout, _ = await process.communicate()
            output = stdout.decode("utf-8", errors="replace")
            return process.returncode == 0, output
        except Exception as e:
            return False, str(e)
    
    async def sync_image_with_docker(
            self,
            task: SyncTask,
            harbor_username: Optional[str] = None,
            harbor_password: Optional[str] = None
    ) -> bool:
        """
        使用 Docker 命令同步镜像（支持多平台）
        :param task:
        :param harbor_username:
        :param harbor_password:
        :return:
        """
        source_registry, source_name, source_tag = self.parse_image_reference(
            task.source_image
        )
        
        # 构建完整的源镜像地址
        if source_registry == "docker.io":
            full_source = f"{source_name}:{source_tag}"
        else:
            full_source = f"{source_registry}/{source_name}:{source_tag}"
        
        target_registry = task.target_image.split("/")[0]
        
        # 登录到目标 Harbor
        if harbor_username and harbor_password:
            task.current_step = "登录到 Harbor"
            task.progress = 5
            task.logs.append(f"正在登录到 {target_registry}...")
            task.logs.append(f"用户名: {harbor_username}")
            
            # 使用 --password-stdin 安全传递密码
            success, output = await self.run_command(
                [
                    "docker", "login",
                    "-u", harbor_username,
                    "--password-stdin",
                    target_registry
                ],
                task,
                stdin_input=harbor_password
            )
            
            if not success:
                task.error = f"Harbor 登录失败: {output}"
                return False
            
            task.logs.append("Harbor 登录成功")
        
        pulled_images = []
        
        # 为每个平台拉取镜像
        for i, platform in enumerate(task.platforms):
            platform_str = platform.value
            arch = platform_str.split("/")[1]
            
            task.current_step = f"拉取 {arch} 架构镜像"
            task.progress = 10 + (i * 30)
            task.logs.append(f"正在拉取 {full_source} ({platform_str})...")
            
            success, _ = await self.run_command(
                ["docker", "pull", "--platform", platform_str, full_source],
                task
            )
            
            if not success:
                task.logs.append(f"警告: {platform_str} 架构拉取失败，跳过")
                continue
            
            # 为该平台的镜像打 tag
            target_with_arch = f"{task.target_image}-{arch}"
            
            task.logs.append(f"为 {arch} 镜像打标签: {target_with_arch}")
            success, _ = await self.run_command(
                ["docker", "tag", full_source, target_with_arch],
                task
            )
            
            if success:
                pulled_images.append((platform_str, target_with_arch))
        
        if not pulled_images:
            task.error = "没有成功拉取任何平台的镜像"
            return False
        
        # 推送各平台镜像
        task.current_step = "推送镜像到 Harbor"
        task.progress = 70
        
        for platform_str, target_image in pulled_images:
            arch = platform_str.split("/")[1]
            task.logs.append(f"正在推送 {arch} 架构镜像...")
            
            success, _ = await self.run_command(
                ["docker", "push", target_image],
                task
            )
            
            if not success:
                task.logs.append(f"警告: {arch} 架构推送失败")
        
        # 创建并推送 manifest
        task.current_step = "创建多平台 manifest"
        task.progress = 85
        
        manifest_images = [img for _, img in pulled_images]
        
        if len(manifest_images) > 1:
            task.logs.append("创建多平台 manifest...")
            
            # 先删除可能存在的旧 manifest（忽略错误，因为可能不存在）
            task.logs.append("清理旧 manifest（如果存在）...")
            await self.run_command_silent(
                ["docker", "manifest", "rm", task.target_image]
            )
            
            # 创建新的 manifest
            create_cmd = ["docker", "manifest", "create", task.target_image]
            create_cmd.extend(manifest_images)
            
            success, _ = await self.run_command(create_cmd, task)
            
            if success:
                task.logs.append("推送多平台 manifest...")
                success, _ = await self.run_command(
                    ["docker", "manifest", "push", task.target_image],
                    task
                )
                
                if not success:
                    task.logs.append("警告: manifest 推送失败，但各平台镜像已推送成功")
        
        # 清理本地镜像
        task.current_step = "清理本地镜像"
        task.progress = 95
        task.logs.append("清理本地镜像...")
        
        # 删除推送的目标镜像
        for _, target_image in pulled_images:
            await self.run_command_silent(["docker", "rmi", target_image])
        
        # 删除拉取的源镜像
        await self.run_command_silent(["docker", "rmi", full_source])
        
        task.logs.append("本地镜像已清理")
        task.progress = 100
        return True
    
    async def sync_image_with_skopeo(
            self,
            task: SyncTask,
            harbor_username: Optional[str] = None,
            harbor_password: Optional[str] = None
    ) -> bool:
        """
        使用 Skopeo 同步镜像（更高效，无需本地存储）
        :param task:
        :param harbor_username:
        :param harbor_password:
        :return:
        """
        source_registry, source_name, source_tag = self.parse_image_reference(
            task.source_image
        )
        
        # 构建 skopeo 格式的源地址
        if source_registry == "docker.io":
            source_ref = f"docker://docker.io/{source_name}:{source_tag}"
        else:
            source_ref = f"docker://{source_registry}/{source_name}:{source_tag}"
        
        target_ref = f"docker://{task.target_image}"
        
        task.current_step = "使用 Skopeo 复制镜像"
        task.progress = 10
        
        # 构建 skopeo copy 命令
        cmd = ["skopeo", "copy", "--all"]
        
        if harbor_username and harbor_password:
            cmd.extend([
                "--dest-creds",
                f"{harbor_username}:{harbor_password}"
            ])
        
        cmd.extend([source_ref, target_ref])
        
        task.logs.append(f"从 {source_ref} 复制到 {target_ref}")
        task.logs.append("正在复制所有平台架构的镜像...")
        
        success, _ = await self.run_command(cmd, task)
        
        task.progress = 100
        return success
    
    async def sync_image(
            self,
            source_image: str,
            target_image: str,
            platforms: List[Platform],
            harbor_username: Optional[str] = None,
            harbor_password: Optional[str] = None,
            use_skopeo: bool = False
    ) -> SyncTask:
        """
        执行镜像同步任务
        :param source_image:
        :param target_image:
        :param platforms:
        :param harbor_username:
        :param harbor_password:
        :param use_skopeo:
        :return:
        """
        task_id = str(uuid.uuid4())[:8]
        
        task = SyncTask(
            task_id=task_id,
            source_image=source_image,
            target_image=target_image,
            platforms=platforms,
            status=SyncStatus.PULLING
        )
        
        self.tasks[task_id] = task
        
        task.logs.append(f"开始同步任务: {task_id}")
        task.logs.append(f"源镜像: {source_image}")
        task.logs.append(f"目标镜像: {target_image}")
        task.logs.append(f"平台: {[p.value for p in platforms]}")
        
        try:
            if use_skopeo and self.check_skopeo_available():
                success = await self.sync_image_with_skopeo(
                    task,
                    harbor_username,
                    harbor_password
                )
            else:
                success = await self.sync_image_with_docker(
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
        
        return task
    
    def get_task(self, task_id: str) -> Optional[SyncTask]:
        """
        获取任务状态
        :param task_id:
        :return:
        """
        return self.tasks.get(task_id)
    
    def get_task_progress(self, task_id: str) -> Optional[SyncProgress]:
        """
        获取任务进度
        :param task_id:
        :return:
        """
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return SyncProgress(
            task_id=task.task_id,
            status=task.status,
            current_step=task.current_step,
            progress=task.progress,
            logs=task.logs.copy(),
            error=task.error
        )


# 全局服务实例
image_sync_service = ImageSyncService()


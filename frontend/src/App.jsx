import { useState, useEffect, useRef } from 'react'
import { 
  Container, 
  Cloud, 
  ArrowRight, 
  Server, 
  CheckCircle2, 
  XCircle, 
  Loader2,
  Settings,
  ChevronDown,
  Cpu,
  Box,
  Terminal,
  Zap
} from 'lucide-react'

const PLATFORMS = [
  { id: 'linux/amd64', label: 'AMD64', icon: '💻', desc: 'x86_64 架构' },
  { id: 'linux/arm64', label: 'ARM64', icon: '📱', desc: 'ARM 架构' },
]

const STATUS_MAP = {
  pending: { label: '等待中', color: 'text-gray-400' },
  pulling: { label: '拉取中', color: 'text-yellow-400' },
  pushing: { label: '推送中', color: 'text-blue-400' },
  success: { label: '成功', color: 'text-green-400' },
  failed: { label: '失败', color: 'text-red-400' },
}

function App() {
  // 表单状态
  const [sourceImage, setSourceImage] = useState('')
  const [targetRegistry, setTargetRegistry] = useState('')
  const [targetProject, setTargetProject] = useState('library')
  const [targetImageName, setTargetImageName] = useState('')
  const [targetTag, setTargetTag] = useState('')
  const [selectedPlatforms, setSelectedPlatforms] = useState(['linux/amd64', 'linux/arm64'])
  
  // Harbor 配置
  const [showHarborConfig, setShowHarborConfig] = useState(false)
  const [harborUsername, setHarborUsername] = useState('')
  const [harborPassword, setHarborPassword] = useState('')
  const [harborConfigured, setHarborConfigured] = useState(false)
  
  // 系统状态
  const [systemConfig, setSystemConfig] = useState(null)
  
  // 任务状态
  const [currentTask, setCurrentTask] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [logs, setLogs] = useState([])
  
  const logsEndRef = useRef(null)
  const pollIntervalRef = useRef(null)

  // 滚动到日志底部
  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [logs])

  // 获取系统配置
  useEffect(() => {
    fetchSystemConfig()
  }, [])

  const fetchSystemConfig = async () => {
    try {
      const response = await fetch('/api/config')
      const data = await response.json()
      setSystemConfig(data)
      setHarborConfigured(data.harbor_configured)
      
      // 自动填充默认值
      if (data.default_registry && !targetRegistry) {
        setTargetRegistry(data.default_registry)
      }
      if (data.default_username && !harborUsername) {
        setHarborUsername(data.default_username)
      }
    } catch (error) {
      console.error('获取系统配置失败:', error)
    }
  }

  // 保存 Harbor 配置
  const saveHarborConfig = async () => {
    try {
      const response = await fetch('/api/config/harbor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          registry: targetRegistry,
          username: harborUsername,
          password: harborPassword
        })
      })
      
      if (response.ok) {
        setHarborConfigured(true)
        setShowHarborConfig(false)
        addLog('Harbor 配置已保存', 'success')
      }
    } catch (error) {
      addLog('Harbor 配置保存失败: ' + error.message, 'error')
    }
  }

  // 添加日志
  const addLog = (message, type = 'normal') => {
    setLogs(prev => [...prev, { message, type, time: new Date().toLocaleTimeString() }])
  }

  // 切换平台选择
  const togglePlatform = (platformId) => {
    setSelectedPlatforms(prev => {
      if (prev.includes(platformId)) {
        if (prev.length === 1) return prev // 至少保留一个
        return prev.filter(p => p !== platformId)
      }
      return [...prev, platformId]
    })
  }

  // 开始同步
  const startSync = async () => {
    if (!sourceImage || !targetRegistry) {
      addLog('请填写源镜像地址和目标仓库地址', 'error')
      return
    }

    setIsLoading(true)
    setLogs([])
    
    // 如果有 Harbor 凭据，先保存配置
    if (harborUsername && harborPassword) {
      addLog(`正在配置 Harbor 认证 (用户: ${harborUsername})...`, 'command')
      try {
        const configResponse = await fetch('/api/config/harbor', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            registry: targetRegistry,
            username: harborUsername,
            password: harborPassword
          })
        })
        if (configResponse.ok) {
          addLog('Harbor 认证配置成功', 'success')
          setHarborConfigured(true)
        } else {
          addLog('Harbor 认证配置失败', 'error')
        }
      } catch (error) {
        addLog('Harbor 认证配置失败: ' + error.message, 'error')
      }
    } else if (systemConfig?.harbor_configured) {
      addLog(`使用服务器默认 Harbor 配置 (用户: ${systemConfig?.default_username || '已配置'})`, 'success')
    }
    
    addLog('正在创建同步任务...', 'command')

    try {
      const response = await fetch('/api/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_image: sourceImage,
          target_registry: targetRegistry,
          target_project: targetProject || 'library',
          target_image_name: targetImageName || null,
          target_tag: targetTag || null,
          platforms: selectedPlatforms
        })
      })

      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.detail || '创建任务失败')
      }

      addLog(`任务已创建: ${data.task_id}`, 'success')
      addLog(`目标镜像: ${data.message}`, 'normal')
      
      setCurrentTask(data)
      startPolling(data.task_id)
      
    } catch (error) {
      addLog('创建任务失败: ' + error.message, 'error')
      setIsLoading(false)
    }
  }

  // 轮询任务状态
  const startPolling = (taskId) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }

    const poll = async () => {
      try {
        const response = await fetch(`/api/sync/${taskId}`)
        const data = await response.json()
        
        setCurrentTask(data)
        
        // 更新日志（增量）
        if (data.logs && data.logs.length > logs.length) {
          const newLogs = data.logs.slice(logs.length)
          newLogs.forEach(log => {
            let type = 'normal'
            if (log.startsWith('$')) type = 'command'
            else if (log.includes('✅') || log.includes('成功')) type = 'success'
            else if (log.includes('❌') || log.includes('失败') || log.includes('错误')) type = 'error'
            addLog(log, type)
          })
        }
        
        // 检查是否完成
        if (data.status === 'success' || data.status === 'failed') {
          clearInterval(pollIntervalRef.current)
          pollIntervalRef.current = null
          setIsLoading(false)
        }
        
      } catch (error) {
        console.error('轮询失败:', error)
      }
    }

    pollIntervalRef.current = setInterval(poll, 1000)
    poll() // 立即执行一次
  }

  // 清理
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [])

  return (
    <div className="min-h-screen relative">
      {/* 网格背景 */}
      <div className="grid-bg" />
      
      {/* 顶部装饰线 */}
      <div className="h-1 bg-gradient-to-r from-transparent via-terminal-green to-transparent" />
      
      <div className="max-w-5xl mx-auto px-6 py-12">
        {/* 标题区域 */}
        <header className="text-center mb-12">
          <div className="flex items-center justify-center gap-4 mb-4">
            <Container className="w-12 h-12 text-terminal-green" />
            <h1 className="font-display text-4xl font-bold bg-gradient-to-r from-terminal-green via-terminal-blue to-terminal-purple bg-clip-text text-transparent">
              Docker Image Sync
            </h1>
            <Box className="w-12 h-12 text-terminal-blue" />
          </div>
          <p className="text-gray-400 text-lg">
            跨平台镜像同步 · DockerHub → Harbor
          </p>
          
          {/* 系统状态 */}
          {systemConfig && (
            <div className="flex items-center justify-center gap-6 mt-6 text-sm">
              <span className={`flex items-center gap-2 ${systemConfig.docker_available ? 'text-terminal-green' : 'text-red-400'}`}>
                <span className={`status-dot ${systemConfig.docker_available ? 'success' : 'failed'}`} />
                Docker
              </span>
              <span className={`flex items-center gap-2 ${systemConfig.buildx_available ? 'text-terminal-green' : 'text-gray-500'}`}>
                <span className={`status-dot ${systemConfig.buildx_available ? 'success' : 'pending'}`} />
                Buildx
              </span>
              <span className={`flex items-center gap-2 ${systemConfig.skopeo_available ? 'text-terminal-green' : 'text-gray-500'}`}>
                <span className={`status-dot ${systemConfig.skopeo_available ? 'success' : 'pending'}`} />
                Skopeo
              </span>
            </div>
          )}
        </header>

        {/* 主表单卡片 */}
        <div className="glow-card p-8 mb-8">
          {/* 源镜像 → 目标镜像 可视化 */}
          <div className="flex items-center justify-between mb-8 px-4">
            <div className="flex items-center gap-3">
              <Cloud className="w-8 h-8 text-terminal-blue" />
              <div>
                <div className="text-sm text-gray-400">源镜像</div>
                <div className="text-terminal-green font-medium">
                  {sourceImage || 'DockerHub'}
                </div>
              </div>
            </div>
            
            <div className="flex-1 mx-8 relative">
              <div className="h-px bg-gradient-to-r from-terminal-blue via-terminal-green to-terminal-purple" />
              <ArrowRight className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-6 text-terminal-green bg-terminal-surface px-1" />
            </div>
            
            <div className="flex items-center gap-3">
              <div className="text-right">
                <div className="text-sm text-gray-400">目标仓库</div>
                <div className="text-terminal-purple font-medium">
                  {targetRegistry || 'Harbor'}
                </div>
              </div>
              <Server className="w-8 h-8 text-terminal-purple" />
            </div>
          </div>

          {/* 表单网格 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            {/* 源镜像 */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                <Terminal className="inline w-4 h-4 mr-2" />
                源镜像地址
              </label>
              <input
                type="text"
                className="terminal-input"
                placeholder="nginx:latest 或 bitnami/redis:7.0"
                value={sourceImage}
                onChange={e => setSourceImage(e.target.value)}
              />
            </div>

            {/* 目标仓库 */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                <Server className="inline w-4 h-4 mr-2" />
                Harbor 地址
              </label>
              <input
                type="text"
                className="terminal-input"
                placeholder="harbor.company.com"
                value={targetRegistry}
                onChange={e => setTargetRegistry(e.target.value)}
              />
            </div>

            {/* 目标项目 */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                <Box className="inline w-4 h-4 mr-2" />
                目标项目名
              </label>
              <input
                type="text"
                className="terminal-input"
                placeholder="library"
                value={targetProject}
                onChange={e => setTargetProject(e.target.value)}
              />
            </div>

            {/* 目标镜像名（可选） */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                <Container className="inline w-4 h-4 mr-2" />
                目标镜像名 <span className="text-gray-600">(可选)</span>
              </label>
              <input
                type="text"
                className="terminal-input"
                placeholder="留空则使用源镜像名"
                value={targetImageName}
                onChange={e => setTargetImageName(e.target.value)}
              />
            </div>

            {/* 目标 Tag */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">
                <Zap className="inline w-4 h-4 mr-2" />
                目标 Tag <span className="text-gray-600">(可选)</span>
              </label>
              <input
                type="text"
                className="terminal-input"
                placeholder="留空则使用源 tag"
                value={targetTag}
                onChange={e => setTargetTag(e.target.value)}
              />
            </div>

            {/* Harbor 配置按钮 */}
            <div className="flex items-end">
              <button
                className={`flex items-center gap-2 px-4 py-3 rounded border transition-all ${
                  harborConfigured 
                    ? 'border-terminal-green text-terminal-green' 
                    : 'border-terminal-orange text-terminal-orange'
                }`}
                onClick={() => setShowHarborConfig(!showHarborConfig)}
              >
                <Settings className="w-5 h-5" />
                Harbor 认证
                {harborConfigured && <CheckCircle2 className="w-4 h-4" />}
                <ChevronDown className={`w-4 h-4 transition-transform ${showHarborConfig ? 'rotate-180' : ''}`} />
              </button>
            </div>
          </div>

          {/* Harbor 配置展开区域 */}
          {showHarborConfig && (
            <div className="border border-terminal-border rounded-lg p-6 mb-8 bg-terminal-bg/50">
              <h3 className="text-terminal-orange font-medium mb-4">Harbor 认证配置</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">用户名</label>
                  <input
                    type="text"
                    className="terminal-input"
                    placeholder="admin"
                    value={harborUsername}
                    onChange={e => setHarborUsername(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-2">密码</label>
                  <input
                    type="password"
                    className="terminal-input"
                    placeholder="••••••••"
                    value={harborPassword}
                    onChange={e => setHarborPassword(e.target.value)}
                  />
                </div>
              </div>
              <button
                className="px-4 py-2 bg-terminal-orange text-terminal-bg rounded font-medium hover:bg-opacity-80 transition-colors"
                onClick={saveHarborConfig}
              >
                保存配置
              </button>
            </div>
          )}

          {/* 平台选择 */}
          <div className="mb-8">
            <label className="block text-sm text-gray-400 mb-3">
              <Cpu className="inline w-4 h-4 mr-2" />
              目标平台架构
            </label>
            <div className="flex gap-4">
              {PLATFORMS.map(platform => (
                <button
                  key={platform.id}
                  className={`platform-chip ${selectedPlatforms.includes(platform.id) ? 'selected' : ''}`}
                  onClick={() => togglePlatform(platform.id)}
                >
                  <span className="text-xl">{platform.icon}</span>
                  <div className="text-left">
                    <div className="font-medium">{platform.label}</div>
                    <div className="text-xs text-gray-500">{platform.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 同步按钮 */}
          <button
            className="cyber-button w-full flex items-center justify-center gap-3"
            onClick={startSync}
            disabled={isLoading || !sourceImage || !targetRegistry}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                同步中...
              </>
            ) : (
              <>
                <Zap className="w-5 h-5" />
                开始同步
              </>
            )}
          </button>
        </div>

        {/* 任务状态和日志 */}
        {(currentTask || logs.length > 0) && (
          <div className="glow-card p-6">
            {/* 任务状态栏 */}
            {currentTask && (
              <div className="flex items-center justify-between mb-4 pb-4 border-b border-terminal-border">
                <div className="flex items-center gap-4">
                  <span className={`status-dot ${currentTask.status}`} />
                  <span className={STATUS_MAP[currentTask.status]?.color}>
                    {STATUS_MAP[currentTask.status]?.label}
                  </span>
                  <span className="text-gray-500">|</span>
                  <span className="text-gray-400">{currentTask.current_step}</span>
                </div>
                <div className="text-terminal-green font-mono">
                  {currentTask.progress}%
                </div>
              </div>
            )}

            {/* 进度条 */}
            {currentTask && (
              <div className="progress-bar mb-4">
                <div 
                  className="progress-bar-fill" 
                  style={{ width: `${currentTask.progress}%` }}
                />
              </div>
            )}

            {/* 日志输出 */}
            <div className="terminal-log">
              <div className="text-gray-500 mb-2">$ docker-sync --verbose</div>
              {logs.map((log, index) => (
                <div key={index} className={`log-line ${log.type}`}>
                  <span className="text-gray-600 mr-2">[{log.time}]</span>
                  {log.message}
                </div>
              ))}
              <div ref={logsEndRef} />
              {isLoading && (
                <div className="flex items-center gap-2 text-terminal-green mt-2">
                  <span className="animate-pulse">▌</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 页脚 */}
        <footer className="text-center mt-12 text-gray-600 text-sm">
          <p>Docker Image Sync v1.0.0 · 支持多平台镜像同步</p>
        </footer>
      </div>
    </div>
  )
}

export default App


#!/bin/bash
# 启动服务
set -e
source "$(dirname "$0")/common.sh"

echo "🚀 启动 Docker Image Sync 服务..."
$COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build

echo ""
echo "✅ 服务已启动"
echo "   访问地址: http://localhost:${FRONTEND_PORT}"
echo "   后端 API: http://localhost:${FRONTEND_PORT}/api/docs"

#!/bin/bash
# 停止服务
set -e
source "$(dirname "$0")/common.sh"

echo "🛑 停止 Docker Image Sync 服务..."
$COMPOSE_CMD -f "$COMPOSE_FILE" down

echo "✅ 服务已停止"

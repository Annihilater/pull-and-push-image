#!/bin/bash
# 拉取最新镜像
source "$(dirname "$0")/common.sh"

echo "📦 拉取最新镜像..."
$COMPOSE_CMD -f "$COMPOSE_FILE" pull
echo "✅ 镜像已更新"

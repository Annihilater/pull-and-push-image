#!/bin/bash
# 进入容器
source "$(dirname "$0")/common.sh"

SERVICE="${1:-backend}"
echo "进入 ${SERVICE} 容器..."
$COMPOSE_CMD -f "$COMPOSE_FILE" exec "$SERVICE" sh

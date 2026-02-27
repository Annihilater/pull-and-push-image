#!/bin/bash
# 查看服务状态
source "$(dirname "$0")/common.sh"

$COMPOSE_CMD -f "$COMPOSE_FILE" ps

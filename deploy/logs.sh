#!/bin/bash
# 查看日志
source "$(dirname "$0")/common.sh"

$COMPOSE_CMD -f "$COMPOSE_FILE" logs -f "$@"

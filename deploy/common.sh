#!/bin/bash
# 公共函数和环境变量

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

# 自动检测 docker compose 命令（兼容新旧版本）
get_compose_cmd() {
    if docker compose version &>/dev/null; then
        echo "docker compose"
    elif docker-compose version &>/dev/null; then
        echo "docker-compose"
    else
        echo "ERROR: docker compose 或 docker-compose 均不可用" >&2
        exit 1
    fi
}

COMPOSE_CMD=$(get_compose_cmd)

# 导出外部端口（可通过环境变量覆盖）
export FRONTEND_PORT="${FRONTEND_PORT:-8080}"
export DOCKER_CONFIG_PATH="${DOCKER_CONFIG_PATH:-/root/.docker}"

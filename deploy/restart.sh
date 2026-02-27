#!/bin/bash
# 重启服务
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"${SCRIPT_DIR}/stop.sh"
"${SCRIPT_DIR}/start.sh"

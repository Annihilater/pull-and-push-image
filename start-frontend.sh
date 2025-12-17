#!/bin/bash

# Docker Image Sync 前端启动脚本

cd "$(dirname "$0")/frontend"

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 启动开发服务器
echo "启动前端服务..."
echo "访问地址: http://localhost:5173"
npm run dev


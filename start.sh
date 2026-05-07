#!/usr/bin/env bash
# 使用 PM2 后台常驻：关闭终端不会停止服务。
# 依赖：pm2（npm i -g pm2）、python3、pnpm，web-ui 已 pnpm install
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

command -v pm2 >/dev/null || {
  echo "[start] 请先安装 pm2: npm i -g pm2"
  exit 1
}
command -v python3 >/dev/null || {
  echo "[start] 未找到 python3"
  exit 1
}
command -v pnpm >/dev/null || {
  echo "[start] 未找到 pnpm"
  exit 1
}

kill_port() {
  local port=$1
  local pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "${pids}" ]]; then
    echo "[start] 端口 ${port} 已被占用，正在结束: ${pids}"
    kill ${pids} 2>/dev/null || true
    sleep 0.5
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "${pids}" ]]; then
      kill -9 ${pids} 2>/dev/null || true
      sleep 0.3
    fi
  fi
}

kill_port 8000
kill_port 8001

# 避免重复注册同名应用
pm2 delete stock-api 2>/dev/null || true
pm2 delete stock-web 2>/dev/null || true

echo "[start] PM2 启动 stock-api :8000 + stock-web :8001"
pm2 start "${SCRIPT_DIR}/ecosystem.config.cjs"

echo ""
echo "  API:    http://127.0.0.1:8000  （Swagger /docs）"
echo "  前端:   http://127.0.0.1:8001"
echo ""
echo "  常用:   pm2 status | pm2 logs | pm2 logs stock-api"
echo "  停止:   ./stop.sh   或   pm2 stop stock-api stock-web"
echo ""

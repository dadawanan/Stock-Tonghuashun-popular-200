#!/usr/bin/env bash
# 使用 PM2 后台常驻：关闭终端不会停止服务。
# 依赖：pm2（npm i -g pm2）、python3、pnpm，web-ui 已 pnpm install
#
# 若前端在 PM2 里起不来、但你本地 `pnpm run start` 正常：多半是 PATH 不一致。
# 请在「已经 conda activate / 能执行 which pnpm」的同一终端里运行 ./start.sh，
# 以便 ecosystem.config.js 把当前 PATH 传给 PM2 子进程。
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

# 删掉正确名称的应用
pm2 delete stock-api stock-web stock-scheduler 2>/dev/null || true
# 若曾用 ecosystem.config.cjs 启动失败，PM2 会把配置文件当 Node 脚本跑，进程名显示 ecosystem.config，需反复删干净
for _ in 1 2 3 4 5 6 7 8; do
  pm2 delete ecosystem.config 2>/dev/null || break
done
sleep 1

WEB_MODE="${WEB_MODE:-dev}"
echo "[start] PM2 启动 stock-api :8000 + stock-web :8001 + stock-scheduler（前端模式: ${WEB_MODE}）"
# 勿用 .cjs：若干 PM2 版本不识别为 ecosystem；勿加 -f，避免异常解析
WEB_MODE="$WEB_MODE" pm2 start "${SCRIPT_DIR}/ecosystem.config.js"

sleep 1
echo ""

# 后端启动后要连库（lifespan），2s 内 curl 容易误报；多试几次
wait_http_ok() {
  local url=$1
  local label=$2
  local max=${3:-30}
  local i
  for ((i = 1; i <= max; i++)); do
    if curl -sf --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1; then
      echo "[start] ${label} 探测正常: ${url}（约 ${i}s）"
      return 0
    fi
    sleep 1
  done
  echo "[start] 警告: ${label} 在 ${max}s 内仍无响应: ${url}"
  return 1
}

if wait_http_ok "http://127.0.0.1:8000/" "后端" 30; then
  :
else
  echo "        常见原因: PostgreSQL 未启动、DATABASE_URL/.env 配置不对、依赖未装"
  echo "        排查: pm2 logs stock-api --lines 80"
fi

if wait_http_ok "http://127.0.0.1:8001/" "前端" 25; then
  :
else
  echo "        排查: pm2 logs stock-web --lines 80"
fi

echo ""
echo "  API:    http://127.0.0.1:8000  （Swagger /docs）"
echo "  前端:   http://127.0.0.1:8001  （模式: ${WEB_MODE}）"
echo ""
echo "  定时任务: stock-scheduler（交易日 9:25 / 14:30 自动采集人气榜）"
echo ""
echo "  常用:   pm2 status | pm2 logs | pm2 logs stock-api"
echo "  停止:   ./stop.sh   或   pm2 stop stock-api stock-web stock-scheduler"
echo "  切换模式: WEB_MODE=dev ./start.sh  或  WEB_MODE=prod ./start.sh"
echo ""

#!/usr/bin/env bash
# 生产模式：构建后用 serve 托管静态文件
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/web-ui"

# 确保 dist 存在
if [ ! -d "dist" ]; then
  echo "[pm2-web-prod] dist 不存在，先执行 pnpm build..."
  pnpm run build
fi

export PORT="${PORT:-8001}"
export HOST="${HOST:-0.0.0.0}"

# 用 serve 托管静态文件（自动处理 SPA 路由）
exec npx serve dist -l "tcp://${HOST}:${PORT}" --single

#!/usr/bin/env bash
# 停止 PM2 中的 stock-api / stock-web（不删除 pm2 列表记录，便于再次 start.sh）
set -euo pipefail

command -v pm2 >/dev/null || {
  echo "[stop] 未找到 pm2"
  exit 1
}

pm2 stop stock-api 2>/dev/null || true
pm2 stop stock-web 2>/dev/null || true
pm2 stop stock-scheduler 2>/dev/null || true
echo "[stop] 已停止 stock-api、stock-web、stock-scheduler（仍在 pm2 列表中，需要可 pm2 delete）"

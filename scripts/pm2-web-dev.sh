#!/usr/bin/env bash
# 供 PM2 调用：与在 web-ui 目录手动执行 `pnpm run dev` 一致（避免 node 直拉 umi 与 PATH 不一致）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/web-ui"
export PORT="${PORT:-8001}"
export HOST="${HOST:-0.0.0.0}"
exec pnpm run dev

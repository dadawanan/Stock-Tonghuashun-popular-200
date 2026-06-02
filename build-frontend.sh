#!/usr/bin/env bash
# 前端构建脚本
# 用法: ./build-frontend.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_UI_DIR="${SCRIPT_DIR}/web-ui"
DIST_DIR="${WEB_UI_DIR}/dist"

echo "=== 前端构建 ==="
echo ""

# 安装/更新依赖（pnpm install 会自动比对 lock 文件，有变化才更新）
echo "[1/3] 检查依赖..."
cd "${WEB_UI_DIR}" && pnpm install --frozen-lockfile 2>/dev/null || pnpm install

# 构建
echo "[2/3] 构建中..."
cd "${WEB_UI_DIR}" && pnpm build

# 输出结果
FILE_COUNT=$(find "${DIST_DIR}" -type f | wc -l | tr -d ' ')
DIST_SIZE=$(du -sh "${DIST_DIR}" | cut -f1)
echo "[3/3] 构建完成"
echo ""
echo "  输出目录: ${DIST_DIR}"
echo "  文件数量: ${FILE_COUNT}"
echo "  总大小:   ${DIST_SIZE}"
echo ""
echo "=== 构建结束 ==="

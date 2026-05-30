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

# 检查 dist 是否为空
if [ -z "$(ls -A dist 2>/dev/null)" ]; then
  echo "[pm2-web-prod] dist 目录为空，重新执行 pnpm build..."
  rm -rf dist
  pnpm run build
fi

# 检查 index.html 是否存在
if [ ! -f "dist/index.html" ]; then
  echo "[pm2-web-prod] 错误: dist/index.html 不存在，构建可能失败"
  echo "[pm2-web-prod] 请手动运行: cd web-ui && pnpm run build 查看错误"
  exit 1
fi

export PORT="${PORT:-8001}"
export HOST="${HOST:-0.0.0.0}"
# 配置 API 地址（与后端服务在同一台机器时使用相对路径，否则需要指定完整 URL）
# 默认使用相对路径 /api，这样前端会请求当前域名的 /api，由 Nginx 或反向代理转发到后端
export API_BASE_URL="${API_BASE_URL:-}"

echo "[pm2-web-prod] 启动生产模式前端服务"
echo "[pm2-web-prod]   端口: ${PORT}"
echo "[pm2-web-prod]   主机: ${HOST}"
echo "[pm2-web-prod]   API_BASE_URL: ${API_BASE_URL:-'(相对路径 /api)'}"

# 用 serve 托管静态文件（自动处理 SPA 路由）
# --single 参数确保所有路由都返回 index.html（SPA 必需）
# -n 禁用目录列表（安全考虑）
exec npx serve dist -l "tcp://${HOST}:${PORT}" --single -n

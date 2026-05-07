/**
 * PM2 进程描述：终端退出后仍保持运行。
 * 用法：仓库根目录 ./start.sh 或 pm2 start ecosystem.config.cjs
 */
const path = require("path");

const root = __dirname;

module.exports = {
  apps: [
    {
      name: "stock-api",
      cwd: root,
      // interpreter: none → 直接执行 python3，不按 Node 解释
      interpreter: "none",
      script: "python3",
      args: "-m uvicorn stock_service.api.app:app --host 0.0.0.0 --port 8000",
      env: {
        PYTHONPATH: path.join(root, "src"),
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
    },
    {
      name: "stock-web",
      cwd: path.join(root, "web-ui"),
      interpreter: "none",
      script: "pnpm",
      args: "dev",
      env: {
        PORT: "8001",
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
    },
  ],
};

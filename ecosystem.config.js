/**
 * PM2 进程描述：终端退出后仍保持运行。
 *
 * 前端模式控制：
 *   WEB_MODE=dev   → 开发模式（pnpm dev，热更新）
 *   WEB_MODE=prod  → 生产模式（pnpm build + serve 静态托管）
 *   未设置时默认 dev
 */
const fs = require("fs");
const path = require("path");

const root = __dirname;
const webUi = path.join(root, "web-ui");
/** 优先用项目 .venv，避免 PM2 用到 PATH 里另一个 python3（依赖/环境不一致） */
const venvPython = path.join(root, ".venv", "bin", "python");
const stockApiPython = fs.existsSync(venvPython) ? venvPython : "python3";

const inheritShellEnv = {
  PATH: process.env.PATH || "",
  HOME: process.env.HOME || "",
};

const WEB_MODE = process.env.WEB_MODE || "dev";
const webScript =
  WEB_MODE === "prod"
    ? path.join(root, "scripts", "pm2-web-prod.sh")
    : path.join(root, "scripts", "pm2-web-dev.sh");

module.exports = {
  apps: [
    {
      name: "stock-api",
      cwd: root,
      interpreter: "none",
      script: stockApiPython,
      args: "-m uvicorn stock_service.api.app:app --host 0.0.0.0 --port 8000",
      env: {
        ...inheritShellEnv,
        PYTHONPATH: path.join(root, "src"),
      },
      autorestart: true,
      max_restarts: 15,
      restart_delay: 4000,
      exp_backoff_restart_delay: 1000,
    },
    {
      name: "stock-web",
      cwd: webUi,
      script: webScript,
      interpreter: "bash",
      env: {
        ...inheritShellEnv,
        PORT: "8001",
        HOST: "0.0.0.0",
        WEB_MODE: WEB_MODE,
        // 生产模式下配置 API 地址（默认空，使用相对路径 /api）
        // 如果前后端不在同一域名，可设置：API_BASE_URL=http://your-api-domain:8000
        API_BASE_URL: process.env.API_BASE_URL || "localhost:8000",
      },
      autorestart: true,
      max_restarts: 15,
      restart_delay: 4000,
      exp_backoff_restart_delay: 1000,
    },
    {
      name: "stock-scheduler",
      cwd: root,
      interpreter: "none",
      script: stockApiPython,
      args: "-m stock_service.scheduler",
      env: {
        ...inheritShellEnv,
        PYTHONPATH: path.join(root, "src"),
      },
      autorestart: true,
      max_restarts: 100,
      restart_delay: 10000,
      exp_backoff_restart_delay: 5000,
    },
  ],
};

/**
 * PM2 进程描述：终端退出后仍保持运行。
 *
 * 前端已改用 nginx 托管，PM2 只管理后端 API 和定时任务调度器。
 */
const fs = require("fs");
const path = require("path");

const root = __dirname;
/** 优先用项目 .venv，避免 PM2 用到 PATH 里另一个 python3（依赖/环境不一致） */
const venvPython = path.join(root, ".venv", "bin", "python");
const stockApiPython = fs.existsSync(venvPython) ? venvPython : "python3";

const inheritShellEnv = {
  PATH: process.env.PATH || "",
  HOME: process.env.HOME || "",
};

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
        // 配置允许的前端域名（CORS），支持多个域名用逗号分隔
        // 开发环境：http://localhost:8001
        // 生产环境：http://101.35.255.200:8001 或其他域名
        ALLOWED_ORIGINS: process.env.ALLOWED_ORIGINS || "http://localhost:8001,http://101.35.255.200:8001",
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

/**
 * PM2 进程描述：终端退出后仍保持运行。
 * 必须使用 ecosystem.config.js（不要用 .cjs）：否则部分 PM2 版本会把文件当「普通 Node 脚本」执行，
 * 进程名变成 ecosystem.config 且不停重启，stock-api / stock-web 根本不会起来。
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
      script: path.join(root, "scripts", "pm2-web-dev.sh"),
      interpreter: "bash",
      env: {
        ...inheritShellEnv,
        PORT: "8001",
        HOST: "0.0.0.0",
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
      // 只在交易时间运行（可选）
      // cron_restart: "25 9,30 14 * * 1-5",
    },
  ],
};

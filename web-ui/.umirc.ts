import { defineConfig } from "umi";

export default defineConfig({
  // 注意：当前 Umi+schema 不接受顶层 `port`，否则会 fatal「Invalid config keys: port」。
  // 开发端口请在 PM2/start 脚本里用环境变量 PORT=8001，或命令行：PORT=8001 pnpm dev
  // pages 由 src/layouts/index.tsx 全局包裹一层，勿再在 routes 里嵌套同一 layout，否则会重复顶栏
  routes: [
    { path: "/login", component: "login", layout: false },
    { path: "/", component: "index" },
    { path: "/quant/strategies", component: "quant/strategies" },
    { path: "/quant/backtest", component: "quant/backtest" },
    { path: "/quant/sim", component: "quant/sim" },
    { path: "/quant/optimizer", component: "quant/optimizer" },
    { path: "/sim-account", component: "sim-account" },
    { path: "/changelog", component: "changelog" },
    { path: "/docs", component: "docs" },
  ],
  npmClient: 'pnpm',
  utoopack: {},
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
});
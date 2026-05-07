import { defineConfig } from "umi";

export default defineConfig({
  // pages 由 src/layouts/index.tsx 全局包裹一层，勿再在 routes 里嵌套同一 layout，否则会重复顶栏
  routes: [
    { path: "/", component: "index" },
    { path: "/sim-account", component: "sim-account" },
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
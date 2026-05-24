import { Button, Layout, Menu, Spin } from "antd";
import type { MenuProps } from "antd";
import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "umi";

import { authApi, clearAuthStorage, setStoredUsername } from "../utils";
import styles from "./index.less";

const { Header, Content } = Layout;

const navKeys = {
  analysis: "/",
  strategies: "/quant/strategies",
  backtest: "/quant/backtest",
  sim: "/quant/sim",
  optimizer: "/quant/optimizer",
  changelog: "/changelog",
} as const;

const menuItems: MenuProps["items"] = [
  { key: navKeys.analysis, label: "股票分析" },
  { key: navKeys.strategies, label: "策略管理" },
  { key: navKeys.backtest, label: "回测系统" },
  { key: navKeys.sim, label: "模拟盘" },
  { key: navKeys.optimizer, label: "参数优化" },
  { key: navKeys.changelog, label: "更新日志" },
];

export default function RootLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const [ready, setReady] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [authed, setAuthed] = useState(false);
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    (async () => {
      try {
        const u = await authApi.me();
        if (!cancelled) {
          setAuthed(true);
          setStoredUsername(u.username);
          setUsername(u.username);
        }
      } catch {
        clearAuthStorage();
        if (!cancelled) navigate("/login", { replace: true });
      } finally {
        if (!cancelled) setCheckingAuth(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, navigate]);

  const handleLogout = async () => {
    setUsername(null);
    try {
      await authApi.logout();
    } catch {
      // 仍跳转登录页
    } finally {
      clearAuthStorage();
      navigate("/login", { replace: true });
    }
  };

  if (!ready || checkingAuth || !authed) {
    return (
      <div className={styles.authGate}>
        <Spin size="large" />
      </div>
    );
  }

  const selectedKey = pathname.startsWith(navKeys.changelog)
    ? navKeys.changelog
    : pathname.startsWith(navKeys.strategies)
      ? navKeys.strategies
      : pathname.startsWith(navKeys.backtest)
        ? navKeys.backtest
        : pathname.startsWith(navKeys.sim)
          ? navKeys.sim
          : pathname.startsWith(navKeys.optimizer)
            ? navKeys.optimizer
            : navKeys.analysis;

  return (
    <Layout className={styles.root}>
      <Header className={styles.header}>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(String(key))}
          className={styles.menu}
        />
        <div className={styles.headerRight}>
          <span className={styles.username} title={username ?? undefined}>
            {username ?? "…"}
          </span>
          <Button type="text" style={{ color: "rgba(255,255,255,0.88)" }} onClick={() => void handleLogout()}>
            退出
          </Button>
        </div>
      </Header>
      <Content className={styles.content}>
        <Outlet />
      </Content>
    </Layout>
  );
}

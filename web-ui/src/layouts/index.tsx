import { Button, Layout, Menu, Spin } from "antd";
import type { MenuProps } from "antd";
import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "umi";

import {
  authApi,
  clearAuthStorage,
  getRefreshToken,
  getStoredUsername,
  setStoredUsername,
} from "../utils";
import styles from "./index.less";

const { Header, Content } = Layout;

const navKeys = {
  analysis: "/",
  simAccount: "/sim-account",
  changelog: "/changelog",
} as const;

const menuItems: MenuProps["items"] = [
  { key: navKeys.analysis, label: "股票分析" },
  { key: navKeys.simAccount, label: "模拟账户模块" },
  { key: navKeys.changelog, label: "更新日志" },
];

export default function RootLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const [ready, setReady] = useState(false);
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!getRefreshToken()) {
      navigate("/login", { replace: true });
    }
  }, [ready, navigate]);

  const authed = ready && !!getRefreshToken();

  useEffect(() => {
    if (!authed) return;
    setUsername(getStoredUsername());
    authApi
      .me()
      .then((u) => {
        setUsername(u.username);
        setStoredUsername(u.username);
      })
      .catch(() => {
        clearAuthStorage();
        navigate("/login", { replace: true });
      });
  }, [authed, navigate]);

  const handleLogout = async () => {
    const rt = getRefreshToken();
    clearAuthStorage();
    setUsername(null);
    try {
      if (rt) {
        await authApi.logout(rt);
      }
    } catch {
      // 仍跳转登录页
    }
    navigate("/login", { replace: true });
  };

  if (!ready || !getRefreshToken()) {
    return (
      <div className={styles.authGate}>
        <Spin size="large" />
      </div>
    );
  }

  const selectedKey = pathname.startsWith(navKeys.changelog)
    ? navKeys.changelog
    : pathname.startsWith(navKeys.simAccount)
      ? navKeys.simAccount
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

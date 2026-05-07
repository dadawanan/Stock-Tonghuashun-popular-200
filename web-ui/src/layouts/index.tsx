import { Outlet, useLocation, useNavigate } from "umi";
import { Layout, Menu } from "antd";
import type { MenuProps } from "antd";
import styles from "./index.less";

const { Header, Content } = Layout;

const navKeys = {
  analysis: "/",
  simAccount: "/sim-account",
} as const;

const menuItems: MenuProps["items"] = [
  { key: navKeys.analysis, label: "股票分析" },
  { key: navKeys.simAccount, label: "模拟账户模块" },
];

export default function RootLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const selectedKey = pathname.startsWith(navKeys.simAccount)
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
      </Header>
      <Content className={styles.content}>
        <Outlet />
      </Content>
    </Layout>
  );
}

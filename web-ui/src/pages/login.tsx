import { Button, Card, Form, Input, message, Tabs, Typography } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "umi";

import {
  authApi,
  getRefreshToken,
  setStoredUsername,
  setTokens,
} from "../utils";
import styles from "./login.less";

export default function LoginPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<"login" | "register">("login");
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getRefreshToken()) {
      navigate("/", { replace: true });
    }
  }, [navigate]);

  const onLogin = async (v: { username: string; password: string }) => {
    setLoading(true);
    try {
      const tokens = await authApi.login(v.username.trim(), v.password);
      setTokens(tokens);
      const me = await authApi.me();
      setStoredUsername(me.username);
      void navigate("/", { replace: true });
    } finally {
      setLoading(false);
    }
  };

  const onRegister = async (v: {
    username: string;
    password: string;
    confirm: string;
  }) => {
    setLoading(true);
    try {
      await authApi.register(v.username.trim(), v.password);
      message.success("注册成功，请登录");
      loginForm.setFieldsValue({ username: v.username.trim() });
      setTab("login");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.wrap}>
      <Card className={styles.card} bordered={false}>
        <Typography.Title level={3} className={styles.title}>
          股票分析平台
        </Typography.Title>
        <Typography.Paragraph type="secondary" className={styles.sub}>
          登录后可使用分析、人气与新闻等接口
        </Typography.Paragraph>
        <Tabs
          activeKey={tab}
          onChange={(k) => setTab(k as "login" | "register")}
          items={[
            {
              key: "login",
              label: "登录",
              children: (
                <Form
                  form={loginForm}
                  layout="vertical"
                  onFinish={(vals) => void onLogin(vals)}
                  requiredMark={false}
                >
                  <Form.Item
                    name="username"
                    label="用户名"
                    rules={[{ required: true, message: "请输入用户名" }]}
                  >
                    <Input
                      autoComplete="username"
                      size="large"
                      placeholder="用户名"
                    />
                  </Form.Item>
                  <Form.Item
                    name="password"
                    label="密码"
                    rules={[{ required: true, message: "请输入密码" }]}
                  >
                    <Input.Password
                      autoComplete="current-password"
                      size="large"
                      placeholder="密码"
                    />
                  </Form.Item>
                  <Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      block
                      size="large"
                      loading={loading}
                    >
                      登录
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: "register",
              label: "注册",
              children: (
                <Form
                  form={registerForm}
                  layout="vertical"
                  onFinish={(vals) => void onRegister(vals)}
                  requiredMark={false}
                >
                  <Form.Item
                    name="username"
                    label="用户名"
                    rules={[
                      { required: true, message: "请输入用户名" },
                      { min: 2, max: 64, message: "长度需在 2–64 个字符之间" },
                    ]}
                  >
                    <Input autoComplete="username" size="large" />
                  </Form.Item>
                  <Form.Item
                    name="password"
                    label="密码"
                    rules={[
                      { required: true, message: "请输入密码" },
                      {
                        min: 6,
                        max: 128,
                        message: "长度需在 6–128 个字符之间",
                      },
                    ]}
                  >
                    <Input.Password autoComplete="new-password" size="large" />
                  </Form.Item>
                  <Form.Item
                    name="confirm"
                    label="确认密码"
                    dependencies={["password"]}
                    rules={[
                      { required: true, message: "请再次输入密码" },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue("password") === value) {
                            return Promise.resolve();
                          }
                          return Promise.reject(new Error("两次输入的密码不一致"));
                        },
                      }),
                    ]}
                  >
                    <Input.Password autoComplete="new-password" size="large" />
                  </Form.Item>
                  <Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      block
                      size="large"
                      loading={loading}
                    >
                      注册
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}

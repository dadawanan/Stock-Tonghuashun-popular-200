import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import {
  quantApi,
  SimAccount,
  Position,
  TradeOrder,
} from "../../utils";

const { Title, Text } = Typography;

export default function SimTradingPage() {
  const [accounts, setAccounts] = useState<SimAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<SimAccount | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<TradeOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [tradeForm] = Form.useForm();

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const data = await quantApi.listSimAccounts();
      setAccounts(Array.isArray(data) ? data : []);
      if (data && data.length > 0 && !selectedAccount) {
        selectAccount(data[0]);
      }
    } catch {
      message.error("加载账户列表失败");
    } finally {
      setLoading(false);
    }
  };

  const selectAccount = async (account: SimAccount) => {
    setSelectedAccount(account);
    try {
      const [posData, orderData] = await Promise.all([
        quantApi.getPositions(account.id),
        quantApi.getOrders(account.id),
      ]);
      setPositions(Array.isArray(posData) ? posData : []);
      setOrders(Array.isArray(orderData) ? orderData : []);
    } catch {
      message.error("加载账户详情失败");
    }
  };

  const handleCreateAccount = async () => {
    try {
      const values = await createForm.validateFields();
      await quantApi.createSimAccount({
        account_name: values.account_name,
        initial_capital: values.initial_capital || 1000000,
      });
      message.success("账户创建成功");
      setCreateModalOpen(false);
      loadAccounts();
    } catch (e: any) {
      message.error(e?.message || "创建失败");
    }
  };

  const handleTrade = async () => {
    try {
      const values = await tradeForm.validateFields();
      if (!selectedAccount) return;

      await quantApi.executeTrade({
        account_id: selectedAccount.id,
        code: values.code,
        side: values.side,
        quantity: values.quantity,
        price: values.price,
      });

      message.success("交易成功");
      setTradeModalOpen(false);
      tradeForm.resetFields();
      selectAccount(selectedAccount);
    } catch (e: any) {
      message.error(e?.message || "交易失败");
    }
  };

  const handleSettlement = async () => {
    if (!selectedAccount) return;
    try {
      const today = dayjs().format("YYYY-MM-DD");
      await quantApi.dailySettlement(selectedAccount.id, today);
      message.success("每日结算完成");
      selectAccount(selectedAccount);
    } catch (e: any) {
      message.error(e?.message || "结算失败");
    }
  };

  const positionColumns: ColumnsType<Position> = [
    { title: "股票代码", dataIndex: "code", width: 120 },
    { title: "持仓数量", dataIndex: "quantity", width: 100 },
    { title: "可用数量", dataIndex: "available_quantity", width: 100 },
    {
      title: "成本价",
      dataIndex: "avg_price",
      width: 100,
      render: (v: string) => parseFloat(v).toFixed(2),
    },
  ];

  const orderColumns: ColumnsType<TradeOrder> = [
    { title: "股票代码", dataIndex: "code", width: 120 },
    {
      title: "方向",
      dataIndex: "side",
      width: 80,
      render: (side: string) => (
        <Tag color={side === "buy" ? "green" : "red"}>
          {side === "buy" ? "买入" : "卖出"}
        </Tag>
      ),
    },
    {
      title: "价格",
      dataIndex: "price",
      width: 100,
      render: (v: string) => parseFloat(v).toFixed(2),
    },
    { title: "数量", dataIndex: "quantity", width: 100 },
    { title: "状态", dataIndex: "status", width: 80 },
    {
      title: "手续费",
      dataIndex: "commission",
      width: 100,
      render: (v: string | null) => (v ? parseFloat(v).toFixed(2) : "-"),
    },
    {
      title: "时间",
      dataIndex: "created_at",
      width: 180,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm:ss"),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Title level={3}>模拟盘</Title>
        <Space>
          <Button onClick={() => setCreateModalOpen(true)}>新建账户</Button>
          <Button type="primary" onClick={() => setTradeModalOpen(true)} disabled={!selectedAccount}>
            下单
          </Button>
          <Button onClick={handleSettlement} disabled={!selectedAccount}>
            每日结算
          </Button>
        </Space>
      </div>

      {selectedAccount && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic title="账户名称" value={selectedAccount.account_name} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="当前资金"
                value={parseFloat(selectedAccount.current_capital)}
                precision={2}
                prefix="¥"
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总资产"
                value={parseFloat(selectedAccount.total_assets)}
                precision={2}
                prefix="¥"
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="盈亏"
                value={parseFloat(selectedAccount.total_assets) - parseFloat(selectedAccount.initial_capital)}
                precision={2}
                prefix="¥"
                styles={{
                  content: {
                    color:
                      parseFloat(selectedAccount.total_assets) >= parseFloat(selectedAccount.initial_capital)
                        ? "#3f8600"
                        : "#cf1322",
                  },
                }}
              />
            </Card>
          </Col>
        </Row>
      )}

      <Row gutter={16}>
        <Col span={8}>
          <Card title="账户列表" size="small">
            <Table
              columns={[
                { title: "名称", dataIndex: "account_name" },
                {
                  title: "总资产",
                  dataIndex: "total_assets",
                  render: (v: string) => `¥${parseFloat(v).toFixed(2)}`,
                },
              ]}
              dataSource={accounts}
              rowKey="id"
              loading={loading}
              size="small"
              pagination={false}
              onRow={(record) => ({
                onClick: () => selectAccount(record),
                style: {
                  cursor: "pointer",
                  background: selectedAccount?.id === record.id ? "#e6f7ff" : undefined,
                },
              })}
            />
          </Card>
        </Col>

        <Col span={16}>
          <Card title="持仓" size="small" style={{ marginBottom: 16 }}>
            <Table columns={positionColumns} dataSource={positions} rowKey="id" size="small" pagination={false} />
          </Card>

          <Card title="交易记录" size="small">
            <Table columns={orderColumns} dataSource={orders} rowKey="id" size="small" pagination={{ pageSize: 10 }} />
          </Card>
        </Col>
      </Row>

      {/* Create Account Modal */}
      <Modal
        title="新建模拟账户"
        open={createModalOpen}
        onOk={handleCreateAccount}
        onCancel={() => setCreateModalOpen(false)}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="account_name" label="账户名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="initial_capital" label="初始资金" initialValue={1000000}>
            <InputNumber min={10000} step={100000} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Trade Modal */}
      <Modal
        title="下单"
        open={tradeModalOpen}
        onOk={handleTrade}
        onCancel={() => setTradeModalOpen(false)}
      >
        <Form form={tradeForm} layout="vertical">
          <Form.Item name="code" label="股票代码" rules={[{ required: true }]}>
            <Input placeholder="000725.SZ" />
          </Form.Item>
          <Form.Item name="side" label="方向" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "buy", label: "买入" },
                { value: "sell", label: "卖出" },
              ]}
            />
          </Form.Item>
          <Form.Item name="quantity" label="数量" rules={[{ required: true }]}>
            <InputNumber min={100} step={100} style={{ width: "100%" }} />
          </Form.Item>
          <div style={{ color: "#999", fontSize: 12, marginTop: -8 }}>
            * 价格为实时行情价，仅在交易时间（周一至周五 9:30-11:30, 13:00-15:00）可下单
          </div>
        </Form>
      </Modal>
    </div>
  );
}

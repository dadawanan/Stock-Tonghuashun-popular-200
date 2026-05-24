import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Popconfirm,
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
  PendingOrder,
  quantApi,
  SimAccount,
  Position,
  Strategy,
  TradeOrder,
} from "../../utils";

const { Title, Text } = Typography;

export default function SimTradingPage() {
  const [accounts, setAccounts] = useState<SimAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<SimAccount | null>(
    null,
  );
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<TradeOrder[]>([]);
  const [pendingOrders, setPendingOrders] = useState<PendingOrder[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedAccountKeys, setSelectedAccountKeys] = useState<React.Key[]>(
    [],
  );
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [sellModalOpen, setSellModalOpen] = useState(false);
  const [pendingOrderModalOpen, setPendingOrderModalOpen] = useState(false);
  const [sellPosition, setSellPosition] = useState<Position | null>(null);
  const [createForm] = Form.useForm();
  const [tradeForm] = Form.useForm();
  const [sellForm] = Form.useForm();
  const [pendingOrderForm] = Form.useForm();

  useEffect(() => {
    loadAccounts();
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      const data = await quantApi.listStrategies();
      setStrategies(Array.isArray(data) ? data : []);
    } catch {}
  };

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
      const [posData, orderData, pendingData] = await Promise.all([
        quantApi.getPositions(account.id),
        quantApi.getOrders(account.id),
        quantApi.listPendingOrders(account.id),
      ]);
      setPositions(Array.isArray(posData) ? posData : []);
      setOrders(Array.isArray(orderData) ? orderData : []);
      setPendingOrders(Array.isArray(pendingData) ? pendingData : []);
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
        strategy_id: values.strategy_id,
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

  const handleDeleteAccount = async (id: number) => {
    try {
      await quantApi.deleteSimAccount(id);
      message.success("账户已删除");
      if (selectedAccount?.id === id) {
        setSelectedAccount(null);
        setPositions([]);
        setOrders([]);
      }
      setSelectedAccountKeys((prev) => prev.filter((k) => k !== id));
      loadAccounts();
    } catch (e: any) {
      message.error(e?.message || "删除失败");
    }
  };

  const handleBatchDeleteAccounts = () => {
    if (selectedAccountKeys.length === 0) {
      message.warning("请先选择要删除的账户");
      return;
    }

    Modal.confirm({
      title: "确认批量删除",
      content: `确定要删除选中的 ${selectedAccountKeys.length} 个模拟账户吗？此操作不可恢复。`,
      okText: "确认删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        try {
          const ids = selectedAccountKeys.map(Number);
          let deleted = 0;
          for (const id of ids) {
            try {
              await quantApi.deleteSimAccount(id);
              deleted++;
            } catch {}
          }
          message.success(`成功删除 ${deleted} 个账户`);
          setSelectedAccountKeys([]);
          if (selectedAccount && ids.includes(selectedAccount.id)) {
            setSelectedAccount(null);
            setPositions([]);
            setOrders([]);
          }
          loadAccounts();
        } catch {
          message.error("批量删除失败");
        }
      },
    });
  };

  const handleOpenSellModal = (position: Position) => {
    setSellPosition(position);
    sellForm.setFieldsValue({
      code: position.code,
      quantity: position.available_quantity,
      price: null, // 需要从后端获取最新价格
    });
    setSellModalOpen(true);
  };

  const handleSellFromPosition = async () => {
    if (!selectedAccount || !sellPosition) return;
    try {
      const values = await sellForm.validateFields();
      await quantApi.executeTrade({
        account_id: selectedAccount.id,
        code: values.code,
        side: "sell",
        quantity: values.quantity,
        price: values.price,
      });
      message.success("卖出成功");
      setSellModalOpen(false);
      selectAccount(selectedAccount);
    } catch (e: any) {
      message.error(e?.message || "卖出失败");
    }
  };

  const handleCreatePendingOrder = async () => {
    if (!selectedAccount) return;
    try {
      const values = await pendingOrderForm.validateFields();
      await quantApi.createPendingOrder({
        account_id: selectedAccount.id,
        code: values.code,
        side: values.side,
        target_price: values.target_price,
        quantity: values.quantity,
        note: values.note,
      });
      message.success("挂单创建成功");
      setPendingOrderModalOpen(false);
      pendingOrderForm.resetFields();
      selectAccount(selectedAccount);
    } catch (e: any) {
      message.error(e?.message || "创建挂单失败");
    }
  };

  const handleCancelPendingOrder = async (orderId: number) => {
    try {
      await quantApi.cancelPendingOrder(orderId);
      message.success("挂单已取消");
      if (selectedAccount) {
        selectAccount(selectedAccount);
      }
    } catch (e: any) {
      message.error(e?.message || "取消失败");
    }
  };

  const handleCancelAllPendingOrders = async () => {
    if (!selectedAccount) return;
    try {
      const result = await quantApi.cancelAllPendingOrders(selectedAccount.id);
      message.success(`已取消 ${result.cancelled} 个挂单`);
      selectAccount(selectedAccount);
    } catch (e: any) {
      message.error(e?.message || "取消失败");
    }
  };

  const positionColumns: ColumnsType<Position> = [
    { title: "股票代码", dataIndex: "code", width: 110 },
    { title: "股票名称", dataIndex: "stock_name", width: 100 },
    { title: "持仓数量", dataIndex: "quantity", width: 90 },
    { title: "可用数量", dataIndex: "available_quantity", width: 90 },
    {
      title: "成本价",
      dataIndex: "avg_price",
      width: 80,
      render: (v: string) => parseFloat(v).toFixed(2),
    },
    {
      title: "操作",
      width: 80,
      render: (_, record) => (
        <Button
          size="small"
          danger
          disabled={
            !record.available_quantity || record.available_quantity <= 0
          }
          onClick={() => handleOpenSellModal(record)}
        >
          卖出
        </Button>
      ),
    },
  ];

  const orderColumns: ColumnsType<TradeOrder> = [
    { title: "股票代码", dataIndex: "code", width: 110 },
    { title: "股票名称", dataIndex: "stock_name", width: 100 },
    {
      title: "方向",
      dataIndex: "side",
      width: 70,
      render: (side: string) => (
        <Tag color={side === "buy" ? "green" : "red"}>
          {side === "buy" ? "买入" : "卖出"}
        </Tag>
      ),
    },
    {
      title: "价格",
      dataIndex: "price",
      width: 80,
      render: (v: string) => parseFloat(v).toFixed(2),
    },
    { title: "数量", dataIndex: "quantity", width: 80 },
    {
      title: "手续费",
      dataIndex: "commission",
      width: 80,
      render: (v: string | null) => (v ? parseFloat(v).toFixed(2) : "-"),
    },
    {
      title: "时间",
      dataIndex: "created_at",
      width: 160,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm:ss"),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <Title level={3}>模拟盘</Title>
        <Space>
          <Button onClick={() => setCreateModalOpen(true)}>新建账户</Button>
          <Button
            type="primary"
            onClick={() => setTradeModalOpen(true)}
            disabled={!selectedAccount}
          >
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
              <Statistic
                title="账户名称"
                value={selectedAccount.account_name}
              />
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
                value={
                  parseFloat(selectedAccount.total_assets) -
                  parseFloat(selectedAccount.initial_capital)
                }
                precision={2}
                prefix="¥"
                styles={{
                  content: {
                    color:
                      parseFloat(selectedAccount.total_assets) >=
                      parseFloat(selectedAccount.initial_capital)
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
          <Card
            title="账户列表"
            size="small"
            extra={
              selectedAccountKeys.length > 0 && (
                <Button size="small" danger onClick={handleBatchDeleteAccounts}>
                  批量删除 ({selectedAccountKeys.length})
                </Button>
              )
            }
          >
            <Table
              columns={[
                { title: "名称", dataIndex: "account_name", width: 120 },
                {
                  title: "策略",
                  dataIndex: "strategy_id",
                  width: 100,
                  render: (id: number | null) => {
                    if (!id)
                      return <span style={{ color: "#999" }}>未绑定</span>;
                    const s = strategies.find((s) => s.id === id);
                    return s ? <Tag>{s.name}</Tag> : `#${id}`;
                  },
                },
                {
                  title: "总资产",
                  dataIndex: "total_assets",
                  width: 100,
                  render: (v: string) => `¥${parseFloat(v).toFixed(2)}`,
                },
                {
                  title: "操作",
                  width: 60,
                  render: (_, record) => (
                    <Popconfirm
                      title="确定删除此账户？"
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        handleDeleteAccount(record.id);
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                    >
                      <Button
                        size="small"
                        danger
                        onClick={(e) => e.stopPropagation()}
                      >
                        删除
                      </Button>
                    </Popconfirm>
                  ),
                },
              ]}
              dataSource={accounts}
              rowKey="id"
              loading={loading}
              size="small"
              pagination={false}
              rowSelection={{
                selectedRowKeys: selectedAccountKeys,
                onChange: (keys) => setSelectedAccountKeys(keys),
              }}
              onRow={(record) => ({
                onClick: () => selectAccount(record),
                style: {
                  cursor: "pointer",
                  background:
                    selectedAccount?.id === record.id ? "#e6f7ff" : undefined,
                },
              })}
            />
          </Card>
        </Col>

        <Col span={16}>
          <Card
            title="持仓"
            size="small"
            style={{ marginBottom: 16 }}
            extra={
              <Button size="small" onClick={() => setPendingOrderModalOpen(true)}>
                挂单
              </Button>
            }
          >
            <Table
              columns={positionColumns}
              dataSource={positions}
              rowKey="id"
              size="small"
              pagination={false}
            />
          </Card>

          {pendingOrders.length > 0 && (
            <Card
              title="挂单列表"
              size="small"
              style={{ marginBottom: 16 }}
              extra={
                <Popconfirm
                  title="确定取消所有挂单？"
                  onConfirm={handleCancelAllPendingOrders}
                >
                  <Button size="small" danger>
                    全部取消
                  </Button>
                </Popconfirm>
              }
            >
              <Table
                columns={[
                  { title: "股票代码", dataIndex: "code", width: 100 },
                  { title: "股票名称", dataIndex: "stock_name", width: 90 },
                  {
                    title: "方向",
                    dataIndex: "side",
                    width: 60,
                    render: (side: string) => (
                      <Tag color={side === "buy" ? "green" : "red"}>
                        {side === "buy" ? "买入" : "卖出"}
                      </Tag>
                    ),
                  },
                  {
                    title: "目标价",
                    dataIndex: "target_price",
                    width: 80,
                    render: (v: string) => parseFloat(v).toFixed(2),
                  },
                  { title: "数量", dataIndex: "quantity", width: 80 },
                  { title: "备注", dataIndex: "note", ellipsis: true },
                  {
                    title: "操作",
                    width: 70,
                    render: (_, record) => (
                      <Popconfirm
                        title="确定取消此挂单？"
                        onConfirm={() => handleCancelPendingOrder(record.id)}
                      >
                        <Button size="small" danger>
                          取消
                        </Button>
                      </Popconfirm>
                    ),
                  },
                ]}
                dataSource={pendingOrders}
                rowKey="id"
                size="small"
                pagination={false}
              />
            </Card>
          )}

          <Card title="交易记录" size="small">
            <Table
              columns={orderColumns}
              dataSource={orders}
              rowKey="id"
              size="small"
              pagination={{ pageSize: 10 }}
            />
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
          <Form.Item
            name="account_name"
            label="账户名称"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="initial_capital"
            label="初始资金"
            initialValue={1000000}
          >
            <InputNumber min={10000} step={100000} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="strategy_id" label="绑定策略（可选）">
            <Select
              allowClear
              placeholder="选择策略后可自动交易"
              options={strategies.map((s) => ({
                value: s.id,
                label: `${s.name} (${s.type})`,
              }))}
            />
          </Form.Item>
          <div style={{ color: "#999", fontSize: 12, marginTop: -8 }}>
            * 绑定策略后，定时任务会在交易时间自动执行该策略的买卖信号
          </div>
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
            * 价格为实时行情价，仅在交易时间（周一至周五 9:30-11:30,
            13:00-15:00）可下单
          </div>
        </Form>
      </Modal>

      {/* Sell Modal */}
      <Modal
        title="卖出持仓"
        open={sellModalOpen}
        onOk={handleSellFromPosition}
        onCancel={() => setSellModalOpen(false)}
      >
        <Form form={sellForm} layout="vertical">
          <Form.Item name="code" label="股票代码">
            <Input disabled />
          </Form.Item>
          {sellPosition && (
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">
                {sellPosition.stock_name} | 持仓 {sellPosition.quantity} 股 |
                可卖 {sellPosition.available_quantity} 股
              </Text>
            </div>
          )}
          <Form.Item
            name="quantity"
            label="卖出数量"
            rules={[{ required: true }]}
          >
            <InputNumber
              min={100}
              max={sellPosition?.available_quantity || 0}
              step={100}
              style={{ width: "100%" }}
            />
          </Form.Item>
          <Form.Item name="price" label="价格（留空使用实时价）">
            <InputNumber
              min={0.01}
              step={0.01}
              style={{ width: "100%" }}
              placeholder="实时行情价"
            />
          </Form.Item>
          <div style={{ color: "#999", fontSize: 12, marginTop: -8 }}>
            * 交易时间内使用实时行情价，非交易时间可手动输入价格
          </div>
        </Form>
      </Modal>

      {/* Pending Order Modal */}
      <Modal
        title="创建挂单"
        open={pendingOrderModalOpen}
        onOk={handleCreatePendingOrder}
        onCancel={() => setPendingOrderModalOpen(false)}
      >
        <Form form={pendingOrderForm} layout="vertical">
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
          <Form.Item
            name="target_price"
            label="目标价格"
            rules={[{ required: true }]}
          >
            <InputNumber min={0.01} step={0.01} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            name="quantity"
            label="数量"
            rules={[{ required: true }]}
          >
            <InputNumber min={100} step={100} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input placeholder="可选" />
          </Form.Item>
          <div style={{ color: "#999", fontSize: 12, marginTop: -8 }}>
            <div>
              <Text strong>买入单：</Text>当股价{" "}
              <Text type="success">低于</Text> 目标价时自动成交
            </div>
            <div>
              <Text strong>卖出单：</Text>当股价{" "}
              <Text type="danger">高于</Text> 目标价时自动成交
            </div>
            <div>系统每分钟检查一次价格</div>
          </div>
        </Form>
      </Modal>
    </div>
  );
}

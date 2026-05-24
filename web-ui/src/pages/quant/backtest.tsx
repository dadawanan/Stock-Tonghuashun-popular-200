import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  InputNumber,
  message,
  Modal,
  Popconfirm,
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
import BacktestChart from "../../components/BacktestChart";
import { exportBacktestToCsv, exportBacktestTradesToCsv } from "../../utils/export";
import {
  BacktestResult,
  BacktestTrade,
  BacktestNav,
  quantApi,
  Strategy,
} from "../../utils";

const { Title, Text } = Typography;

export default function BacktestPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [results, setResults] = useState<BacktestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [selectedResult, setSelectedResult] = useState<BacktestResult | null>(null);
  const [trades, setTrades] = useState<BacktestTrade[]>([]);
  const [navData, setNavData] = useState<BacktestNav[]>([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [form] = Form.useForm();

  useEffect(() => {
    loadStrategies();
    loadResults();
  }, []);

  const loadStrategies = async () => {
    try {
      const data = await quantApi.listStrategies();
      setStrategies(Array.isArray(data) ? data : []);
    } catch {}
  };

  const loadResults = async () => {
    setLoading(true);
    try {
      const data = await quantApi.listBacktestResults();
      setResults(Array.isArray(data) ? data : []);
    } catch {
      message.error("加载回测结果失败");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await quantApi.deleteBacktestResult(id);
      message.success("删除成功");
      setSelectedRowKeys((prev) => prev.filter((k) => k !== id));
      if (selectedResult?.id === id) {
        setSelectedResult(null);
        setTrades([]);
        setNavData([]);
      }
      loadResults();
    } catch {
      message.error("删除失败");
    }
  };

  const handleBatchDelete = () => {
    if (selectedRowKeys.length === 0) {
      message.warning("请先选择要删除的记录");
      return;
    }

    Modal.confirm({
      title: "确认批量删除",
      content: `确定要删除选中的 ${selectedRowKeys.length} 条回测记录吗？此操作不可恢复。`,
      okText: "确认删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        try {
          const ids = selectedRowKeys.map(Number);
          const result = await quantApi.batchDeleteBacktestResults(ids);
          message.success(`成功删除 ${result.deleted} 条记录`);
          setSelectedRowKeys([]);
          if (selectedResult && ids.includes(selectedResult.id)) {
            setSelectedResult(null);
            setTrades([]);
            setNavData([]);
          }
          loadResults();
        } catch {
          message.error("批量删除失败");
        }
      },
    });
  };

  const handleRun = async () => {
    try {
      const values = await form.validateFields();
      setRunning(true);

      const strategyIds: number[] = values.strategy_ids;
      const startDate = values.dates[0].format("YYYY-MM-DD");
      const endDate = values.dates[1].format("YYYY-MM-DD");
      const initialCapital = values.initial_capital || 1000000;

      let successCount = 0;
      let totalTrades = 0;

      for (const strategyId of strategyIds) {
        try {
          const result = await quantApi.runBacktest({
            strategy_id: strategyId,
            start_date: startDate,
            end_date: endDate,
            initial_capital: initialCapital,
          });
          successCount++;
          totalTrades += result.trade_count || 0;
        } catch (e: any) {
          const strategy = strategies.find((s) => s.id === strategyId);
          message.error(`策略「${strategy?.name || strategyId}」回测失败: ${e?.message}`);
        }
      }

      if (successCount > 0) {
        message.success(`回测完成！${successCount} 个策略共 ${totalTrades} 笔交易`);
      }
      loadResults();
    } catch (e: any) {
      message.error(e?.message || "回测失败");
    } finally {
      setRunning(false);
    }
  };

  const handleViewDetail = async (record: BacktestResult) => {
    setSelectedResult(record);
    try {
      const [tradesData, navDataRes] = await Promise.all([
        quantApi.getBacktestTrades(record.id),
        quantApi.getBacktestNav(record.id),
      ]);
      setTrades(Array.isArray(tradesData) ? tradesData : []);
      setNavData(Array.isArray(navDataRes) ? navDataRes : []);
    } catch {
      message.error("加载详情失败");
    }
  };

  const strategyMap = Object.fromEntries(strategies.map((s) => [s.id, s.name]));

  const resultColumns: ColumnsType<BacktestResult> = [
    { title: "ID", dataIndex: "id", width: 60 },
    {
      title: "策略",
      dataIndex: "strategy_id",
      width: 120,
      render: (id: number) => strategyMap[id] || `#${id}`,
    },
    { title: "开始日期", dataIndex: "start_date", width: 110 },
    { title: "结束日期", dataIndex: "end_date", width: 110 },
    {
      title: "总收益",
      dataIndex: "total_return",
      width: 100,
      render: (v: number | null) =>
        v != null ? (
          <Text type={v >= 0 ? "success" : "danger"}>{(v * 100).toFixed(2)}%</Text>
        ) : (
          "-"
        ),
    },
    {
      title: "年化收益",
      dataIndex: "annual_return",
      width: 100,
      render: (v: number | null) =>
        v != null ? (
          <Text type={Number(v) >= 0 ? "success" : "danger"}>{(Number(v) * 100).toFixed(2)}%</Text>
        ) : (
          "-"
        ),
    },
    {
      title: "最大回撤",
      dataIndex: "max_drawdown",
      width: 100,
      render: (v: string | number | null) => (v != null ? `${(Number(v) * 100).toFixed(2)}%` : "-"),
    },
    {
      title: "夏普比率",
      dataIndex: "sharpe_ratio",
      width: 100,
      render: (v: string | number | null) => (v != null ? Number(v).toFixed(2) : "-"),
    },
    {
      title: "胜率",
      dataIndex: "win_rate",
      width: 80,
      render: (v: string | number | null) => (v != null ? `${(Number(v) * 100).toFixed(1)}%` : "-"),
    },
    { title: "交易次数", dataIndex: "total_trades", width: 90 },
    {
      title: "操作",
      width: 130,
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => handleViewDetail(record)}>
            详情
          </Button>
          <Popconfirm
            title="确定删除此回测记录？"
            description="删除后不可恢复"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const tradeColumns: ColumnsType<BacktestTrade> = [
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
    { title: "价格", dataIndex: "price", width: 80 },
    { title: "数量", dataIndex: "quantity", width: 80 },
    { title: "日期", dataIndex: "trade_date", width: 110 },
    {
      title: "盈亏",
      dataIndex: "pnl",
      width: 100,
      render: (v: string | number | null) =>
        v != null ? (
          <Text type={Number(v) >= 0 ? "success" : "danger"}>{Number(v).toFixed(2)}</Text>
        ) : (
          "-"
        ),
    },
    { title: "信号来源", dataIndex: "signal_source", width: 100 },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>回测系统</Title>

      <Card title="运行回测" style={{ marginBottom: 16 }}>
        <Form form={form} layout="inline" initialValues={{ initial_capital: 1000000 }}>
          <Form.Item name="strategy_ids" label="策略" rules={[{ required: true, message: "请选择至少一个策略" }]}>
            <Select mode="multiple" style={{ minWidth: 300 }} placeholder="选择策略（可多选）">
              {strategies.map((s) => (
                <Select.Option key={s.id} value={s.id}>
                  {s.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="dates" label="回测区间" rules={[{ required: true }]}>
            <DatePicker.RangePicker />
          </Form.Item>
          <Form.Item name="initial_capital" label="初始资金">
            <InputNumber min={10000} step={100000} style={{ width: 150 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={handleRun} loading={running}>
              运行回测
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic title="总回测次数" value={results.length} />
          </Card>
        </Col>
        {selectedResult && (
          <>
            <Col span={4}>
              <Card>
                <Statistic
                  title="总收益"
                  value={selectedResult.total_return != null ? Number(selectedResult.total_return) * 100 : 0}
                  precision={2}
                  suffix="%"
                  styles={{ content: { color: (Number(selectedResult.total_return) || 0) >= 0 ? "#3f8600" : "#cf1322" } }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card>
                <Statistic
                  title="年化收益"
                  value={selectedResult.annual_return != null ? Number(selectedResult.annual_return) * 100 : 0}
                  precision={2}
                  suffix="%"
                  styles={{ content: { color: (Number(selectedResult.annual_return) || 0) >= 0 ? "#3f8600" : "#cf1322" } }}
                />
              </Card>
            </Col>
            <Col span={4}>
              <Card>
                <Statistic
                  title="最大回撤"
                  value={selectedResult.max_drawdown != null ? Number(selectedResult.max_drawdown) * 100 : 0}
                  precision={2}
                  suffix="%"
                  styles={{ content: { color: "#cf1322" } }}
                />
              </Card>
            </Col>
            <Col span={3}>
              <Card>
                <Statistic title="夏普比率" value={Number(selectedResult.sharpe_ratio) || 0} precision={2} />
              </Card>
            </Col>
            <Col span={3}>
              <Card>
                <Statistic
                  title="胜率"
                  value={selectedResult.win_rate != null ? selectedResult.win_rate * 100 : 0}
                  precision={1}
                  suffix="%"
                />
              </Card>
            </Col>
          </>
        )}
      </Row>

      <Card
        title="回测记录"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            {selectedRowKeys.length > 0 && (
              <Button danger onClick={handleBatchDelete}>
                批量删除 ({selectedRowKeys.length})
              </Button>
            )}
            <Button onClick={() => exportBacktestToCsv(results, strategies)}>
              导出
            </Button>
          </Space>
        }
      >
        <Table
          columns={resultColumns}
          dataSource={results}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={false}
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys),
          }}
        />
      </Card>

      {selectedResult && (
        <>
          <BacktestChart backtestId={selectedResult.id} />

          <Card
            title={`交易明细 (回测 #${selectedResult.id})`}
            style={{ marginBottom: 16 }}
            extra={
              <Button onClick={() => exportBacktestTradesToCsv(trades, selectedResult.id)}>
                导出
              </Button>
            }
          >
            <Table columns={tradeColumns} dataSource={trades} rowKey={(record) => `${record.code}-${record.trade_date}-${record.side}`} size="small" pagination={{ pageSize: 20 }} />
          </Card>
        </>
      )}
    </div>
  );
}

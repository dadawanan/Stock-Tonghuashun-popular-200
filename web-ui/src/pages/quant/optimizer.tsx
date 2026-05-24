import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  InputNumber,
  message,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Alert,
  Spin,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { quantApi, Strategy } from "../../utils";

const { Title, Text, Paragraph } = Typography;

interface OptimizationResult {
  params: Record<string, any>;
  metrics: {
    total_return: number;
    annual_return: number;
    max_drawdown: number;
    sharpe_ratio: number;
    win_rate: number;
    total_trades: number;
  };
  backtest_id: number;
}

export default function OptimizerPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [results, setResults] = useState<OptimizationResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [suggestedParams, setSuggestedParams] = useState<Record<string, any[]>>({});
  const [form] = Form.useForm();

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      const data = await quantApi.listStrategies();
      setStrategies(Array.isArray(data) ? data : []);
    } catch {}
  };

  const handleStrategyChange = async (strategyId: number) => {
    const strategy = strategies.find((s) => s.id === strategyId);
    if (strategy) {
      try {
        const params = await quantApi.suggestParams(strategy.type);
        setSuggestedParams(params || {});
      } catch {
        setSuggestedParams({});
      }
    }
  };

  const handleRun = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      // Parse param_grid from form
      const paramGrid: Record<string, any[]> = {};
      for (const [key, value] of Object.entries(suggestedParams)) {
        if (Array.isArray(value) && value.length > 0) {
          paramGrid[key] = value;
        }
      }

      if (Object.keys(paramGrid).length === 0) {
        message.warning("没有可优化的参数");
        return;
      }

      const result = await quantApi.gridSearch({
        strategy_id: values.strategy_id,
        param_grid: paramGrid,
        start_date: values.dates[0].format("YYYY-MM-DD"),
        end_date: values.dates[1].format("YYYY-MM-DD"),
        initial_capital: values.initial_capital || 1000000,
        metric: values.metric || "sharpe_ratio",
        top_n: values.top_n || 5,
      });

      setResults(Array.isArray(result) ? result : []);
      message.success(`优化完成，找到 ${result.length} 个结果`);
    } catch (e: any) {
      message.error(e?.message || "优化失败");
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<OptimizationResult> = [
    {
      title: "排名",
      width: 60,
      render: (_, __, index) => index + 1,
    },
    {
      title: "参数",
      dataIndex: "params",
      render: (params: Record<string, any>) => (
        <div style={{ fontSize: 12 }}>
          {Object.entries(params).map(([k, v]) => (
            <div key={k}>
              <Text type="secondary">{k}:</Text> <Text strong>{String(v)}</Text>
            </div>
          ))}
        </div>
      ),
    },
    {
      title: "总收益",
      render: (_, record) => {
        const v = record.metrics?.total_return;
        return v != null ? (
          <Text type={v >= 0 ? "success" : "danger"}>{(v * 100).toFixed(2)}%</Text>
        ) : (
          "-"
        );
      },
    },
    {
      title: "年化收益",
      render: (_, record) => {
        const v = record.metrics?.annual_return;
        return v != null ? (
          <Text type={v >= 0 ? "success" : "danger"}>{(v * 100).toFixed(2)}%</Text>
        ) : (
          "-"
        );
      },
    },
    {
      title: "最大回撤",
      render: (_, record) => {
        const v = record.metrics?.max_drawdown;
        return v != null ? `${(v * 100).toFixed(2)}%` : "-";
      },
    },
    {
      title: "夏普比率",
      render: (_, record) => {
        const v = record.metrics?.sharpe_ratio;
        return v != null ? Number(v).toFixed(2) : "-";
      },
    },
    {
      title: "胜率",
      render: (_, record) => {
        const v = record.metrics?.win_rate;
        return v != null ? `${(v * 100).toFixed(1)}%` : "-";
      },
    },
    {
      title: "交易次数",
      render: (_, record) => record.metrics?.total_trades || 0,
    },
    {
      title: "操作",
      width: 80,
      render: (_, record) => (
        <Button
          size="small"
          onClick={() => {
            // Copy params to clipboard
            navigator.clipboard.writeText(JSON.stringify(record.params, null, 2));
            message.success("参数已复制");
          }}
        >
          复制参数
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>参数优化</Title>

      <Alert
        type="info"
        showIcon
        message="参数优化说明"
        description={
          <div>
            <p>网格搜索会遍历所有参数组合，找出最优参数。</p>
            <p>优化目标：夏普比率（越高越好）、总收益、胜率等。</p>
            <p style={{ color: "#999" }}>
              注意：参数组合越多，耗时越长。建议先小范围测试。
            </p>
          </div>
        }
        style={{ marginBottom: 16 }}
      />

      <Card title="配置优化参数" style={{ marginBottom: 16 }}>
        <Form form={form} layout="vertical" initialValues={{ metric: "sharpe_ratio", top_n: 5 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name="strategy_id" label="策略" rules={[{ required: true }]}>
                <Select
                  placeholder="选择策略"
                  onChange={handleStrategyChange}
                  options={strategies.map((s) => ({
                    value: s.id,
                    label: `${s.name} (${s.type})`,
                  }))}
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="dates" label="回测区间" rules={[{ required: true }]}>
                <DatePicker.RangePicker style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="initial_capital" label="初始资金" initialValue={1000000}>
                <InputNumber min={10000} step={100000} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="metric" label="优化目标">
                <Select
                  options={[
                    { value: "sharpe_ratio", label: "夏普比率" },
                    { value: "total_return", label: "总收益" },
                    { value: "win_rate", label: "胜率" },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={4}>
              <Form.Item name="top_n" label="返回数量">
                <InputNumber min={1} max={20} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </Row>

          {Object.keys(suggestedParams).length > 0 && (
            <Card title="参数搜索范围" size="small" style={{ marginBottom: 16 }}>
              <Row gutter={16}>
                {Object.entries(suggestedParams).map(([key, values]) => (
                  <Col span={4} key={key}>
                    <Text strong>{key}</Text>
                    <div style={{ marginTop: 4 }}>
                      {Array.isArray(values) &&
                        values.map((v, i) => (
                          <Tag key={i} style={{ marginBottom: 4 }}>
                            {v}
                          </Tag>
                        ))}
                    </div>
                  </Col>
                ))}
              </Row>
            </Card>
          )}

          <Button type="primary" onClick={handleRun} loading={loading}>
            开始优化
          </Button>
        </Form>
      </Card>

      {results.length > 0 && (
        <Card title="优化结果">
          <Table
            columns={columns}
            dataSource={results}
            rowKey={(_, index) => String(index)}
            size="small"
            pagination={false}
          />
        </Card>
      )}
    </div>
  );
}

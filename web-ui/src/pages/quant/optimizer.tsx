import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Form,
  InputNumber,
  message,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { quantApi, Strategy } from "../../utils";
import styles from "../common.less";

const { Title, Text } = Typography;

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

interface WFWindow {
  window_id: number;
  train_period: string;
  test_period: string;
  best_params: Record<string, any>;
  train_metrics: Record<string, number>;
  test_metrics: Record<string, number>;
}

interface WFResult {
  windows: WFWindow[];
  avg_test_metrics: Record<string, number>;
  best_params_per_window: Record<string, any>[];
  stability_score: number;
}

export default function OptimizerPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [results, setResults] = useState<OptimizationResult[]>([]);
  const [wfResult, setWfResult] = useState<WFResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [wfLoading, setWfLoading] = useState(false);
  const [suggestedParams, setSuggestedParams] = useState<Record<string, any[]>>({});
  const [form] = Form.useForm();
  const [wfForm] = Form.useForm();

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      const data = await quantApi.listStrategies();
      setStrategies(Array.isArray(data) ? data : []);
    } catch {}
  };

  const handleStrategyChange = async (strategyId: number, f: typeof form) => {
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

  const getParamGrid = (): Record<string, any[]> => {
    const paramGrid: Record<string, any[]> = {};
    for (const [key, value] of Object.entries(suggestedParams)) {
      if (Array.isArray(value) && value.length > 0) {
        paramGrid[key] = value;
      }
    }
    return paramGrid;
  };

  const handleRun = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const paramGrid = getParamGrid();
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

  const handleWalkForward = async () => {
    try {
      const values = await wfForm.validateFields();
      setWfLoading(true);
      setWfResult(null);
      const paramGrid = getParamGrid();
      if (Object.keys(paramGrid).length === 0) {
        message.warning("没有可优化的参数，请先在网格搜索 Tab 选择策略");
        return;
      }
      const result = await quantApi.walkForward({
        strategy_id: values.strategy_id,
        param_grid: paramGrid,
        start_date: values.dates[0].format("YYYY-MM-DD"),
        end_date: values.dates[1].format("YYYY-MM-DD"),
        train_days: values.train_days || 180,
        test_days: values.test_days || 60,
        step_days: values.step_days || 60,
        initial_capital: values.initial_capital || 1000000,
        metric: values.metric || "sharpe_ratio",
      });
      setWfResult(result);
      message.success(`滚动前进优化完成，${result.windows.length} 个窗口`);
    } catch (e: any) {
      message.error(e?.message || "优化失败");
    } finally {
      setWfLoading(false);
    }
  };

  const columns: ColumnsType<OptimizationResult> = [
    { title: "排名", width: 60, render: (_, __, index) => index + 1 },
    {
      title: "参数",
      dataIndex: "params",
      render: (params) => (
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
      render: (_, r) => {
        const v = r.metrics?.total_return;
        return v != null ? <Text type={v >= 0 ? "success" : "danger"}>{(v * 100).toFixed(2)}%</Text> : "-";
      },
    },
    {
      title: "年化收益",
      render: (_, r) => {
        const v = r.metrics?.annual_return;
        return v != null ? <Text type={v >= 0 ? "success" : "danger"}>{(v * 100).toFixed(2)}%</Text> : "-";
      },
    },
    {
      title: "最大回撤",
      render: (_, r) => (r.metrics?.max_drawdown != null ? `${(r.metrics.max_drawdown * 100).toFixed(2)}%` : "-"),
    },
    {
      title: "夏普比率",
      render: (_, r) => (r.metrics?.sharpe_ratio != null ? Number(r.metrics.sharpe_ratio).toFixed(2) : "-"),
    },
    {
      title: "胜率",
      render: (_, r) => (r.metrics?.win_rate != null ? `${(r.metrics.win_rate * 100).toFixed(1)}%` : "-"),
    },
    { title: "交易次数", render: (_, r) => r.metrics?.total_trades || 0 },
    {
      title: "操作",
      width: 80,
      render: (_, record) => (
        <Button
          size="small"
          onClick={() => {
            navigator.clipboard.writeText(JSON.stringify(record.params, null, 2));
            message.success("参数已复制");
          }}
        >
          复制参数
        </Button>
      ),
    },
  ];

  const wfColumns: ColumnsType<WFWindow> = [
    { title: "窗口", dataIndex: "window_id", width: 60 },
    { title: "训练期", dataIndex: "train_period", width: 200 },
    { title: "测试期", dataIndex: "test_period", width: 200 },
    {
      title: "最优参数",
      dataIndex: "best_params",
      render: (params) => (
        <div style={{ fontSize: 11 }}>
          {Object.entries(params).map(([k, v]) => (
            <span key={k} style={{ marginRight: 8 }}>
              {k}=<strong>{String(v)}</strong>
            </span>
          ))}
        </div>
      ),
    },
    {
      title: "测试收益",
      render: (_, r) => {
        const v = r.test_metrics?.total_return;
        return v != null ? <Text type={v >= 0 ? "success" : "danger"}>{(v * 100).toFixed(2)}%</Text> : "-";
      },
    },
    {
      title: "测试夏普",
      render: (_, r) => (r.test_metrics?.sharpe_ratio != null ? Number(r.test_metrics.sharpe_ratio).toFixed(2) : "-"),
    },
    {
      title: "测试回撤",
      render: (_, r) => (r.test_metrics?.max_drawdown != null ? `${(r.test_metrics.max_drawdown * 100).toFixed(2)}%` : "-"),
    },
  ];

  const commonFormFields = (
    <>
      <Col span={6}>
        <Form.Item name="strategy_id" label="策略" rules={[{ required: true }]}>
          <Select
            placeholder="选择策略"
            onChange={(v) => handleStrategyChange(v, form)}
            options={strategies.map((s) => ({ value: s.id, label: `${s.name} (${s.type})` }))}
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
        <Form.Item name="metric" label="优化目标" initialValue="sharpe_ratio">
          <Select
            options={[
              { value: "sharpe_ratio", label: "夏普比率" },
              { value: "total_return", label: "总收益" },
              { value: "win_rate", label: "胜率" },
            ]}
          />
        </Form.Item>
      </Col>
    </>
  );

  return (
    <div className={styles.pageContainer}>
      <Title level={3} className={styles.pageTitle}>参数优化</Title>

      <Tabs
        items={[
          {
            key: "grid",
            label: "网格搜索",
            children: (
              <>
                <Alert
                  type="info"
                  showIcon
                  message="网格搜索"
                  description="遍历所有参数组合，找出最优参数。参数组合越多，耗时越长。"
                  className={styles.sectionGap}
                />
                <Card title="配置" className={styles.sectionGap}>
                  <Form form={form} layout="vertical" initialValues={{ top_n: 5 }}>
                    <Row gutter={16}>
                      {commonFormFields}
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
                                {Array.isArray(values) && values.map((v, i) => <Tag key={i} style={{ marginBottom: 4 }}>{v}</Tag>)}
                              </div>
                            </Col>
                          ))}
                        </Row>
                      </Card>
                    )}
                    <Button type="primary" onClick={handleRun} loading={loading}>开始优化</Button>
                  </Form>
                </Card>
                {results.length > 0 && (
                  <Card title="优化结果">
                    <Table columns={columns} dataSource={results} rowKey={(_, i) => String(i)} size="small" pagination={false} />
                  </Card>
                )}
              </>
            ),
          },
          {
            key: "wf",
            label: "滚动前进优化",
            children: (
              <>
                <Alert
                  type="warning"
                  showIcon
                  message="滚动前进优化（Walk-Forward）"
                  description={
                    <div>
                      <p>将历史数据分成多个滚动窗口，每个窗口在训练期找最优参数，在测试期验证。</p>
                      <p>最终取各窗口测试结果的平均值，有效防止过拟合。</p>
                      <p style={{ color: "#999" }}>参数稳定性越高（接近1），说明策略在不同时期都适用。</p>
                    </div>
                  }
                  className={styles.sectionGap}
                />
                <Card title="配置" className={styles.sectionGap}>
                  <Form form={wfForm} layout="vertical" initialValues={{ train_days: 180, test_days: 60, step_days: 60 }}>
                    <Row gutter={16}>
                      {commonFormFields}
                      <Col span={2}>
                        <Form.Item name="train_days" label="训练天数">
                          <InputNumber min={60} max={365} step={30} style={{ width: "100%" }} />
                        </Form.Item>
                      </Col>
                      <Col span={2}>
                        <Form.Item name="test_days" label="测试天数">
                          <InputNumber min={20} max={180} step={10} style={{ width: "100%" }} />
                        </Form.Item>
                      </Col>
                      <Col span={2}>
                        <Form.Item name="step_days" label="步长天数">
                          <InputNumber min={10} max={180} step={10} style={{ width: "100%" }} />
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
                                {Array.isArray(values) && values.map((v, i) => <Tag key={i} style={{ marginBottom: 4 }}>{v}</Tag>)}
                              </div>
                            </Col>
                          ))}
                        </Row>
                      </Card>
                    )}
                    <Button type="primary" onClick={handleWalkForward} loading={wfLoading}>开始滚动优化</Button>
                  </Form>
                </Card>

                {wfResult && (
                  <>
                    <Card title="汇总" className={styles.sectionGap}>
                      <Descriptions bordered size="small" column={4}>
                        <Descriptions.Item label="有效窗口">{wfResult.windows.length}</Descriptions.Item>
                        <Descriptions.Item label="参数稳定性">
                          <Text type={wfResult.stability_score >= 0.7 ? "success" : wfResult.stability_score >= 0.4 ? "warning" : "danger"}>
                            {(wfResult.stability_score * 100).toFixed(0)}%
                          </Text>
                        </Descriptions.Item>
                        {Object.entries(wfResult.avg_test_metrics).map(([k, v]) => (
                          <Descriptions.Item key={k} label={k.replace("avg_", "").replace(/_/g, " ")}>
                            {typeof v === "number" ? (k.includes("return") || k.includes("drawdown") || k.includes("win_rate") ? `${(v * 100).toFixed(2)}%` : v.toFixed(4)) : String(v)}
                          </Descriptions.Item>
                        ))}
                      </Descriptions>
                    </Card>
                    <Card title="各窗口详情">
                      <Table columns={wfColumns} dataSource={wfResult.windows} rowKey="window_id" size="small" pagination={false} />
                    </Card>
                  </>
                )}
              </>
            ),
          },
        ]}
      />
    </div>
  );
}

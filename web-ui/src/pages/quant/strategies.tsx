import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Collapse,
  Form,
  Input,
  message,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { quantApi, Strategy } from "../../utils";
import styles from "../common.less";

const { Title, Paragraph, Text, Link } = Typography;

const strategyTypeLabels: Record<string, { label: string; color: string }> = {
  popularity: { label: "人气榜策略", color: "blue" },
  sentiment: { label: "情绪驱动策略", color: "green" },
  technical: { label: "技术面策略", color: "orange" },
  multi_factor: { label: "多因子策略", color: "purple" },
  volume_price: { label: "量价策略", color: "cyan" },
  momentum: { label: "动量策略", color: "magenta" },
  mean_reversion: { label: "均值回归策略", color: "gold" },
  fund_flow: { label: "资金流策略", color: "lime" },
  breakout: { label: "突破策略", color: "red" },
  grid: { label: "网格策略", color: "geekblue" },
};

const strategyGuides = [
  {
    key: "popularity",
    label: "人气榜策略 (popularity)",
    description:
      "基于同花顺人气榜排名变化生成信号。当股票新进入榜单或排名大幅下降时产生买入信号，排名大幅上升时产生卖出信号。",
    params: [
      {
        name: "top_n",
        type: "number",
        default: "50",
        desc: "只关注人气榜前 N 名的股票",
      },
      {
        name: "new_entry_score_boost",
        type: "number",
        default: "1.2",
        desc: "新进入榜单的股票信号强度加权倍数",
      },
      {
        name: "rank_drop_threshold",
        type: "number",
        default: "-20",
        desc: "排名下降超过此值时触发买入信号（负数表示下降）",
      },
    ],
    example:
      '{"top_n": 50, "new_entry_score_boost": 1.2, "rank_drop_threshold": -20}',
  },
  {
    key: "sentiment",
    label: "情绪驱动策略 (sentiment)",
    description:
      "基于新闻情绪分析和市场行为分析的综合得分生成信号。需要先运行分析流水线生成 text_score、market_score 等数据。",
    params: [
      {
        name: "text_weight",
        type: "number",
        default: "0.55",
        desc: "文本情绪分数权重（0-1）",
      },
      {
        name: "market_weight",
        type: "number",
        default: "0.45",
        desc: "市场行为分数权重（0-1）",
      },
      {
        name: "buy_threshold",
        type: "number",
        default: "2.0",
        desc: "综合得分超过此值时触发买入",
      },
      {
        name: "sell_threshold",
        type: "number",
        default: "-1.5",
        desc: "综合得分低于此值时触发卖出",
      },
    ],
    example:
      '{"text_weight": 0.55, "market_weight": 0.45, "buy_threshold": 2.0, "sell_threshold": -1.5}',
  },
  {
    key: "technical",
    label: "技术面策略 (technical)",
    description:
      "基于 MA、RSI、MACD 等技术指标生成信号。MA5 上穿 MA20 为买入信号，RSI 超卖/超买、MACD 金叉/死叉作为辅助确认。",
    params: [
      { name: "ma_short", type: "number", default: "5", desc: "短期均线周期" },
      { name: "ma_long", type: "number", default: "20", desc: "长期均线周期" },
      {
        name: "rsi_overbought",
        type: "number",
        default: "70",
        desc: "RSI 超买阈值（高于此值视为超买）",
      },
      {
        name: "rsi_oversold",
        type: "number",
        default: "30",
        desc: "RSI 超卖阈值（低于此值视为超卖）",
      },
      {
        name: "buy_threshold",
        type: "number",
        default: "0.3",
        desc: "买入信号阈值（综合得分超过此值触发）",
      },
      {
        name: "sell_threshold",
        type: "number",
        default: "-0.3",
        desc: "卖出信号阈值（综合得分低于此值触发）",
      },
    ],
    example:
      '{"ma_short": 5, "ma_long": 20, "rsi_overbought": 70, "rsi_oversold": 30, "buy_threshold": 0.3, "sell_threshold": -0.3}',
  },
  {
    key: "multi_factor",
    label: "多因子策略 (multi_factor)",
    description:
      "将人气榜、情绪驱动、技术面三种策略的信号按权重加权组合。综合多个信号源，降低单一信号的误判风险。",
    params: [
      {
        name: "weights.popularity",
        type: "number",
        default: "0.25",
        desc: "人气榜信号权重（0-1）",
      },
      {
        name: "weights.sentiment",
        type: "number",
        default: "0.35",
        desc: "情绪驱动信号权重（0-1）",
      },
      {
        name: "weights.technical",
        type: "number",
        default: "0.40",
        desc: "技术面信号权重（0-1）",
      },
      {
        name: "buy_threshold",
        type: "number",
        default: "0.6",
        desc: "加权综合得分超过此值时触发买入",
      },
      {
        name: "sell_threshold",
        type: "number",
        default: "-0.4",
        desc: "加权综合得分低于此值时触发卖出",
      },
    ],
    example:
      '{"weights": {"popularity": 0.25, "sentiment": 0.35, "technical": 0.40}, "buy_threshold": 0.6, "sell_threshold": -0.4}',
  },
  {
    key: "volume_price",
    label: "量价策略 (volume_price)",
    description:
      "基于成交量和价格的关系生成信号。放量上涨为买入信号，放量下跌为卖出信号，缩量横盘为观望。",
    params: [
      {
        name: "volume_ratio_threshold",
        type: "number",
        default: "1.5",
        desc: "放量倍数阈值（量比超过此值视为放量）",
      },
      {
        name: "price_change_threshold",
        type: "number",
        default: "2.0",
        desc: "涨跌幅阈值(%)",
      },
      {
        name: "buy_threshold",
        type: "number",
        default: "0.3",
        desc: "买入信号阈值",
      },
      {
        name: "sell_threshold",
        type: "number",
        default: "-0.3",
        desc: "卖出信号阈值",
      },
    ],
    example:
      '{"volume_ratio_threshold": 1.5, "price_change_threshold": 2.0, "buy_threshold": 0.3, "sell_threshold": -0.3}',
  },
  {
    key: "momentum",
    label: "动量策略 (momentum)",
    description:
      "基于价格动量生成信号。强势上涨趋势中追涨买入，弱势下跌趋势中卖出。",
    params: [
      {
        name: "lookback_days",
        type: "number",
        default: "5",
        desc: "回看天数",
      },
      {
        name: "momentum_threshold",
        type: "number",
        default: "3.0",
        desc: "动量阈值(%)，超过此值视为强势/弱势",
      },
      {
        name: "buy_threshold",
        type: "number",
        default: "0.3",
        desc: "买入信号阈值",
      },
      {
        name: "sell_threshold",
        type: "number",
        default: "-0.3",
        desc: "卖出信号阈值",
      },
    ],
    example:
      '{"lookback_days": 5, "momentum_threshold": 3.0, "buy_threshold": 0.3, "sell_threshold": -0.3}',
  },
  {
    key: "mean_reversion",
    label: "均值回归策略 (mean_reversion)",
    description:
      "价格偏离均线过多时反向操作。价格远低于均线时买入（超卖），远高于均线时卖出（超买）。",
    params: [
      {
        name: "deviation_threshold",
        type: "number",
        default: "5.0",
        desc: "偏离均线阈值(%)，超过此值触发信号",
      },
      {
        name: "ma_period",
        type: "number",
        default: "20",
        desc: "均线周期",
      },
      {
        name: "buy_threshold",
        type: "number",
        default: "0.3",
        desc: "买入信号阈值",
      },
      {
        name: "sell_threshold",
        type: "number",
        default: "-0.3",
        desc: "卖出信号阈值",
      },
    ],
    example:
      '{"deviation_threshold": 5.0, "ma_period": 20, "buy_threshold": 0.3, "sell_threshold": -0.3}',
  },
  {
    key: "fund_flow",
    label: "资金流策略 (fund_flow)",
    description:
      "基于主力资金净流入生成信号。主力大幅净流入时买入，大幅净流出时卖出。",
    params: [
      {
        name: "inflow_threshold",
        type: "number",
        default: "1000000",
        desc: "净流入阈值(元)，超过此值触发买入",
      },
      {
        name: "outflow_threshold",
        type: "number",
        default: "-1000000",
        desc: "净流出阈值(元)，低于此值触发卖出",
      },
      {
        name: "buy_threshold",
        type: "number",
        default: "0.3",
        desc: "买入信号阈值",
      },
      {
        name: "sell_threshold",
        type: "number",
        default: "-0.3",
        desc: "卖出信号阈值",
      },
    ],
    example:
      '{"inflow_threshold": 1000000, "outflow_threshold": -1000000, "buy_threshold": 0.3, "sell_threshold": -0.3}',
  },
  {
    key: "breakout",
    label: "突破策略 (breakout)",
    description:
      "价格突破布林带上轨时买入（强势突破），跌破布林带下轨时卖出（弱势跌破）。",
    params: [
      {
        name: "lookback_days",
        type: "number",
        default: "20",
        desc: "回看天数（用于计算布林带）",
      },
      {
        name: "breakout_pct",
        type: "number",
        default: "1.0",
        desc: "突破幅度(%)",
      },
      {
        name: "buy_threshold",
        type: "number",
        default: "0.3",
        desc: "买入信号阈值",
      },
      {
        name: "sell_threshold",
        type: "number",
        default: "-0.3",
        desc: "卖出信号阈值",
      },
    ],
    example:
      '{"lookback_days": 20, "breakout_pct": 1.0, "buy_threshold": 0.3, "sell_threshold": -0.3}',
  },
  {
    key: "grid",
    label: "网格策略 (grid)",
    description:
      "在设定价格区间内进行网格交易。价格偏离均线越远，信号越强。适合震荡行情。",
    params: [
      {
        name: "grid_pct",
        type: "number",
        default: "3.0",
        desc: "网格大小(%)",
      },
      {
        name: "upper_limit",
        type: "number",
        default: "20.0",
        desc: "上限偏离(%)，超过此值卖出",
      },
      {
        name: "lower_limit",
        type: "number",
        default: "-20.0",
        desc: "下限偏离(%)，低于此值买入",
      },
      {
        name: "buy_threshold",
        type: "number",
        default: "0.3",
        desc: "买入信号阈值",
      },
      {
        name: "sell_threshold",
        type: "number",
        default: "-0.3",
        desc: "卖出信号阈值",
      },
    ],
    example:
      '{"grid_pct": 3.0, "upper_limit": 20.0, "lower_limit": -20.0, "buy_threshold": 0.3, "sell_threshold": -0.3}',
  },
];

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const data = await quantApi.listStrategies();
      setStrategies(Array.isArray(data) ? data : []);
    } catch {
      message.error("加载策略列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStrategies();
  }, []);

  const handleCreate = () => {
    setEditingId(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: Strategy) => {
    setEditingId(record.id);
    form.setFieldsValue({
      name: record.name,
      type: record.type,
      description: record.description,
      params: JSON.stringify(record.params, null, 2),
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const params = values.params ? JSON.parse(values.params) : {};

      if (editingId) {
        await quantApi.updateStrategy(editingId, {
          name: values.name,
          params,
          description: values.description,
        });
        message.success("策略已更新");
      } else {
        await quantApi.createStrategy({
          name: values.name,
          type: values.type,
          params,
          description: values.description,
        });
        message.success("策略已创建");
      }

      setModalOpen(false);
      loadStrategies();
    } catch (e: any) {
      if (e?.message) {
        message.error(e.message);
      }
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await quantApi.deleteStrategy(id);
      message.success("策略已删除");
      loadStrategies();
    } catch {
      message.error("删除失败");
    }
  };

  const handleFillExample = (type: string) => {
    const guide = strategyGuides.find((g) => g.key === type);
    if (guide) {
      form.setFieldsValue({ params: guide.example });
    }
  };

  const columns: ColumnsType<Strategy> = [
    { title: "名称", dataIndex: "name", width: 150 },
    {
      title: "类型",
      dataIndex: "type",
      width: 130,
      render: (type: string) => {
        const meta = strategyTypeLabels[type] || {
          label: type,
          color: "default",
        };
        return <Tag color={meta.color}>{meta.label}</Tag>;
      },
    },
    {
      title: "参数",
      dataIndex: "params",
      ellipsis: true,
      render: (params: Record<string, any>) => (
        <span style={{ fontSize: 12, color: "#666" }}>
          {JSON.stringify(params).slice(0, 80)}...
        </span>
      ),
    },
    { title: "描述", dataIndex: "description", ellipsis: true },
    {
      title: "状态",
      dataIndex: "is_active",
      width: 80,
      render: (active: boolean) => (
        <Tag color={active ? "success" : "default"}>
          {active ? "启用" : "禁用"}
        </Tag>
      ),
    },
    {
      title: "操作",
      width: 150,
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Button size="small" danger onClick={() => handleDelete(record.id)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  const selectedType = Form.useWatch("type", form);

  return (
    <div className={styles.pageContainer}>
      <div className={styles.pageHeader}>
        <Title level={3} className={styles.pageTitle}>策略管理</Title>
        <Button type="primary" onClick={handleCreate}>
          新建策略
        </Button>
      </div>

      {/* 使用说明 */}
      <Card title="使用说明" className={styles.sectionGap}>
        <Paragraph>
          策略是量化交易的核心，决定了何时买入、何时卖出。系统提供 4
          种内置策略，每种策略有不同的参数可调。
          你可以修改参数来调整策略的激进程度，也可以创建多个同类型策略来对比不同参数的效果。
        </Paragraph>

        <Paragraph>
          <Text strong>使用流程：</Text>
        </Paragraph>
        <ol style={{ marginBottom: 16 }}>
          <li>选择或创建一个策略</li>
          <li>在「回测系统」中用历史数据验证策略效果</li>
          <li>根据回测结果调整参数（闭环反馈会给出建议）</li>
          <li>在「模拟盘」中用实时行情模拟交易</li>
        </ol>

        <Collapse
          items={strategyGuides.map((guide) => ({
            key: guide.key,
            label: guide.label,
            children: (
              <>
                <Paragraph>{guide.description}</Paragraph>
                <Paragraph>
                  <Text strong>参数说明：</Text>
                </Paragraph>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    marginBottom: 16,
                  }}
                >
                  <thead>
                    <tr style={{ borderBottom: "1px solid #f0f0f0" }}>
                      <th style={{ textAlign: "left", padding: "8px 12px" }}>
                        参数名
                      </th>
                      <th style={{ textAlign: "left", padding: "8px 12px" }}>
                        类型
                      </th>
                      <th style={{ textAlign: "left", padding: "8px 12px" }}>
                        默认值
                      </th>
                      <th style={{ textAlign: "left", padding: "8px 12px" }}>
                        说明
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {guide.params.map((p) => (
                      <tr
                        key={p.name}
                        style={{ borderBottom: "1px solid #f0f0f0" }}
                      >
                        <td style={{ padding: "8px 12px" }}>
                          <code>{p.name}</code>
                        </td>
                        <td style={{ padding: "8px 12px" }}>{p.type}</td>
                        <td style={{ padding: "8px 12px" }}>
                          <code>{p.default}</code>
                        </td>
                        <td style={{ padding: "8px 12px" }}>{p.desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <Paragraph>
                  <Text type="secondary">示例参数：</Text>
                  <br />
                  <code
                    style={{
                      background: "#f5f5f5",
                      padding: "4px 8px",
                      borderRadius: 4,
                    }}
                  >
                    {guide.example}
                  </code>
                </Paragraph>
              </>
            ),
          }))}
        />
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={strategies}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      <Modal
        title={editingId ? "编辑策略" : "新建策略"}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="策略名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label="策略类型" rules={[{ required: true }]}>
            <Select
              options={Object.entries(strategyTypeLabels).map(
                ([value, { label }]) => ({
                  value,
                  label,
                }),
              )}
              disabled={!!editingId}
            />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="params"
            label={
              <Space>
                <span>参数 (JSON)</span>
                {selectedType && (
                  <Button
                    size="small"
                    type="link"
                    onClick={() => handleFillExample(selectedType)}
                  >
                    填入示例
                  </Button>
                )}
              </Space>
            }
          >
            <Input.TextArea
              rows={6}
              placeholder='{"buy_threshold": 0.3, "sell_threshold": -0.3}'
              style={{ fontFamily: "monospace" }}
            />
          </Form.Item>
          {selectedType && (
            <Alert
              type="info"
              showIcon
              message={`已选择「${strategyTypeLabels[selectedType]?.label || selectedType}」，点击上方「填入示例」可快速填入默认参数。`}
              style={{ marginBottom: 16 }}
            />
          )}
        </Form>
      </Modal>
    </div>
  );
}

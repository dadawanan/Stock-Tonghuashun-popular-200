import {
  BarChartOutlined,
  LineChartOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  Button,
  Card,
  Col,
  DatePicker,
  message,
  Modal,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import {
  analysisApi,
  AnalysisResult,
  copyToClipboard,
  newsApi,
  NewsItem,
} from "../utils";
import dayjs from "dayjs";
import styles from "./index.less";

const { Title, Paragraph, Text } = Typography;
const { RangePicker } = DatePicker;

const EVENT_LABEL_MAP: Record<string, string> = {
  major_order: "大订单",
  supply_chain_risk: "供应链风险",
  earnings_growth: "盈利增长",
  management_risk: "管理风险",
  technology_breakthrough: "科技突破",
  policy_support: "政策支持",
  other: "其他",
};

const EVENT_COLOR_MAP: Record<string, string> = {
  大订单: "blue",
  供应链风险: "red",
  盈利增长: "green",
  管理风险: "orange",
  科技突破: "purple",
  政策支持: "cyan",
  其他: "default",
};

const DECISION_COLOR_MAP: Record<string, string> = {
  买入: "green",
  推荐买入: "green",
  卖出: "red",
  推荐卖出: "red",
  观望: "default",
  持有: "blue",
  减持: "orange",
};

function ScoreBar({
  value,
  max = 10,
}: {
  value: number | string;
  max?: number;
}) {
  const num = typeof value === "string" ? parseFloat(value) : value;
  const safe = isNaN(num) ? 0 : num;
  const pct = Math.min(Math.max((safe / max) * 100, 0), 100);
  const color = safe >= 7 ? "#52c41a" : safe >= 4 ? "#faad14" : "#ff4d4f";
  return (
    <div className={styles.scoreBar}>
      <div className={styles.scoreBarBg}>
        <div
          className={styles.scoreBarFill}
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className={styles.scoreBarValue}>{safe.toFixed(1)}</span>
    </div>
  );
}

export default function HomePage() {
  const [data, setData] = useState<AnalysisResult[]>([]);
  const [totalData, setTotalData] = useState<AnalysisResult[]>([]);
  const [running, setRunning] = useState(false);
  const [singleModalOpen, setSingleModalOpen] = useState(false);
  const [singleStockInput, setSingleStockInput] = useState("");
  const [singleAnalyzing, setSingleAnalyzing] = useState(false);
  const [newsModalOpen, setNewsModalOpen] = useState(false);
  const [newsLoading, setNewsLoading] = useState(false);
  const [newsRows, setNewsRows] = useState<NewsItem[]>([]);
  const [newsModalTitle, setNewsModalTitle] = useState("");
  const [filters, setFilters] = useState<{
    startTime: string | null;
    endTime: string | null;
  }>({ startTime: "", endTime: "" });

  const openNewsModal = (record: AnalysisResult) => {
    setNewsModalTitle(`${record.stock_name}（${record.stock_code}）`);
    setNewsModalOpen(true);
    setNewsLoading(true);
    setNewsRows([]);
    newsApi
      .getByStockCode(record.stock_code, 100)
      .then((rows) => setNewsRows(Array.isArray(rows) ? rows : []))
      .catch(() => setNewsRows([]))
      .finally(() => setNewsLoading(false));
  };

  const stats = useMemo(() => {
    const total = data.length;
    const bullish = data.filter(
      (d) => d.text_event_label === "利好" || d.decision?.includes("买入"),
    ).length;
    const bearish = data.filter(
      (d) => d.text_event_label === "利空" || d.decision?.includes("卖出"),
    ).length;
    const neutral = total - bullish - bearish;
    const avgScore =
      total > 0
        ? data.reduce((sum, d) => sum + Number(d.integrated_score || 0), 0) /
          total
        : 0;
    return { total, bullish, bearish, neutral, avgScore };
  }, [data]);

  const columns: ColumnsType<AnalysisResult> = [
    {
      title: "股票代码",
      dataIndex: "stock_code",
      key: "stock_code",
      fixed: "left",
      width: 110,
      render: (text: string) => (
        <Text strong style={{ fontFamily: "monospace" }}>
          {text}
        </Text>
      ),
    },
    {
      title: "股票名称",
      dataIndex: "stock_name",
      key: "stock_name",
      fixed: "left",
      width: 100,
      render: (text: string) => (
        <a
          onClick={() => {
            void copyToClipboard(text).then(
              () => message.success("已复制"),
              () => message.error("复制失败"),
            );
          }}
        >
          {text}
        </a>
      ),
    },
    {
      title: (
        <Tooltip title="与最近一次人气抓取快照一致；不在 Top200 内显示「榜外」">
          人气排名
        </Tooltip>
      ),
      dataIndex: "popularity_rank",
      key: "popularity_rank",
      width: 100,
      sorter: (a, b) => {
        const av = a.popularity_rank ?? 10_000;
        const bv = b.popularity_rank ?? 10_000;
        return av - bv;
      },
      render: (_: unknown, record: AnalysisResult) => {
        const v = record.popularity_rank;
        if (v != null) {
          return (
            <Tooltip
              title={
                <span>
                  {record.popularity_snapshot_time && (
                    <span>
                      快照：
                      {dayjs(record.popularity_snapshot_time).format(
                        "YYYY-MM-DD HH:mm:ss",
                      )}
                      <br />
                    </span>
                  )}
                  {record.popularity_previous_rank != null && (
                    <span>
                      上期名次：{record.popularity_previous_rank}
                      <br />
                    </span>
                  )}
                  {record.popularity_score != null && (
                    <span>人气值：{record.popularity_score}</span>
                  )}
                </span>
              }
            >
              <Tag color="processing">{v}</Tag>
            </Tooltip>
          );
        }
        if (record.popularity_snapshot_time) {
          return <Text type="secondary">榜外</Text>;
        }
        return <Text type="secondary">—</Text>;
      },
    },
    {
      title: (
        <Tooltip title="相对上一期人气快照的名次变化，正值表示名次上升">
          名次变动
        </Tooltip>
      ),
      key: "popularity_rank_change",
      width: 96,
      sorter: (a, b) =>
        (a.popularity_rank_change ?? -10_000) -
        (b.popularity_rank_change ?? -10_000),
      render: (_: unknown, record: AnalysisResult) => {
        const ch = record.popularity_rank_change;
        if (ch == null) return <Text type="secondary">—</Text>;
        if (ch === 0) return <Text type="secondary">持平</Text>;
        const up = ch > 0;
        return (
          <Text style={{ color: up ? "#389e0d" : "#cf1322", fontWeight: 600 }}>
            {up ? "↑" : "↓"}
            {Math.abs(ch)}
          </Text>
        );
      },
    },
    {
      title: "事件类型",
      dataIndex: "event_types",
      key: "event_types",
      width: 180,
      render: (text: string) => {
        const tags = text
          .split("|")
          .map((t) => t.trim())
          .map((t) => EVENT_LABEL_MAP[t] || t)
          .filter(Boolean);
        return (
          <Space size={[4, 4]} wrap>
            {tags.map((tag) => (
              <Tag key={tag} color={EVENT_COLOR_MAP[tag] || "default"}>
                {tag}
              </Tag>
            ))}
          </Space>
        );
      },
    },
    {
      title: "新闻",
      dataIndex: "news_count",
      key: "news_count",
      width: 70,
      render: (count: number | undefined, record) => (
        <Button
          type="link"
          size="small"
          icon={<SearchOutlined />}
          onClick={() => openNewsModal(record)}
        >
          {count ?? 0}
        </Button>
      ),
    },
    {
      title: "评分",
      dataIndex: "text_score",
      key: "text_score",
      width: 120,
      sorter: (a, b) => Number(a.text_score) - Number(b.text_score),
      render: (v: number) => <ScoreBar value={v} />,
    },
    {
      title: "市场评分",
      dataIndex: "market_score",
      key: "market_score",
      width: 120,
      sorter: (a, b) => Number(a.market_score) - Number(b.market_score),
      render: (v: number) => <ScoreBar value={v} />,
    },
    {
      title: "综合得分",
      dataIndex: "integrated_score",
      key: "integrated_score",
      width: 120,
      sorter: (a, b) => Number(a.integrated_score) - Number(b.integrated_score),
      defaultSortOrder: "descend",
      render: (v: number) => <ScoreBar value={v} />,
    },
    {
      title: "决策建议",
      dataIndex: "decision",
      key: "decision",
      width: 150,
      render: (text: string) => {
        const color = Object.entries(DECISION_COLOR_MAP).find(([k]) =>
          text?.includes(k),
        )?.[1];
        return (
          <Tooltip title={text}>
            <div style={{ width: 150, overflow: "hidden" }}>
              <Tag color={color || "default"} style={{ fontWeight: 500 }}>
                {text || "—"}
              </Tag>
            </div>
          </Tooltip>
        );
      },
    },
    {
      title: "事件标签",
      dataIndex: "text_event_label",
      key: "text_event_label",
      width: 80,
      filters: [
        { text: "中性", value: "中性" },
        { text: "利好", value: "利好" },
        { text: "利空", value: "利空" },
      ],
      onFilter: (value, record) =>
        record.text_event_label.includes(String(value)),
      render: (text: string) => {
        const colorMap: Record<string, string> = {
          利好: "green",
          利空: "red",
          中性: "default",
        };
        return <Tag color={colorMap[text] || "default"}>{text}</Tag>;
      },
    },
    {
      title: "情绪强度",
      dataIndex: "sentiment_strength",
      key: "sentiment_strength",
      width: 90,
    },
    {
      title: "事实支撑",
      dataIndex: "fact_support",
      key: "fact_support",
      width: 90,
    },
    {
      title: "看多逻辑",
      dataIndex: "bullish_logic",
      key: "bullish_logic",
      ellipsis: true,
      width: 200,
    },
    {
      title: "量价信号",
      dataIndex: "price_volume_signal",
      key: "price_volume_signal",
      width: 100,
    },
    {
      title: "资金流信号",
      dataIndex: "fund_flow_signal",
      key: "fund_flow_signal",
      width: 110,
      sorter: (a, b) => a.fund_flow_signal.localeCompare(b.fund_flow_signal),
    },
    {
      title: "分析时间",
      dataIndex: "analyzed_at",
      key: "analyzed_at",
      width: 160,
      render: (text: string) => dayjs(text).format("MM-DD HH:mm"),
    },
  ];

  const getStocks = () => {
    analysisApi.getList().then((res) => setTotalData(res));
  };

  useEffect(() => {
    getStocks();
  }, []);

  useEffect(() => {
    if (filters.startTime && filters.endTime) {
      setData(
        totalData.filter(
          (item) =>
            dayjs(item.analyzed_at).isAfter(filters.startTime) &&
            dayjs(item.analyzed_at).isBefore(filters.endTime),
        ),
      );
    } else {
      setData(totalData);
    }
  }, [filters, totalData]);

  const busy = running || singleAnalyzing;

  const submitAnalyzeSingle = (): Promise<void> => {
    const code = singleStockInput.trim();
    if (!code) {
      message.warning("请输入股票代码");
      return Promise.reject(new Error("empty"));
    }
    setSingleAnalyzing(true);
    message.success(`已将 ${code} 加入分析，请稍候`);
    return analysisApi
      .analyzeSingle(code)
      .then((res) => {
        message.success(`分析完成，共写入 ${res.result_count ?? 0} 条结果`);
        setSingleModalOpen(false);
        setSingleStockInput("");
        getStocks();
      })
      .finally(() => setSingleAnalyzing(false));
  };

  return (
    <div className={styles.page}>
      {/* Stats Cards */}
      <Row gutter={[16, 16]} className={styles.statsRow}>
        <Col xs={12} sm={6}>
          <Card size="small" className={styles.statCard}>
            <Statistic
              title="分析股票"
              value={stats.total}
              prefix={<BarChartOutlined />}
              styles={{ content: { color: "#1677ff" } }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" className={styles.statCard}>
            <Statistic
              title="利好"
              value={stats.bullish}
              styles={{ content: { color: "#52c41a" } }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" className={styles.statCard}>
            <Statistic
              title="利空"
              value={stats.bearish}
              styles={{ content: { color: "#ff4d4f" } }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" className={styles.statCard}>
            <Statistic
              title="平均综合分"
              value={stats.avgScore}
              precision={1}
              prefix={<LineChartOutlined />}
              styles={{
                content: {
                  color:
                    stats.avgScore >= 6
                      ? "#52c41a"
                      : stats.avgScore >= 4
                        ? "#faad14"
                        : "#ff4d4f",
                },
              }}
            />
          </Card>
        </Col>
      </Row>

      {/* Action Bar */}
      <Card size="small" className={styles.actionBar}>
        <Space wrap size="middle">
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            disabled={busy}
            loading={running}
            onClick={() => {
              setRunning(true);
              message.success("开始获取新增人气股票");
              analysisApi
                .runAll()
                .then((res) => {
                  message.success(
                    `获取完成,成功获取到${res.analysis.result_count}条数据`,
                  );
                  getStocks();
                })
                .finally(() => setRunning(false));
            }}
          >
            获取新增人气股票
          </Button>
          <Button
            disabled={busy}
            loading={singleAnalyzing}
            icon={<SearchOutlined />}
            onClick={() => setSingleModalOpen(true)}
          >
            分析单只股票
          </Button>
          <span className={styles.filterLabel}>时间筛选:</span>
          <RangePicker
            onChange={(values) =>
              setFilters({
                startTime: values?.[0]?.format("YYYY-MM-DD HH:mm:ss") || null,
                endTime: values?.[1]
                  ? dayjs(values[1]).endOf("day").format("YYYY-MM-DD HH:mm:ss")
                  : null,
              })
            }
          />
        </Space>
      </Card>

      {/* Data Table */}
      <div>
        <Table
          dataSource={data}
          columns={columns}
          scroll={{ x: 2200 }}
          rowKey={(row) =>
            `${row.stock_code}-${row.analyzed_at}-${row.integrated_score}`
          }
          size="small"
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
          }}
          rowClassName={(record) => {
            if (record.text_event_label === "利好") return styles.rowBullish;
            if (record.text_event_label === "利空") return styles.rowBearish;
            return "";
          }}
        />
      </div>

      {/* Single Stock Modal */}
      <Modal
        title="分析单只股票"
        open={singleModalOpen}
        confirmLoading={singleAnalyzing}
        okText="开始分析"
        cancelText="取消"
        destroyOnHidden
        mask={{ closable: !singleAnalyzing }}
        closable={!singleAnalyzing}
        onCancel={() => !singleAnalyzing && setSingleModalOpen(false)}
        onOk={() => submitAnalyzeSingle()}
        afterClose={() => setSingleStockInput("")}
      >
        <input
          className={styles.stockInput}
          placeholder="6位代码或完整代码，如 688353 / 002155.SZ"
          value={singleStockInput}
          disabled={singleAnalyzing}
          onChange={(e) => setSingleStockInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void submitAnalyzeSingle()}
        />
      </Modal>

      {/* News Modal */}
      <Modal
        title={`新闻明细 — ${newsModalTitle}`}
        open={newsModalOpen}
        onCancel={() => setNewsModalOpen(false)}
        footer={null}
        width={960}
        destroyOnHidden
      >
        <Spin spinning={newsLoading}>
          <Table<NewsItem>
            size="small"
            pagination={{ pageSize: 8, showSizeChanger: true }}
            dataSource={newsRows}
            rowKey={(row) => String(row.id)}
            scroll={{ x: 840 }}
            columns={[
              {
                title: "标题",
                dataIndex: "title",
                key: "title",
                width: 260,
                ellipsis: true,
              },
              {
                title: "时间",
                dataIndex: "published_at",
                key: "published_at",
                width: 168,
                render: (t: string | null | undefined) =>
                  t ? dayjs(t).format("YYYY-MM-DD HH:mm:ss") : "—",
              },
              {
                title: "来源",
                dataIndex: "source",
                key: "source",
                width: 96,
                ellipsis: true,
              },
              {
                title: "链接",
                dataIndex: "url",
                key: "url",
                width: 72,
                render: (url: string | null | undefined) =>
                  url ? (
                    <a href={url} target="_blank" rel="noreferrer">
                      打开
                    </a>
                  ) : (
                    "—"
                  ),
              },
              {
                title: "内容摘要",
                key: "snippet",
                ellipsis: true,
                render: (_: unknown, row) => (
                  <Tooltip title={row.content}>
                    <div>{row.summary || row.content}</div>
                  </Tooltip>
                ),
              },
            ]}
          />
        </Spin>
      </Modal>
    </div>
  );
}

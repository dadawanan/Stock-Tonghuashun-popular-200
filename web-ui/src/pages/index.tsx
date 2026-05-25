import {
  Button,
  Input,
  message,
  Modal,
  Spin,
  Table,
  Tag,
  Typography,
  DatePicker,
  Space,
  Tooltip,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useState } from "react";
import {
  analysisApi,
  AnalysisResult,
  copyToClipboard,
  newsApi,
  NewsItem,
} from "../utils";
import dayjs from "dayjs";
const { Title, Paragraph, Text, Link } = Typography;

const { RangePicker } = DatePicker;
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
  }>({
    startTime: "",
    endTime: "",
  });

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

  const columns: ColumnsType<AnalysisResult> = [
    {
      title: "股票代码",
      dataIndex: "stock_code",
      key: "stock_code",
    },
    {
      title: "股票名称",
      dataIndex: "stock_name",
      key: "stock_name",
      width: "100px",
      render: (text: string) => (
        <a
          onClick={() => {
            void copyToClipboard(text).then(
              () => {
                message.success("已复制股票名称");
              },
              () => {
                message.error("复制失败");
              },
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
                  {record.popularity_snapshot_time ? (
                    <span>
                      快照：
                      {dayjs(record.popularity_snapshot_time).format(
                        "YYYY-MM-DD HH:mm:ss",
                      )}
                      <br />
                    </span>
                  ) : null}
                  {record.popularity_previous_rank != null ? (
                    <span>
                      上期名次：{record.popularity_previous_rank}
                      <br />
                    </span>
                  ) : null}
                  {record.popularity_score != null ? (
                    <span>人气值：{record.popularity_score}</span>
                  ) : null}
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
        if (ch == null) {
          return <Text type="secondary">—</Text>;
        }
        if (ch === 0) {
          return <Text type="secondary">持平</Text>;
        }
        const up = ch > 0;
        return (
          <Text style={{ color: up ? "#389e0d" : "#cf1322" }}>
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
      render: (text: string) => {
        text = text.replace("major_order", "大订单");
        text = text.replace("supply_chain_risk", "供应链风险");
        text = text.replace("earnings_growth", "盈利增长");
        text = text.replace("management_risk", "管理风险");
        text = text.replace("technology_breakthrough", "科技突破");
        text = text.replace("policy_support", "政策支持");
        text = text.replace("other", "");
        const tags = text.split("|");

        return tags.map((tag) => <Tag key={tag}>{tag}</Tag>);
      },
    },
    {
      title: "新闻数量",
      dataIndex: "news_count",
      key: "news_count",
      render: (count: number | undefined, record) => (
        <Button type="link" size="small" onClick={() => openNewsModal(record)}>
          {count ?? 0}
        </Button>
      ),
    },
    {
      title: "评分",
      dataIndex: "text_score",
      key: "text_score",
      sorter: (a, b) => a.text_score - b.text_score,
    },
    {
      title: "市场评分",
      dataIndex: "market_score",
      key: "market_score",
      sorter: (a, b) => a.market_score - b.market_score,
    },
    {
      title: "综合得分",
      dataIndex: "integrated_score",
      key: "integrated_score",
      sorter: (a, b) => a.integrated_score - b.integrated_score,
    },
    {
      title: "决策建议",
      dataIndex: "decision",
      key: "decision",
    },
    {
      title: "分析时间",
      dataIndex: "analyzed_at",
      key: "analyzed_at",
      render: (text: string) => dayjs(text).format("YYYY-MM-DD HH:mm:ss"),
    },
    {
      title: "事件标签",
      dataIndex: "text_event_label",
      key: "text_event_label",
      filters: [
        {
          text: "中性",
          value: "中性",
        },
        {
          text: "利好",
          value: "利好",
        },
        {
          text: "利空",
          value: "利空",
        },
      ],
      onFilter: (value, record) =>
        record.text_event_label.includes(String(value)),
    },

    {
      title: "情绪强度",
      dataIndex: "sentiment_strength",
      key: "sentiment_strength",
      sorter: (a, b) =>
        a.sentiment_strength.localeCompare(b.sentiment_strength),
    },
    // {
    //   title: "持续周期",
    //   dataIndex: "duration_tag",
    //   key: "duration_tag",
    // },
    {
      title: "事实支撑度",
      dataIndex: "fact_support",
      key: "fact_support",
      sorter: (a, b) =>
        a.sentiment_strength.localeCompare(b.sentiment_strength),
    },
    {
      title: "看多逻辑",
      dataIndex: "bullish_logic",
      key: "bullish_logic",
    },

    {
      title: "量价信号",
      dataIndex: "price_volume_signal",
      key: "price_volume_signal",
    },
    {
      title: "资金流向信号",
      dataIndex: "fund_flow_signal",
      key: "fund_flow_signal",
      sorter: (a, b) => a.fund_flow_signal.localeCompare(b.fund_flow_signal),
    },
    // {
    //   title: "行为标签",
    //   dataIndex: "behavior_label",
    //   key: "behavior_label",
    // },
  ];

  const getStocks = () => {
    analysisApi.getList().then((res) => {
      setTotalData(res);
    });
  };

  useEffect(() => {
    getStocks();
  }, []);

  useEffect(() => {
    // 过滤时间
    if (filters.startTime && filters.endTime) {
      console.log(filters.startTime, filters.endTime);
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
      .finally(() => {
        setSingleAnalyzing(false);
      });
  };

  return (
    <div>
      <Typography>
        <Title>使用说明</Title>

        <Paragraph>
          当前同花顺人气前200新增的股票，比较的是上次的前200和现在的前200。
        </Paragraph>
        <Paragraph>数据仅保留14天。</Paragraph>
      </Typography>
      <Space wrap>
        <Button
          type="primary"
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
              .finally(() => {
                setRunning(false);
              });
          }}
        >
          获取新增人气股票
        </Button>
        <Button
          disabled={busy}
          loading={singleAnalyzing}
          onClick={() => setSingleModalOpen(true)}
          type="primary"
        >
          分析单只股票
        </Button>
        <span>时间:</span>

        <RangePicker
          onChange={(values) => {
            console.log(values);
            setFilters({
              startTime:
                values && values[0] && values[0].format("YYYY-MM-DD HH:mm:ss"),
              endTime: dayjs(values && values[1] && values[1])
                .endOf("day")
                .format("YYYY-MM-DD HH:mm:ss"),
            });
          }}
        ></RangePicker>
      </Space>

      <Modal
        title="分析单只股票"
        open={singleModalOpen}
        confirmLoading={singleAnalyzing}
        okText="开始分析"
        cancelText="取消"
        destroyOnHidden
        maskClosable={!singleAnalyzing}
        closable={!singleAnalyzing}
        onCancel={() => {
          if (!singleAnalyzing) {
            setSingleModalOpen(false);
          }
        }}
        onOk={() => submitAnalyzeSingle()}
        afterClose={() => setSingleStockInput("")}
      >
        <Input
          placeholder="6位代码或完整代码，如 688353 / 002155.SZ（可不写后缀）"
          value={singleStockInput}
          disabled={singleAnalyzing}
          onChange={(e) => setSingleStockInput(e.target.value)}
          onPressEnter={() => void submitAnalyzeSingle()}
        />
      </Modal>

      <Table
        dataSource={data}
        columns={columns}
        scroll={{ x: 3000 }}
        rowKey={(row) =>
          `${row.stock_code}-${row.analyzed_at}-${row.integrated_score}`
        }
      />

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
                render: (s: string | null | undefined) => s ?? "—",
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
                render: (_: unknown, row) => {
                  return (
                    <Tooltip title={row.content}>
                      <div>{row.summary || row.content}</div>
                    </Tooltip>
                  );
                },
              },
            ]}
          />
        </Spin>
      </Modal>
    </div>
  );
}

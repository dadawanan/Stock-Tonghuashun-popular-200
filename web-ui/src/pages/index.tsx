import { Button, message, Table, Typography } from "antd";
import { useEffect, useState } from "react";
import { analysisApi, AnalysisResult } from "../utils";
import dayjs from "dayjs";
const { Title, Paragraph, Text, Link } = Typography;

export default function HomePage() {
  const [data, setData] = useState<AnalysisResult[]>([]);
  const [running, setRunning] = useState(false);

  const columns = [
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
            try {
              window.navigator.clipboard.writeText(text);
              console.log("复制成功！");
            } catch (e) {
              console.error(e);
              console.error("复制失败：", e);
            }
          }}
        >
          {text}
        </a>
      ),
    },
    {
      title: "事件类型",
      dataIndex: "event_types",
      key: "event_types",
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
      onFilter: (value, record) => record.text_event_label.includes(value),
    },
    {
      title: "评分",
      dataIndex: "text_score",
      key: "text_score",
      sorter: (a, b) => a.text_score - b.text_score,
    },
    {
      title: "情绪强度",
      dataIndex: "sentiment_strength",
      key: "sentiment_strength",
    },
    {
      title: "持续周期",
      dataIndex: "duration_tag",
      key: "duration_tag",
    },
    {
      title: "事实支撑度",
      dataIndex: "fact_support",
      key: "fact_support",
    },
    {
      title: "看多逻辑",
      dataIndex: "bullish_logic",
      key: "bullish_logic",
    },
    {
      title: "看空逻辑",
      dataIndex: "bullish_logic",
      key: "bearish_logic",
    },
    {
      title: "新闻数量",
      dataIndex: "news_count",
      key: "news_count",
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
    },
    {
      title: "行为标签",
      dataIndex: "behavior_label",
      key: "behavior_label",
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
  ];

  const getStocks = () => {
    analysisApi.getList().then((res) => {
      setData(res);
    });
  };

  useEffect(() => {
    getStocks();
  }, []);

  return (
    <div>
      <Typography>
        <Title>使用说明</Title>

        <Paragraph>
          当前同花顺人气前200新增的股票，比较的是上次的前200和现在的前200。
        </Paragraph>
      </Typography>
      <Button
        type="primary"
        disabled={running}
        onClick={() => {
          setRunning(true);
          message.success("开始获取新增人气股票");
          analysisApi.runAll().then((res) => {
            message.success(
              `获取完成,成功获取到${res.analysis.result_count}条数据`,
            );
            getStocks();
            setRunning(false);
          });
        }}
      >
        获取新增人气股票
      </Button>

      <Table dataSource={data} columns={columns} scroll={{ x: 3000 }}></Table>
    </div>
  );
}
